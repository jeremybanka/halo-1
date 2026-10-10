"""Compare complete gameplay state per tick against a Git checkpoint.

Builds both game adapters with the same generated banks, source solver and
compiler contracts. No renderer or wall-clock timing claim is made here.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import tarfile
import io
import sys

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


def run(reference, output, solver_opt=2, lto=False):
    output.mkdir(parents=True, exist_ok=True)
    candidate_solver = output / "candidate-solver"
    subprocess.run(
        [sys.executable, ROOT / "port/n64/blam/prepare_vehicle.py", "--output", candidate_solver],
        cwd=ROOT,
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="halo-checkpoint-") as directory:
        baseline = Path(directory)
        # Compare both implementations, including shared collision/movement and
        # inline headers. Sharing today's adapters between both binaries would
        # hide regressions when optimizing those adapters themselves.
        simulation_sources = (
            "game.c",
            "combat_geometry.c",
            "terrain.c",
            "movement.c",
            "blam/runtime.c",
            "blam/core.c",
            "blam/vehicle_physics.c",
            "replay.c",
            "showcase.c",
        )
        archive = subprocess.check_output(["git", "archive", reference, "port/n64"], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
            for member in tree:
                prefix = "port/n64/"
                if not member.isfile() or not member.name.startswith(prefix):
                    continue
                name = member.name[len(prefix) :]
                if name not in (
                    *simulation_sources,
                    "blam/prepare_vehicle.py",
                    "blam/prepare_collision.py",
                ) and Path(name).suffix not in (
                    ".h",
                    ".inc",
                    ".def",
                ):
                    continue
                destination = baseline / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(tree.extractfile(member).read())
        # Solver adaptations also belong to the checkpoint. Sharing today's
        # generated implementations would hide a changed original-body loop.
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import importlib.util,sys; from pathlib import Path; "
                "sys.path.insert(0,sys.argv[1]); "
                "s=importlib.util.spec_from_file_location('checkpoint_preparer',Path(sys.argv[1])/'prepare_vehicle.py'); "
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
                "m.ROOT=Path(sys.argv[2]);m.OUT=Path(sys.argv[3]);m.prepare()",
                str(baseline / "blam"),
                str(ROOT),
                str(baseline / "solver"),
            ],
            cwd=ROOT,
            check=True,
        )
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
            "-I" + str(candidate_solver),
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
            (
                "checkpoint",
                baseline / "game.c",
                ["-I" + str(baseline), "-I" + str(baseline / "solver")],
            ),
            ("candidate", ROOT / "port/n64/game.c", []),
        ]:
            binary = output / label
            record = output / (label + ".bin")
            paths = [
                str((baseline if label == "checkpoint" else ROOT / "port/n64") / s) for s in sources
            ]
            if label == "candidate" and solver_opt != 2:
                adapter = str(ROOT / "port/n64/blam/vehicle_physics.c")
                obj = output / ("vehicle-o" + str(solver_opt) + ".o")
                subprocess.run(
                    ["clang", *flags, "-O" + str(solver_opt), "-c", adapter, "-o", str(obj)],
                    cwd=ROOT,
                    check=True,
                )
                paths[paths.index(adapter)] = str(obj)
            subprocess.run(
                [
                    "clang",
                    *(["-flto"] if lto and label == "candidate" else []),
                    *includes,
                    *flags,
                    str(trace),
                    str(game),
                    *paths,
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
    parser.add_argument("--reference", default="ffc5e53d")
    parser.add_argument(
        "--solver-opt",
        type=lambda value: int(value) if value in ("2", "3") else value,
        choices=(2, 3, "s"),
        default=2,
    )
    parser.add_argument(
        "--lto", action="store_true", help="Compare candidate link-time optimization"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "build/n64-validation/equivalence"
    )
    args = parser.parse_args()
    run(args.reference, args.output_dir, args.solver_opt, args.lto)
