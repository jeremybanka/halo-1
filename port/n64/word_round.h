#ifndef BG_WORD_ROUND_H
#define BG_WORD_ROUND_H
#include <stdint.h>
#include <string.h>
#include <math.h>

/* Exact integer rounding for finite world coordinates whose rounded result
 * fits int32. Do not substitute approximate trigonometry or reassociate source
 * math. VR4300 word conversions avoid a libm call and float/int round trip.
 * Explicit subnormal handling also works with the N64's flush-to-zero mode. */
static inline int32_t bg_floor_word(float value) {
#ifdef N64
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    if (!(bits & UINT32_C(0x7f800000)))
        return (bits & UINT32_C(0x80000000)) && (bits & UINT32_C(0x007fffff)) ? -1 : 0;
    float word;
    __asm__("floor.w.s %0,%1" : "=f"(word) : "f"(value));
    int32_t result;
    memcpy(&result, &word, sizeof(result));
    return result;
#else
    return (int32_t)floorf(value);
#endif
}

static inline int32_t bg_ceil_word(float value) {
#ifdef N64
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    if (!(bits & UINT32_C(0x7f800000)))
        return !(bits & UINT32_C(0x80000000)) && (bits & UINT32_C(0x007fffff)) ? 1 : 0;
    float word;
    __asm__("ceil.w.s %0,%1" : "=f"(word) : "f"(value));
    int32_t result;
    memcpy(&result, &word, sizeof(result));
    return result;
#else
    return (int32_t)ceilf(value);
#endif
}
#endif
