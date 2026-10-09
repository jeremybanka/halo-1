#ifndef BG_CAMOUFLAGE_H
#define BG_CAMOUFLAGE_H
#include "game.h"
#include <math.h>
/* Deliberate demake timing, not Xbox's per-weapon ding/regrowth constants.
 * Actual shots reveal over one second; three quiet seconds start a one-second
 * fade out. No distortion pass or extra skinned shell is needed. */
static inline float bg_player_visibility(const bg_player*p){
    return p->health<=0||p->invisibility<=0?1:fmaxf(p->camo_opacity,1-p->invisibility);
}
static inline void bg_camo_reveal(bg_player*p){
    if(p->invisibility>0&&p->health>0)p->camo_quiet=3;
}
static inline void bg_camo_tick(bg_player*p,float dt){
    if(p->invisibility<=0){p->camo_quiet=p->camo_opacity=0;return;}
    p->camo_opacity=fmaxf(0,fminf(1,p->camo_opacity+(p->camo_quiet>0?dt:-dt)));
    p->camo_quiet=fmaxf(0,p->camo_quiet-dt);
    p->invisibility=fmaxf(0,p->invisibility-dt);
}
/* CE multiplayer camouflage does not suppress the motion sensor. Crouching
 * suppresses movement, but not firing/throwing. Vehicle movement uses the
 * hull's velocity rather than the stale pre-boarding biped velocity. */
static inline bool bg_motion_sensor_visible(const bg_player*p){
    if(p->health<=0)return false;
    if(p->fire_held||p->flash>0||p->grenade_cooldown>.7f)return true;
    if(p->crouched&&p->vehicle<0)return false;
    const float*v=p->vehicle>=0?bg_vehicles[p->vehicle].velocity:p->velocity;
    return v[0]*v[0]+v[1]*v[1]+v[2]*v[2]>=.01f;
}
#endif
