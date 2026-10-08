#include "game.h"
#include "blam/collision.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
extern const blam_collision_bsp bg_blam_collision_bsp;
static unsigned seed=7654;
static float random01(void){seed=1664525u*seed+1013904223u;return (seed>>8)*(1.f/16777216);}
int main(void){unsigned rays=0;
    for(unsigned i=0;i<3000;i++){
        float x=-35+70*random01(),z=-45+90*random01(),floor=bg_floor(x,z,100);if(floor< -900)continue;
        float p[3]={x,floor+.7f,z},v[3]={random01()*2-1,random01()*2-1,random01()*2-1};
        float len=sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);if(len<.01f)continue;for(int k=0;k<3;k++)v[k]/=len;
        float source[3]={x+68,-z-118,p[1]},delta[3]={v[0]*40,-v[2]*40,v[1]*40};blam_collision_hit hit;
        float original=blam_collision_segment(&bg_blam_collision_bsp,source,delta,true,&hit)?hit.fraction*40:40;
        float compact=bg_raycast(p,v,40);
        if(fabsf(original-compact)>.003f){fprintf(stderr,"source ray %u: original %g compact %g from %g,%g,%g\n",i,original,compact,p[0],p[1],p[2]);return 1;}
        rays++;
    }
    printf("PASS: %u shared BVH surface rays agree with original BSP within 0.003 world units\n",rays);
}
