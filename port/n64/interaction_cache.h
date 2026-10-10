#include "telemetry.h"
#ifndef BG_INTERACTION_CACHE_H
#define BG_INTERACTION_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>
/* Immutable ROM frame pairs. Separate small marker entries keep grips and
 * hatches from evicting body poses. Returned bytes live until the next fetch;
 * callers interpolate immediately into their fenced geometry buffers. */
#define BG_POSE_CACHE_SLOTS 8
#define BG_POSE_CACHE_SMALL 128
typedef struct {
    uint8_t *storage;
    uint32_t stride, next[2];
    struct {
        uint32_t offset, bytes;
    } entries[BG_POSE_CACHE_SLOTS * 2];
} bg_pose_cache;
static inline uint32_t bg_pose_cache_bytes(uint32_t stride) {
    return BG_POSE_CACHE_SLOTS * (stride + BG_POSE_CACHE_SMALL);
}
static inline const uint8_t *bg_pose_cache_fetch(bg_pose_cache *c, uint32_t offset, uint32_t bytes,
                                                 void (*read)(void *, uint32_t, uint32_t)) {
    assert(bytes && bytes <= c->stride);
    unsigned small = bytes <= BG_POSE_CACHE_SMALL, first = small * BG_POSE_CACHE_SLOTS;
    uint32_t stride = small ? BG_POSE_CACHE_SMALL : c->stride;
    uint8_t *base = c->storage + (small ? c->stride * BG_POSE_CACHE_SLOTS : 0);
    for (unsigned i = 0; i < BG_POSE_CACHE_SLOTS; i++)
        if (c->entries[first + i].bytes == bytes && c->entries[first + i].offset == offset) {
            BG_COUNT(BG_COUNT_POSE_HIT, 1);
            return base + i * stride;
        }
    BG_COUNT(BG_COUNT_POSE_MISS, 1);
    unsigned slot = 0, shared_first = 0, shared_end = 0, shared_bytes = 0;
    assert(offset <= UINT32_MAX - bytes);
    for (unsigned i = 0; i < BG_POSE_CACHE_SLOTS; i++) {
        const uint32_t old_offset = c->entries[first + i].offset,
                       old_bytes = c->entries[first + i].bytes;
        if (!old_bytes)
            continue;
        uint32_t begin = offset > old_offset ? offset : old_offset;
        uint32_t end =
            offset + bytes < old_offset + old_bytes ? offset + bytes : old_offset + old_bytes;
        if (end > begin && end - begin > shared_bytes &&
            !(((uintptr_t)(base + i * stride) | offset | bytes | begin | end) & 15u)) {
            slot = i;
            shared_first = begin;
            shared_end = end;
            shared_bytes = end - begin;
        }
    }
    uint8_t *data;
    if (shared_bytes) {
        data = base + slot * stride;
        /* A pair advancing by one frame reuses its previous second endpoint.
         * Copy before replacing the entry. Sixteen-byte boundaries keep PI
         * invalidation from discarding copied neighboring cache lines. */
        memmove(data + shared_first - offset, data + shared_first - c->entries[first + slot].offset,
                shared_bytes);
        if (shared_first > offset)
            read(data, offset, shared_first - offset);
        if (shared_end < offset + bytes)
            read(data + shared_end - offset, shared_end, offset + bytes - shared_end);
        BG_COUNT(BG_COUNT_POSE_PARTIAL_HIT, 1);
        BG_COUNT(BG_COUNT_POSE_REUSED_BYTES, shared_bytes);
    } else {
        slot = c->next[small]++ % BG_POSE_CACHE_SLOTS;
        data = base + slot * stride;
        read(data, offset, bytes);
    }
    c->entries[first + slot].offset = offset;
    c->entries[first + slot].bytes = bytes;
    return data;
}
#endif
