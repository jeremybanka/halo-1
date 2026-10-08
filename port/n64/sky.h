#ifndef BG_SKY_H
#define BG_SKY_H
#include <math.h>
#include <stdint.h>

extern const uint8_t bg_sky_rgb[33][3];

/* Reconstruct a world-space sky ray from the production projection, including
 * the Xbox reticle offset and zoom. Translation cannot affect the sky. */
static inline void bg_sky_color(const float camera[4][4],const float projection[4][4],
    float ndc_x,float ndc_y,float rgb[3])
{
    float x=(ndc_x+projection[2][0])/projection[0][0];
    float y=(ndc_y+projection[2][1])/projection[1][1];
    float up=(camera[1][0]*x+camera[1][1]*y-camera[1][2])/sqrtf(x*x+y*y+1);
    float sample=fmaxf(0,fminf(1,up))*32;
    unsigned lo=(unsigned)sample,hi=lo<32?lo+1:lo;float f=sample-lo;
    for(unsigned c=0;c<3;c++)rgb[c]=(bg_sky_rgb[lo][c]*(1-f)+bg_sky_rgb[hi][c]*f)/255.f;
}
#endif
