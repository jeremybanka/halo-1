"""Compare the production projection block with its checkpoint implementation.

Uses the installed SDK's real perspective/normalization setters. Camera work
is a deterministic spy: it records fresh camera/combined/frustum state so a
cache cannot accidentally retain those fields. No GPU timing claim is made.
"""

import argparse
from pathlib import Path
import re
import subprocess

from runtime_source import validation_output
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT.parent / "n64-3d-splitscreen/.build/tiny3d/src/t3d"


def projection_block(source):
    body = function(source, "prepare_view")
    first = re.search(r"\bT3DViewport\s*\*\s*vp\s*=\s*&viewports\[slot\]\[p\];", body).start()
    last = re.search(r"\bview_eyes\[p\]\s*=\s*eye;", body[first:]).start() + first
    return body[first:last]


PRELUDE = r"""
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "view_camera.h"
#include "hud_layout.h"
#include "render_cull.h"
typedef struct{float m[4][4];}T3DMat4;
typedef struct{float v[3];}T3DVec3;
typedef struct{
    uint32_t camera_fp[16],projection_fp[16];
    T3DMat4 matCamera,matProj,matCamProj;
    struct{float planes[6][4];}viewFrustum;
    bool _isCamProjDirty;
    int offset[2],size[2],guardBandScale,useRejection;
    float _normScaleW;
}T3DViewport;
typedef struct{float health;int weapon,zoom;}bg_player;
enum{BG_W_SNIPER=6};
static T3DViewport viewports[2][4],gun_viewports[2][4];
static uint8_t projection_keys[2][4];
static uint8_t cull_selected[4][6][3];
static unsigned views,slot,setups;
static void t3d_viewport_set_area(T3DViewport*v,int x,int y,int w,int h){
    v->offset[0]=x;v->offset[1]=y;v->size[0]=w;v->size[1]=h;
}
static void t3d_viewport_look_at(T3DViewport*v,const T3DVec3*eye,const T3DVec3*target,const T3DVec3*up){
    for(unsigned a=0;a<4;a++)for(unsigned b=0;b<4;b++){
        v->matCamera.m[a][b]=eye->v[a%3]+target->v[b%3]+up->v[a%3];
        v->matCamProj.m[a][b]=v->matCamera.m[a][b]+v->matProj.m[a][b];
    }
    for(unsigned a=0;a<6;a++)for(unsigned b=0;b<4;b++)v->viewFrustum.planes[a][b]=v->matCamProj.m[a%4][b];
    v->_isCamProjDirty=false;
}
static void bg_visibility_side_planes(float planes[6][4],const float m[4][4],int w,int h){
    for(unsigned a=0;a<4;a++)for(unsigned b=0;b<4;b++)planes[a][b]=m[a][b]+w*.001f+h*.002f;
}
"""
TEST = r"""
int main(void){
    static T3DViewport reference_world[2][4],reference_gun[2][4],cached_world[2][4],cached_gun[2][4];
    unsigned calls=0,reference_setups=0,cached_setups=0;
    bg_player players[4]={{100,0,0},{100,1,0},{100,6,0},{100,7,0}};
    for(unsigned frame=0;frame<20000;frame++){
        views=1+(frame/113)%4;slot=frame&1;
        for(unsigned p=0;p<views;p++){
            bg_player*q=&players[p];
            if((frame+p)%61==0){q->weapon=(q->weapon+1)%8;q->zoom=(q->zoom+1)%3;}
            q->health=(frame+p)%257<13?0:100;
            T3DVec3 eye={{sinf(frame*.013f)*50,(float)p+.25f,cosf(frame*.017f)*50}},target=eye;
            target.v[p%3]+=.75f;
            memcpy(viewports,reference_world,sizeof(viewports));memcpy(gun_viewports,reference_gun,sizeof(gun_viewports));
            unsigned before=setups;reference_projection(p,q,eye,target);reference_setups+=setups-before;
            memcpy(reference_world,viewports,sizeof(viewports));memcpy(reference_gun,gun_viewports,sizeof(gun_viewports));
            memcpy(viewports,cached_world,sizeof(viewports));memcpy(gun_viewports,cached_gun,sizeof(gun_viewports));
            before=setups;cached_projection(p,q,eye,target);cached_setups+=setups-before;
            memcpy(cached_world,viewports,sizeof(viewports));memcpy(cached_gun,gun_viewports,sizeof(gun_viewports));
            assert(!memcmp(&reference_world[slot][p],&cached_world[slot][p],sizeof(T3DViewport)));
            assert(!memcmp(&reference_gun[slot][p],&cached_gun[slot][p],sizeof(T3DViewport)));
            /* GPU attachment may update private fixed matrices. Those fields
             * must continue to follow the slot, not a cached camera template. */
            for(unsigned i=0;i<16;i++)reference_world[slot][p].camera_fp[i]=cached_world[slot][p].camera_fp[i]=frame+p+i;
            for(unsigned i=0;i<6;i++)for(unsigned a=0;a<3;a++)assert(cull_selected[p][i][a]==a+(cached_world[slot][p].viewFrustum.planes[i][a]>=0?3:0));
            calls++;
        }
    }
    assert(cached_setups*10<reference_setups);
    printf("PASS: %u world/gun viewport states identical; perspective evaluations %u -> %u\n",calls,reference_setups,cached_setups);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=validation_output("projection-cache"))
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    old = subprocess.check_output(["git", "show", "ffc5e53d:port/n64/scene.c"], cwd=ROOT, text=True)
    new = (ROOT / "port/n64/scene.c").read_text()
    setters = []
    for filename, names in (
        ("t3d.h", ("t3d_viewport_set_w_normalize",)),
        ("t3dmath.c", ("t3d_mat4_perspective",)),
        ("t3d.c", ("t3d_viewport_set_perspective", "t3d_viewport_set_projection")),
    ):
        source = (SDK / filename).read_text()
        signatures = {
            "t3d_viewport_set_w_normalize": "T3DViewport *viewport,float near,float far",
            "t3d_mat4_perspective": "T3DMat4 *mat,float fov,float aspect,float near,float far",
            "t3d_viewport_set_perspective": "T3DViewport *viewport,float fov,float aspectRatio,float near,float far",
            "t3d_viewport_set_projection": "T3DViewport *viewport,float fov,float near,float far",
        }
        for name in names:
            counted = "setups++;" if name == "t3d_mat4_perspective" else ""
            setters.append(
                f"static void {name}({signatures[name]}){{{counted}{function(source,name)}}}"
            )
    helpers = []
    for name, source in (("reference_projection", old), ("cached_projection", new)):
        helpers.append(
            f"static void {name}(unsigned p,bg_player*player,T3DVec3 eye,T3DVec3 target){{int w=views>=3?160:320,h=views==1?240:120,x=views>=3?(p%2)*160:0,y=views==1?0:(views>=3?p/2:p)*120;{projection_block(source)}}}"
        )
    test = out / "projection.c"
    test.write_text(PRELUDE + "\n".join(setters + helpers) + TEST)
    for label, math in (
        ("strict", ["-fno-fast-math"]),
        (
            "target",
            ["-ffast-math", "-ftrapping-math", "-fno-associative-math", "-fno-finite-math-only"],
        ),
    ):
        binary = out / label
        subprocess.run(
            [
                "clang",
                "-std=c17",
                "-O2",
                "-g",
                "-ffp-contract=off",
                "-fsanitize=address,undefined",
                "-Iport/n64",
                *math,
                str(test),
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
