#ifndef BG_PVE_CRUNCH_LOD_H
#define BG_PVE_CRUNCH_LOD_H
#include "render_bounds.h"
/* Enter below 28 pixels; return to the old far model above 34. Use the
 * entire unclipped, all-poses box, never just its visible screen fragment. */
#define BG_PVE_CRUNCH_ENTER 28.f
#define BG_PVE_CRUNCH_EXIT 34.f
typedef struct { uint16_t generation; uint8_t kind; bool small; } bg_pve_crunch_state;
static inline bool bg_pve_crunch_below(const bg_cull_bounds*b,const float camera[4][4],
        const float projection[4][4],unsigned width,unsigned height,float near,float pixels){
    if(!b||!b->valid||!width||!height||!bg_render_finite(near)||near<=0)return false;
    for(unsigned a=0;a<3;a++){
        if(b->min[a]>b->max[a])return false;
        for(unsigned j=0;j<4;j++)if(!bg_render_finite(camera[j][a]))return false;
    }
    if(!bg_render_finite(projection[0][0])||!bg_render_finite(projection[1][1])||
       projection[0][0]<=0||projection[1][1]<=0)return false;
    float lo[2]={FLT_MAX,FLT_MAX},hi[2]={-FLT_MAX,-FLT_MAX};
    for(unsigned corner=0;corner<8;corner++){
        float q[3];for(unsigned a=0;a<3;a++){
            q[a]=camera[3][a];for(unsigned j=0;j<3;j++)
                q[a]+=((corner&(1u<<j))?b->max[j]:b->min[j])*camera[j][a];
        }
        float z=-q[2];if(!bg_render_finite(z)||z<=near+.001f)return false;
        for(unsigned a=0;a<2;a++){
            float p=q[a]*((a?height:width)*.5f*projection[a][a])/z;
            if(!bg_render_finite(p))return false;
            lo[a]=fminf(lo[a],p);hi[a]=fmaxf(hi[a],p);
            if(hi[a]-lo[a]>=pixels-.5f)return false;
        }
    }
    return true;
}
static inline bool bg_pve_crunch_select(bg_pve_crunch_state*s,unsigned generation,unsigned kind,
        const bg_cull_bounds*b,const float camera[4][4],const float projection[4][4],
        unsigned width,unsigned height,float near,bool far,bool zoom){
    if(s->generation!=generation||s->kind!=kind){s->small=false;s->generation=generation;s->kind=kind;}
    s->small=far&&!zoom&&bg_pve_crunch_below(b,camera,projection,width,height,near,
        s->small?BG_PVE_CRUNCH_EXIT:BG_PVE_CRUNCH_ENTER);
    return s->small;
}
#endif
