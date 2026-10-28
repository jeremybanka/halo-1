#ifndef BG_PLAYER_ANIMATION_H
#define BG_PLAYER_ANIMATION_H
#include <math.h>
#include "game.h"
/* Authored stand rifle ar fire-1 overlay: five source frames at 30 Hz.
 * Render and hit poses share the simulation shot age, not presentation time. */
#define BG_BODY_FIRE_FRAMES 5
static inline bool bg_player_body_firing(const bg_player *p) {
    return p->health > 0 && p->vehicle < 0 && p->grounded && p->weapon_ready <= 0 &&
        p->melee_time <= 0 && p->reload <= 0 && p->grenade_cooldown <= .55f &&
        p->landing_time <= 0 && p->fire_ticks[p->slot] < BG_BODY_FIRE_FRAMES;
}
static inline float bg_player_body_fire_frame(const bg_player *p) {
    return p->fire_ticks[p->slot] * ((BG_BODY_FIRE_FRAMES - 1.f) / BG_BODY_FIRE_FRAMES);
}
#endif
