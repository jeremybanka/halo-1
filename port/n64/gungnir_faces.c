#include "gungnir_faces.h"

void bg_gungnir_faces_prepare(bg_model_asset *model, unsigned lod) {
    static bool prepared[2];
    assertf(lod < 2, "GUNGNIR face LOD");
    const bg_gungnir_face_mesh *face = &bg_gungnir_faces[lod];
    for (unsigned i = 0; i < face->uv_count; i++) {
        const bg_gungnir_face_uv *uv = &face->uv[i];
        assertf(uv->vertex < model->vertex_count, "GUNGNIR face vertex");
        int16_t *st = t3d_vertbuffer_get_uv(model->vertices, uv->vertex);
        st[0] = uv->s; st[1] = uv->t;
    }
    data_cache_hit_writeback(model->vertices, model->vertex_count*16);
    if (!prepared[lod]) {
        for (unsigned b = 0; b < face->batch_count; b++) {
            const bg_mesh_batch *batch = &face->batches[b];
            int16_t *indices = face->indices + batch->index_first;
            assertf(!(batch->first & 1) && batch->count <= 60 &&
                    batch->index_count <= 120 && !(batch->index_first & 3) &&
                    batch->first + batch->count <= model->vertex_count,
                    "GUNGNIR face batch");
            for (unsigned i = 0; i < batch->index_count; i++) {
                assertf(indices[i] >= 0 && indices[i] < batch->count,
                        "GUNGNIR face index");
                if (i && i % 3 == 0) indices[i] |= 0x8000;
            }
            t3d_indexbuffer_convert(indices, batch->index_count);
            data_cache_hit_writeback(indices, ((batch->index_count+3)&~3u)*2);
        }
        prepared[lod] = true;
    }
}

rspq_block_t *bg_gungnir_faces_record(T3DVertPacked *vertices, unsigned lod) {
    const bg_gungnir_face_mesh *face = &bg_gungnir_faces[lod];
    rspq_block_begin();
    for (unsigned b = 0; b < face->batch_count; b++) {
        const bg_mesh_batch *batch = &face->batches[b];
        t3d_vert_load(vertices + batch->first/2, 0, (batch->count+1)&~1u);
        t3d_tri_draw_strip(face->indices + batch->index_first, batch->index_count);
        t3d_tri_sync();
    }
    return rspq_block_end();
}

void bg_gungnir_faces_draw(rspq_block_t *block, unsigned profile, bool fading,
                           bool shield) {
    assertf(block && profile < 4, "GUNGNIR face profile");
    surface_t ink = surface_make_linear((void *)bg_gungnir_face_textures[profile],
                                        FMT_IA8, 64, 64);
    rdpq_sync_pipe();
    rdpq_mode_push();
    rdpq_mode_begin();
    rdpq_mode_zbuf(true, false);
    rdpq_mode_antialias(AA_NONE);
    rdpq_mode_alphacompare(0);
    rdpq_mode_persp(true);
    rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_mipmap(MIPMAP_NONE, 0);
    rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    if (shield) {
        if (fading)
            rdpq_mode_combiner(RDPQ_COMBINER2(
                (0,0,0,TEX0), (0,0,0,TEX0),
                (PRIM,COMBINED,PRIM_ALPHA,COMBINED),
                (COMBINED,0,ENV,0)));
        else
            rdpq_mode_combiner(RDPQ_COMBINER2(
                (0,0,0,TEX0), (0,0,0,TEX0),
                (PRIM,COMBINED,PRIM_ALPHA,COMBINED), (0,0,0,COMBINED)));
    } else if (fading)
        rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,TEX0), (TEX0,0,ENV,0)));
    else
        rdpq_mode_combiner(RDPQ_COMBINER_TEX);
    rdpq_mode_end();
    /* The public raw SOM API exposes the RDP's coplanar decal depth mode.
     * Apply it after mode fixups; mode_pop restores the complete prior mode.
     * The existing animated helmet is reused exactly, without offset shells. */
    rdpq_change_other_modes_raw(SOM_ZMODE_MASK, SOM_ZMODE_DECAL);
    rdpq_sync_tile();
    rdpq_sync_load();
    rdpq_tex_upload(TILE0, &ink, NULL); /* Default repeat count 1 clamps both axes. */
    t3d_state_set_drawflags(T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK | T3D_FLAG_TEXTURED);
    rspq_block_run(block);
    rdpq_sync_pipe();
    rdpq_mode_pop();
    t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK);
}
