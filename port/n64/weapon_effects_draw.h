#ifndef BG_WEAPON_EFFECTS_DRAW_H
#define BG_WEAPON_EFFECTS_DRAW_H
#include <t3d/t3d.h>
void bg_fx_draw_init(void);
void bg_fx_draw_begin(unsigned slot,unsigned view,const T3DViewport*vp,const T3DVec3*eye);
void bg_fx_pose(unsigned player,unsigned weapon,unsigned clip,unsigned f0,unsigned f1,int fraction);
unsigned bg_fx_draw_weapon(unsigned player,const T3DMat4FP*matrix,float units,bool firstperson,float time);
unsigned bg_fx_draw_blasts(void);
unsigned bg_fx_draw_trails(float time);
unsigned bg_fx_draw_vehicle_destruction(void);
unsigned bg_fx_draw_shield_breaks(unsigned viewer);
void bg_fx_muzzle_pose(unsigned player,const int16_t points[2][3]);
void bg_fx_vent_pose(unsigned player,const int16_t points[3][3]);
#endif
