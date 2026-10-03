#ifndef BG_FIRSTPERSON_AMMO_LOGIC_H
#define BG_FIRSTPERSON_AMMO_LOGIC_H
#include <stdint.h>
#include <string.h>
#include "asset_fp_ammo.h"

static inline unsigned bg_fp_ammo_clamp(int value, unsigned maximum) {
    return value < 0 ? 0 : (unsigned)value > maximum ? maximum : (unsigned)value;
}

/* Original numeric shader: limit 60, ten bitmap frames, permutations 1/0. */
static inline void bg_ar_ammo_digits(int ammo, unsigned digits[2]) {
    unsigned count=bg_fp_ammo_clamp(ammo,60);
    digits[0]=count/10;digits[1]=count%10;
}

static inline void bg_ar_ammo_sample(int16_t positions[8][3],int16_t uv[8][2],
        unsigned clip,unsigned f0,unsigned f1,int fraction,int ammo) {
    if(clip>=4)clip=0;
    const bg_ar_ammo_clip*a=&bg_ar_ammo_clips[clip];
    if(f0>=a->frames)f0=a->frames-1;
    if(f1>=a->frames)f1=a->frames-1;
    fraction=(int)bg_fp_ammo_clamp(fraction,256);
    unsigned digits[2];bg_ar_ammo_digits(ammo,digits);
    for(unsigned i=0;i<8;i++) {
        for(unsigned axis=0;axis<3;axis++) {
            int x=a->positions[(f0*8+i)*3+axis],y=a->positions[(f1*8+i)*3+axis];
            positions[i][axis]=(int16_t)(x+(y-x)*fraction/256);
        }
        uv[i][0]=(int16_t)(bg_ar_ammo_uv[i*2]+digits[i/4]*10*32);
        uv[i][1]=bg_ar_ammo_uv[i*2+1];
    }
}

/* Original Needler reload starts regrowing at tick 44, settling over 5 ticks.
 * Caller normalizes demake reload time to the source animation duration.
 * reload_elapsed < 0 means normal loaded-rounds display. The port predicts
 * loaded+reserve, matching its actual completion rule; the Xbox expression
 * uses reserve-exclusive rounds_total instead. This is presentation only. */
static inline unsigned bg_needler_ammo_state(int ammo,int reserve,float reload_elapsed) {
    unsigned count=bg_fp_ammo_clamp(ammo,20);
    if(reload_elapsed>=44.0f/30.0f) {
        float fraction=(reload_elapsed*30.0f-44.0f)*.2f;
        if(fraction>1)fraction=1;
        unsigned predicted=bg_fp_ammo_clamp(ammo+(reserve>0?reserve:0),20);
        if(predicted>count)count+=(unsigned)((predicted-count)*fraction);
    }
    return count;
}

/* Tiny3D pair layout: position+normal at byte0/8, color and UV at16..31.
 * Only XYZ is written. RGB, normals, UV, indices and padding are preserved. */
static inline void bg_needler_ammo_sample(void*output,const bg_needler_ammo_asset*a,
        unsigned clip,unsigned f0,unsigned f1,int fraction,unsigned ammo) {
    if(clip>=4)clip=0;
    if(f0>=a->clip_frames[clip])f0=a->clip_frames[clip]-1;
    if(f1>=a->clip_frames[clip])f1=a->clip_frames[clip]-1;
    fraction=(int)bg_fp_ammo_clamp(fraction,256);if(ammo>20)ammo=20;
    f0+=a->clip_offsets[clip];f1+=a->clip_offsets[clip];
    const uint16_t*indices=a->indices+ammo*a->count;
    for(unsigned i=0;i<a->count;i++) {
        unsigned track=indices[i],vertex=a->vertices[i];
        const uint8_t*x=a->positions+(f0*a->tracks+track)*3;
        const uint8_t*y=a->positions+(f1*a->tracks+track)*3;
        int16_t p[3];
        for(unsigned c=0;c<3;c++)p[c]=(int16_t)(a->origin[c]+x[c]+((int)y[c]-x[c])*fraction/256);
        memcpy((uint8_t*)output+(vertex/2)*32+(vertex%2)*8,p,sizeof(p));
    }
}
#endif
