#ifndef BG_RENDER_WORLD_LOD_H
#define BG_RENDER_WORLD_LOD_H
#include <math.h>
#include <stdint.h>
#include "render_lod.h"
#define BG_WORLD_LOD_MAX_GROUPS 128
/* Coordinates are renderer units (world * BG_SCALE). error is a symmetric
 * surface-distance bound including quantization. A zero error selects the
 * explicit projected-diameter limit instead (cutout foliage). */
typedef struct {
    float center[3], radius, error, pixels, diameter_pixels, near_distance;
    float bounds[6];
    unsigned box_diameter;
} bg_world_lod_group;
typedef struct {
    const bg_world_lod_group *groups;
    const uint16_t *chunks; /* 0: fixed; otherwise 1 + 2*group + level. */
    unsigned group_count, chunk_count, map_id;
} bg_world_lod_data;
extern const bg_world_lod_data bg_world_lod;
static inline bool bg_world_lod_far(const bg_world_lod_group *g,
        const float camera[4][4],const float projection[4][4],
        float width,float height,float near_plane,const float eye[3]) {
    float distance_box=0;
    for(unsigned a=0;a<3;a++) {
        float d=fmaxf(g->bounds[a]-eye[a],fmaxf(eye[a]-g->bounds[a+3],0));
        distance_box+=d*d;
    }
    if(!isfinite(distance_box)||distance_box<=g->near_distance*g->near_distance)return false;
    if(g->box_diameter && g->diameter_pixels>0) {
        /* For an entirely front-facing AABB, perspective extrema occur at
         * its corners. This avoids a large sphere falsely crossing the near
         * plane for long thin terrain regions. Bounds contain both meshes. */
        float lo[2]={INFINITY,INFINITY},hi[2]={-INFINITY,-INFINITY};
        /* Reuse the 18 axis/end-point products across all eight corners.
         * Keep each corner's addition order identical to the direct form. */
        float product[3][2][3];
        for(unsigned b=0;b<3;b++)for(unsigned end=0;end<2;end++)
            for(unsigned a=0;a<3;a++)product[b][end][a]=g->bounds[b+3*end]*camera[b][a];
        for(unsigned corner=0;corner<8;corner++) {
            float v[3]={camera[3][0],camera[3][1],camera[3][2]};
            for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)
                v[a]+=product[b][corner>>b&1][a];
            float depth=-v[2];
            if(!isfinite(depth)||depth<=near_plane)return false;
            for(unsigned a=0;a<2;a++) {
                float q=v[a]/depth;
                if(!isfinite(q))return false;
                lo[a]=fminf(lo[a],q);hi[a]=fmaxf(hi[a],q);
            }
        }
        float sx=(hi[0]-lo[0])*width*fabsf(projection[0][0])*.5f;
        float sy=(hi[1]-lo[1])*height*fabsf(projection[1][1])*.5f;
        return isfinite(sx)&&isfinite(sy)&&fmaxf(sx,sy)+.01f<g->diameter_pixels;
    }
    float c[3]={camera[3][0],camera[3][1],camera[3][2]};
    for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)c[a]+=g->center[b]*camera[b][a];
    float depth=-c[2],d2=c[0]*c[0]+c[1]*c[1]+c[2]*c[2];
    float scale=fmaxf(width*fabsf(projection[0][0]),height*fabsf(projection[1][1]));
    if(!isfinite(depth)||!isfinite(d2)||!isfinite(scale)||scale<=0||depth-g->radius<=near_plane)return false;
    if(g->diameter_pixels>0)return bg_lod_diameter_below(g->radius,scale,depth,d2,g->diameter_pixels);
    float nearest=depth-g->radius;
    float limit=2*g->pixels*nearest*nearest/(g->error*scale)-g->radius;
    return isfinite(limit)&&limit>0&&d2<limit*limit;
}
static inline bool bg_world_lod_keep(const bg_world_lod_data *data,
        const uint8_t *levels,unsigned chunk) {
    if(chunk>=data->chunk_count)return true;
    unsigned code=data->chunks[chunk];
    return !code||levels[(code-1)/2]==((code-1)&1);
}
#endif
