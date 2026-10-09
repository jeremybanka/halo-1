#ifndef BG_VEHICLE_PHYSICS_H
#define BG_VEHICLE_PHYSICS_H
#include "game.h"
/* All input/output use the demake's coordinates and seconds. The retained
 * solver operates exclusively in original Halo XYZ and 30 Hz tick units. */
/* Release match-only world geometry while the front end owns the heap. */
void bg_vehicle_world_release(void);
/* Shared original polygon/BVH ray service in demake coordinates. */
float bg_world_raycast(const float origin[3],const float direction[3],float distance);
float bg_world_raycast_normal(const float origin[3],const float direction[3],float distance,float normal[3]);
/* Five short camera rays share a single conservative surface query. */
void bg_world_camera_rays(const float origin[3],const float rays[5][3],const float reaches[5],float hits[5]);
void bg_vehicle_physics_prepare(void);
void bg_vehicle_physics_step(unsigned index,const bg_input *input);
bool bg_vehicle_airborne(unsigned index);
void bg_vehicle_physics_wreck(unsigned index);

void bg_vehicle_physics_explosion(unsigned index,const float origin[3],int projectile_kind);
void bg_vehicle_physics_flip(unsigned index,const float player_position[3]);
void bg_vehicle_transform(const bg_vehicle *vehicle,const float local[3],float out[3]);
#endif
