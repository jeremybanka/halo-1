#ifndef BG_TERRAIN_H
#define BG_TERRAIN_H
#include "game.h"
/* Exact closest points between the capsule axis and triangle, used by
 * narrow-phase contacts and clearance. Returns squared separation. */
float bg_capsule_triangle(const float base[3],float height,float radius,const bg_triangle*t,float axis[3],float surface[3]);
void bg_terrain_reset(void);
bool bg_terrain_clearance(const bg_player*p);
bool bg_can_stand(const bg_player*p);
float bg_move_capsule(bg_player*p,float dt);
#endif
