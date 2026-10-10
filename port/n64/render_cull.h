#ifndef BG_RENDER_CULL_H
#define BG_RENDER_CULL_H
#include <stdbool.h>
#include <stdint.h>

static inline void bg_frustum_prepare(uint8_t selected[6][3], const float planes[6][4]) {
    for (unsigned i = 0; i < 6; i++)
        for (unsigned a = 0; a < 3; a++)
            selected[i][a] = a + (planes[i][a] >= 0 ? 3 : 0);
}

static inline bool bg_frustum_box_cached(const float planes[6][4], const uint8_t selected[6][3],
                                         const int16_t values[6]) {
    for (unsigned i = 0; i < 6; i++) {
        const float *p = planes[i];
        float x = p[0] * values[selected[i][0]], y = p[1] * values[selected[i][1]];
        float threshold = -p[3] - p[2] * values[selected[i][2]];
        if (!(x + y > threshold))
            return false;
    }
    return true;
}

/* Same strict predicate and expression grouping as Tiny3D's eight-corner
 * test. For a valid AABB, each rounded multiplication/addition is monotone,
 * so the maximum XY sum and minimum Z threshold cover all eight choices.
 * This avoids reassociating the plane equation at clipping boundaries. */
static inline bool bg_frustum_box(const float planes[6][4], const int16_t min[3],
                                  const int16_t max[3]) {
    for (unsigned i = 0; i < 6; i++) {
        const float *p = planes[i];
        float x = p[0] * (p[0] >= 0 ? max[0] : min[0]);
        float y = p[1] * (p[1] >= 0 ? max[1] : min[1]);
        float threshold = -p[3] - p[2] * (p[2] >= 0 ? max[2] : min[2]);
        if (!(x + y > threshold))
            return false;
    }
    return true;
}
#endif
