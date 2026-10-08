#ifndef BG_MOVEMENT_H
#define BG_MOVEMENT_H
#include "game.h"
typedef struct {
    float run[3],sneak[3],accel[3],jump,gravity,crouch_rate,camera[2];
    float curve[6],yaw_rate,pitch_rate,peg_time,peg_scale,peg_threshold;
    float friction,adhesion,aim_width,height[2];
    float radius,slope[7],landing[5];
} bg_movement_config;
typedef struct {float auto_angle,auto_range,mag_angle,mag_range,deviation;bool zoom_only;} bg_aim_config;
extern const bg_movement_config bg_movement;
extern const bg_aim_config bg_aim_configs[BG_WEAPON_COUNT];
typedef struct {int player;float point[3],distance,auto_level,mag_level;} bg_aim_target;
bg_aim_target bg_aim_query(unsigned player);
float bg_aim_attenuation(float value,float maximum);
float bg_look_curve(float value);
void bg_start_landing(bg_player*p,float speed);
float bg_body_height(const bg_player*p);
void bg_walk_velocity(bg_player*p,float forward,float strafe,float dt);
void bg_look_input(bg_player*p,const bg_input*in,float magnification,float dt,float *yaw,float *pitch);
static inline float bg_eye_height(const bg_player*p){return bg_movement.camera[0]+(bg_movement.camera[1]-bg_movement.camera[0])*p->crouch_amount;}
#endif
