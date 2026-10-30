#ifndef BG_PVE_MOTION_CACHE_H
#define BG_PVE_MOTION_CACHE_H
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

/* CPU-only immutable ROM spans. A returned pointer is consumed before the next
 * reserve; it is never handed to the RSP. FIFO allocation invalidates every
 * overlapping span before reuse, including wraparound and large requests. */
#define BG_PVE_MOTION_CACHE_BYTES (192u*1024u)
#define BG_PVE_MOTION_CACHE_ENTRIES 32
typedef struct {uint32_t source,offset,size;} bg_pve_motion_entry;
typedef struct {
    uint8_t bytes[BG_PVE_MOTION_CACHE_BYTES] __attribute__((aligned(16)));
    bg_pve_motion_entry entries[BG_PVE_MOTION_CACHE_ENTRIES];
    unsigned cursor,next;
} bg_pve_motion_cache;
static inline void bg_pve_motion_cache_reset(bg_pve_motion_cache*c){
    memset(c->entries,0,sizeof(c->entries));c->cursor=c->next=0;
}
static inline uint8_t*bg_pve_motion_reserve(bg_pve_motion_cache*c,uint32_t source,unsigned size,bool*hit){
    assert(size&&!(source&15)&&!(size&15)&&size<=BG_PVE_MOTION_CACHE_BYTES);
    for(unsigned i=0;i<BG_PVE_MOTION_CACHE_ENTRIES;i++){
        const bg_pve_motion_entry*e=&c->entries[i];
        if(e->size==size&&e->source==source){*hit=true;return c->bytes+e->offset;}
    }
    *hit=false;if(c->cursor+size>BG_PVE_MOTION_CACHE_BYTES)c->cursor=0;
    unsigned offset=c->cursor;c->cursor+=size;
    for(unsigned i=0;i<BG_PVE_MOTION_CACHE_ENTRIES;i++){
        bg_pve_motion_entry*e=&c->entries[i];
        if(e->size&&e->offset<offset+size&&offset<e->offset+e->size)e->size=0;
    }
    bg_pve_motion_entry*e=&c->entries[c->next++%BG_PVE_MOTION_CACHE_ENTRIES];
    *e=(bg_pve_motion_entry){source,offset,size};return c->bytes+offset;
}
#endif
