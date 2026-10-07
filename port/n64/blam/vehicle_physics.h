#ifndef BG_VEHICLE_PHYSICS_H
#define BG_VEHICLE_PHYSICS_H
#include "game.h"
/* All input/output use the demake's coordinates and seconds. The retained
 * solver operates exclusively in original Halo XYZ and 30 Hz tick units. */
/* Release match-only world geometry while the front end owns the heap. */
void bg_vehicle_world_release(void);
void bg_vehicle_physics_prepare(void);
void bg_vehicle_physics_step(unsigned index,const bg_input *input);

void bg_vehicle_physics_explosion(unsigned index,const float origin[3],int projectile_kind);
void bg_vehicle_physics_flip(unsigned index,const float player_position[3]);
void bg_vehicle_transform(const bg_vehicle *vehicle,const float local[3],float out[3]);
#endif
