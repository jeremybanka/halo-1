#ifndef BG_VEHICLE_VISUALS_H
#define BG_VEHICLE_VISUALS_H
#include "asset_models.h"
/* Original ~damaged low permutations: Ghost, Banshee. */
extern const bg_model_asset bg_covenant_wrecks[2];
extern const bg_bounds bg_covenant_wreck_bounds[2];
enum {BG_VFX_FIRE,BG_VFX_SMOKE,BG_VFX_FLAME,BG_VFX_PANEL,BG_VFX_SPARK};
extern const uint32_t bg_vehicle_fx_textures[5][256];
#endif
