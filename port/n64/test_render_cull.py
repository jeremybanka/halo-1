"""Differential positive-corner culling against the installed Tiny3D source."""

from pathlib import Path
import subprocess
from runtime_source import validation_output
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT.parent / "n64-3d-splitscreen/.build/tiny3d/src/t3d/t3dmath.c"
C = r"""
#include "render_cull.h"
#include "render_bounds.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
typedef struct{float v[4];}Vec;
typedef struct{Vec planes[6];}T3DFrustum;
static bool reference(const T3DFrustum*frustum,const int16_t min[3],const int16_t max[3]){REFERENCE}
static uint32_t seed=0xce064;
static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static float value(float range){return ((int)(rnd()>>8)-8388608)*(range/8388608.f);}
int main(void){
    unsigned visible=0,checked=0;
    for(unsigned trial=0;trial<1000000;trial++){
        int16_t min[3],max[3];T3DFrustum f;
        for(unsigned a=0;a<3;a++){int16_t x=rnd(),y=rnd();min[a]=x<y?x:y;max[a]=x>y?x:y;}
        for(unsigned i=0;i<6;i++){
            for(unsigned a=0;a<3;a++)f.planes[i].v[a]=value(4);
            f.planes[i].v[3]=value(32768);
            if(trial%4==0){
                /* Exact/tiny-offset plane boundaries and degenerate axes. */
                f.planes[i].v[3]=-f.planes[i].v[0]*max[0]-f.planes[i].v[1]*max[1]-f.planes[i].v[2]*max[2];
                f.planes[i].v[3]=nextafterf(f.planes[i].v[3],trial&4?INFINITY:-INFINITY);
            }
            if(trial%31==0)f.planes[i].v[i%3]=-0.f;
        }
        bool old=reference(&f,min,max),now=bg_frustum_box((const float(*)[4])f.planes,min,max);
        if(old!=now){fprintf(stderr,"cull trial %u expected %u got %u\n",trial,old,now);assert(0);}
        bg_cull_bounds box={.valid=true};memcpy(box.min,min,sizeof(min));memcpy(box.max,max,sizeof(max));
        uint8_t selected[6][3];bg_frustum_prepare(selected,(const float(*)[4])f.planes);
        assert(bg_frustum_box_cached((const float(*)[4])f.planes,selected,box.values)==old);
        visible+=now;checked++;
    }
    assert(visible&&visible<checked);
    printf("PASS: %u AABB decisions exactly match SDK; %u retained; boundary/signed-zero cases included\n",checked,visible);
}
"""
out = validation_output("render-cull")
out.mkdir(parents=True, exist_ok=True)
p = out / "cull.c"
p.write_text(C.replace("REFERENCE", function(SDK.read_text(), "t3d_frustum_vs_aabb_s16")))
for label, flags in [
    ("strict", ["-fno-fast-math"]),
    (
        "target",
        ["-ffast-math", "-ftrapping-math", "-fno-associative-math", "-fno-finite-math-only"],
    ),
]:
    exe = out / label
    subprocess.run(
        [
            "clang",
            "-std=c17",
            "-O2",
            "-g",
            "-ffp-contract=off",
            "-fsanitize=address,undefined",
            "-Iport/n64",
            *flags,
            str(p),
            "-lm",
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)
