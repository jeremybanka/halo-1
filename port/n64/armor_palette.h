#ifndef BG_ARMOR_PALETTE_H
#define BG_ARMOR_PALETTE_H
#include "character.h"
#include <stdint.h>
enum { BG_JORGE_KEEP, BG_JORGE_PLATE, BG_JORGE_PACK, BG_JORGE_SECONDARY, BG_JORGE_ACCENT };
/* Components share nearby palette hues, while retaining their baked shading.
 * Green keeps the accepted plates; every profile gets the same matte gray bag. */
static inline uint32_t bg_jorge_palette_color(uint32_t rgba, unsigned profile, unsigned mask) {
    if (!mask || profile >= BG_PROFILE_COUNT) return rgba;
    static const unsigned colors[3][3][3] = {
        {{225,45,38}, {169,43,68}, {226,80,49}},
        {{39,92,215}, {32,124,190}, {84,77,190}},
        {{215,179,44}, {198,140,50}, {225,200,85}}
    };
    unsigned rgb[3] = {rgba>>24, (rgba>>16)&255, (rgba>>8)&255};
    unsigned shade=rgb[0]>rgb[1]?rgb[0]:rgb[1];
    if (rgb[2]>shade) shade=rgb[2];
    uint32_t result=rgba&255;
    if (mask==BG_JORGE_PACK) {
        unsigned gray=(rgb[0]*54+rgb[1]*183+rgb[2]*19+128)/256;
        return (gray<<24)|(gray<<16)|(gray<<8)|result;
    }
    if (profile==BG_PROFILE_GREEN) return rgba;
    unsigned plate=mask==BG_JORGE_SECONDARY?1:mask==BG_JORGE_ACCENT?2:0;
    for (unsigned c=0;c<3;c++)
        result |= ((shade*(64+3*colors[profile][plate][c]/4)+127)/255) << (24-8*c);
    return result;
}
#endif
