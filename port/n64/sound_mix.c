#include "sound_mix.h"
#include <stddef.h>
#include <string.h>

void bg_sound_mix(bg_sound_voice *voices, unsigned voice_count, int16_t *output, unsigned frames) {
    enum { BLOCK = 256 };
    /* Every used entry is explicitly zeroed below. Avoid the toolchain's
     * additional 2 KiB pattern fill on every audio buffer call. */
    int32_t mixed[BLOCK * 2]
#if defined(__has_attribute)
#if __has_attribute(uninitialized)
        __attribute__((uninitialized))
#endif
#endif
        ;
    while (frames) {
        unsigned count = frames < BLOCK ? frames : BLOCK;
        memset(mixed, 0, count * 2 * sizeof(*mixed));
        for (unsigned channel = 0; channel < voice_count; channel++) {
            bg_sound_voice *v = &voices[channel];
            const bg_audio_asset *asset = v->asset;
            if (!asset)
                continue;
            const int8_t *samples = asset->samples;
            uint32_t frame = v->frame, fraction = v->fraction, step = v->step;
            uint32_t length = asset->count;
            int left = v->left, right = v->right;
            /* Most owned PCM is 1/2 or 1/4 output rate. Reuse its scaled
             * stereo sample until the source cursor advances; output and
             * phase are bit-identical to the sample-major reference. */
            int sample = samples[frame], scaled_left = sample * left, scaled_right = sample * right;
            for (unsigned f = 0; f < count; f++) {
                mixed[f * 2] += scaled_left;
                mixed[f * 2 + 1] += scaled_right;
                fraction += step;
                unsigned advance = fraction >> 16;
                fraction &= 65535;
                if (advance) {
                    frame += advance;
                    if (frame >= length) {
                        if (v->loop)
                            frame %= length;
                        else {
                            v->asset = NULL;
                            break;
                        }
                    }
                    sample = samples[frame];
                    scaled_left = sample * left;
                    scaled_right = sample * right;
                }
            }
            v->frame = frame;
            v->fraction = fraction;
        }
        for (unsigned f = 0; f < count * 2; f++) {
            int sample = mixed[f] / 2;
            output[f] = sample > 32767 ? 32767 : sample < -32768 ? -32768 : sample;
        }
        output += count * 2;
        frames -= count;
    }
}
