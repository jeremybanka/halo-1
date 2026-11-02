#ifndef BG_GUNGNIR_H
#define BG_GUNGNIR_H
#include "movement.h"
enum { BG_AUTOPILOT_ELITE, BG_AUTOPILOT_FOLLOW, BG_AUTOPILOT_PANIC };
/* Normalized radius relative to the viewport's shorter dimension. Shared by
 * target selection and HUD drawing, including the wide third viewport. */
#define BG_GUNGNIR_RADIUS .28f
bool bg_gungnir_aim_active(const bg_player *player);
bg_aim_target bg_gungnir_target(unsigned player);
void bg_gungnir_weapon_angles(unsigned player,float *yaw,float *pitch);
void bg_gungnir_reset(unsigned player);
void bg_gungnir_toggle(unsigned player);
void bg_gungnir_move(unsigned player,bg_input *movement,float dt);
const char *bg_gungnir_status(unsigned player);
#endif
