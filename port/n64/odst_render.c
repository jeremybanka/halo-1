#include "asset_odst.h"
#include "blam/runtime.h"
#include <libdragon.h>
#include <malloc.h>
#include <math.h>
#include <string.h>
bg_model_asset bg_odst_model, bg_odst_lod_model;
static uint8_t *mesh, *scratch;
static uint32_t rom, rom_bytes, cached_offset = UINT32_MAX;
static void read_bank(void *out, unsigned offset, unsigned bytes) {
    assertf(offset <= rom_bytes && bytes <= rom_bytes - offset, "ODST bank bounds");
    data_cache_hit_invalidate(out, bytes);
    dma_read(out, rom + offset, bytes);
}
bool bg_odst_load(void) {
    if (mesh) return false;
    rom = dfs_rom_addr("odst.bin"); rom_bytes = dfs_rom_size("odst.bin");
    assertf(rom && rom_bytes, "Missing ODST bank");
    mesh = memalign(16, bg_odst_meshes[0].bytes + bg_odst_meshes[1].bytes);
    unsigned stride = bg_odst_clips[0].stride;
    if (bg_odst_lod_clips[0].stride > stride) stride = bg_odst_lod_clips[0].stride;
    scratch = memalign(16, stride * 2);
    assertf(mesh && scratch, "ODST workspace allocation");
    for (unsigned lod = 0; lod < 2; lod++) {
        const bg_jorge_mesh_info *info = &bg_odst_meshes[lod];
        uint8_t *data = mesh + (lod ? bg_odst_meshes[0].bytes : 0);
        read_bank(data, info->offset, info->bytes);
        bg_model_asset *model = lod ? &bg_odst_lod_model : &bg_odst_model;
        *model = (bg_model_asset){(T3DVertPacked *)data, info->vertices, info->radius,
            (bg_mesh_batch *)(data + info->batches_offset),
            (int16_t *)(data + info->indices_offset), info->batches, info->triangles};
    }
    cached_offset = UINT32_MAX;
    return true;
}
void bg_odst_release(void) {
    free(mesh); free(scratch); mesh = scratch = NULL;
    memset(&bg_odst_model, 0, sizeof(bg_odst_model)); cached_offset = UINT32_MAX;
    memset(&bg_odst_lod_model, 0, sizeof(bg_odst_lod_model));
}
void bg_odst_pose(T3DVertPacked *out, unsigned lod, unsigned clip, float seconds, bool loop,
                   float blend, bg_attachment_pose *hand) {
    assertf(mesh && lod < 2 && clip < BG_J_CLIP_COUNT, "ODST pose state");
    const bg_jorge_mesh_info *info = &bg_odst_meshes[lod];
    const bg_jorge_clip *c = &(lod ? bg_odst_lod_clips : bg_odst_clips)[clip];
    float phase = fmaxf(0, seconds / c->duration);
    phase = loop ? phase - floorf(phase) : fminf(phase, 1);
    float frame = phase * (c->frames - 1); unsigned f0 = frame;
    unsigned f1 = f0 + 1 < c->frames ? f0 + 1 : f0;
    float t = frame - f0;
    unsigned offset = c->offset + f0 * c->stride;
    if (offset != cached_offset) {
        read_bank(scratch, offset, c->stride * (f0 == f1 ? 1 : 2));
        cached_offset = offset;
    }
    const int16_t *a = (const int16_t *)scratch;
    const int16_t *b = (const int16_t *)(scratch + (f1 == f0 ? 0 : c->stride));
    unsigned tracks=bg_odst_track_counts[lod], high=(tracks+7)/8;
    unsigned grip_offset=(8+tracks*3+high*3+3)&~3u;
    if (out) {
        const uint8_t *fa=(const uint8_t *)a,*fb=(const uint8_t *)b;
        for(unsigned i=0;i<info->vertices;i++) {
            unsigned track=bg_odst_tracks[lod][i];
            int16_t *p=t3d_vertbuffer_get_pos(out,i);
            for(unsigned k=0;k<3;k++) {
                unsigned index=8+k*tracks+track,bit=8+tracks*3+k*high+track/8;
                int x=a[k]+fa[index]+(((fa[bit]>>(track%8))&1)<<8);
                int y=b[k]+fb[index]+(((fb[bit]>>(track%8))&1)<<8);
                float target=x+(y-x)*t;
                p[k]=lroundf(p[k]+(target-p[k])*blend);
            }
        }
        data_cache_hit_writeback(out,info->vertices*16);
    }
    if (hand) {
        bg_attachment_pose x, y, target;
        /* Vertex count is even; float socket data is naturally aligned. */
        memcpy(&x, (const uint8_t *)a + grip_offset, sizeof(x));
        memcpy(&y, (const uint8_t *)b + grip_offset, sizeof(y));
        blam_quaternions_interpolate_and_normalize(x.quat, y.quat, t, target.quat);
        for (unsigned k = 0; k < 3; k++) target.pos[k] = x.pos[k] + (y.pos[k] - x.pos[k]) * t;
        if (blend >= 1) *hand = target;
        else {
            blam_quaternions_interpolate_and_normalize(hand->quat, target.quat, blend, hand->quat);
            for (unsigned k = 0; k < 3; k++) hand->pos[k] += (target.pos[k] - hand->pos[k]) * blend;
        }
    }
}
