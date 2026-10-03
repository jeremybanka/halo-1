#include "sound_mix.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t seed = 0x72656d61;
static unsigned random_u32(void) { seed = seed*1664525u+1013904223u; return seed; }

/* Frozen sample-major implementation: this is an output-equivalence test,
 * including clip endings, rate changes, looping and saturation. */
static void reference(bg_sound_voice *voices, int16_t *out, unsigned frames) {
    for (unsigned f = 0; f < frames; f++) {
        int left=0,right=0;
        for (unsigned c=0;c<14;c++) {
            bg_sound_voice *v=&voices[c];if(!v->asset)continue;
            int sample=v->asset->samples[v->frame];
            left+=sample*v->left;right+=sample*v->right;
            v->fraction+=v->step;v->frame+=v->fraction>>16;v->fraction&=65535;
            if(v->frame>=v->asset->count){if(v->loop)v->frame%=v->asset->count;else v->asset=NULL;}
        }
        left/=2;right/=2;
        out[f*2]=left>32767?32767:left< -32768?-32768:left;
        out[f*2+1]=right>32767?32767:right< -32768?-32768:right;
    }
}
int main(void) {
    int8_t samples[14][4096];bg_audio_asset assets[14];
    int16_t expected[4096],actual[4096];
    unsigned checked=0;
    for (unsigned run=0;run<300;run++) {
        bg_sound_voice a[14]={0},b[14];
        for (unsigned c=0;c<14;c++) {
            for(unsigned i=0;i<4096;i++)samples[c][i]=(int8_t)(random_u32()>>24);
            assets[c]=(bg_audio_asset){samples[c],run%7?1+random_u32()%4096:1,11025,false};
            a[c]=(bg_sound_voice){random_u32()%5?&assets[c]:NULL,
                random_u32()%assets[c].count,random_u32()%65536,random_u32()%262144,
                (int)(random_u32()%257),(int)(random_u32()%257),(run+c)%3!=0};
        }
        memcpy(b,a,sizeof(a));
        for(unsigned buffer=0;buffer<8;buffer++) {
            unsigned frames=random_u32()%2049;
            reference(a,expected,frames);bg_sound_mix(b,14,actual,frames);
            assert(!memcmp(expected,actual,frames*2*sizeof(*actual)));
            for(unsigned c=0;c<14;c++) {
                assert(a[c].asset==b[c].asset&&a[c].frame==b[c].frame&&a[c].fraction==b[c].fraction);
                a[c].step=b[c].step=random_u32()%262144;
            }
            checked+=frames;
        }
    }
    printf("Mixer PCM and voice state exactly match for %u stereo frames.\n",checked);
}
