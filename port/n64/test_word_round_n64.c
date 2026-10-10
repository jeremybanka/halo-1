#include <libdragon.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "word_round.h"

/* Runs the actual VR4300 conversions, including subnormals and both signs.
 * The reference keeps the original libm -> float -> int32 path. */
int main(void) {
    debug_init_isviewer();
    display_init(RESOLUTION_320x240, DEPTH_16_BPP, 2, GAMMA_NONE, FILTERS_RESAMPLE);
    rdpq_init();
    rdpq_text_register_font(1, rdpq_font_load_builtin(FONT_BUILTIN_DEBUG_VAR));
    unsigned failures = 0, checked = 0;
    uint32_t seed = 0xce064, first_bits = 0;
    static const uint32_t edges[] = {0,          0x80000000, 1,          0x80000001, 0x7fffff,
                                     0x807fffff, 0x3f7fffff, 0xbf7fffff, 0x3f800001, 0xbf800001,
                                     0x4effffff, 0xceffffff, 0xcf000000};
    for (unsigned trial = 0; trial < 1000013; trial++) {
        uint32_t bits;
        if (trial < 13)
            bits = edges[trial];
        else {
            seed = seed * 1664525u + 1013904223u;
            bits = seed;
            if ((bits & 0x7fffffff) > 0x4effffff)
                continue;
        }
        float value;
        memcpy(&value, &bits, sizeof(value));
        int32_t floor_reference, ceil_reference;
        if (!(bits & 0x7f800000)) {
            /* VR4300 libm traps on subnormal arithmetic. Test their defined
             * integer result directly; normal inputs use the original path. */
            floor_reference = (bits & 0x80000000) && (bits & 0x7fffff) ? -1 : 0;
            ceil_reference = !(bits & 0x80000000) && (bits & 0x7fffff) ? 1 : 0;
        } else {
            floor_reference = (int32_t)floorf(value);
            ceil_reference = (int32_t)ceilf(value);
        }
        if (floor_reference != bg_floor_word(value) || ceil_reference != bg_ceil_word(value)) {
            if (!failures)
                first_bits = bits;
            failures++;
        }
        checked++;
    }
    debugf("WORD ROUND checked=%u failures=%u first=%08lx\n", checked, failures,
           (unsigned long)first_bits);
    for (;;) {
        surface_t *screen = display_get();
        rdpq_attach(screen, NULL);
        rdpq_set_mode_standard();
        rdpq_clear(RGBA32(9, 20, 39, 255));
        rdpq_text_print(NULL, 1, 12, 36, "VR4300 EXACT WORD ROUNDING");
        rdpq_text_printf(NULL, 1, 12, 64, "%u INPUTS / %u FAILURES", checked, failures);
        rdpq_text_printf(NULL, 1, 12, 92, "FIRST BAD BITS %08lx", (unsigned long)first_bits);
        rdpq_text_print(NULL, 1, 12, 120, failures ? "FAIL" : "PASS");
        rdpq_detach_show();
    }
}
