#ifndef BG_RENDER_ANIMATION_H
#define BG_RENDER_ANIMATION_H
#include <stdint.h>

/* Eight-byte alignment lets VR4300 scatter an XYZ position with one LD/SD.
 * The fourth halfword overlaps Tiny3D's normal and is preserved on output. */
typedef union { int16_t xyz[4]; uint64_t word; } bg_motion_track;
typedef uint64_t bg_motion_word __attribute__((__may_alias__));

static inline void bg_motion_decode(bg_motion_track*output,unsigned count,
        const uint8_t*frame0,const uint8_t*frame1,const int16_t origin[3],int fraction) {
    const int ox=origin[0],oy=origin[1],oz=origin[2];
    for(unsigned i=0;i<count;i++,frame0+=3,frame1+=3) {
        int x=frame0[0],y=frame0[1],z=frame0[2];
        output[i].xyz[0]=ox+x+((frame1[0]-x)*fraction)/256;
        output[i].xyz[1]=oy+y+((frame1[1]-y)*fraction)/256;
        output[i].xyz[2]=oz+z+((frame1[2]-z)*fraction)/256;
        output[i].xyz[3]=0;
    }
}
static inline void bg_motion_write(bg_motion_word*output,uint64_t position) {
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    const uint64_t normal_mask=UINT64_C(0xffff);
#else
    const uint64_t normal_mask=UINT64_C(0xffff000000000000);
#endif
    *output=(position&~normal_mask)|(*output&normal_mask);
}
/* Tiny3D packs a vertex pair into 32 bytes: XYZ+normal at offsets 0 and 8,
 * followed by their RGBA/UV fields. output must be eight-byte aligned. */
static inline void bg_motion_scatter(void*output,unsigned vertices,
        const uint16_t*indices,const bg_motion_track*tracks) {
    bg_motion_word*packed=output;
    unsigned pairs=vertices/2;
    for(unsigned i=0;i<pairs;i++,indices+=2,packed+=4) {
        bg_motion_write(packed,tracks[indices[0]].word);
        bg_motion_write(packed+1,tracks[indices[1]].word);
    }
    if(vertices&1)bg_motion_write(packed,tracks[indices[0]].word);
}
#endif
