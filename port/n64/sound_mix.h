#ifndef BG_SOUND_MIX_H
#define BG_SOUND_MIX_H
#include <stdbool.h>
#include <stdint.h>

typedef struct { const int8_t *samples; uint32_t count; uint16_t rate; bool loop; } bg_audio_asset;
typedef struct {
    const bg_audio_asset *asset;
    uint32_t frame, fraction, step;
    int left, right;
    bool loop;
} bg_sound_voice;

/* Same nearest-sample resampling and final headroom/clamping as the original
 * mixer. Processing one voice at a time keeps its state in CPU registers. */
void bg_sound_mix(bg_sound_voice *voices, unsigned voice_count, int16_t *output, unsigned frames);
#endif
