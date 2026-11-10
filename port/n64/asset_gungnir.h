#ifndef BG_ASSET_GUNGNIR_H
#define BG_ASSET_GUNGNIR_H
#include "asset_jorge.h" /* Shared streamed-mesh metadata and gameplay clip order. */
#define BG_GUNGNIR_SCALE 512.0f
extern const bg_jorge_mesh_info bg_gungnir_meshes[2];
extern const bg_jorge_clip bg_gungnir_clips[BG_J_CLIP_COUNT], bg_gungnir_lod_clips[BG_J_CLIP_COUNT];
extern const uint16_t *const bg_gungnir_tracks[2];
extern const uint8_t *const bg_gungnir_team_masks[2];
extern const unsigned bg_gungnir_track_counts[2];
extern const uint16_t bg_gungnir_portraits[4][32*40];
extern bg_model_asset bg_gungnir_model, bg_gungnir_lod_model;
bool bg_gungnir_load(void);
void bg_gungnir_release(void);
void bg_gungnir_pose(T3DVertPacked *out, unsigned lod, unsigned clip, float seconds, bool loop,
                  float blend, bg_attachment_pose *hand);
#endif
