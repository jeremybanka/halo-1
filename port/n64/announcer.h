#ifndef BG_ANNOUNCER_H
#define BG_ANNOUNCER_H
#include <stddef.h>
#include "asset_models.h"
#include "game_modes.h"
/* NULL selects the resident CE Slayer clip. Mode variants otherwise share
 * their engine's announcement, except Reach's SWAT / Slayer pair. */
static inline const char *bg_mode_announcement(unsigned mode) {
    if(mode==BG_MODE_SWAT || mode==BG_MODE_TEAM_SWAT)return "mode_swat.s8";
    const bg_mode_rules *r=bg_mode_preset(mode);
    static const char *const solo[]={NULL,"mode_capture_the_flag.s8","mode_oddball.s8","mode_king_of_the_hill.s8","mode_race.s8"};
    static const char *const team[]={"mode_team_slayer.s8","mode_capture_the_flag.s8","mode_team_oddball.s8","mode_team_king_of_the_hill.s8","mode_team_race.s8"};
    return (r->teams?team:solo)[r->engine];
}
/* Xbox CE game_engine.c: four or more kills use Killtacular, including
 * chains beyond four. Later games' additional tiers are not part of CE. */
static inline unsigned bg_multikill_sound(unsigned kills) {
    return kills >= 4 ? BG_S_KILLTACULAR : kills == 3 ? BG_S_TRIPLE_KILL
         : kills == 2 ? BG_S_DOUBLE_KILL : BG_S_COUNT;
}
#endif
