#ifndef BG_PVE_PREPARE_MATH_H
#define BG_PVE_PREPARE_MATH_H
#include "render_animation.h"
/* NPCs historically round negative deltas down with >>8. The Spartan decoder
 * divides by 256 (toward zero), so reusing it would change authored positions. */
static inline void bg_pve_motion_decode(bg_motion_track*out,unsigned count,
        const uint16_t*a,const uint16_t*b,const int16_t origin[3],int mix){
    const int ox=origin[0],oy=origin[1],oz=origin[2];
    for(unsigned t=0;t<count;t++,a+=3,b+=3){
        int x=a[0],y=a[1],z=a[2];
        out[t].xyz[0]=ox+x+(((int)b[0]-x)*mix>>8);
        out[t].xyz[1]=oy+y+(((int)b[1]-y)*mix>>8);
        out[t].xyz[2]=oz+z+(((int)b[2]-z)*mix>>8);
        out[t].xyz[3]=0;
    }
}
#endif
