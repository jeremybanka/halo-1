#ifndef BG_RENDER_WORLD_SUBMIT_H
#define BG_RENDER_WORLD_SUBMIT_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
/* Exact cache of the ordered pre-frustum candidate list. The caller must
 * invalidate at map release, and include every non-frustum selector in key.
 * Camera orientation/zoom are represented by the newly evaluated LOD levels;
 * frustum tests are always performed against this frame's camera. */
typedef struct {
    const uint32_t *cell;
    uint64_t pvs;
    unsigned map, groups, chunks;
    bool room, lod;
    uint8_t levels[128];
} bg_world_submit_key;
typedef struct {
    bool valid;
    unsigned count;
    bg_world_submit_key key;
    uint16_t ids[BG_WORLD_CHUNK_CAPACITY];
    int16_t bounds[(BG_WORLD_CHUNK_CAPACITY+15)/16][6];
} bg_world_submit_cache;
static inline bool bg_world_submit_same(const bg_world_submit_cache *c,
                                        const bg_world_submit_key *k) {
    const bg_world_submit_key *a=&c->key;
    return c->valid&&a->cell==k->cell&&a->pvs==k->pvs&&a->map==k->map&&
        a->groups==k->groups&&a->chunks==k->chunks&&a->room==k->room&&a->lod==k->lod&&
        (!k->lod||memcmp(a->levels,k->levels,k->groups)==0);
}
#endif
