#ifndef BG_SHIELD_AUDIO_H
#define BG_SHIELD_AUDIO_H
#include "sound_mix.h"
#include <math.h>
#include <stddef.h>
/* Tick at simulation rate. Phase survives repeated active-state updates;
 * shutdown keeps the source loop running only for its tag's fade duration. */
static inline void bg_shield_loop_update(bg_sound_voice*v,float*gain,const bg_audio_asset*a,
    bool active,unsigned pan,int volume,float fade_in,float fade_out,unsigned rate){
    if(!active&&*gain==0){v->asset=NULL;return;}
    float target=active?1:0,fade=active?fade_in:fade_out;
    if(fade==0)*gain=target;
    else if(*gain<target)*gain=fminf(target,*gain+1.f/(30*fade));
    else *gain=fmaxf(target,*gain-1.f/(30*fade));
    if(*gain<=.000001f){*gain=0;v->asset=NULL;return;}
    if(!v->asset)*v=(bg_sound_voice){.asset=a,.step=((uint32_t)a->rate<<16)/rate,.loop=true};
    volume=(int)(volume * (*gain));
    v->left=volume*(256-pan)/256;v->right=volume*pan/256;
}
#endif
