#ifndef BG_ASSET_OBJECTIVES_H
#define BG_ASSET_OBJECTIVES_H
#include "asset_firstperson.h"
#include "flag_cloth.h"
/* Flag then skull. Cloth is a separate dynamic grid with source markers. */
extern const bg_model_asset bg_objective_models[2],bg_objective_fp_models[2];
extern const bg_anim_asset bg_objective_fp_animations[2][BG_FP_CLIPS];
/* The close grip needs finer coordinates than the byte-packed gun bank.
 * Flag metadata has a NULL byte stream; these 16-bit offset tracks supply it. */
#define BG_FLAG_FP_SCALE 4096.0f
extern const uint16_t *const bg_flag_fp_positions[BG_FP_CLIPS];
extern const float bg_flag_world_corners[3][3],bg_flag_wind_noise[3][64][3];
extern const int16_t (*const bg_flag_fp_corners[BG_FP_CLIPS])[3][3];
extern const bg_cloth_physics bg_flag_cloth_physics;
extern const bg_cloth_weather bg_flag_weather[13];
extern const uint8_t *const bg_objective_fp_team_masks[2];
extern const uint16_t bg_flag_textures[2][2048];
#endif
