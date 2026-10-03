#include "blam/collision.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include "collision_reference.inc"
extern const blam_collision_bsp bg_blam_collision_bsp;
#define COUNT(a) (sizeof(a)/sizeof((a)[0]))
static double dot(const double a[3],const double b[3]){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void cross(const double a[3],const double b[3],double c[3]){
    c[0]=a[1]*b[2]-a[2]*b[1];c[1]=a[2]*b[0]-a[0]*b[2];c[2]=a[0]*b[1]-a[1]*b[0];
}
/* Independent double-precision Moller-Trumbore ray/triangle intersection. */
static double reference(const float from[3],const float move[3],int *surface){
    double nearest=2,d[3]={move[0],move[1],move[2]};*surface=-1;
    for(unsigned n=0;n<COUNT(ref_triangles);n++){
        const float *a=ref_vertices[ref_triangles[n][0]],*b=ref_vertices[ref_triangles[n][1]],*c=ref_vertices[ref_triangles[n][2]];
        double e1[3],e2[3],offset[3],p[3],q[3];
        for(int i=0;i<3;i++){e1[i]=b[i]-a[i];e2[i]=c[i]-a[i];offset[i]=from[i]-a[i];}
        cross(d,e2,p);double det=dot(e1,p);if(fabs(det)<1e-12)continue;
        double u=dot(offset,p)/det;if(u<0||u>1)continue;
        cross(offset,e1,q);double v=dot(d,q)/det;if(v<0||u+v>1)continue;
        double t=dot(e2,q)/det;if(t<0||t>1||t>=nearest)continue;
        nearest=t;*surface=ref_triangles[n][3];
    }
    return nearest;
}
static uint32_t state=0x201f5a19;
static float random_signed(void){state=state*1664525u+1013904223u;return (state>>8)*(2.f/16777216.f)-1.f;}
int main(void){
    unsigned count=0,hits=0,mismatches=0;double worst=0;
    for(unsigned s=0;s<COUNT(ref_spawns);s++)for(unsigned ray=0;ray<12;ray++){
        float from[3]={ref_spawns[s][0],ref_spawns[s][1],ref_spawns[s][2]+.25f};
        float move[3]={ray?random_signed()*50:0,ray?random_signed()*50:0,ray?random_signed()*20:-10};
        blam_collision_hit hit;bool found=blam_collision_segment(&bg_blam_collision_bsp,from,move,true,&hit);
        int surface;double expected=reference(from,move,&surface);bool ref_found=expected<=1;count++;
        double error=found&&ref_found?fabs(expected-hit.fraction):0;
        if(error>worst)worst=error;
        if(found!=ref_found||error>1e-4){
            if(mismatches<12)fprintf(stderr,"spawn %u ray %u native %d %.8f surface %d reference %d %.8f surface %d\n",s,ray,found,found?hit.fraction:0,found?hit.surface:-1,ref_found,expected,surface);
            mismatches++;
        }
        if(found){hits++;assert(hit.surface>=0&&hit.surface<bg_blam_collision_bsp.surfaces.count);}
    }
    printf("%u rays across %zu spawn positions; %u hits, %u mismatches; worst fraction error %.9g\n",count,COUNT(ref_spawns),hits,mismatches,worst);
    return mismatches?1:0;
}
