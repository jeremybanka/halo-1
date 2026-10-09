#include "render_lod.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void) {
    const float pi=3.14159265358979323846f,projection=120*1.668f;
    unsigned far_cases=0;
    for(unsigned size=1;size<=3;size++)for(unsigned z=1;z<=40;z++)for(int side=-3;side<=3;side++) {
        float radius=.075f*size,depth=.5f*z,x=depth*.45f*side,y=depth*.19f*side;
        if(!bg_lod_diameter_below(radius,projection,depth,x*x+y*y+depth*depth,12))continue;
        far_cases++;
        /* Independent projection of dense surface samples. Every projected
         * point must remain in a six-pixel circle about the source center. */
        for(unsigned u=0;u<64;u++)for(unsigned v=0;v<=32;v++) {
            float phi=u*pi/32,theta=v*pi/32;
            float px=x+radius*cosf(phi)*sinf(theta),py=y+radius*sinf(phi)*sinf(theta);
            float pz=depth+radius*cosf(theta);
            float dx=(px/pz-x/depth)*projection*.5f,dy=(py/pz-y/depth)*projection*.5f;
            assert(2*sqrtf(dx*dx+dy*dy)<12.0001f);
        }
    }
    assert(far_cases>100);
    assert(!bg_lod_diameter_below(.2f,projection,.1f,1,12));
    assert(!bg_lod_diameter_below(.2f,projection,1,1,12));
    assert(bg_lod_diameter_below(.2f,projection,20,400,12));
    printf("Conservative off-axis LOD verified against sphere projections in %u far cases\n",far_cases);
}
