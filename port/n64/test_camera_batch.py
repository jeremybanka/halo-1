"""Compare camera clearance against the checkpoint using real articulated hulls.

The only instrumentation counts actual collision-pose cache misses; all rays,
terrain and joint/hatch transforms run through production code. This measures
work avoided, not target FPS. Both strict and production integration math run.
"""

import argparse
from pathlib import Path
import subprocess
import sys

from test_render_matrix import function
from runtime_source import validation_output

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r"""
#include "game.h"
#include "combat_geometry.h"
#include "blam/vehicle_physics.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
extern unsigned bg_test_refits;
static float dot(const float*a,const float*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void normalize(float*v){float n=sqrtf(dot(v,v));if(n>.00001f)for(unsigned a=0;a<3;a++)v[a]/=n;}
float reference_camera(const float origin[3],const float direction[3],float length,int ignore_vehicle){
REFERENCE
}
int main(void){
    bg_reset();bg_vehicle_count=BG_MAX_VEHICLES;
    unsigned reference_refits=0,candidate_refits=0,blocked=0;
    for(unsigned frame=0;frame<4096;frame++){
        for(unsigned i=0;i<bg_vehicle_count;i++){
            bg_vehicle*v=&bg_vehicles[i];memset(v,0,sizeof(*v));v->kind=i%4;
            v->active=(frame+i)%7!=0;v->wreck_time=v->active?0:4;
            v->pos[0]=(i%3-1.f)*.65f;v->pos[1]=.7f;v->pos[2]=4+(i/3-1.f)*.65f;
            v->yaw=sinf((frame+i)*.03f);v->pitch=cosf((frame+i)*.05f)*.4f;
            v->turret_yaw=sinf((frame+i)*.017f);v->turret_pitch=cosf((frame+i)*.011f)*.35f;
            v->hatch=((frame+i)%31)/30.f;v->hatch_closing=((frame+i)/31)&1;
            if(frame&1){
                float f[3]={1,0,0},u[3]={0,1,0};
                bg_vehicle_transform(v,f,v->forward);bg_vehicle_transform(v,u,v->up);
                for(unsigned a=0;a<3;a++){v->forward[a]-=v->pos[a];v->up[a]-=v->pos[a];}
                v->physics_valid=true;
            }
        }
        float origin[3]={sinf(frame*.137f)*3,.1f+(frame%19)*.15f,4+cosf(frame*.131f)*3};
        float direction[3]={cosf(frame*.211f),sinf(frame*.079f)*.5f,-sinf(frame*.211f)};
        normalize(direction);float length=frame%23==0?0:1+(frame%29)*.3f;
        int ignore=(int)(frame%13)-1;
        unsigned before=bg_test_refits;
        float expected=reference_camera(origin,direction,length,ignore);
        reference_refits+=bg_test_refits-before;before=bg_test_refits;
        float actual=bg_camera_clearance(origin,direction,length,ignore);
        candidate_refits+=bg_test_refits-before;
        if(memcmp(&actual,&expected,sizeof(actual))){
            fprintf(stderr,"camera %u: expected %.9g actual %.9g\n",frame,expected,actual);
            assert(!"Camera clearance changed");
        }
        blocked+=actual<length-.15f-.0001f;
    }
    assert(blocked>100);assert(candidate_refits<reference_refits);
    printf("PASS: 4096 exact camera clearances, %u obstructed; real pose refits %u -> %u\n",
           blocked,reference_refits,candidate_refits);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="ffc5e53d")
    parser.add_argument(
        "--output-dir", type=Path, default=validation_output("camera-batch")
    )
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = subprocess.check_output(
        ["git", "show", f"{args.reference}:port/n64/game.c"], cwd=ROOT, text=True
    )
    test = out / "camera.c"
    test.write_text(HARNESS.replace("REFERENCE", function(checkpoint, "bg_camera_clearance")))
    geometry = out / "counted-geometry.c"
    original = (ROOT / "port/n64/combat_geometry.c").read_text()
    assert original.count("unsigned changed=0;") == 1
    geometry.write_text(
        "unsigned bg_test_refits;\n"
        + original.replace("unsigned changed=0;", "++bg_test_refits;unsigned changed=0;")
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
        "blam/vehicle_physics.c",
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
                str(geometry),
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
