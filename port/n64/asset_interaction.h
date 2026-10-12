#ifndef BG_ASSET_INTERACTION_H
#define BG_ASSET_INTERACTION_H
#include "asset_models.h"
#include "interaction.h"
#include "interaction_poses.h"
void bg_interaction_render_init(void);
void bg_interaction_render_release(void);
void bg_interaction_pose(T3DVertPacked *out,const bg_rom_pose *pose,float seconds,bool loop);
void bg_interaction_pose_blend(T3DVertPacked*out,const bg_rom_pose*p,float seconds,bool loop,float weight);
void bg_interaction_points(int16_t (*out)[3],const bg_rom_pose *pose,float seconds);
void bg_interaction_needles(T3DVertPacked *out,unsigned ammo,float seconds);
#endif
