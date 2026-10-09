"""Compare actual prepared effect boxes with the former per-view calculation.

The harness extracts the current preparation loops, helper and Tiny3D AABB
test. It exercises all four views, negative coordinates, overflow, and slots
becoming inactive then active with different positions. No GPU timing claim.
"""
from pathlib import Path
import hashlib
import json
import subprocess
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/n64/visibility-weapon-qa/effect-bounds-cache'
OUT.mkdir(parents=True, exist_ok=True)
main = (ROOT/'port/n64/main.c').read_text()
sdk = ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src/t3d/t3dmath.c'
prepare = function(main, 'prepare_frame')
start = prepare.index('for(unsigned i=0;i<BG_MAX_PROJECTILES;i++)')
end = prepare.index('data_cache_hit_writeback(transforms[slot]')
loops = prepare[start:end]
assert loops.count('prepare_effect_bounds(&projectile_bounds[i],q->pos,.2f);') == 1
draw = compact(function(main, 'draw_view'))
assert '!q||!q->active||!visible_bounds(vp,&projectile_bounds[i])' in draw
assert 'prepare_effect_bounds(' not in draw
c = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "render_bounds.h"
#define BG_OBJECT_SCALE 1024.f
typedef struct {float v[4];} T3DVec4;
typedef struct {T3DVec4 planes[6];} T3DFrustum;
typedef struct {T3DFrustum viewFrustum;} T3DViewport;
typedef struct {float pos[3],scale;} Matrix;
static Matrix projectile_matrices[2][BG_MAX_PROJECTILES];
static bg_cull_bounds projectile_bounds[BG_MAX_PROJECTILES];
static bg_projectile projectiles[BG_MAX_PROJECTILES];
static bool present[BG_MAX_PROJECTILES];
static unsigned slot,matrix_calls;
static float game_time;
bg_projectile*bg_projectile_at(unsigned i){return present[i]?&projectiles[i]:NULL;}
static void matrix(Matrix*out,float scale,float yaw,float pitch,const float pos[3]){
    (void)yaw;(void)pitch;memcpy(out->pos,pos,12);out->scale=scale;matrix_calls++;
}
'''
for src, ret, name, args in (
    (sdk.read_text(), 'bool', 't3d_frustum_vs_aabb_s16', 'const T3DFrustum*frustum,const int16_t min[3],const int16_t max[3]'),
    (main, 'void', 'prepare_effect_bounds', 'bg_cull_bounds*bounds,const float pos[3],float radius'),
    (main, 'bool', 'visible_bounds', 'T3DViewport*vp,const bg_cull_bounds*bounds'),
):
    c += f'\nstatic {ret} {name}({args}){{{function(src,name)}}}\n'
c += '\nstatic void prepare_effects(void){'+loops+'}\n'
c += r'''
/* Exact pre-cache expression, independently evaluated anew for each view. */
static bool reference(T3DViewport*vp,const float pos[3],float radius,bg_cull_bounds*out){
    bg_bounds box;
    for(unsigned a=0;a<3;a++){
        box.min[a]=(pos[a]-radius)*BG_SCALE;box.max[a]=(pos[a]+radius)*BG_SCALE;
    }
    bg_bounds_quantize(out,&box);
    return !out->valid||t3d_frustum_vs_aabb_s16(&vp->viewFrustum,out->min,out->max);
}
static uint32_t seed=0xCE064;
static uint32_t random_u32(void){seed=seed*1664525u+1013904223u;return seed;}
static float uniform(float lo,float hi){return lo+(hi-lo)*(float)(random_u32()>>8)/16777215.f;}
static unsigned checks,overflow;
static void check(T3DViewport*vp,const float pos[3],float radius,const bg_cull_bounds*cached){
    bg_cull_bounds old;
    bool expected=reference(vp,pos,radius,&old);
    assert(visible_bounds(vp,cached)==expected);assert(old.valid==cached->valid);
    if(old.valid){assert(!memcmp(old.min,cached->min,6));assert(!memcmp(old.max,cached->max,6));}
    else{assert(expected);overflow++;}
    checks++;
}
int main(void){
    for(unsigned frame=0;frame<4096;frame++){
        slot=frame%2;game_time=frame/30.f;
        memset(projectile_bounds,0x5a,sizeof projectile_bounds);
        unsigned active=0;
        for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
            bg_projectile*q=&projectiles[i];present[i]=(frame+i)%7!=0;
            q->active=(frame+i)%3!=0;q->kind=(frame+i)%7;
            for(unsigned a=0;a<3;a++)q->pos[a]=uniform(-100,100);
            /* Finite values beyond signed-short bounds must stay visible. */
            if(i%11==0)q->pos[i%3]=(i&1?1:-1)*100000.f;
            if(present[i]&&q->active)active++;
        }
        matrix_calls=0;prepare_effects();assert(matrix_calls==active);
        bg_cull_bounds saved_p[BG_MAX_PROJECTILES];
        memcpy(saved_p,projectile_bounds,sizeof saved_p);
        for(unsigned view=0;view<4;view++){
            T3DViewport vp;
            for(unsigned p=0;p<6;p++){
                for(unsigned a=0;a<3;a++)vp.viewFrustum.planes[p].v[a]=uniform(-2,2);
                vp.viewFrustum.planes[p].v[3]=uniform(-4000,4000);
            }
            for(unsigned i=0;i<BG_MAX_PROJECTILES;i++)if(present[i]&&projectiles[i].active)
                check(&vp,projectiles[i].pos,.2f,&projectile_bounds[i]);
        }
        assert(!memcmp(saved_p,projectile_bounds,sizeof saved_p));
    }
    assert(overflow>0);
    printf("PASS: %u cached/per-view decisions; %u overflow-visible cases; 4096 active/inactive/reused frames; boxes immutable across four views.\n",checks,overflow);
}
'''
source = OUT/'actual-effect-bounds.c'
source.write_text(c)
results = []
for label, flags in [('strict', []), ('target-math', ['-ffast-math','-ftrapping-math','-fno-associative-math'])]:
    binary = OUT/label
    command = ['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
               *flags,'-I'+str(ROOT/'port/n64'),str(source),'-lm','-o',str(binary)]
    subprocess.run(command, check=True)
    result = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
    print(result.stdout, end='');results.append({'mode':label,'command':command,'output':result.stdout})
(OUT/'equivalence-proof.json').write_text(json.dumps({'results':results,
    'main_sha256':hashlib.sha256(main.encode()).hexdigest(),
    'sdk_math_sha256':hashlib.sha256(sdk.read_bytes()).hexdigest(),
    'note':'Actual CPU helper/preparation loops and SDK AABB routine; no target pixel or timing claim.'},indent=2)+'\n')
