#ifndef HALO_N64_SHOWCASE_H
#define HALO_N64_SHOWCASE_H
#include "game.h"
typedef enum {
    BG_SHOWCASE_BANSHEE, BG_SHOWCASE_FRAG_DOUBLE_KILL, BG_SHOWCASE_WARTHOG_PASSENGER,
    BG_SHOWCASE_SHOTGUN_KILL, BG_SHOWCASE_NEEDLER_SUPERCOMBINE, BG_SHOWCASE_NEEDLER_HOMING,
    BG_SHOWCASE_COUNT
} bg_showcase_kind;
typedef struct {
    unsigned shots,kills,grenades,boardings,supercombines,needle_hits,double_kills;
    unsigned driver_frames,passenger_frames,airborne_frames;
    float traveled,maximum_altitude,maximum_homing_turn;
    bool passed;
} bg_showcase_stats;
/* Begin once, call input immediately before each real 30 Hz bg_tick, and
 * observe immediately afterward before clearing the game's event buffer. */
void bg_showcase_begin(bg_showcase_kind scenario);
void bg_showcase_input(bg_input input[BG_PLAYERS],float seconds);
void bg_showcase_observe(void);
unsigned bg_showcase_views(void);
float bg_showcase_duration(void);
const char *bg_showcase_title(void);
const char *bg_showcase_caption(void);
const bg_showcase_stats *bg_showcase_telemetry(void);
#endif
