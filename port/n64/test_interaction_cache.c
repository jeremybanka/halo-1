#include "interaction_cache.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t rom[1048576];
static unsigned reads, read_bytes;
static void load(void *out, uint32_t offset, uint32_t bytes) {
    assert(offset + bytes <= sizeof(rom));
    memcpy(out, rom + offset, bytes);
    reads++;
    read_bytes += bytes;
}
int main(void) {
    const unsigned stride = 7520;
    bg_pose_cache c = {.storage = malloc(bg_pose_cache_bytes(stride)), .stride = stride};
    assert(c.storage);
    for (unsigned i = 0; i < sizeof(rom); i++)
        rom[i] = (i * 37 + (i >> 8)) & 255;
    /* Four seats with near/far geometry and eight tiny marker tracks. Reuse
     * interpolation endpoints without re-reading their immutable ROM bytes. */
    for (unsigned frame = 0; frame < 30; frame++)
        for (unsigned i = 0; i < 8; i++) {
            unsigned offset = i * 8192, bytes = 3008 + i * 16;
            assert(!memcmp(bg_pose_cache_fetch(&c, offset, bytes, load), rom + offset, bytes));
            assert(!memcmp(bg_pose_cache_fetch(&c, 90000 + i * 128, 64, load),
                           rom + 90000 + i * 128, 64));
        }
    /* The validator's smaller cache evicts this eight-track working set.
     * Both layouts must still return every original ROM byte. */
    assert(reads == (BG_POSE_CACHE_SLOTS >= 8 ? 16 : 30 * 16));
    /* Changed endpoint lengths, clip changes and repeated evictions must
     * return the same bytes as an uncached read, including maximum pairs. */
    for (unsigned i = 0; i < 10000; i++) {
        unsigned offset = (i * 31 % 1400) * 64, bytes = i % 5 ? 16 * (1 + i % 400) : stride;
        assert(!memcmp(bg_pose_cache_fetch(&c, offset, bytes, load), rom + offset, bytes));
    }
    uint8_t *storage = c.storage;
    memset(&c, 0, sizeof(c));
    c.storage = storage;
    c.stride = stride;
    reads = read_bytes = 0;
    /* Eight advancing animation pairs retain byte-exact endpoint overlap,
     * including reverse playback and wrap to another clip. */
    for (unsigned frame = 0; frame < 120; frame++)
        for (unsigned i = 0; i < 8; i++) {
            unsigned at = i * 131072 + (frame < 60 ? frame : 119 - frame) * 400;
            assert(!memcmp(bg_pose_cache_fetch(&c, at, 800, load), rom + at, 800));
        }
    if (BG_POSE_CACHE_SLOTS >= 8) assert(read_bytes < 400000);
    printf("Moving pairs: %u DMA bytes instead of 768000\n", read_bytes);
    free(c.storage);
    /* Blood Gulch uses four slots even in the eight-slot production build.
     * Allocate exactly that budget so sanitizers catch either pool crossing
     * its end; exercise both maximum body pairs and small marker tracks. */
    c = (bg_pose_cache){.storage = malloc(4 * (stride + BG_POSE_CACHE_SMALL)),
                        .stride = stride, .slots = 4};
    assert(c.storage);
    for (unsigned i = 0; i < 10000; i++) {
        unsigned offset = (i * 31 % 100) * 8192;
        assert(!memcmp(bg_pose_cache_fetch(&c, offset, stride, load), rom + offset, stride));
        unsigned marker = 900000 + (i % 13) * 128;
        assert(!memcmp(bg_pose_cache_fetch(&c, marker, 64, load), rom + marker, 64));
    }
    free(c.storage);
    puts("PASS: runtime four-slot budget preserves body and marker bytes through 10000 evictions");
    printf("PASS: %u-slot ROM frame cache byte-identical through reuse, length changes and 10000 evictions\n",
           (unsigned)BG_POSE_CACHE_SLOTS);
}
