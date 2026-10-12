#ifndef BG_RENDER_BOUNDS_H
#define BG_RENDER_BOUNDS_H
#include <stdbool.h>
#include <stdint.h>
#include <float.h>
#include <math.h>
#include <string.h>
#include "word_round.h"
_Static_assert(sizeof(float) == sizeof(uint32_t), "Renderer requires IEEE binary32 floats");
static inline bool bg_render_finite(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return (bits & UINT32_C(0x7f800000)) != UINT32_C(0x7f800000);
}

/* Source bounds are Y-up Halo units. Runtime transformed bounds are render
 * units. Keep the conversion explicit so asset precision cannot change size. */
typedef struct {
    float min[3], max[3];
} bg_bounds;
typedef struct {
    union {
        struct {
            int16_t min[3], max[3];
        };
        int16_t values[6];
    };
    bool valid;
} bg_cull_bounds;

static inline void bg_bounds_union(bg_bounds *out, const bg_bounds *other) {
    for (unsigned a = 0; a < 3; a++) {
        out->min[a] = fminf(out->min[a], other->min[a]);
        out->max[a] = fmaxf(out->max[a], other->max[a]);
    }
}

/* Tiny3D stores each matrix column in m[column][row]. The center/extent
 * transform encloses all eight corners, including nonuniform/negative scale. */
static inline void bg_bounds_transform(bg_bounds *out, const bg_bounds *in, const float m[4][4],
                                       float local_scale) {
    float center[3], extent[3];
    for (unsigned a = 0; a < 3; a++) {
        center[a] = (in->min[a] + in->max[a]) * .5f * local_scale;
        extent[a] = (in->max[a] - in->min[a]) * .5f * fabsf(local_scale);
    }
    for (unsigned a = 0; a < 3; a++) {
        float c = m[3][a], e = 0;
        for (unsigned b = 0; b < 3; b++) {
            c += m[b][a] * center[b];
            e += fabsf(m[b][a]) * extent[b];
        }
        out->min[a] = c - e;
        out->max[a] = c + e;
    }
}

static inline void bg_bounds_expand(bg_bounds *out, float radius) {
    for (unsigned a = 0; a < 3; a++) {
        out->min[a] -= radius;
        out->max[a] += radius;
    }
}

/* Asset validation proves one render unit exceeds final 16.16 matrix error
 * for every packed vertex. Outward rounding also protects negative positions;
 * C casts alone truncate inward on one side of a box. Overflow keeps a model
 * visible rather than wrapping its signed-short bounds into another place. */
static inline void bg_bounds_quantize(bg_cull_bounds *out, const bg_bounds *in) {
    out->valid = false;
    for (unsigned a = 0; a < 3; a++) {
        if (!bg_render_finite(in->min[a]) || !bg_render_finite(in->max[a]))
            return;
        float lo = in->min[a] - 1.f, hi = in->max[a] + 1.f;
        if (!bg_render_finite(lo) || !bg_render_finite(hi) || lo < INT16_MIN || hi > INT16_MAX ||
            lo >= (float)INT16_MAX + 1.f || hi <= (float)INT16_MIN - 1.f)
            return;
        /* Range checks precede the VR4300 word instructions. Their rounded
         * results equal the original libm path without float/int round trips. */
        int32_t lower = bg_floor_word(lo), upper = bg_ceil_word(hi);
        if (lower > upper)
            return;
        out->min[a] = (int16_t)lower;
        out->max[a] = (int16_t)upper;
    }
    out->valid = true;
}
#endif
