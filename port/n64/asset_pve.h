#ifndef BG_ASSET_PVE_H
#define BG_ASSET_PVE_H
#include "asset_models.h"
#include "pve.h"
#define BG_PVE_SCALE 128.f
#ifdef BG_PVE_CRUNCH
#define BG_PVE_LODS 3
extern const bg_bounds bg_pve_crunch_bounds[BG_PVE_KINDS][PVE_CLIPS];
#else
#define BG_PVE_LODS 2
#endif
extern const bg_model_asset bg_pve_models[BG_PVE_MODELS][BG_PVE_LODS];
extern const bg_pve_animation bg_pve_animations[BG_PVE_MODELS][BG_PVE_LODS][PVE_CLIPS];
extern const bg_attachment_clip bg_pve_grips[BG_PVE_MODELS][PVE_CLIPS];
extern const uint8_t *const bg_pve_shield_vertices[BG_PVE_LODS];
extern const uint8_t *const bg_pve_batch_modes[BG_PVE_MODELS][BG_PVE_LODS];
extern const float bg_spirit_seats[8][3];
#ifdef BG_PVE_ROSTER
#include "pve_roster.h"
extern const uint32_t *const bg_pve_variant_colors[PVE_R_COUNT][BG_PVE_LODS];
extern const bg_model_asset bg_pve_roster_weapons[2];
#endif
#endif
