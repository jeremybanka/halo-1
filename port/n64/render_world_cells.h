#ifndef BG_RENDER_WORLD_CELLS_H
#define BG_RENDER_WORLD_CELLS_H
#include <math.h>
#include <stdint.h>
typedef struct bg_world_cells_data {
    float origin[3], step[3];
    unsigned dimensions[3], words, chunks, map_id;
    const uint32_t *visible;
    const uint16_t *indices; /* Optional deduplicated row lookup. */
    const struct bg_world_cells_data *fallback; /* Scoped/outside fine grid. */
} bg_world_cells_data;
extern const bg_world_cells_data bg_world_cells;
/* Outside/uncertain cells retain every chunk. Visibility is an all-eyes
 * bound for the complete cell, independent of camera direction and zoom. */
static inline const uint32_t *bg_world_cells_row(const bg_world_cells_data *d,
        unsigned map_id,const float eye[3]) {
    if(!d||map_id!=d->map_id)return 0;
    unsigned cell[3];
    for(unsigned a=0;a<3;a++) {
        float v=(eye[a]-d->origin[a])/d->step[a];
        if(!isfinite(v)||v<0||v>=d->dimensions[a])
            return d->fallback?bg_world_cells_row(d->fallback,map_id,eye):0;
        cell[a]=(unsigned)v;
    }
    unsigned index=(cell[1]*d->dimensions[2]+cell[2])*d->dimensions[0]+cell[0];
    return d->visible+(d->indices?d->indices[index]:index)*d->words;
}
static inline const uint32_t *bg_world_cells_row_view(const bg_world_cells_data *d,
        unsigned map_id,const float eye[3],int scoped) {
    return bg_world_cells_row(d&&scoped&&d->fallback?d->fallback:d,map_id,eye);
}
static inline int bg_world_cells_keep(const bg_world_cells_data *d,
        const uint32_t *row,unsigned chunk) {
    return !row||chunk>=d->chunks||((row[chunk/32]>>(chunk%32))&1);
}
#endif
