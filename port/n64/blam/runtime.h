#ifndef HALO_N64_BLAM_RUNTIME_H
#define HALO_N64_BLAM_RUNTIME_H

#include <stdbool.h>
#include <stdint.h>

/* Narrow N64 adapters for routines ported from this repository's Blam source.
 * This is a subset of the engine, not an ABI-compatible replacement for it. */
#define BLAM_TICKS_PER_SECOND 30
#define BLAM_TICK_SECONDS (1.0f / BLAM_TICKS_PER_SECOND)

typedef struct {
    float leftover_dt, speed;
    uint32_t ticks;
    uint16_t elapsed;
    bool paused;
} blam_clock;

void blam_clock_reset(blam_clock *clock);
unsigned blam_clock_update(blam_clock *clock, float elapsed_seconds);
float blam_clock_fraction(const blam_clock *clock);

uint16_t blam_seed_random(uint32_t *seed);
int16_t blam_seed_random_range(uint32_t *seed, int16_t lower, int16_t upper);
float blam_real_seed_random(uint32_t *seed);
float blam_real_seed_random_range(uint32_t *seed, float lower, float upper);

/* Hamilton XYZW storage matches the extracted hand attachment poses. The
 * original routine uses shortest-hemisphere normalized linear interpolation,
 * not spherical interpolation. result may alias either input. */
void blam_quaternions_interpolate_and_normalize(const float q0[4],
    const float q1[4], float t, float result[4]);

#endif
