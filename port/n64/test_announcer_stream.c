#include <stdio.h>
#include <string.h>
#include "sound_stream.h"
#ifndef BG_TEST_PCM_BYTES
#define BG_TEST_PCM_BYTES 14048
#endif
static int8_t pcm[BG_TEST_PCM_BYTES],window[1024];
static unsigned maximum;
/* Simulate the aligned ROM read, including an unaligned file/sample start. */
static const int8_t *read_pcm(unsigned at,unsigned count) {
    unsigned prefix=(at+8)&15,span=(prefix+count+15)&~15u;
    assert(span<=sizeof(window)&&at+count<=sizeof(pcm));
    if(span>maximum)maximum=span;
    memcpy(window+prefix,pcm+at,count);
    return window+prefix;
}
int main(int argc,char **argv) {
    assert(argc==2);FILE *file=fopen(argv[1],"rb");assert(file);
    assert(fread(pcm,1,sizeof(pcm),file)==sizeof(pcm));fclose(file);
    bg_audio_asset source={pcm,sizeof(pcm),11025,false};
    int16_t resident[3600],streamed[3600];unsigned compared=0;
    for(unsigned step=32765;step<32780;step++)for(unsigned phase=0;phase<3;phase++) {
        bg_sound_voice a={&source,0,(uint32_t[]){0,49111,65535}[phase],step,80,80,false},b=a;
        bg_sound_stream stream={0};unsigned random=step+phase,iteration=0;
        while(a.asset) {
            if(iteration==5||iteration==20||iteration==30) {
                /* A new 4+ announcement replaces an unfinished voice. */
                a.frame=a.fraction=0;a.asset=&source;b=a;stream=(bg_sound_stream){0};
            }
            random=random*1664525u+1013904223u;unsigned frames=1+random%1800;
            assert(bg_sound_stream_refill(&stream,&b,&source,frames,read_pcm));
            bg_sound_mix(&a,1,resident,frames);bg_sound_mix(&b,1,streamed,frames);
            assert(!memcmp(resident,streamed,frames*4)&&a.fraction==b.fraction);
            assert(a.frame==stream.at+b.frame&&!!a.asset==!!b.asset);
            compared+=frames;iteration++;
        }
        assert(!bg_sound_stream_refill(&stream,&b,&source,880,read_pcm));
    }
    printf("PASS: %u streamed/resident stereo frames byte-identical, including phase, restart and completion; %u-byte maximum aligned window\n",compared,maximum);
}
