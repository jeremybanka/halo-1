#ifndef BG_RENDER_WORLD_REP_H
#define BG_RENDER_WORLD_REP_H
#include <stdbool.h>
#include <math.h>
/* Private regional representation experiment. Bounds and eye are renderer
 * units; uncertain/outside cameras retain the ordinary world and its LOD. */
typedef struct {
    float bounds[6];
    unsigned original_chunks, total_chunks, map_id;
    const float (*footprint)[3];
    unsigned plane_count;
} bg_world_rep_data;
extern const bg_world_rep_data bg_world_rep;
static inline bool bg_world_rep_active(const bg_world_rep_data *d,
        unsigned map_id,const float eye[3]) {
    if(!d||map_id!=d->map_id)return false;
    for(unsigned a=0;a<3;a++)
        if(!isfinite(eye[a])||eye[a]<=d->bounds[a]||eye[a]>=d->bounds[a+3])return false;
    for(unsigned i=0;i<d->plane_count;i++) {
        const float *p=d->footprint[i];
        if(p[0]*eye[0]+p[1]*eye[2]<=p[2])return false;
    }
    return true;
}
static inline bool bg_world_rep_keep(const bg_world_rep_data *d,
        bool active,unsigned chunk) {
    if(chunk>=d->total_chunks)return true;
    return active?chunk>=d->original_chunks:chunk<d->original_chunks;
}
#endif
