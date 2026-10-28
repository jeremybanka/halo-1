#ifndef BG_ASSET_PVE_H
#define BG_ASSET_PVE_H
#include "asset_models.h"
#include "pve.h"
#define BG_PVE_SCALE 128.f
typedef struct { const uint16_t *positions,*indices; unsigned frames,vertices,tracks;float duration;int16_t origin[3]; } bg_pve_animation;
extern const bg_model_asset bg_pve_models[2][2];
extern const bg_pve_animation bg_pve_animations[2][2][PVE_CLIPS];
extern const bg_attachment_clip bg_pve_grips[2][PVE_CLIPS];
#endif
