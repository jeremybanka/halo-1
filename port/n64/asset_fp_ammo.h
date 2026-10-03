#ifndef BG_ASSET_FP_AMMO_H
#define BG_ASSET_FP_AMMO_H
#include <stdint.h>
#define BG_AR_AMMO_VERTICES 8
#define BG_AR_AMMO_SCALE 4096.0f
#define BG_AR_AMMO_TEXTURE_WIDTH 100
#define BG_AR_AMMO_TEXTURE_HEIGHT 16
typedef struct { const int16_t *positions; uint16_t frames; } bg_ar_ammo_clip;
extern const bg_ar_ammo_clip bg_ar_ammo_clips[4];
extern const int16_t bg_ar_ammo_uv[];
extern const uint16_t bg_ar_ammo_texture[];
/* Native ammo index 0..20, then the affected packed-vertex index. Position
 * tracks share complete trajectories across all four base animation clips. */
typedef struct {
    const uint8_t *positions;
    const uint16_t *indices, *vertices;
    uint16_t tracks, count, base_vertices;
    int16_t origin[3];
    uint8_t clip_offsets[4], clip_frames[4];
} bg_needler_ammo_asset;
extern const bg_needler_ammo_asset bg_needler_ammo;
#endif
