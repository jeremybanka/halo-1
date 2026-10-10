"""Compare cached ordered candidate streams with the unchanged raw BVH iterator.

Includes cache pressure, empty cells, large uncached queries, cache overflow,
and nextafter probes around cell/octant boundaries. No contact math changes.
"""

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_source import validation_output

ROOT = Path(__file__).resolve().parents[3]
C = r"""
#include <stdio.h>
static uint32_t test_seed=0xb10c;
static uint32_t rnd(void){test_seed=test_seed*1664525u+1013904223u;return test_seed;}
int main(void){
 world_load();unsigned queries=0,ids=0,empty=0;
 static const float reaches[]={0,.000001f,.03f,.25f,.5f,1,2,4,4.001f,15};
 for(unsigned trial=0;trial<150000;trial++){
  float lo[3],hi[3];
  for(unsigned a=0;a<3;a++){
   float center=a==0?18+(rnd()%6400)/64.f:a==1?-178+(rnd()%7680)/64.f:-2+(rnd()%1024)/64.f;
   if(trial%3==0)center=nextafterf(center,trial&1?FLT_MAX:-FLT_MAX);
   float radius=reaches[(trial+a)%10];lo[a]=center-radius;hi[a]=center+radius;
  }
  struct surface_query reference,cached;query_begin_raw(&reference,lo,hi);query_begin(&cached,lo,hi);
  unsigned count=0;
  for(;;){int old=query_next_raw(&reference),now=query_next(&cached);
   if(old!=now){fprintf(stderr,"query %u index %u: raw %d cached %d\n",trial,count,old,now);assert(0);}
   if(old<0)break;count++;ids++;
  }
  empty+=!count;queries++;
 }
 printf("PASS: %u ordered candidate streams / %u surface IDs / %u empty queries match raw BVH\n",queries,ids,empty);
}
"""


def main():
    out = validation_output("vehicle-candidates")
    out.mkdir(parents=True, exist_ok=True)
    solver = out / "solver"
    subprocess.run(
        [sys.executable, ROOT / "port/n64/blam/prepare_vehicle.py", "--output", solver], check=True
    )
    source = out / "query.c"
    source.write_text((ROOT / "port/n64/blam/vehicle_physics.c").read_text() + C)
    shared = (
        "game.c",
        "combat_geometry.c",
        "terrain.c",
        "movement.c",
        "blam/runtime.c",
        "blam/core.c",
    )
    generated = (
        "pickup_data.c",
        "combat_data.c",
        "movement_data.c",
        "interaction_defs.c",
        "vehicle_data.c",
        "terrain_data.c",
    )
    for label, math in (
        ("strict", ["-fno-fast-math"]),
        ("target", ["-ffast-math", "-ftrapping-math", "-fno-associative-math"]),
    ):
        binary = out / label
        subprocess.run(
            [
                "clang",
                "-std=c17",
                "-O2",
                "-g",
                "-fsanitize=address,undefined",
                "-ffp-contract=off",
                "-fno-strict-aliasing",
                "-fwrapv",
                "-Wno-multichar",
                "-Wno-unused-function",
                "-Wno-incompatible-pointer-types",
                "-Iport/n64",
                "-Iport/n64/blam",
                "-Ibuild/n64/blam-core",
                "-I" + str(solver),
                *math,
                str(source),
                *(str(ROOT / "port/n64" / s) for s in shared),
                *(str(ROOT / "build/n64/generated" / s) for s in generated),
                "-lm",
                "-o",
                str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
