#ifndef BG_VISR_H
#define BG_VISR_H
#include "game.h"
/* The ordinary flashlight control toggles VISR only for an ODST wearer. */
static inline bool bg_visr_active(const bg_player *p) {
    return p->health > 0 && p->flashlight_on && (bg_armor_def(p->armor)->abilities & BG_ARMOR_VISR);
}
static inline bool bg_visr_enemy(unsigned viewer, unsigned target) {
    return target < bg_unit_count() && viewer != target && bg_players[target].health > 0 &&
           !bg_players_allied(viewer, target);
}
static inline bool bg_visr_any(unsigned views) {
    for (unsigned p=0;p<views;p++) if (bg_visr_active(&bg_players[p])) return true;
    return false;
}
#endif
