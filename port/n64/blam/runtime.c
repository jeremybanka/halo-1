/* Source-derived Blam routines with a small N64 boundary. The game-specific
 * graph, allocator, networking and XDK dependencies are removed, while the
 * arithmetic and event ordering below follow the cited original functions.
 * Repository source version: cybersecurity/halo-ce-universal 80d30410.
 */
#include "runtime.h"
#include <math.h>
#include <string.h>

/* source/game/game_time.c: game_time_start/game_time_update, local connection
 * branch; source/cseries/cseries.h: TICKS_PER_SECOND = 30. The original calls
 * game_tick for each result. The caller owns the input latch and those calls.
 * The original local branch discards backlog after seven catch-up ticks. */
void blam_clock_reset(blam_clock *clock) {
    memset(clock, 0, sizeof(*clock));
    clock->speed = 1.f;
}

unsigned blam_clock_update(blam_clock *clock, float elapsed_seconds) {
    clock->elapsed = 0;
    if (clock->paused || clock->speed <= 0.f) return 0;
    /* The platform clock is monotonic; reject invalid external values rather
     * than pass them to the float-to-integer conversion. */
    uint32_t elapsed_bits;
    memcpy(&elapsed_bits, &elapsed_seconds, sizeof(elapsed_bits));
    if ((elapsed_bits & UINT32_C(0x7f800000)) == UINT32_C(0x7f800000) ||
        elapsed_seconds < 0.f) return 0;
    float ticks_per_second = clock->speed * BLAM_TICKS_PER_SECOND;
    float game_time = elapsed_seconds + clock->leftover_dt;
    float ticks_elapsed_real = floorf(game_time * ticks_per_second);
    unsigned ticks_elapsed = (unsigned)fminf(ticks_elapsed_real, 1000.f);
    if (ticks_elapsed > 7) {
        ticks_elapsed = 7;
        game_time = ticks_elapsed_real / ticks_per_second;
    }
    clock->leftover_dt = game_time - ticks_elapsed_real / ticks_per_second;
    if (clock->leftover_dt < 0.f) clock->leftover_dt = 0.f;
    clock->elapsed = (uint16_t)ticks_elapsed;
    clock->ticks += ticks_elapsed;
    return ticks_elapsed;
}

float blam_clock_fraction(const blam_clock *clock) {
    if (clock->paused) return 1.f;
    float fraction = clock->leftover_dt * clock->speed * BLAM_TICKS_PER_SECOND;
    return fminf(fmaxf(fraction, 0.f), 1.f);
}

/* source/math/random_math.c: seed_random, seed_random_range,
 * real_seed_random, real_seed_random_range. Explicit uint32_t retains the
 * Xbox's unsigned-long wrap on both the 32-bit N64 and 64-bit host tests. */
uint16_t blam_seed_random(uint32_t *seed) {
    *seed = *seed * UINT32_C(1664525) + UINT32_C(1013904223);
    return (uint16_t)(*seed >> 16);
}
int16_t blam_seed_random_range(uint32_t *seed, int16_t lower, int16_t upper) {
    return (int16_t)(lower + ((uint32_t)(upper-lower) * blam_seed_random(seed) >> 16));
}
float blam_real_seed_random(uint32_t *seed) {
    *seed = *seed * UINT32_C(1664525) + UINT32_C(1013904223);
    return (float)(*seed >> 16) / 65535.0f;
}
float blam_real_seed_random_range(uint32_t *seed, float lower, float upper) {
    float random = blam_real_seed_random(seed);
    return lower + (upper-lower)*random;
}

/* source/math/real_math.c: quaternions_interpolate_and_normalize,
 * quaternions_interpolate and quaternion_normalize. This retains the source
 * hemisphere decision, arithmetic order and identity fallback. Arrays replace
 * real_quaternion's vector-plus-w layout at the N64 asset boundary. */
void blam_quaternions_interpolate_and_normalize(const float q0[4],
    const float q1[4], float t, float result[4]) {
    float v=1.f-t;
    if (q0[0]*q1[0]+q0[1]*q1[1]+q0[2]*q1[2]+q0[3]*q1[3]<0.f) t=-t;
    for (unsigned i=0;i<4;i++) result[i]=q0[i]*v+q1[i]*t;
    float magnitude_squared=result[0]*result[0]+result[1]*result[1]+
        result[2]*result[2]+result[3]*result[3];
    if (magnitude_squared>0.f) {
        float one_over_magnitude=1.f/sqrtf(magnitude_squared);
        for (unsigned i=0;i<4;i++) result[i]=one_over_magnitude*result[i];
    } else {
        result[0]=result[1]=result[2]=0.f;result[3]=1.f;
    }
}
