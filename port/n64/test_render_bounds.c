#include "render_bounds.h"
#include <assert.h>
#include <stdio.h>

static uint32_t seed=0x583729u;
static float random_float(float lo,float hi){
    seed=seed*1664525u+1013904223u;
    return lo+(hi-lo)*(float)(seed>>8)/16777215.f;
}
int main(void){
    const bg_bounds box={{-.5001f,-.001f,.0001f},{.4999f,.002f,.5001f}};
    bg_cull_bounds rounded;bg_bounds_quantize(&rounded,&box);
    assert(rounded.valid&&rounded.min[0]==-2&&rounded.max[0]==2);
    assert(rounded.min[1]==-2&&rounded.max[2]==2);
    bg_bounds overflow={{-32768,0,0},{1,1,1}};
    bg_bounds_quantize(&rounded,&overflow);assert(!rounded.valid);
    overflow.min[0]=NAN;bg_bounds_quantize(&rounded,&overflow);assert(!rounded.valid);
    unsigned vertices=0;
    for(unsigned trial=0;trial<10000;trial++){
        bg_bounds local;
        for(unsigned a=0;a<3;a++){
            local.min[a]=random_float(-2,0);local.max[a]=random_float(0,2);
        }
        float m[4][4]={{0}},fixed[4][4]={{0}};
        for(unsigned col=0;col<4;col++)for(unsigned row=0;row<3;row++){
            m[col][row]=col<3?random_float(-.04f,.04f):random_float(-8000,8000);
            fixed[col][row]=truncf(m[col][row]*65536.f)/65536.f;
        }
        bg_bounds world;bg_bounds_transform(&world,&local,m,1024);
        bg_bounds_quantize(&rounded,&world);assert(rounded.valid);
        /* Checking every extreme of the box proves containment of its entire
         * interior under an affine transform, not just surface samples. */
        for(unsigned mask=0;mask<8;mask++)for(unsigned a=0;a<3;a++){
            float value=fixed[3][a];
            for(unsigned b=0;b<3;b++)value+=fixed[b][a]*1024*(mask&(1u<<b)?local.max[b]:local.min[b]);
            assert(value>=rounded.min[a]&&value<=rounded.max[a]);
            vertices++;
        }
    }
    printf("Bounds contain %u fixed-matrix corner coordinates; negative rounding and overflow pass.\n",vertices);
}
