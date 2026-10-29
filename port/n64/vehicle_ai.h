#ifndef BG_VEHICLE_AI_H
#define BG_VEHICLE_AI_H
#include <stdbool.h>
#include <math.h>
#include "vehicle_kinds.h"
typedef struct {
    float sideslip,destination,avoidance,radius,repeat,abort_range,oversteer[2],steering,throttle;
    float speed,acceleration,begin_angle,fixed_pitch,health;
    float range,rate,error,leading,damage,desired[2],first_delay[2],burst[2],pause[2];
    float new_target_time,new_target[4],special_delay,special_chance,superballistic;
    unsigned flags,special_mode;
} bg_vehicle_ai_definition;
extern const bg_vehicle_ai_definition bg_vehicle_ai_defs[BG_VEHICLE_COUNT];
extern const float bg_vehicle_muzzles[BG_VEHICLE_COUNT][3];
extern const unsigned bg_vehicle_muzzle_parts[BG_VEHICLE_COUNT];
/* CE coordinates: X forward, Y left, Z up. Per-actor state stays with pilot. */
void bg_vehicle_ai_movement(unsigned kind,const float facing[3],const float aim[3],
    const float desired[3],float speed,bool keep_moving,float *oversteer,
    float out_facing[3],float out_throttle[3]);
#endif
