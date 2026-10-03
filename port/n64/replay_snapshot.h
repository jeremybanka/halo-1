#ifndef BG_REPLAY_SNAPSHOT_H
#define BG_REPLAY_SNAPSHOT_H
#include "replay.h"
#include "blam/runtime.h"

/* QA-only advance: identical ordering and cumulative float time to one
 * ordinary replay tick. The caller applies presentation effects immediately
 * afterward, while this tick's events are still available. */
static inline void bg_replay_snapshot_tick(float*game_time){
    bg_input in[BG_PLAYERS]={0};
    bg_replay_input(in,*game_time);bg_set_players(4);
    bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);
    *game_time+=BLAM_TICK_SECONDS;
}
#endif
