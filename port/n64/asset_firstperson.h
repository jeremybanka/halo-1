#ifndef BG_ASSET_FIRSTPERSON_H
#define BG_ASSET_FIRSTPERSON_H
#include "asset_models.h"
#define BG_FP_WEAPONS 9
extern const unsigned bg_fp_max_vertices;
extern const uint16_t bg_fp_pistol_texture[2048];
#define BG_FP_SCALE 256.0f
enum { BG_FP_IDLE, BG_FP_FIRE, BG_FP_RELOAD, BG_FP_MELEE, BG_FP_CLIPS };
/* Gun and hands are already posed in camera space, +X forward and +Y up.
 * Place at the eye, rotate by yaw/pitch; do not add a held-gun offset.
 * Mesh/animation positions use BG_FP_SCALE units per Halo unit: multiply
 * their model matrix scale by BG_SCALE/BG_FP_SCALE (0.125). */
extern const bg_model_asset bg_fp_models[BG_FP_WEAPONS];
extern const uint8_t *const bg_fp_team_masks[BG_FP_WEAPONS];
extern const bg_anim_asset bg_fp_animations[BG_FP_WEAPONS][BG_FP_CLIPS];
/* Tiny high-precision displays reuse the sniper's twelve-vertex workspace. */
typedef struct {
 const int16_t (*poses)[3];
 const uint16_t *offsets;
 const uint32_t *colors;
 const uint8_t *indices;
 uint8_t vertices,triangles;
} bg_fp_detail_asset;
extern const bg_fp_detail_asset bg_fp_details[BG_FP_WEAPONS];
#endif
