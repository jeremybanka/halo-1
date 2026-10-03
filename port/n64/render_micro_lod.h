#ifndef BG_RENDER_MICRO_LOD_H
#define BG_RENDER_MICRO_LOD_H
#include <string.h>
#include "render_bounds.h"
#include "render_lod.h"
/* Original outward world bounds in render units.
 * Sphere data is CPU-owned and independent of the two queued geometry slots. */
typedef struct { float center[3],radius; bool valid; const bg_cull_bounds* bounds; } bg_micro_sphere;
#define BG_MICRO_PIXELS 8
#define BG_MICRO_PIXEL_MARGIN .5f
static inline bool bg_micro_finite(const void*value){
    uint32_t bits;memcpy(&bits,value,sizeof(bits));return (bits&0x7f800000u)!=0x7f800000u;
}
static inline void bg_micro_sphere_from_bounds(bg_micro_sphere*out,const bg_cull_bounds*in){
    out->valid=false;out->bounds=in;if(!in||!in->valid)return;
    float radius_squared=0;
    for(unsigned a=0;a<3;a++){
        if(in->min[a]>in->max[a])return;
        out->center[a]=((float)in->min[a]+in->max[a])*.5f;
        float extent=((float)in->max[a]-in->min[a])*.5f;
        radius_squared+=extent*extent;
    }
    /* Outward float guard in addition to the existing one-unit box margin. */
    out->radius=sqrtf(radius_squared)*1.00001f+.001f;
    out->valid=bg_micro_finite(&out->radius)&&out->radius>0;
}
static inline bool bg_micro_lod_below(const bg_micro_sphere*s,const float camera[4][4],
        const float projection[4][4],unsigned width,unsigned height,float near_plane,
        float pixels,bool already_far,bool zoom,unsigned views){
    if(views!=4||!already_far||zoom||!s||!s->valid||!width||!height)return false;
    if(!bg_micro_finite(&s->radius)||s->radius<=0||!bg_micro_finite(&near_plane)||near_plane<=0||
       !bg_micro_finite(&pixels)||pixels<=0)return false;
    for(unsigned a=0;a<3;a++){
        if(!bg_micro_finite(&s->center[a]))return false;
        for(unsigned b=0;b<4;b++)if(!bg_micro_finite(&camera[b][a])||
            fabsf(camera[b][a])>(b<3?1.001f:65536.f))return false;
    }
    if(!bg_micro_finite(&projection[0][0])||!bg_micro_finite(&projection[1][1]))return false;
    float c[3];for(unsigned a=0;a<3;a++){
        c[a]=camera[3][a];for(unsigned b=0;b<3;b++)c[a]+=s->center[b]*camera[b][a];
    }
    float depth=-c[2],distance_squared=c[0]*c[0]+c[1]*c[1]+c[2]*c[2];
    float projection_size=fmaxf(width*fabsf(projection[0][0]),height*fabsf(projection[1][1]));
    if(!bg_micro_finite(&depth)||!bg_micro_finite(&distance_squared)||!bg_micro_finite(&projection_size)||
       projection_size<=0)return false;
    float limit=pixels-BG_MICRO_PIXEL_MARGIN;
    if(limit<=0)return false;
    if(depth-s->radius>near_plane+.001f&&
       bg_lod_diameter_below(s->radius,projection_size,depth,distance_squared,limit))return true;
    /* Positive-depth linear-fractional projection has its extrema at box
     * corners. Keep the full unclipped rectangle, including offscreen parts.
     * No screen clipping, integer casts or model-origin approximation. */
    const bg_cull_bounds*b=s->bounds;if(!b||!b->valid)return false;
    for(unsigned a=0;a<3;a++)if(b->min[a]>b->max[a])return false;
    float minx=FLT_MAX,maxx=-FLT_MAX,miny=FLT_MAX,maxy=-FLT_MAX;
    for(unsigned corner=0;corner<8;corner++){
        float q[3];for(unsigned a=0;a<3;a++){
            q[a]=camera[3][a];for(unsigned axis=0;axis<3;axis++)
                q[a]+=((corner&(1u<<axis))?b->max[axis]:b->min[axis])*camera[axis][a];
        }
        float z=-q[2];if(!bg_micro_finite(&z)||z<=near_plane+.001f)return false;
        float x=q[0]*(width*.5f*projection[0][0])/z;
        float y=q[1]*(height*.5f*projection[1][1])/z;
        if(!bg_micro_finite(&x)||!bg_micro_finite(&y))return false;
        minx=fminf(minx,x);maxx=fmaxf(maxx,x);miny=fminf(miny,y);maxy=fmaxf(maxy,y);
        /* Finite projected ranges only expand. Later invalid/near corners
         * also reject, so an already-too-wide box cannot become eligible. */
        if(maxx-minx>=limit||maxy-miny>=limit)return false;
    }
    float extent=fmaxf(maxx-minx,maxy-miny);
    return bg_micro_finite(&extent)&&extent<limit;

}
#endif
