#ifndef BG_DAMAGE_INDICATOR_H
#define BG_DAMAGE_INDICATOR_H
#include <math.h>
/* Camera-relative quadrants in the port's Y-up coordinates. Source HUD
 * order and 1..29/30-second lifetime are retained. Latch direction at impact. */
static inline void bg_damage_indicator_hit(float timers[4],float yaw,float pitch,
                                           const float delta[3]) {
    float cy=cosf(yaw),sy=sinf(yaw),cp=cosf(pitch),sp=sinf(pitch);
    float forward=delta[0]*cy*cp+delta[1]*sp-delta[2]*sy*cp;
    float right=delta[0]*sy+delta[2]*cy;
    float up=-delta[0]*cy*sp+delta[1]*cp+delta[2]*sy*sp;
    float length=sqrtf(forward*forward+right*right+up*up);
    if(length<.0001f)return;
    if(fabsf(up)>length*.5f)timers[up>0?0:2]=29.f/30.f;
    if(fabsf(forward)>=fabsf(right))timers[forward>=0?0:2]=29.f/30.f;
    else timers[right>0?3:1]=29.f/30.f;
}
#endif
