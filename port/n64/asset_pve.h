#ifndef BG_ASSET_PVE_H
#define BG_ASSET_PVE_H
#include "asset_models.h"
#include "pve.h"
#define BG_PVE_SCALE 128.f
extern const bg_model_asset bg_pve_models[BG_PVE_MODELS][2];
extern const bg_pve_animation bg_pve_animations[BG_PVE_MODELS][2][PVE_CLIPS];
extern const bg_attachment_clip bg_pve_grips[BG_PVE_MODELS][PVE_CLIPS];
extern const uint8_t *const bg_pve_shield_vertices[2];
extern const float bg_spirit_seats[8][3];
#endif
