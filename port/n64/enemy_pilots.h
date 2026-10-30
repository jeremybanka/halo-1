#ifndef BG_ENEMY_PILOTS_H
#define BG_ENEMY_PILOTS_H
#include <math.h>
#include "pve.h"
#include "game.h"
#include "blam/vehicle_physics.h"
#include "render_bounds.h"
extern const bg_pve_animation bg_enemy_pilot_animations[BG_VEHICLE_COUNT][3][3];
extern const bg_pve_animation bg_enemy_pilot_hits[BG_VEHICLE_COUNT][3];
extern const bg_bounds bg_enemy_pilot_bounds[BG_VEHICLE_COUNT][3];
static inline unsigned bg_pilot_state(const bg_player*p){return p->seat_state==BG_SEAT_ENTERING?1:p->seat_state==BG_SEAT_EXITING?2:0;}
/* Same rigid basis for rendering and exact animated hit geometry. */
static inline void bg_pilot_basis(const bg_player*p,float basis[3][3]){
 const bg_vehicle*v=&bg_vehicles[p->vehicle];const bg_seat_definition*s=bg_player_seat(p);
 float yaw=s->yaw+(v->kind==BG_V_SHADE?v->turret_yaw:0),c=cosf(yaw),sn=sinf(yaw);
 for(unsigned axis=0;axis<3;axis++){
  float local[3]={0},world[3];local[axis]=1;float rotated[3]={c*local[0]+sn*local[2],local[1],-sn*local[0]+c*local[2]};
  bg_vehicle_transform(v,rotated,world);for(unsigned k=0;k<3;k++)basis[axis][k]=world[k]-v->pos[k];
 }
}
#endif
