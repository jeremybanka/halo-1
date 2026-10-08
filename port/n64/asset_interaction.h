#ifndef BG_ASSET_INTERACTION_H
#define BG_ASSET_INTERACTION_H
#include "asset_models.h"
#include "interaction.h"
/* Frames are read from DragonFS, never copied wholesale into RDRAM. Each
 * frame is padded to 16 bytes and contains big-endian XYZ int16 positions. */
typedef struct {
    uint32_t offset,stride;
    uint16_t vertices,frames;
    float duration;
    bg_bounds bounds;
} bg_rom_pose;
extern const bg_rom_pose bg_locomotion_poses[6][2],bg_locomotion_grips[6];
extern const bg_rom_pose bg_seat_poses[][3][2];
extern const bg_rom_pose bg_body_ready_poses[2],bg_body_ready_grip;
extern const bg_rom_pose bg_seat_grips[],bg_hatch_poses[2][2];
extern const bg_rom_pose bg_ready_poses[9],bg_ready_ar_digits,bg_ready_scope,bg_ready_needles[21];
extern const uint16_t bg_ready_needle_vertices[];
extern const unsigned bg_interaction_scratch_bytes;
void bg_interaction_render_init(void);
void bg_interaction_render_release(void);
void bg_interaction_pose(T3DVertPacked *out,const bg_rom_pose *pose,float seconds,bool loop);
void bg_interaction_pose_blend(T3DVertPacked*out,const bg_rom_pose*p,float seconds,bool loop,float weight);
void bg_interaction_points(int16_t (*out)[3],const bg_rom_pose *pose,float seconds);
void bg_interaction_needles(T3DVertPacked *out,unsigned ammo,float seconds);
#endif
