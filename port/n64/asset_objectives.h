#ifndef BG_ASSET_OBJECTIVES_H
#define BG_ASSET_OBJECTIVES_H
#include "asset_firstperson.h"
/* Flag then skull. Source flag cloth is a two-triangle textured banner;
 * both colours share geometry and preserve the source attachment markers. */
extern const bg_model_asset bg_objective_models[2],bg_objective_fp_models[2];
extern const bg_anim_asset bg_objective_fp_animations[2][BG_FP_CLIPS];
extern const uint8_t *const bg_objective_fp_team_masks[2];
extern const uint16_t bg_flag_textures[2][2048];
#endif
