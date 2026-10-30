#include "scope_depth.h"
/* Keep a bounded local batch list while the eye stays within half a unit.
 * Overflow safely chooses the close projection; it never drops geometry. */
#define SCOPE_CANDIDATES 128
#define SCOPE_TRIANGLE_BUDGET 12
typedef struct {
    bool valid,have_probe,result,have_witness;
    float eye[3],witness[3][3];bg_scope_probe probe;
    unsigned count;uint16_t chunks[SCOPE_CANDIDATES];
} scope_candidates;
static scope_candidates scope_near_candidates[4];
static void scope_depth_reset(void) { memset(scope_near_candidates,0,sizeof(scope_near_candidates)); }
static bool scope_bounds_close(const bg_scope_probe *probe,const bg_cull_bounds *bounds) {
    if(!bounds->valid)return true;
    float lo[3],hi[3];
    for(unsigned k=0;k<3;k++){lo[k]=bounds->min[k]/BG_SCALE;hi[k]=bounds->max[k]/BG_SCALE;}
    return bg_scope_probe_box(probe,lo,hi);
}
static bool scope_near_geometry(unsigned viewer,const T3DVec3 *eye,const T3DVec3 *target,float fov,int w,int h) {
    float origin[3],forward[3],length=0;
    for(unsigned a=0;a<3;a++){origin[a]=eye->v[a]/BG_SCALE;forward[a]=target->v[a]-eye->v[a];length+=forward[a]*forward[a];}
    length=sqrtf(length);for(unsigned a=0;a<3;a++)forward[a]/=length;
    float ax,ay;bg_hud_aim_point(views,viewer,0,0,1,1,&ax,&ay);
    bg_scope_probe probe;float ty=tanf(fov*.5f);
    bg_scope_probe_init(&probe,origin,forward,ty*w/h,ty,ax,ay);
    /* Existing conservative animated bounds protect nearby moving objects.
     * NPCs use their established all-motion sphere, before pose preparation. */
    for(unsigned p=0;p<views;p++)if(p!=viewer && bg_player_visibility(&bg_players[p])>0 && (scope_bounds_close(&probe,&body_bounds[p])||scope_bounds_close(&probe,&held_bounds[p])))return true;
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicle_body_present(&bg_vehicles[i])&&scope_bounds_close(&probe,&vehicle_bounds[i]))return true;
    for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].active&&scope_bounds_close(&probe,&pickup_bounds[i]))return true;
#ifdef BG_PVE
    for(unsigned i=0;i<bg_pve_count;i++)if(bg_pve_actors[i].occupied && !(bg_players[BG_PLAYERS+i].health<=0&&bg_pve_actors[i].death_time>15)) {
        float lo[3],hi[3];for(unsigned a=0;a<3;a++){float c=bg_players[BG_PLAYERS+i].pos[a]+(a==1?.4f:0);lo[a]=c-2;hi[a]=c+2;}
        if(bg_scope_probe_box(&probe,lo,hi))return true;
    }
#endif
    for(unsigned i=0;i<bg_objective_count;i++)if(bg_objectives[i].active&&bg_objectives[i].owner<0) {
        bg_cull_bounds bounds;prepare_effect_bounds(&bounds,bg_objectives[i].pos,bg_objectives[i].kind==BG_OBJECTIVE_FLAG?2.f:bg_objective_models[bg_objectives[i].kind].radius+.5f);
        if(scope_bounds_close(&probe,&bounds))return true;
    }
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++) {
        bg_projectile *q=bg_projectile_at(i);if(!q||!q->active)continue;
        bg_cull_bounds bounds;prepare_effect_bounds(&bounds,q->pos,.2f);
        if(scope_bounds_close(&probe,&bounds))return true;
    }
#ifdef BG_PVE
    if(bg_ff_dropship.phase) {
        bg_cull_bounds bounds;prepare_effect_bounds(&bounds,bg_ff_dropship.pos,9);
        if(scope_bounds_close(&probe,&bounds))return true;
    }
#endif
    scope_candidates *cache=&scope_near_candidates[viewer];
    if(cache->have_probe && !memcmp(&cache->probe,&probe,sizeof(probe)))return cache->result;
    cache->probe=probe;cache->have_probe=true;cache->result=true;
    /* The previous intersecting face is usually still under a moving player.
     * Re-test it first, with the current camera; never reuse a stale result. */
    if(cache->have_witness&&bg_scope_probe_triangle(&probe,(const float (*)[3])cache->witness))return true;
    bool moved=!cache->valid;
    for(unsigned a=0;a<3;a++)if(fabsf(cache->eye[a]-origin[a])>.5f)moved=true;
    if(moved) {
        memcpy(cache->eye,origin,sizeof(origin));cache->count=0;cache->valid=true;
        for(unsigned b=0;b<bg_chunk_count;b++) {
            const bg_chunk *c=&bg_chunks[b];bool nearby=true;
            for(unsigned a=0;a<3;a++)if(c->bounds[a]/BG_SCALE>origin[a]+2 || c->bounds[a+3]/BG_SCALE<origin[a]-2)nearby=false;
            if(!nearby)continue;
            if(cache->count==SCOPE_CANDIDATES){cache->count++;break;}
            cache->chunks[cache->count++]=b;
        }
    }
    if(cache->count>SCOPE_CANDIDATES)return true;
    int16_t encoded[2]={0,1};t3d_indexbuffer_convert(encoded,2);
    unsigned base=(uint16_t)encoded[0]&0x3fff,stride=((uint16_t)encoded[1]&0x3fff)-base;
    unsigned tested=0;
    for(unsigned i=0;i<cache->count;i++) {
        const bg_chunk *c=&bg_chunks[cache->chunks[i]];float lo[3],hi[3];
        for(unsigned a=0;a<3;a++){lo[a]=c->bounds[a]/BG_SCALE;hi[a]=c->bounds[a+3]/BG_SCALE;}
        if(!bg_scope_probe_box(&probe,lo,hi))continue;
        for(unsigned tri=0;tri<c->index_count;tri+=3) {
            /* An inconclusive bounded search selects the safe close plane. */
            if(tested++==SCOPE_TRIANGLE_BUDGET)return true;
            float corners[3][3];
            for(unsigned v=0;v<3;v++) {
                unsigned index=(((uint16_t)bg_chunk_indices[c->index_first+tri+v]&0x3fff)-base)/stride;
                assertf(index<c->count,"Scope render index");
                int16_t *position=t3d_vertbuffer_get_pos(bg_vertices+c->first/2,index);
                for(unsigned a=0;a<3;a++)corners[v][a]=position[a]/BG_TERRAIN_SCALE;
            }
            if(bg_scope_probe_triangle(&probe,(const float (*)[3])corners)) {
                memcpy(cache->witness,corners,sizeof(corners));cache->have_witness=true;return true;
            }
        }
    }
    cache->result=false;return false;
}
