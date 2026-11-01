#ifndef BG_ASSET_ODST_H
#define BG_ASSET_ODST_H
#include "asset_jorge.h" /* Shared streamed-mesh metadata and gameplay clip order. */
#define BG_ODST_SCALE 512.0f
extern const bg_jorge_mesh_info bg_odst_meshes[2];
extern const bg_jorge_clip bg_odst_clips[BG_J_CLIP_COUNT], bg_odst_lod_clips[BG_J_CLIP_COUNT];
extern const uint16_t *const bg_odst_tracks[2];
extern const uint8_t *const bg_odst_team_masks[2];
extern const unsigned bg_odst_track_counts[2];
extern const uint16_t bg_odst_portraits[4][32*40];
extern bg_model_asset bg_odst_model, bg_odst_lod_model;
bool bg_odst_load(void);
void bg_odst_release(void);
void bg_odst_pose(T3DVertPacked *out, unsigned lod, unsigned clip, float seconds, bool loop,
                  float blend, bg_attachment_pose *hand);
#endif
