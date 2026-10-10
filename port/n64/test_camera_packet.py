"""Compare conservative camera-ray filtering with the checkpoint packet solver.

The surface iterator and directed-edge arithmetic are production code. Tests
cover 250,000 rays, including zero reach, under strict and integration math.
"""

import argparse
from pathlib import Path
import subprocess
from test_render_matrix import function
from runtime_source import validation_output

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r"""
#include "game.h"
#include "blam/vehicle_physics.h"
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
void reference_world_camera(const float origin[3],const float rays[5][3],const float reaches[5],float hits[5]);
static uint32_t seed=0xcea064;
static float rnd(float lo,float hi){seed=seed*1664525u+1013904223u;return lo+(hi-lo)*(seed>>8)/16777215.f;}
int main(void){unsigned checked=0,blocked=0;
for(unsigned trial=0;trial<50000;trial++){
 float o[3]={rnd(-50,50),rnd(-2,15),rnd(-60,60)},yaw=rnd(-3.14,3.14),pitch=rnd(-1.5,1.5),length=trial%19?rnd(.01,12):0;
 float d[3]={cosf(yaw)*cosf(pitch),sinf(pitch),-sinf(yaw)*cosf(pitch)};
 float rays[5][3],reach[5],expected[5],actual[5];
 for(unsigned i=0;i<5;i++){
  for(unsigned a=0;a<3;a++)rays[i][a]=d[a]*length;
  if(i==1)rays[i][0]+=.1f;if(i==2)rays[i][0]-=.1f;if(i==3)rays[i][1]+=.1f;if(i==4)rays[i][1]-=.1f;
  reach[i]=sqrtf(rays[i][0]*rays[i][0]+rays[i][1]*rays[i][1]+rays[i][2]*rays[i][2]);
  for(unsigned a=0;a<3;a++)rays[i][a]/=fmaxf(.001f,reach[i]);
 }
 reference_world_camera(o,rays,reach,expected);bg_world_camera_rays(o,rays,reach,actual);
 for(unsigned i=0;i<5;i++){
  if(memcmp(expected+i,actual+i,sizeof(float))){fprintf(stderr,"packet %u lane %u expected %.9g got %.9g\n",trial,i,expected[i],actual[i]);assert(0);}
  blocked+=actual[i]<reach[i];checked++;
 }
}
printf("PASS: %u exact camera rays (%u obstructed) against checkpoint packet algorithm\n",checked,blocked);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="ffc5e53d")
    parser.add_argument("--output-dir", type=Path, default=validation_output("camera-packet"))
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    test = out / "camera.c"
    test.write_text(HARNESS)
    checkpoint = subprocess.check_output(
        ["git", "show", f"{args.reference}:port/n64/blam/vehicle_physics.c"],
        cwd=ROOT,
        text=True,
    )
    physics = out / "physics.c"
    physics.write_text(
        (ROOT / "port/n64/blam/vehicle_physics.c").read_text()
        + "\nvoid reference_world_camera(const float origin[3], const float rays[5][3], "
        "const float reaches[5], float hits[5]) {\n"
        + function(checkpoint, "bg_world_camera_rays")
        + "\n}\n"
    )
    generated = (
        "pickup_data.c",
        "combat_data.c",
        "movement_data.c",
        "interaction_defs.c",
        "vehicle_data.c",
        "terrain_data.c",
    )
    shared = (
        "game.c",
        "terrain.c",
        "movement.c",
        "blam/runtime.c",
        "blam/core.c",
    )
    common = [
        "-std=c17",
        "-O2",
        "-g",
        "-fsanitize=address,undefined",
        "-ffp-contract=off",
        "-fno-strict-aliasing",
        "-fwrapv",
        "-Wno-multichar",
        "-Wno-unused-function",
        "-Wno-unused-parameter",
        "-Wno-unused-variable",
        "-Wno-incompatible-pointer-types",
        "-Iport/n64",
        "-Iport/n64/blam",
        "-Ibuild/n64/blam-core",
        "-Ibuild/n64/blam-vehicle",
    ]
    for label, flags in (
        ("strict", ["-fno-fast-math"]),
        ("target-math", ["-ffast-math", "-ftrapping-math", "-fno-associative-math"]),
    ):
        binary = out / label
        subprocess.run(
            [
                "clang",
                *common,
                *flags,
                str(test),
                str(physics),
                str(ROOT / "port/n64/combat_geometry.c"),
                *(str(ROOT / "port/n64" / name) for name in shared),
                *(str(ROOT / "build/n64/generated" / name) for name in generated),
                "-lm",
                "-o",
                str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(binary)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
