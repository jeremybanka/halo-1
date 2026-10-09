#include "render_animation.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
enum { TRACKS=123,VERTICES=735,PAIRS=(VERTICES+1)/2 };
typedef struct { int16_t posA[3];uint16_t normA;int16_t posB[3];uint16_t normB;
    uint32_t rgbaA,rgbaB;int16_t stA[2],stB[2]; } test_packed;
_Static_assert(sizeof(test_packed)==32&&offsetof(test_packed,posB)==8,"Tiny3D pair layout");
static uint32_t random_state=42;
static uint32_t random_value(void) { random_state=random_state*1664525+1013904223;return random_state; }
int main(void) {
    _Alignas(8) test_packed initial[PAIRS],expected[PAIRS],actual[PAIRS];
    bg_motion_track tracks[TRACKS];
    uint16_t indices[VERTICES];uint8_t a[TRACKS*3],b[TRACKS*3];
    const int16_t origin[3]={-16000,1234,-73};
    for(unsigned i=0;i<sizeof(initial);i++)((uint8_t*)initial)[i]=random_value()>>24;
    for(unsigned i=0;i<TRACKS*3;i++){a[i]=random_value()>>24;b[i]=random_value()>>24;}
    for(unsigned i=0;i<VERTICES;i++)indices[i]=random_value()%TRACKS;
    for(unsigned vertices=VERTICES-1;vertices<=VERTICES;vertices++)for(int f=0;f<=256;f++) {
        memcpy(expected,initial,sizeof(expected));memcpy(actual,initial,sizeof(actual));
        for(unsigned i=0;i<vertices;i++) {
            int16_t*position=i&1?expected[i/2].posB:expected[i/2].posA;
            for(unsigned axis=0;axis<3;axis++) {
                unsigned at=indices[i]*3+axis;
                position[axis]=origin[axis]+a[at]+((b[at]-a[at])*f)/256;
            }
        }
        bg_motion_decode(tracks,TRACKS,a,b,origin,f);
        bg_motion_scatter(actual,vertices,indices,tracks);
        assert(memcmp(expected,actual,sizeof(actual))==0);
    }
    puts("Aligned animation matches every byte of scalar output at257 blends, odd/even counts; normals/RGBA/UV/padding preserved");
    return 0;
}
