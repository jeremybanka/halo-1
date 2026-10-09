#include "shield_audio.h"
#include "shield_assets.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    bg_sound_voice v={0};float gain=0;int16_t out[1470];
    for(unsigned clip=0;clip<2;clip++){
        const bg_audio_asset*a=&bg_shield_audio[clip];assert(a->rate==5512&&a->count>1000);
        v=(bg_sound_voice){0};gain=0;
        for(unsigned tick=0;tick<180;tick++){
            unsigned previous=v.frame;
            bg_shield_loop_update(&v,&gain,a,true,80,80,.5f,.5f,22050);
            assert(v.frame==previous&&v.asset==a&&v.loop&&v.left>v.right);
            bg_sound_mix(&v,1,out,735);
            if(tick>=14)assert(gain==1);
        }
        for(unsigned tick=0;tick<15;tick++)bg_shield_loop_update(&v,&gain,a,false,128,80,.5f,.5f,22050);
        assert(!v.asset&&gain==0);
    }
    bg_shield_loop_update(&v,&gain,&bg_shield_audio[0],true,128,80,0,.1f,22050);
    assert(gain==1&&v.frame==0);
    for(unsigned i=0;i<3;i++)bg_shield_loop_update(&v,&gain,&bg_shield_audio[0],false,128,80,0,.1f,22050);
    assert(!v.asset&&gain==0);
    puts("PASS: original warning PCM, smooth tagged fades, unbroken loop phase, viewport pan, recharge stop");
}
