#ifndef BG_SHIELDS_H
#define BG_SHIELDS_H
#include "game.h"
#include <math.h>
/* Xbox cyborg B_out: very_early(recent shield damage). Full and quietly
 * damaged shields, recharge, and resting overshields have no body modifier. */
static inline float bg_shield_glow(const bg_player*p){
    return p->shield_hit>0&&p->health>0&&p->shield>0?sqrtf(sqrtf(fmaxf(0,p->shield_hit))):0;
}
enum { BG_SHIELD_CHARGE=1, BG_SHIELD_LOW=2, BG_SHIELD_DOWN=4 };
static inline unsigned bg_shield_sounds(const bg_player*p){
    if(p->health<=0)return 0;
    return (p->shield_charging?BG_SHIELD_CHARGE:0)|
        (p->shield<=0?BG_SHIELD_DOWN:p->shield<25?BG_SHIELD_LOW:0);
}
#endif
