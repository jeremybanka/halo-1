#ifndef BG_SCOPE_MASK_H
#define BG_SCOPE_MASK_H
#include <stdint.h>
/* Native pixels: preserve the source mask's clear aperture and half-dark exterior without stretching its low-resolution baked ellipse. */
#define BG_SCOPE_LARGE_SIZE 152
#define BG_SCOPE_SMALL_SIZE 80
#define BG_SCOPE_MASK_BYTES (BG_SCOPE_LARGE_SIZE * BG_SCOPE_LARGE_SIZE + BG_SCOPE_SMALL_SIZE * BG_SCOPE_SMALL_SIZE)
static inline unsigned bg_scope_mask_size(unsigned height) {
    return height >= 240 ? BG_SCOPE_LARGE_SIZE : BG_SCOPE_SMALL_SIZE;
}
static inline void bg_scope_mask_generate(uint8_t *pixels, unsigned size, uint8_t exterior) {
    float center = (size - 1) * .5f;
    float radius = size == BG_SCOPE_LARGE_SIZE ? 75.f : 37.f;
    for (unsigned y = 0; y < size; y++) for (unsigned x = 0; x < size; x++) {
        float dx = x - center, dy = y - center, r2 = dx * dx + dy * dy;
        pixels[y * size + x] = r2 <= radius * radius ? 0 : exterior;
    }
}
#endif
