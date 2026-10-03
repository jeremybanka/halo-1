#ifndef HALO_N64_REPLAY_H
#define HALO_N64_REPLAY_H
#include "game.h"
/* Deterministic, explicitly staged recording mode. Call immediately before each
 * simulation tick with monotonically increasing game time in seconds. */
void bg_replay_input(bg_input input[BG_PLAYERS],float time);
#endif
