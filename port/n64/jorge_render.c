#include "asset_jorge.h"
#include "blam/runtime.h"
#include <libdragon.h>
#include <malloc.h>
#include <math.h>
#include <string.h>
bg_model_asset bg_jorge_model;
static uint8_t *mesh, *scratch;
static uint32_t rom, rom_bytes, cached_offset = UINT32_MAX;
static void read_bank(void *out, unsigned offset, unsigned bytes) {
    assertf(offset <= rom_bytes && bytes <= rom_bytes - offset, "Jorge bank bounds");
    data_cache_hit_invalidate(out, bytes);
    dma_read(out, rom + offset, bytes);
}
bool bg_jorge_load(void) {
    if (mesh) return false;
    rom = dfs_rom_addr("jorge.bin"); rom_bytes = dfs_rom_size("jorge.bin");
    assertf(rom && rom_bytes, "Missing Jorge bank");
    mesh = memalign(16, bg_jorge_mesh.bytes);
    scratch = memalign(16, bg_jorge_clips[0].stride * 2);
    assertf(mesh && scratch, "Jorge workspace allocation");
    read_bank(mesh, 0, bg_jorge_mesh.bytes);
    bg_jorge_model = (bg_model_asset){(T3DVertPacked *)mesh, bg_jorge_mesh.vertices,
        bg_jorge_mesh.radius, (bg_mesh_batch *)(mesh + bg_jorge_mesh.batches_offset),
        (int16_t *)(mesh + bg_jorge_mesh.indices_offset), bg_jorge_mesh.batches,
        bg_jorge_mesh.triangles};
    cached_offset = UINT32_MAX;
    return true;
}
void bg_jorge_release(void) {
    free(mesh); free(scratch); mesh = scratch = NULL;
    memset(&bg_jorge_model, 0, sizeof(bg_jorge_model)); cached_offset = UINT32_MAX;
}
void bg_jorge_pose(T3DVertPacked *out, unsigned clip, float seconds, bool loop,
                   float blend, bg_attachment_pose *hand) {
    assertf(mesh && clip < BG_J_CLIP_COUNT, "Jorge pose state");
    const bg_jorge_clip *c = &bg_jorge_clips[clip];
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
    if (out) {
        for (unsigned i = 0; i < bg_jorge_mesh.vertices; i++) {
            int16_t *p = t3d_vertbuffer_get_pos(out, i);
            for (unsigned k = 0; k < 3; k++) {
                unsigned j = i * 3 + k;
                float target = a[j] + (b[j] - a[j]) * t;
                p[k] = lroundf(p[k] + (target - p[k]) * blend);
            }
        }
        data_cache_hit_writeback(out, bg_jorge_mesh.vertices * 16);
    }
    if (hand) {
        bg_attachment_pose x, y, target;
        /* Vertex count is even; float socket data is naturally aligned. */
        memcpy(&x, a + bg_jorge_mesh.vertices * 3, sizeof(x));
        memcpy(&y, b + bg_jorge_mesh.vertices * 3, sizeof(y));
        blam_quaternions_interpolate_and_normalize(x.quat, y.quat, t, target.quat);
        for (unsigned k = 0; k < 3; k++) target.pos[k] = x.pos[k] + (y.pos[k] - x.pos[k]) * t;
        if (blend >= 1) *hand = target;
        else {
            blam_quaternions_interpolate_and_normalize(hand->quat, target.quat, blend, hand->quat);
            for (unsigned k = 0; k < 3; k++) hand->pos[k] += (target.pos[k] - hand->pos[k]) * blend;
        }
    }
}
