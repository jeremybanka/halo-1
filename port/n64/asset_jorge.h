#ifndef BG_ASSET_JORGE_H
#define BG_ASSET_JORGE_H
#include "asset_models.h"
#include "character.h"
#define BG_JORGE_SCALE 512.0f
enum { BG_J_READY = BG_A_COUNT, BG_J_LOCOMOTION, BG_J_SEATS = BG_J_LOCOMOTION + 6,
       BG_J_CLIP_COUNT = BG_J_SEATS + 7 * 3 };
typedef struct {
    uint32_t bytes, indices_offset, batches_offset;
    uint16_t vertices, batches, triangles;
    float radius;
} bg_jorge_mesh_info;
typedef struct {
    uint32_t offset, stride;
    uint16_t frames;
    float duration;
    bg_bounds bounds, grip_bounds;
} bg_jorge_clip;
extern const bg_jorge_mesh_info bg_jorge_mesh;
extern const bg_jorge_clip bg_jorge_clips[BG_J_CLIP_COUNT];
extern const uint16_t bg_jorge_portrait[32 * 40];
extern bg_model_asset bg_jorge_model;
extern const uint8_t bg_jorge_leg_batches[];
extern const unsigned bg_jorge_leg_triangles;
/* Optional bank lives in ROM. Only the mesh and two endpoints are resident.
 * Jorge deliberately uses this mesh at both distances until his LOD pass. */
bool bg_jorge_load(void);
void bg_jorge_release(void);
void bg_jorge_pose(T3DVertPacked *out, unsigned clip, float seconds, bool loop,
                   float blend, bg_attachment_pose *hand);
#endif
