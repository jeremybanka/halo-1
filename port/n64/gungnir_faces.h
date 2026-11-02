#ifndef BG_GUNGNIR_FACES_H
#define BG_GUNGNIR_FACES_H
#include "asset_gungnir.h"
#include <libdragon.h>
typedef struct { uint16_t vertex; int16_t s, t; } bg_gungnir_face_uv;
typedef struct {
    const bg_gungnir_face_uv *uv;
    const bg_mesh_batch *batches;
    int16_t *indices;
    unsigned uv_count, batch_count, triangles, vertex_loads;
} bg_gungnir_face_mesh;
extern const bg_gungnir_face_mesh bg_gungnir_faces[2];
extern const uint8_t bg_gungnir_face_textures[4][64*64];
void bg_gungnir_faces_prepare(bg_model_asset *model, unsigned lod);
rspq_block_t *bg_gungnir_faces_record(T3DVertPacked *vertices, unsigned lod);
void bg_gungnir_faces_draw(rspq_block_t *block, unsigned profile, bool fading,
                           bool shield);
#endif
