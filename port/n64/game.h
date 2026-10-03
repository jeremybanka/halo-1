#ifndef HALO_N64_GAME_H
#define HALO_N64_GAME_H
#include <stdbool.h>
#include "world.h"
#define BG_PLAYERS 4
typedef struct {
    float pos[3], yaw, pitch, vy, cooldown, reload, respawn, hurt, flash;
    int health, ammo, score;
    bool grounded;
} bg_player;
typedef struct { float forward, strafe, turn, look; bool jump, fire, reload; } bg_input;
extern bg_player bg_players[BG_PLAYERS];
void bg_reset(void);
void bg_set_players(unsigned count);
void bg_tick(const bg_input input[BG_PLAYERS], float dt);
float bg_floor(float x, float z, float ceiling);
float bg_raycast(const float origin[3], const float direction[3], float max_distance);
#endif
