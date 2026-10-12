#ifndef BG_ANNOUNCER_H
#define BG_ANNOUNCER_H
#include "asset_models.h"
/* Xbox CE game_engine.c: four or more kills use Killtacular, including
 * chains beyond four. Later games' additional tiers are not part of CE. */
static inline unsigned bg_multikill_sound(unsigned kills) {
    return kills >= 4 ? BG_S_KILLTACULAR : kills == 3 ? BG_S_TRIPLE_KILL
         : kills == 2 ? BG_S_DOUBLE_KILL : BG_S_COUNT;
}
#endif
