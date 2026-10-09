#ifndef BG_INTERACTION_CACHE_H
#define BG_INTERACTION_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
/* Immutable ROM frame pairs. Separate small marker entries keep grips and
 * hatches from evicting body poses. Returned bytes live until the next fetch;
 * callers interpolate immediately into their fenced geometry buffers. */
#define BG_POSE_CACHE_SLOTS 8
#define BG_POSE_CACHE_SMALL 128
typedef struct {
    uint8_t *storage;
    uint32_t stride,next[2];
    struct {uint32_t offset,bytes;} entries[BG_POSE_CACHE_SLOTS*2];
} bg_pose_cache;
static inline uint32_t bg_pose_cache_bytes(uint32_t stride){return BG_POSE_CACHE_SLOTS*(stride+BG_POSE_CACHE_SMALL);}
static inline const uint8_t *bg_pose_cache_fetch(bg_pose_cache*c,uint32_t offset,uint32_t bytes,
        void (*read)(void*,uint32_t,uint32_t)){
    assert(bytes&&bytes<=c->stride);
    unsigned small=bytes<=BG_POSE_CACHE_SMALL,first=small*BG_POSE_CACHE_SLOTS;
    uint32_t stride=small?BG_POSE_CACHE_SMALL:c->stride;
    uint8_t *base=c->storage+(small?c->stride*BG_POSE_CACHE_SLOTS:0);
    for(unsigned i=0;i<BG_POSE_CACHE_SLOTS;i++)
        if(c->entries[first+i].bytes==bytes&&c->entries[first+i].offset==offset)return base+i*stride;
    unsigned slot=c->next[small]++%BG_POSE_CACHE_SLOTS;
    uint8_t *data=base+slot*stride;read(data,offset,bytes);
    c->entries[first+slot].offset=offset;c->entries[first+slot].bytes=bytes;
    return data;
}
#endif
