"""Compare complete gameplay state per tick against a Git checkpoint.

Builds both game adapters with the same generated banks, source solver and
compiler contracts. No renderer or wall-clock timing claim is made here.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TRACE = r"""
#include "game.h"
#include "replay.h"
#include "showcase.h"
#include "blam/runtime.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void state(FILE*out){
#define SAVE(value) assert(fwrite(&(value),sizeof(value),1,out)==1)
    SAVE(bg_players);SAVE(bg_vehicles);SAVE(bg_pickups);
    SAVE(bg_vehicle_count);SAVE(bg_pickup_count);SAVE(bg_event_count);
    assert(fwrite(bg_events,sizeof(*bg_events),bg_event_count,out)==bg_event_count);
    float time=bg_match_time();SAVE(time);
    const bg_match_statistics *stats=bg_match_stats();SAVE(*stats);
    for(unsigned p=0;p<4;p++){const bg_shot_trace *trace=bg_sniper_trace(p);SAVE(*trace);}
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile *projectile=bg_projectile_at(i);bool live=projectile!=NULL;SAVE(live);
        if(live){SAVE(*projectile);}
    }
#undef SAVE
}
int main(int argc,char**argv){
    assert(argc==2);FILE*out=fopen(argv[1],"wb");assert(out);
    for(unsigned scenario=0;scenario<7;scenario++){
        bg_set_players(4);bg_set_score_limit(1000);bg_reset();
        if(scenario)bg_showcase_begin(scenario-1);
        float seconds=0;
        unsigned ticks=scenario?1800:4500;
        for(unsigned tick=0;tick<ticks;tick++){
            bg_input input[4]={{0}};
            if(scenario)bg_showcase_input(input,seconds);else bg_replay_input(input,seconds);
            bg_clear_events();bg_tick(input,BLAM_TICK_SECONDS);seconds+=BLAM_TICK_SECONDS;
            if(scenario)bg_showcase_observe();
            state(out);
        }
    }
    assert(fclose(out)==0);
}
"""


def run(reference, output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="halo-checkpoint-") as directory:
        baseline = Path(directory)
        for name in ("game.c", "game.h", "pickups.inc"):
            data = subprocess.check_output(
                ["git", "show", f"{reference}:port/n64/{name}"], cwd=ROOT
            )
            (baseline / name).write_bytes(data)
        trace = output / "trace.c"
        trace.write_text(TRACE)
        flags = [
            "-std=c17",
            "-O2",
            "-fno-fast-math",
            "-ffp-contract=off",
            "-fno-strict-aliasing",
            "-fwrapv",
            "-Wno-multichar",
            "-Wno-unused-function",
            "-Wno-unused-parameter",
            "-Wno-unused-variable",
            "-Wno-incompatible-pointer-types",
            "-Iport/n64",
            "-Ibuild/n64/blam-core",
            "-Ibuild/n64/blam-vehicle",
        ]
        shared = [
            "pickup_data.c",
            "combat_data.c",
            "movement_data.c",
            "interaction_defs.c",
            "vehicle_data.c",
            "terrain_data.c",
        ]
        sources = [
            "combat_geometry.c",
            "terrain.c",
            "movement.c",
            "blam/runtime.c",
            "blam/core.c",
            "blam/vehicle_physics.c",
            "replay.c",
            "showcase.c",
        ]
        results = []
        for label, game, includes in [
            ("checkpoint", baseline / "game.c", ["-I" + str(baseline)]),
            ("cleanup", ROOT / "port/n64/game.c", []),
        ]:
            binary = output / label
            record = output / (label + ".bin")
            subprocess.run(
                [
                    "clang",
                    *includes,
                    *flags,
                    str(trace),
                    str(game),
                    *(str(ROOT / "port/n64" / s) for s in sources),
                    *(str(ROOT / "build/n64/generated" / s) for s in shared),
                    "-lm",
                    "-o",
                    str(binary),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(binary), str(record)], cwd=ROOT, check=True)
            results.append(record)
        old, new = (path.read_bytes() for path in results)
        if old != new:
            first = next(
                (i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new))
            )
            raise AssertionError(
                f"Gameplay divergence at trace byte {first}; retain {output} for diagnosis"
            )
        print(
            f"PASS: 15,300 ticks, replay plus six showcases; {len(new):,} state bytes identical to {reference}; SHA256 {hashlib.sha256(new).hexdigest()}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="b3fba521")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "build/n64-validation/equivalence"
    )
    args = parser.parse_args()
    run(args.reference, args.output_dir)
