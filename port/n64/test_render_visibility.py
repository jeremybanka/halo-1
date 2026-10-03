"""Exercise the actual Tiny3D AABB test against clip-space edge probes."""
from pathlib import Path
import subprocess
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT.parent/'n64-3d-splitscreen/.build/tiny3d'
OUT = ROOT/'build/n64/visibility-weapon-qa/culling-test'
OUT.mkdir(parents=True, exist_ok=True)
math = (SDK/'src/t3d/t3dmath.c').read_text()
c = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "render_bounds.h"
#include "render_visibility.h"
typedef struct { float v[4]; } T3DVec4;
typedef struct { T3DVec4 planes[6]; } T3DFrustum;
'''
c += 'static bool t3d_frustum_vs_aabb_s16(const T3DFrustum*frustum,const int16_t min[3],const int16_t max[3]) {'+function(math,'t3d_frustum_vs_aabb_s16')+'}\n'
c += r'''
static unsigned count,inside,bleed,outside;
int main(void){
    const float sizes[3][2]={{320,240},{320,120},{160,120}};
    const float zooms[3]={1,2,10};
    for(unsigned layout=0;layout<3;layout++)for(unsigned z=0;z<3;z++)
    for(unsigned view=0;view<4;view++)for(unsigned rot=0;rot<37;rot++){
        float w=sizes[layout][0],h=sizes[layout][1];
        float focal=1.f/tanf((layout==1?.72f:1.08f)/zooms[z]*.5f);
        float sx=focal*h/w,sy=focal;
        float angle=rot*.169f,ca=cosf(angle),sa=sinf(angle);
        float tx=(view-1.5f)*200,ty=17,tz=(rot-18.f)*31;
        /* Test asymmetric projections as well as centered projection. */
        float ox=view&1?.1375f:-.1375f,oy=view&2?.133333f:-.133333f;
        if(layout==0)ox=oy=0;
        float camera[4][4]={{ca,0,sa,0},{0,1,0,0},{-sa,0,ca,0},{tx,ty,tz,1}};
        float proj[4][4]={{sx,0,0,0},{0,sy,0,0},{ox,oy,-1.000226f,-1},{0,0,-2.800632f,0}};
        float cp[4][4]={{0}};
        for(unsigned c=0;c<4;c++)for(unsigned r=0;r<4;r++)
            for(unsigned k=0;k<4;k++)cp[c][r]+=proj[k][r]*camera[c][k];
        T3DFrustum f={0};
        for(unsigned c=0;c<4;c++){
            f.planes[4].v[c]=cp[c][3]+cp[c][2];
            f.planes[5].v[c]=cp[c][3]-cp[c][2];
        }
        T3DFrustum saved=f;float saved_cp[4][4];memcpy(saved_cp,cp,sizeof cp);
        bg_visibility_side_planes((float (*)[4])f.planes,cp,w,h);
        assert(!memcmp(&f.planes[4],&saved.planes[4],2*sizeof(T3DVec4)));
        assert(!memcmp(cp,saved_cp,sizeof cp));
        for(unsigned edge=0;edge<4;edge++)for(unsigned d=0;d<9;d++)
        for(unsigned probe=0;probe<3;probe++){
            float depth=400+d*400;
            /* -0.25px: visible; +2px: requested bleed; +32px: culled even with quantized bounds at 10x zoom. */
            float pixel=probe==0?-.25f:probe==1?2.f:32.f;
            float ndcx=0,ndcy=0;
            if(edge<2)ndcx=(edge?1:-1)*(1+2*pixel/w);
            else ndcy=(edge==3?1:-1)*(1+2*pixel/h);
            float cx=(ndcx+ox)*depth/sx,cy=(ndcy+oy)*depth/sy,cz=-depth;
            /* Inverse rigid camera maps independently selected screen points. */
            float dx=cx-tx,dz=cz-tz;
            float world[3]={ca*dx+sa*dz,cy-ty,-sa*dx+ca*dz};
            bg_bounds b;bg_cull_bounds box;
            for(unsigned a=0;a<3;a++)b.min[a]=b.max[a]=world[a];
            bg_bounds_quantize(&box,&b);assert(box.valid);
            bool visible=t3d_frustum_vs_aabb_s16(&f,box.min,box.max);
            if(probe==0){assert(visible);inside++;}
            if(probe==1){assert(visible);bleed++;}
            if(probe==2){assert(!visible);outside++;}
            count++;
        }
    }
    printf("PASS %u probes: %u visible edge, %u 2px bleed, %u off-screen rejection; near/far and projection unchanged.\n",count,inside,bleed,outside);
}
'''
source=OUT/'edge-probes.c'
source.write_text(c)
for suffix, flags in [('strict', []), ('target-math',['-ffast-math','-ftrapping-math','-fno-associative-math'])]:
    binary=OUT/suffix
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined',*flags,'-I'+str(ROOT/'port/n64'),
                    str(source),'-lm','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
