#ifndef BG_SOUND_STREAM_H
#define BG_SOUND_STREAM_H
#include <assert.h>
#include "sound_mix.h"
/* One voice's ROM window. Preserve its source cursor and resampling phase;
 * the existing mixer still owns sample selection, gain and clip completion. */
typedef struct { bg_audio_asset window; unsigned at; } bg_sound_stream;
static inline bool bg_sound_stream_refill(bg_sound_stream *s,bg_sound_voice *v,
        const bg_audio_asset *source,unsigned frames,const int8_t *(*read)(unsigned,unsigned)) {
    if(!v->asset)return false;
    s->at+=v->frame;v->frame=0;
    assert(s->at<source->count&&frames);
    /* Include the mixer's look-ahead sample after its last output frame. */
    unsigned needed=(unsigned)(((uint64_t)v->fraction+(uint64_t)frames*v->step)>>16)+1;
    if(needed>source->count-s->at)needed=source->count-s->at;
    s->window=(bg_audio_asset){read(s->at,needed),needed,source->rate,false};
    v->asset=&s->window;
    return true;
}
#endif
