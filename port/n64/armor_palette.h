#ifndef BG_ARMOR_PALETTE_H
#define BG_ARMOR_PALETTE_H
#include "character.h"
#include <stdint.h>
enum { BG_JORGE_KEEP, BG_JORGE_PLATE, BG_JORGE_PACK, BG_JORGE_SECONDARY, BG_JORGE_ACCENT,
       BG_JORGE_CHEST, BG_JORGE_SHOULDER, BG_JORGE_DARK = 16 };
/* Component hues retain baked shading. The dark flag shades calves, feet and
 * rear codpiece vertices by 20%, including the otherwise original green suit. */
static inline uint32_t bg_jorge_palette_color(uint32_t rgba, unsigned profile, unsigned mask) {
    unsigned kind=mask&15;
    if (!kind || profile >= BG_PROFILE_COUNT) return rgba;
    static const unsigned colors[3][5][3] = {
        {{225,45,38}, {169,43,68}, {226,80,49}, {235,110,32}, {71,152,57}},
        {{39,92,215}, {32,124,190}, {84,77,190}, {165,60,210}, {235,110,32}},
        {{215,179,44}, {198,140,50}, {225,200,85}, {71,152,57}, {165,60,210}}
    };
    unsigned rgb[3] = {rgba>>24, (rgba>>16)&255, (rgba>>8)&255};
    unsigned shade=rgb[0]>rgb[1]?rgb[0]:rgb[1];
    if (rgb[2]>shade) shade=rgb[2];
    uint32_t result=rgba&255;
    if (kind==BG_JORGE_PACK) {
        unsigned gray=(rgb[0]*54+rgb[1]*183+rgb[2]*19+128)/256;
        return (gray<<24)|(gray<<16)|(gray<<8)|result;
    }
    unsigned plate=kind==BG_JORGE_SECONDARY?1:kind==BG_JORGE_ACCENT?2:
                   kind==BG_JORGE_CHEST?3:kind==BG_JORGE_SHOULDER?4:0;
    for (unsigned c=0;c<3;c++) {
        unsigned value=profile==BG_PROFILE_GREEN?rgb[c]:(shade*(64+3*colors[profile][plate][c]/4)+127)/255;
        if (mask&BG_JORGE_DARK) value=value*4/5;
        result |= value << (24-8*c);
    }
    return result;
}
#endif
