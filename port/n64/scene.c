#include <libdragon.h>
#include <t3d/t3d.h>
#include "runtime_config.h"
#include <math.h>
#include <string.h>
#include "game.h"
#include "combat.h"
#include "combat_geometry.h"
#include "pickup_rules.h"
#include "movement.h"
#include "view_camera.h"
#include "sky_draw.h"
#include "shields.h"
#include "camouflage.h"
#include "blam/vehicle_physics.h"
#include "asset_models.h"
#include "asset_firstperson.h"
#include "asset_interaction.h"
#include "firstperson_service.h"
#include "firstperson_ammo.h"
#include "weapon_effects.h"
#include "weapon_effects_draw.h"
#include "vehicle_visuals.h"
#include "render_animation.h"
#include "render_lod.h"
#include "asset_micro.h"
#include "render_micro_lod.h"
#include "render_pose_cache.h"
#include "render_visibility.h"
#include "blam/runtime.h"
#include "hud.h"
#include "scene.h"
#include "runtime_qa.h"

extern T3DVertPacked bg_vertices[];
extern uint16_t bg_textures[][32 * 32];
static const color_t colors[4] = {
    {225, 45, 38, 255}, {39, 92, 215, 255}, {215, 179, 44, 255}, {57, 183, 69, 255}};
static surface_t textures[32];
static T3DVertPacked *armor[BG_FRAME_SLOTS][4], particles[7][12] __attribute__((aligned(16)));
static T3DVertPacked *firstperson[BG_FRAME_SLOTS][4];
static unsigned firstperson_bytes[BG_FRAME_SLOTS][4];
static int firstperson_weapon[BG_FRAME_SLOTS][4];
static T3DVertPacked *armor_lod[BG_FRAME_SLOTS][4];
static rspq_block_t *armor_lod_blocks[BG_FRAME_SLOTS][4];
/* A segmented vertex address shares each weapon's commands across all
 * fenced player/slot buffers. Segment 1 is reserved for these draw calls. */
static rspq_block_t *firstperson_blocks[BG_FP_WEAPONS];
static float fired_at[4] = {-100, -100, -100, -100};
static rspq_block_t *world_blocks[512], *player_blocks[BG_FRAME_SLOTS][4], *models[BG_M_COUNT],
    *particle_blocks[7];
static rspq_block_t *vehicle_lods[4];
static rspq_block_t *covenant_wreck_blocks[2];
static rspq_block_t *pickup_lod_blocks[BG_M_COUNT];
static rspq_block_t *vehicle_micro_blocks[4], *pickup_micro_blocks[BG_M_COUNT];
static bg_micro_sphere vehicle_micro_spheres[BG_MAX_VEHICLES], pickup_micro_spheres[BG_MAX_PICKUPS];
static bool vehicle_micro_available[4], pickup_micro_available[BG_M_COUNT];
static rspq_block_t *vehicle_parts[4][7];
static T3DMat4FP part_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES][7];
static bg_cull_bounds vehicle_part_bounds[BG_MAX_VEHICLES][7];
static float wheel_rotation[BG_MAX_VEHICLES];
static bg_vehicle_pose_cache vehicle_pose_cache[BG_MAX_VEHICLES];
static T3DViewport viewports[BG_FRAME_SLOTS][4] __attribute__((aligned(16)));
static T3DViewport gun_viewports[BG_FRAME_SLOTS][4] __attribute__((aligned(16)));
static T3DVertPacked scope_vertices[BG_FRAME_SLOTS][4][6] __attribute__((aligned(16)));
static T3DMat4FP scope_matrices[BG_FRAME_SLOTS][4];
static T3DMat4FP terrain_matrix;
static T3DMat4FP transforms[BG_FRAME_SLOTS][4], guns[BG_FRAME_SLOTS][4],
    vehicle_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES],
    pickup_matrices[BG_FRAME_SLOTS][BG_MAX_PICKUPS],
    projectile_matrices[BG_FRAME_SLOTS][BG_MAX_PROJECTILES];
static T3DMat4FP held_matrices[BG_FRAME_SLOTS][4];
static unsigned slot, views = 4, triangles;
static float game_time;
static int16_t triangle_lists[20][64] __attribute__((aligned(16)));
static bg_motion_track *motion_tracks;
static unsigned motion_capacity;
static T3DVec3 view_eyes[4];
/* 0: absent, 1: full mesh, 2: distant mesh. Visibility is evaluated once. */
static uint8_t body_lods[4][4], wanted_lods[4], held_masks[4], wanted_held;
static uint8_t vehicle_view_lods[4][BG_MAX_VEHICLES];
static uint8_t pickup_visible[4][BG_MAX_PICKUPS];
static bg_cull_bounds body_bounds[4], held_bounds[4], vehicle_bounds[BG_MAX_VEHICLES],
    pickup_bounds[BG_MAX_PICKUPS];
/* CPU-only effect boxes are immutable from preparation through all views. */
static bg_cull_bounds projectile_bounds[BG_MAX_PROJECTILES];
static T3DMat4 body_matrices[4];
static unsigned body_clips[4];
static int locomotion_clip(const bg_player *p);
static bool body_throwing[4];
/* CPU readiness resets after the geometry-slot fence, before any draw. */
static unsigned body_animation_ready, fp_animation_ready;
static void prepare_view(unsigned p);

#ifdef BG_PROFILE
bg_scene_metrics bg_scene_profile;
#define camera_us bg_scene_profile.camera_us
#define animation_us bg_scene_profile.animation_us
#define matrix_us bg_scene_profile.matrix_us
#define world_us bg_scene_profile.world_us
#define object_us bg_scene_profile.object_us
#define fp_us bg_scene_profile.fp_us
#define submitted_vertices bg_scene_profile.submitted_vertices
#define animated_vertices bg_scene_profile.animated_vertices
#define animated_tracks bg_scene_profile.animated_tracks
#define category_triangles bg_scene_profile.category_triangles
static unsigned model_vertex_loads[BG_M_COUNT], pickup_vertex_loads[BG_M_COUNT];
static unsigned vehicle_vertex_loads[4], part_vertex_loads[4][7], spartan_lod_vertex_loads,
    fp_vertex_loads[BG_FP_WEAPONS];
static unsigned vehicle_micro_vertex_loads[4], pickup_micro_vertex_loads[BG_M_COUNT];
#endif
static unsigned weapon_model(unsigned w) {
    return w == BG_W_FLAMETHROWER ? BG_M_FLAMETHROWER : w < 8 ? w : BG_M_AR;
}
static unsigned pickup_model(unsigned w) {
    return w < BG_WEAPON_COUNT       ? weapon_model(w)
           : w == BG_PICK_FRAG       ? BG_M_FRAG
           : w == BG_PICK_PLASMA     ? BG_M_PLASMA_GRENADE
           : w == BG_PICK_HEALTH     ? BG_M_HEALTHPACK
           : w == BG_PICK_OVERSHIELD ? BG_M_OVERSHIELD
                                     : BG_M_CAMOUFLAGE;
}
static void tint_team(T3DVertPacked *vertices, unsigned count, const uint8_t *masks,
                      unsigned player) {
    player = bg_player_profiles[player];
    for (unsigned i = 0; i < count; i++) {
        uint32_t *rgba = t3d_vertbuffer_get_color(vertices, i);
        unsigned r = *rgba >> 24, g = (*rgba >> 16) & 255, b = (*rgba >> 8) & 255, mask = masks[i];
        r = (r * (65025 - mask * (255 - colors[player].r)) + 32512) / 65025;
        g = (g * (65025 - mask * (255 - colors[player].g)) + 32512) / 65025;
        b = (b * (65025 - mask * (255 - colors[player].b)) + 32512) / 65025;
        *rgba = (r << 24) | (g << 16) | (b << 8) | 255;
    }
}
static rspq_block_t *record(T3DVertPacked *verts, unsigned count) {
    rspq_block_begin();
    for (unsigned first = 0; first < count; first += 60) {
        unsigned n = count - first > 60 ? 60 : count - first;
        t3d_vert_load(verts + first / 2, 0, (n + 1) & ~1u);
        /* Restart every triangle: exact original order/winding, one RSP
         * command per batch. 60 vertices leave 360 bytes of DMEM; indices
         * consume at most 120 bytes, within Tiny3D's documented cache limit. */
        t3d_tri_draw_strip(triangle_lists[n / 3 - 1], n);
        t3d_tri_sync();
    }
    return rspq_block_end();
}
static void prepare_model(const bg_model_asset *asset) {
    static const int16_t *converted[96];
    static unsigned converted_count;
    data_cache_hit_writeback(asset->vertices, ((asset->vertex_count + 1) & ~1u) * 16);
    if (!asset->batch_count)
        return;
    for (unsigned i = 0; i < converted_count; i++)
        if (converted[i] == asset->indices)
            return;
    assertf(converted_count < 96, "Model index conversion capacity");
    converted[converted_count++] = asset->indices;
    for (unsigned b = 0; b < asset->batch_count; b++) {
        const bg_mesh_batch *batch = &asset->batches[b];
        assertf(batch->count <= 60 && batch->index_count <= 120 && batch->index_count % 3 == 0 &&
                    !(batch->first & 1) && !(batch->index_first & 3) &&
                    batch->first + batch->count <= asset->vertex_count,
                "Model batch capacity/alignment");
        int16_t *indices = asset->indices + batch->index_first;
        for (unsigned i = 0; i < batch->index_count; i++) {
            assertf(indices[i] >= 0 && indices[i] < batch->count, "Model batch index range");
            if (i && i % 3 == 0)
                indices[i] |= 0x8000;
        }
        t3d_indexbuffer_convert(indices, batch->index_count);
        data_cache_hit_writeback(indices, ((batch->index_count + 3u) & ~3u) * 2);
    }
}
static rspq_block_t *record_model_range(const bg_model_asset *asset, T3DVertPacked *vertices,
                                        unsigned first, unsigned count, unsigned batch_first,
                                        unsigned batch_count) {
    if (!asset->batch_count)
        return record(vertices + first / 2, count);
    assertf(batch_first + batch_count <= asset->batch_count, "Model batch range");
    rspq_block_begin();
    for (unsigned b = batch_first; b < batch_first + batch_count; b++) {
        const bg_mesh_batch *batch = &asset->batches[b];
        t3d_vert_load(vertices + batch->first / 2, 0, (batch->count + 1) & ~1u);
        t3d_tri_draw_strip(asset->indices + batch->index_first, batch->index_count);
        t3d_tri_sync();
    }
    return rspq_block_end();
}
static rspq_block_t *record_model(const bg_model_asset *asset, T3DVertPacked *vertices) {
    return record_model_range(asset, vertices, 0, asset->vertex_count, 0, asset->batch_count);
}
#ifdef BG_PROFILE
static unsigned model_load_count(const bg_model_asset *asset, unsigned count, unsigned first,
                                 unsigned batches) {
    if (!asset->batch_count)
        return (count + 1) & ~1u;
    unsigned total = 0;
    for (unsigned b = first; b < first + batches; b++)
        total += (asset->batches[b].count + 1) & ~1u;
    return total;
}
#endif
static rspq_block_t *record_indexed(const bg_chunk *chunk) {
    int16_t *indices = bg_chunk_indices + chunk->index_first;
    assertf(chunk->count <= 60 && chunk->index_count <= 120 && chunk->index_count % 3 == 0,
            "Terrain batch capacity");
    for (unsigned i = 3; i < chunk->index_count; i += 3)
        indices[i] |= 0x8000;
    t3d_indexbuffer_convert(indices, chunk->index_count);
    data_cache_hit_writeback(indices, ((chunk->index_count + 3u) & ~3u) * 2);
    rspq_block_begin();
    t3d_vert_load(bg_vertices + chunk->first / 2, 0, (chunk->count + 1) & ~1u);
    t3d_tri_draw_strip(indices, chunk->index_count);
    t3d_tri_sync();
    return rspq_block_end();
}
static void init_scene(void) {
    const float terrain_scale = BG_SCALE / BG_TERRAIN_SCALE;
    t3d_mat4fp_from_srt_euler(&terrain_matrix,
                              (float[]){terrain_scale, terrain_scale, terrain_scale},
                              (float[]){0, 0, 0}, (float[]){0, 0, 0});
    data_cache_hit_writeback(&terrain_matrix, sizeof(terrain_matrix));
    assertf(bg_chunk_count <= 512 && bg_material_count <= 32, "Asset capacity exceeded");
    for (unsigned list = 0; list < 20; list++) {
        unsigned count = (list + 1) * 3;
        for (unsigned i = 0; i < count; i++)
            triangle_lists[list][i] = i | ((i && i % 3 == 0) ? 0x8000 : 0);
        t3d_indexbuffer_convert(triangle_lists[list], count);
    }
    data_cache_hit_writeback(triangle_lists, sizeof(triangle_lists));
    for (unsigned clip = 0; clip < BG_A_COUNT; clip++) {
        if (bg_animations[clip].tracks > motion_capacity)
            motion_capacity = bg_animations[clip].tracks;
        if (bg_spartan_lod_animations[clip].tracks > motion_capacity)
            motion_capacity = bg_spartan_lod_animations[clip].tracks;
    }
    for (unsigned weapon = 0; weapon < BG_FP_WEAPONS; weapon++)
        for (unsigned clip = 0; clip < BG_FP_CLIPS; clip++)
            if (bg_fp_animations[weapon][clip].tracks > motion_capacity)
                motion_capacity = bg_fp_animations[weapon][clip].tracks;
    motion_tracks = malloc(motion_capacity * sizeof(*motion_tracks));
    assertf(motion_tracks, "Animation interpolation scratch allocation");
    data_cache_hit_writeback(bg_vertices, bg_vertex_count * 16);
    data_cache_hit_writeback((void *)bg_ground_palette, 32);
    for (unsigned i = 0; i < bg_material_count; i++) {
        unsigned size = bg_texture_sizes[i];
        textures[i] = surface_make(bg_textures[i], bg_texture_ci4[i] ? FMT_CI4 : FMT_RGBA16, size,
                                   size, bg_texture_ci4[i] ? size / 2 : size * 2);
        data_cache_hit_writeback(bg_textures[i], 2048);
    }
    for (unsigned i = 0; i < bg_chunk_count; i++)
        world_blocks[i] = record_indexed(&bg_chunks[i]);
    for (unsigned m = 0; m < BG_M_COUNT; m++) {
        const bg_model_asset *a = &bg_model_assets[m];
        prepare_model(a);
        models[m] = record_model(a, a->vertices);
        const bg_model_asset *far = &bg_pickup_lods[m];
#ifdef BG_PROFILE
        model_vertex_loads[m] = model_load_count(a, a->vertex_count, 0, a->batch_count);
        pickup_vertex_loads[m] = model_load_count(far, far->vertex_count, 0, far->batch_count);
#endif
        if (far->vertices == a->vertices && far->indices == a->indices)
            pickup_lod_blocks[m] = models[m];
        else {
            prepare_model(far);
            pickup_lod_blocks[m] = record_model(far, far->vertices);
        }
    }
    for (unsigned m = 0; m < 4; m++) {
        const bg_model_asset *a = &bg_vehicle_lods[m];
        prepare_model(a);
        vehicle_lods[m] = record_model(a, a->vertices);
#ifdef BG_PROFILE
        vehicle_vertex_loads[m] = model_load_count(a, a->vertex_count, 0, a->batch_count);
#endif
        const bg_vehicle_rig *rig = &bg_vehicle_rigs[m];
        assertf(rig->count <= 7, "Vehicle rig capacity");
        for (unsigned j = 0; j < rig->count; j++) {
            const bg_vehicle_part *part = &rig->parts[j];
            const bg_model_asset *full = &bg_model_assets[BG_M_WARTHOG + m];
            vehicle_parts[m][j] = record_model_range(full, full->vertices, part->first, part->count,
                                                     part->batch_first, part->batch_count);
#ifdef BG_PROFILE
            part_vertex_loads[m][j] =
                model_load_count(full, part->count, part->batch_first, part->batch_count);
#endif
        }
    }
    /* New tables explicitly alias the existing far asset when absent. */
    for (unsigned m = 0; m < BG_M_COUNT; m++) {
        const bg_model_asset *a = bg_pickup_micro_lods[m], *old = &bg_pickup_lods[m];
        pickup_micro_available[m] = a->vertices != old->vertices || a->indices != old->indices;
        if (!pickup_micro_available[m])
            pickup_micro_blocks[m] = pickup_lod_blocks[m];
        else {
            prepare_model(a);
            pickup_micro_blocks[m] = record_model(a, a->vertices);
        }
#ifdef BG_PROFILE
        pickup_micro_vertex_loads[m] = model_load_count(a, a->vertex_count, 0, a->batch_count);
#endif
    }
    for (unsigned m = 0; m < 4; m++) {
        const bg_model_asset *a = bg_vehicle_micro_lods[m], *old = &bg_vehicle_lods[m];
        vehicle_micro_available[m] = a->vertices != old->vertices || a->indices != old->indices;
        if (!vehicle_micro_available[m])
            vehicle_micro_blocks[m] = vehicle_lods[m];
        else {
            prepare_model(a);
            vehicle_micro_blocks[m] = record_model(a, a->vertices);
        }
#ifdef BG_PROFILE
        vehicle_micro_vertex_loads[m] = model_load_count(a, a->vertex_count, 0, a->batch_count);
#endif
    }
    for (unsigned m = 0; m < 2; m++) {
        const bg_model_asset *a = &bg_covenant_wrecks[m];
        prepare_model(a);
        covenant_wreck_blocks[m] = record_model(a, a->vertices);
    }
    prepare_model(&bg_spartan_lod);
    for (unsigned weapon = 0; weapon < BG_FP_WEAPONS; weapon++) {
        const bg_model_asset *a = &bg_fp_models[weapon];
        prepare_model(a);
        for (unsigned prior = 0; prior < weapon; prior++) {
            const bg_model_asset *b = &bg_fp_models[prior];
            if (a->vertices == b->vertices && a->indices == b->indices) {
                firstperson_blocks[weapon] = firstperson_blocks[prior];
                break;
            }
        }
        if (!firstperson_blocks[weapon])
            firstperson_blocks[weapon] = record_model(a, t3d_segment_placeholder(T3D_SEGMENT_1));
    }
#ifdef BG_PROFILE
    spartan_lod_vertex_loads = model_load_count(&bg_spartan_lod, bg_spartan_lod.vertex_count, 0,
                                                bg_spartan_lod.batch_count);
    for (unsigned weapon = 0; weapon < BG_FP_WEAPONS; weapon++) {
        const bg_model_asset *a = &bg_fp_models[weapon];
        fp_vertex_loads[weapon] = model_load_count(a, a->vertex_count, 0, a->batch_count);
    }
#endif
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++)
        for (unsigned p = 0; p < 4; p++) {
            viewports[s][p] = t3d_viewport_create();
        }
    static const int16_t points[6][3] = {{0, 32, 0}, {0, -32, 0}, {32, 0, 0},
                                         {0, 0, 32}, {-32, 0, 0}, {0, 0, -32}};
    static const uint8_t indices[24] = {0, 3, 2, 0, 4, 3, 0, 5, 4, 0, 2, 5,
                                        1, 2, 3, 1, 3, 4, 1, 4, 5, 1, 5, 2};
    const uint32_t hues[7] = {0x54d9ffff, 0xf15cffff, 0xffd38aff, 0x818977ff,
                              0x76abffff, 0xffbc50ff, 0xff9836ff};
    for (unsigned k = 0; k < 7; k++) {
        for (unsigned i = 0; i < 24; i++) {
            memcpy(t3d_vertbuffer_get_pos(particles[k], i), points[indices[i]], 6);
            *t3d_vertbuffer_get_color(particles[k], i) = hues[k];
        }
        data_cache_hit_writeback(particles[k], sizeof(particles[k]));
        particle_blocks[k] = record(particles[k], 24);
    }
}
static void reset_view_state(void) {
    for (unsigned p = 0; p < 4; p++)
        fired_at[p] = -100;
    bg_fx_reset();
    memset(wheel_rotation, 0, sizeof(wheel_rotation));
}
static void prepare_effect_bounds(bg_cull_bounds *bounds, const float pos[3], float radius) {
    bg_bounds box;
    for (unsigned a = 0; a < 3; a++) {
        box.min[a] = (pos[a] - radius) * BG_SCALE;
        box.max[a] = (pos[a] + radius) * BG_SCALE;
    }
    bg_bounds_quantize(bounds, &box);
}
static bool visible_bounds(T3DViewport *vp, const bg_cull_bounds *bounds) {
    return !bounds->valid || t3d_frustum_vs_aabb_s16(&vp->viewFrustum, bounds->min, bounds->max);
}
static void instance(unsigned model, T3DMat4FP *matrix) {
    t3d_matrix_set(matrix, true);
    rspq_block_run(models[model]);
    triangles += bg_model_assets[model].triangle_count;
#ifdef BG_PROFILE
    submitted_vertices += model_vertex_loads[model];
#endif
}
static void small_model_instance(unsigned model, T3DMat4FP *matrix, T3DViewport *vp,
                                 const T3DVec3 *eye, bool zoom,
                                 const bg_micro_sphere *micro_bounds) {
    /* Positions in matrices are render units; asset radii are Halo units.
     * Camera-forward depth is conservative at the edges of the viewport,
     * unlike Euclidean distance. A bounding sphere controls the pixel LOD.
     * Held guns use the same size or shrink when crouching, so retaining the
     * unscaled source radius safely overestimates the crouched silhouette. */
    float pos[3];
    for (unsigned a = 0; a < 3; a++)
        pos[a] = t3d_mat4fp_get_float(matrix, 3, a);
    float depth = -(pos[0] * vp->matCamera.m[0][2] + pos[1] * vp->matCamera.m[1][2] +
                    pos[2] * vp->matCamera.m[2][2] + vp->matCamera.m[3][2]) /
                  BG_SCALE;
    float distance_squared = 0;
    for (unsigned a = 0; a < 3; a++) {
        float d = (pos[a] - eye->v[a]) / BG_SCALE;
        distance_squared += d * d;
    }
    bool far = !zoom && bg_lod_diameter_below(bg_model_assets[model].radius,
                                              vp->size[1] * fabsf(vp->matProj.m[1][1]), depth,
                                              distance_squared, 12.f);
    bool micro = far && pickup_micro_available[model] &&
                 bg_micro_lod_below(micro_bounds, vp->matCamera.m, vp->matProj.m, vp->size[0],
                                    vp->size[1], 1.4f, BG_MICRO_PIXELS, true, zoom, views);
    t3d_matrix_set(matrix, true);
    rspq_block_run(micro ? pickup_micro_blocks[model]
                   : far ? pickup_lod_blocks[model]
                         : models[model]);
    triangles += micro ? bg_pickup_micro_lods[model]->triangle_count
                 : far ? bg_pickup_lods[model].triangle_count
                       : bg_model_assets[model].triangle_count;
#ifdef BG_PROFILE
    submitted_vertices += micro ? pickup_micro_vertex_loads[model]
                          : far ? pickup_vertex_loads[model]
                                : model_vertex_loads[model];
#endif
}
static void matrix(T3DMat4FP *out, float scale, float yaw, float pitch, const float pos[3]) {
    t3d_mat4fp_from_srt_euler(out, (float[]){scale, scale, scale}, (float[]){0, -yaw, -pitch},
                              (float[]){pos[0] * BG_SCALE, pos[1] * BG_SCALE, pos[2] * BG_SCALE});
}
static void animate_mesh(T3DVertPacked *output, const bg_anim_asset *a, unsigned f0, unsigned f1,
                         int fraction) {
    assertf(a->tracks <= motion_capacity, "Animation scratch capacity");
    const uint8_t *src0 = a->positions + f0 * a->tracks * 3,
                  *src1 = a->positions + f1 * a->tracks * 3;
    bg_motion_decode(motion_tracks, a->tracks, src0, src1, a->origin, fraction);
    bg_motion_scatter(output, a->vertices, a->indices, motion_tracks);
    data_cache_hit_writeback(output, ((a->vertices + 1) & ~1u) * 16);
#ifdef BG_PROFILE
    animated_tracks += a->tracks;
    animated_vertices += a->vertices;
#endif
}
static void prepare_player_bounds(unsigned p) {
    bg_player *player = &bg_players[p];
    unsigned clip;
    float body_yaw = player->yaw, body_pitch = 0;
    switch (player->animation) {
    case BG_ANIM_WALK:
    case BG_ANIM_RUN:
        clip = BG_A_RUN;
        break;
    case BG_ANIM_FIRE:
        clip = BG_A_FIRE;
        break;
    case BG_ANIM_RELOAD:
        clip = BG_A_RELOAD;
        break;
    case BG_ANIM_DIE:
        clip = BG_A_DEATH;
        break;
    case BG_ANIM_JUMP:
        clip = BG_A_JUMP;
        break;
    case BG_ANIM_MELEE:
        clip = BG_A_MELEE;
        break;
    case BG_ANIM_DRIVE:
        clip = BG_A_DRIVE;
        break;
    default:
        clip = BG_A_IDLE;
        break;
    }
    const bg_seat_definition *seat = bg_player_seat(player);
    if (player->health > 0 && seat) {
        const bg_vehicle *vehicle = &bg_vehicles[player->vehicle];
        clip = player->seat == 2 ? BG_A_PASSENGER : player->seat == 1 ? BG_A_GUNNER : BG_A_DRIVE;
        body_yaw = vehicle->yaw + seat->yaw +
                   (vehicle->kind == BG_V_WARTHOG && player->seat == 1 ? vehicle->turret_yaw : 0);
        body_pitch = vehicle->pitch;
    }
    bool throwing = player->health > 0 && player->grenade_cooldown > .55f && player->vehicle < 0;
    if (throwing)
        clip = BG_A_THROW;
    body_clips[p] = clip;
    body_throwing[p] = throwing;
    float size = 1;
    float height_scale =
        locomotion_clip(player) < 0 ? bg_body_height(player) / bg_movement.height[0] : 1;
    T3DMat4 *body = &body_matrices[p];
    t3d_mat4_from_srt_euler(
        body, (float[]){size, height_scale, size}, (float[]){0, -body_yaw, -body_pitch},
        (float[]){player->pos[0] * BG_SCALE, player->pos[1] * BG_SCALE, player->pos[2] * BG_SCALE});
    if (player->health > 0 && player->vehicle >= 0) {
        const bg_vehicle *v = &bg_vehicles[player->vehicle];
        if (v->physics_valid) {
            const float *f = v->forward, *u = v->up;
            float r[3] = {f[1] * u[2] - f[2] * u[1], f[2] * u[0] - f[0] * u[2],
                          f[0] * u[1] - f[1] * u[0]};
            float relative = seat->yaw +
                             (v->kind == BG_V_WARTHOG && player->seat == 1 ? v->turret_yaw : 0),
                  c = cosf(relative), s = sinf(relative);
            for (unsigned a = 0; a < 3; a++) {
                body->m[0][a] = (f[a] * c - r[a] * s) * size;
                body->m[1][a] = u[a] * size;
                body->m[2][a] = (f[a] * s + r[a] * c) * size;
            }
        }
    }
    if (seat && player->seat_blend > 0)
        for (unsigned a = 0; a < 3; a++)
            body->m[3][a] += player->seat_offset[a] * (player->seat_blend / (6.f / 30)) * BG_SCALE;
    const bg_bounds *source_bounds = seat ? &bg_seat_poses[seat->pose][player->seat_state][0].bounds
                                     : player->weapon_ready > 0 ? &bg_body_ready_poses[0].bounds
                                                                : &bg_body_cull_bounds[clip];
    bg_bounds merged = *source_bounds;
    int locomotion = locomotion_clip(player);
    if (locomotion >= 0) {
        const bg_bounds *b = &bg_locomotion_poses[locomotion][0].bounds;
        for (unsigned k = 0; k < 3; k++) {
            merged.min[k] = fminf(merged.min[k], b->min[k]);
            merged.max[k] = fmaxf(merged.max[k], b->max[k]);
        }
    }
    bg_bounds box;
    bg_bounds_transform(&box, &merged, body->m, BG_SCALE);
    bg_bounds_quantize(&body_bounds[p], &box);
    /* Any normalized hand quaternion keeps a weapon within its origin sphere.
     * Marker position interpolation stays inside this clip's endpoint box. */
    bg_bounds marker = bg_attachment_cull_bounds[clip];
    if (seat || player->weapon_ready > 0 || locomotion >= 0)
        marker = (bg_bounds){{-1, -1, -1}, {1, 1, 1}};
    bg_bounds_expand(&marker, bg_model_cull_radii[weapon_model(player->weapon)]);
    bg_bounds_transform(&box, &marker, body->m, BG_SCALE);
    bg_bounds_quantize(&held_bounds[p], &box);
    T3DMat4 armor_matrix = *body;
    for (unsigned a = 0; a < 3; a++)
        for (unsigned b = 0; b < 3; b++)
            armor_matrix.m[a][b] *= BG_SCALE / BG_MODEL_SCALE;
    t3d_mat4_to_fixed_3x4(&transforms[slot][p], &armor_matrix);
}
static int locomotion_clip(const bg_player *p) {
    if (p->health <= 0 || p->vehicle >= 0 || p->weapon_ready > 0 || p->melee_time > 0 ||
        p->reload > 0 || p->flash > 0 || p->grenade_cooldown > .55f)
        return -1;
    if (p->landing_time > 0)
        return 2 + (p->hard_landing ? 1 : 0) + (p->crouch_amount > .5f ? 2 : 0);
    if (p->grounded && p->crouch_amount > 0)
        return hypotf(p->velocity[0], p->velocity[2]) > .15f ? 1 : 0;
    return -1;
}
static float locomotion_seconds(const bg_player *p, int clip) {
    return clip < 2 ? p->anim_time : p->landing_duration - p->landing_time;
}
static void animate_player(unsigned p) {
    if (!wanted_lods[p] && !(wanted_held & (1u << p)))
        return;
    bg_player *player = &bg_players[p];
    unsigned clip = body_clips[p];
    const bg_seat_definition *seat = bg_player_seat(player);
    bool ready = player->weapon_ready > 0;
    if (seat || ready) {
        float ready_seconds = ready ? (1 - player->weapon_ready / bg_ready_times[player->weapon]) *
                                          bg_body_ready_poses[0].duration
                                    : 0;
        for (unsigned lod = 0; lod < 2; lod++)
            if (wanted_lods[p] & (1u << lod))
                bg_interaction_pose(CachedAddr(lod ? armor_lod[slot][p] : armor[slot][p]),
                                    seat ? &bg_seat_poses[seat->pose][player->seat_state][lod]
                                         : &bg_body_ready_poses[lod],
                                    seat ? player->anim_time : ready_seconds,
                                    seat && player->seat_state == BG_SEAT_STABLE);
        if (wanted_held & (1u << p)) {
            const bg_rom_pose *grip = seat ? &bg_seat_grips[seat->pose] : &bg_body_ready_grip;
            float seconds = seat ? fmodf(player->anim_time, grip->duration) : ready_seconds;
            int16_t points[4][3];
            bg_interaction_points(points, grip, seconds);
            T3DMat4 hand, world;
            t3d_mat4_identity(&hand);
            for (unsigned a = 0; a < 3; a++) {
                hand.m[3][a] = points[0][a] * (BG_SCALE / 4096);
                for (unsigned c = 0; c < 3; c++)
                    hand.m[c][a] = points[c + 1][a] * (BG_SCALE / BG_OBJECT_SCALE / 4096);
            }
            t3d_mat4_mul(&world, &body_matrices[p], &hand);
            t3d_mat4_to_fixed_3x4(&held_matrices[slot][p], &world);
        }
        return;
    }
    int locomotion = locomotion_clip(player);
    float loc_seconds = locomotion >= 0 ? locomotion_seconds(player, locomotion) : 0;
    const bg_anim_asset *base = &bg_animations[clip];
    float phase = body_throwing[p] ? (.9f - player->grenade_cooldown) / .35f
                                   : player->anim_time / base->duration;
    bool loop = clip == BG_A_RUN || clip == BG_A_IDLE || clip == BG_A_DRIVE ||
                clip == BG_A_PASSENGER || clip == BG_A_GUNNER;
    if (loop)
        phase -= floorf(phase);
    else
        phase = fminf(fmaxf(phase, 0), .9999f);
    float frame = phase * (base->frames - 1);
    unsigned f0 = (unsigned)frame, f1 = f0 + 1 < base->frames ? f0 + 1 : f0;
    int fraction = (frame - f0) * 256;
    for (unsigned lod = 0; lod < 2; lod++)
        if (!seat && (wanted_lods[p] & (1u << lod))) {
            const bg_anim_asset *a = lod ? &bg_spartan_lod_animations[clip] : base;
            T3DVertPacked *output = CachedAddr(lod ? armor_lod[slot][p] : armor[slot][p]);
            animate_mesh(output, a, f0, f1, fraction);
            if (locomotion >= 0)
                bg_interaction_pose_blend(output, &bg_locomotion_poses[locomotion][lod],
                                          loc_seconds, locomotion < 2,
                                          locomotion < 2 ? player->crouch_amount : 1);
        }
    if (wanted_held & (1u << p)) {
        const bg_attachment_clip *attach = &bg_weapon_attachment[clip];
        const bg_attachment_pose *pose0 = &attach->poses[f0], *pose1 = &attach->poses[f1];
        float q[4], pos[3], weight = frame - f0;
        blam_quaternions_interpolate_and_normalize(pose0->quat, pose1->quat, weight, q);
        for (unsigned c = 0; c < 3; c++)
            pos[c] = (pose0->pos[c] + (pose1->pos[c] - pose0->pos[c]) * weight) * BG_SCALE;
        T3DMat4 hand, world;
        float model_scale = BG_SCALE / BG_OBJECT_SCALE;
        t3d_mat4_from_srt(&hand, (float[]){model_scale, model_scale, model_scale}, q, pos);
        if (locomotion >= 0) {
            const bg_rom_pose *grip = &bg_locomotion_grips[locomotion];
            int16_t points[4][3];
            bg_interaction_points(
                points, grip, locomotion < 2 ? fmodf(loc_seconds, grip->duration) : loc_seconds);
            float weight = locomotion < 2 ? player->crouch_amount : 1;
            for (unsigned a = 0; a < 3; a++) {
                hand.m[3][a] += (points[0][a] * (BG_SCALE / 4096) - hand.m[3][a]) * weight;
                for (unsigned c = 0; c < 3; c++)
                    hand.m[c][a] +=
                        (points[c + 1][a] * (BG_SCALE / BG_OBJECT_SCALE / 4096) - hand.m[c][a]) *
                        weight;
            }
        }
        t3d_mat4_mul(&world, &body_matrices[p], &hand);
        t3d_mat4_to_fixed_3x4(&held_matrices[slot][p], &world);
    }
}
static void pivot_rotation(T3DMat4 *out, const float pivot[3], float yaw, float pitch) {
    t3d_mat4_from_srt_euler(out, (float[]){1, 1, 1}, (float[]){0, -yaw, -pitch},
                            (float[]){0, 0, 0});
    T3DVec3 p = {{pivot[0] * BG_OBJECT_SCALE, pivot[1] * BG_OBJECT_SCALE,
                  pivot[2] * BG_OBJECT_SCALE}},
            rotated;
    t3d_mat3_mul_vec3(&rotated, out, &p);
    for (unsigned a = 0; a < 3; a++)
        out->m[3][a] = p.v[a] - rotated.v[a];
}
static void compute_vehicle_pose(unsigned i) {
    bg_vehicle *v = &bg_vehicles[i];
    const bg_vehicle_rig *rig = &bg_vehicle_rigs[v->kind];
    float model_scale = BG_SCALE / BG_OBJECT_SCALE;
    T3DMat4 base, yaw;
    t3d_mat4_from_srt_euler(
        &base, (float[]){model_scale, model_scale, model_scale}, (float[]){0, -v->yaw, -v->pitch},
        (float[]){v->pos[0] * BG_SCALE, v->pos[1] * BG_SCALE, v->pos[2] * BG_SCALE});
    if (v->physics_valid) {
        const float *f = v->forward, *u = v->up;
        float right[3] = {f[1] * u[2] - f[2] * u[1], f[2] * u[0] - f[0] * u[2],
                          f[0] * u[1] - f[1] * u[0]};
        for (unsigned a = 0; a < 3; a++) {
            base.m[0][a] = f[a] * model_scale;
            base.m[1][a] = u[a] * model_scale;
            base.m[2][a] = right[a] * model_scale;
        }
    }
    t3d_mat4_to_fixed_3x4(&vehicle_matrices[slot][i], &base);
    bg_bounds combined;
    bg_bounds_transform(&combined, &bg_vehicle_micro_gate_bounds[v->kind], base.m, BG_OBJECT_SCALE);
    if (!v->active && (v->kind == BG_V_GHOST || v->kind == BG_V_BANSHEE)) {
        bg_bounds wreck;
        bg_bounds_transform(&wreck, &bg_covenant_wreck_bounds[v->kind == BG_V_BANSHEE], base.m,
                            BG_OBJECT_SCALE);
        bg_bounds_union(&combined, &wreck);
    }
    pivot_rotation(&yaw, rig->turret_pivot, v->turret_yaw, 0);
    for (unsigned j = 0; j < rig->count; j++) {
        const bg_vehicle_part *part = &rig->parts[j];
        T3DMat4 local, world;
        if (part->kind == BG_PART_BODY)
            world = base;
        else {
            if (part->kind == BG_PART_TURRET)
                local = yaw;
            else if (part->kind == BG_PART_HATCH) {
                t3d_mat4_identity(&local);
                if (v->active) {
                    const bg_rom_pose *pose =
                        &bg_hatch_poses[v->kind == BG_V_BANSHEE][v->hatch_closing];
                    int16_t points[4][3];
                    bg_interaction_points(points, pose, v->hatch * pose->duration);
                    for (unsigned a = 0; a < 3; a++) {
                        local.m[3][a] = points[0][a] * (BG_OBJECT_SCALE / 4096);
                        for (unsigned c = 0; c < 3; c++)
                            local.m[c][a] = points[c + 1][a] * (1.f / 4096);
                    }
                }
            } else if (part->kind == BG_PART_WHEEL) {
                /* Wheels rotate about their axle (local Z), then steer with
                 * the original opposite front/rear powered contact groups. */
                T3DMat4 spin, steer;
                pivot_rotation(&spin, part->pivot, 0, -wheel_rotation[i]);
                float angle = v->physics_valid ? v->steering * (part->pivot[0] > 0 ? 1 : -1) : 0;
                pivot_rotation(&steer, part->pivot, angle, 0);
                t3d_mat4_mul(&local, &steer, &spin);
                if (v->physics_valid && v->kind == BG_V_WARTHOG) {
                    unsigned channel = part->pivot[0] > 0 ? (part->pivot[2] < 0 ? 2 : 3)
                                                          : (part->pivot[2] < 0 ? 0 : 1);
                    local.m[3][1] += (v->suspension[channel] + .22f) * BG_OBJECT_SCALE;
                }
            } else {
                T3DMat4 pitch;
                pivot_rotation(&pitch, part->pivot, 0, v->turret_pitch - v->pitch);
                t3d_mat4_mul(&local, &yaw, &pitch);
            }
            t3d_mat4_mul(&world, &base, &local);
        }
        t3d_mat4_to_fixed_3x4(&part_matrices[slot][i][j], &world);
        bg_bounds box;
        bg_bounds_transform(&box, &part->bounds, world.m, BG_OBJECT_SCALE);
        /* Reuse the exact current wheel/turret/barrel pose, not a sampled
         * rotation envelope. CPU-only bounds need no geometry-slot lifetime. */
        bg_bounds_quantize(&vehicle_part_bounds[i][j], &box);
        bg_bounds_union(&combined, &box);
    }
    bg_bounds_quantize(&vehicle_bounds[i], &combined);
}
static void prepare_vehicle(unsigned i) {
    bg_vehicle_pose_cache *cache = &vehicle_pose_cache[i];
    uint32_t key[BG_VEHICLE_POSE_WORDS];
    bg_vehicle_pose_key(key, &bg_vehicles[i], &wheel_rotation[i]);
    if (cache->valid && !memcmp(cache->key, key, sizeof(key))) {
        if (!(cache->slot_mask & (1u << slot))) {
            /* The destination slot is fenced before prepare_frame. The other
             * slot is only read here; RSP matrix DMA never modifies it. */
            unsigned count = bg_vehicle_rigs[bg_vehicles[i].kind].count;
            memcpy(&vehicle_matrices[slot][i], &vehicle_matrices[cache->last_slot][i],
                   sizeof(T3DMat4FP));
            memcpy(part_matrices[slot][i], part_matrices[cache->last_slot][i],
                   count * sizeof(T3DMat4FP));
            cache->slot_mask |= 1u << slot;
        }
        /* These shared CPU bounds have no writer outside the miss path. */
    } else {
        compute_vehicle_pose(i);
        memcpy(cache->key, key, sizeof(key));
        cache->valid = true;
        cache->slot_mask = 1u << slot;
    }
    cache->last_slot = slot;
}
static void prepare_pickup_bounds(void) {
    float scale = BG_SCALE / BG_OBJECT_SCALE;
    T3DMat4 map_rotation;
    t3d_mat4_from_srt_euler(&map_rotation, (float[]){scale, scale, scale},
                            (float[]){0, -game_time * .5f, 0}, (float[]){0, 0, 0});
    for (unsigned i = 0; i < bg_pickup_count; i++) {
        const bg_pickup *q = &bg_pickups[i];
        if (!q->active)
            continue;
        T3DMat4 rotation = map_rotation;
        if (q->dropped)
            t3d_mat4_from_srt_euler(&rotation, (float[]){scale, scale, scale},
                                    (float[]){0, q->yaw, 0}, (float[]){0, 0, 0});
        float pos[3];
        memcpy(pos, q->pos, sizeof(pos));
        if (!q->dropped)
            pos[1] += .035f * sinf(game_time * 2 + i);
        for (unsigned a = 0; a < 3; a++)
            rotation.m[3][a] = pos[a] * BG_SCALE;
        t3d_mat4_to_fixed_3x4(&pickup_matrices[slot][i], &rotation);
        bg_bounds box;
        bg_bounds_transform(&box, &bg_pickup_micro_gate_bounds[pickup_model(q->weapon)], rotation.m,
                            BG_OBJECT_SCALE);
        bg_bounds_quantize(&pickup_bounds[i], &box);
    }
}
/* Body commands retain their vertex addresses; allocate and release together. */
static void body_buffers_load(void) {
    if (armor[0][0])
        return;
    const bg_model_asset *spartan = &bg_model_assets[BG_M_SPARTAN];
    unsigned bytes = ((spartan->vertex_count + 1) & ~1u) * 16;
    unsigned lod_bytes = ((bg_spartan_lod.vertex_count + 1) & ~1u) * 16;
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++)
        for (unsigned p = 0; p < 4; p++) {
            armor[s][p] = malloc_uncached(bytes);
            assertf(armor[s][p], "Spartan buffer allocation");
            memcpy(armor[s][p], spartan->vertices, bytes);
            tint_team(armor[s][p], spartan->vertex_count, bg_spartan_team_mask, p);
            player_blocks[s][p] = record_model(spartan, armor[s][p]);
            armor_lod[s][p] = malloc_uncached(lod_bytes);
            assertf(armor_lod[s][p], "Spartan LOD allocation");
            memcpy(armor_lod[s][p], bg_spartan_lod.vertices, lod_bytes);
            tint_team(armor_lod[s][p], bg_spartan_lod.vertex_count, bg_spartan_lod_team_mask, p);
            armor_lod_blocks[s][p] = record_model(&bg_spartan_lod, armor_lod[s][p]);
        }
}
static void body_buffers_release(void) {
    if (!armor[0][0])
        return;
    /* Full-screen menus never draw gameplay bodies. The recorded blocks own
     * their vertex addresses, so fence and release both together; rebuild on
     * match entry. In-match pause/resume keeps this allocation intact. */
    rspq_wait();
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++)
        for (unsigned p = 0; p < 4; p++) {
            rspq_block_free(player_blocks[s][p]);
            player_blocks[s][p] = NULL;
            rspq_block_free(armor_lod_blocks[s][p]);
            armor_lod_blocks[s][p] = NULL;
            free_uncached(armor[s][p]);
            armor[s][p] = NULL;
            free_uncached(armor_lod[s][p]);
            armor_lod[s][p] = NULL;
        }
}
/* Segment-based weapon commands do not retain these addresses. Keep their
 * animation workspace out of the full-screen menu texture peak. */
static void firstperson_buffers_load(void) {
    /* Buffers are acquired lazily when a personal weapon is first visible. */
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++)
        for (unsigned p = 0; p < 4; p++)
            if (!firstperson[s][p])
                firstperson_weapon[s][p] = -1;
}
static void firstperson_buffers_release(void) {
    /* The RSP consumes vertices; the RDP only retains transformed triangles. */
    rspq_wait();
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++)
        for (unsigned p = 0; p < 4; p++) {
            if (firstperson[s][p])
                free_uncached(firstperson[s][p]);
            firstperson[s][p] = NULL;
            firstperson_bytes[s][p] = 0;
            firstperson_weapon[s][p] = -1;
        }
}
static void firstperson_buffer_resize(unsigned p, unsigned bytes) {
    if (!firstperson[slot][p]) {
        /* Eight independently resized meshes fragmented the 4 MiB heap:
         * enough total free memory remained, but not one pistol-sized hole.
         * Reserve the authored maximum once per live slot/player. Menu entry
         * still fences and releases all buffers, and mesh detail is unchanged. */
        unsigned capacity = 0;
        for (unsigned w = 0; w < BG_FP_WEAPONS; w++) {
            unsigned required = ((bg_fp_models[w].vertex_count + 1) & ~1u) * 16;
            if (required > capacity)
                capacity = required;
        }
        firstperson[slot][p] = malloc_uncached(capacity);
        assertf(firstperson[slot][p], "First-person mesh allocation");
        firstperson_bytes[slot][p] = capacity;
        firstperson_weapon[slot][p] = -1;
    }
    assertf(bytes <= firstperson_bytes[slot][p], "First-person mesh capacity");
}
static void animate_firstperson(unsigned p) {
    if (p >= views)
        return;
    bg_player *player = &bg_players[p];
    unsigned w = player->weapon;
    if (player->vehicle >= 0 || player->health <= 0 || player->zoom || p >= views)
        return;
    const bg_model_asset *m = &bg_fp_models[w];
    unsigned bytes = ((m->vertex_count + 1) & ~1u) * 16;
    firstperson_buffer_resize(p, bytes);
    T3DVertPacked *output = CachedAddr(firstperson[slot][p]);
    if (firstperson_weapon[slot][p] != (int)w) {
        memcpy(output, m->vertices, bytes);
        tint_team(output, m->vertex_count, bg_fp_team_masks[w], p);
        /* The slot fence protects this buffer. Commands are shared and
         * select its address through the RSP's ordered segment table. */
        firstperson_weapon[slot][p] = w;
    }
    unsigned clip = BG_FP_IDLE;
    float seconds = game_time;
    if (player->reload > 0) {
        clip = BG_FP_RELOAD;
        seconds = player->anim_time;
        /* Fit the source needle-regrowth timeline to the game's reload
         * duration; mesh motion and ammunition overlay share that clock. */
        if (player->reload_duration > 0)
            seconds *= bg_fp_animations[w][clip].duration / player->reload_duration;
    } else if (player->overheated) {
        clip = BG_FP_RELOAD;
        seconds = (1 - player->heat) / .85f * bg_fp_animations[w][clip].duration;
    } else if (player->melee_time > 0) {
        clip = BG_FP_MELEE;
        seconds = player->anim_time * bg_fp_animations[w][clip].duration / bg_melee_duration(w);
    } else if (game_time >= fired_at[p] &&
               game_time - fired_at[p] < bg_fp_animations[w][BG_FP_FIRE].duration) {
        clip = BG_FP_FIRE;
        seconds = game_time - fired_at[p];
    }
    const bg_anim_asset *a = &bg_fp_animations[w][clip];
    float phase = fmaxf(0, seconds / a->duration);
    if (clip == BG_FP_IDLE)
        phase -= floorf(phase);
    else
        phase = fminf(phase, .9999f);
    float frame = phase * (a->frames - 1);
    unsigned f0 = frame, f1 = f0 + 1 < a->frames ? f0 + 1 : f0;
    int fraction = (frame - f0) * 256;
    float service_seconds = 0;
    bool service_loop = false;
    int service = bg_firstperson_service(player, &service_seconds, &service_loop);
    if (service < 0 && w == BG_W_SHOTGUN && clip == BG_FP_FIRE) {
        service = BG_SERVICE_SHOTGUN_FIRE;
        service_seconds = seconds;
    }
    if (player->weapon_ready > 0)
        bg_interaction_pose(output, &bg_ready_poses[w], bg_ready_times[w] - player->weapon_ready,
                            false);
    else if (service >= 0)
        bg_interaction_pose(output, &bg_service_poses[service], service_seconds, service_loop);
    else
        animate_mesh(output, a, f0, f1, fraction);
    bg_fx_pose(p, w, clip, f0, f1, fraction);
    if (service == BG_SERVICE_SHOTGUN_FIRE && player->weapon_ready <= 0) {
        int16_t points[2][3];
        bg_interaction_points(points, &bg_shotgun_fire_muzzle, service_seconds);
        bg_fx_muzzle_pose(p, points);
    }
    const bg_fp_detail_asset *detail = &bg_fp_details[w];
    if (detail->vertices) {
        T3DVertPacked *scope = scope_vertices[slot][p];
        const int16_t (*a)[3] = &detail->poses[(detail->offsets[clip] + f0) * detail->vertices];
        const int16_t (*b)[3] = &detail->poses[(detail->offsets[clip] + f1) * detail->vertices];
        for (unsigned v = 0; v < detail->vertices; v++) {
            int16_t *point = t3d_vertbuffer_get_pos(scope, v);
            for (unsigned axis = 0; axis < 3; axis++)
                point[axis] = a[v][axis] + (((int)b[v][axis] - a[v][axis]) * fraction >> 8);
            *t3d_vertbuffer_get_color(scope, v) = detail->colors[v];
        }
        if (player->weapon_ready > 0) {
            int16_t points[12][3];
            bg_interaction_points(points,
                                  w == BG_W_SNIPER ? &bg_ready_scope
                                                   : &bg_ready_plasma[w == BG_W_PLASMA_RIFLE],
                                  bg_ready_times[w] - player->weapon_ready);
            for (unsigned v = 0; v < detail->vertices; v++)
                memcpy(t3d_vertbuffer_get_pos(scope, v), points[v], sizeof(points[v]));
        } else if (service >= 0 && bg_service_details[service].vertices) {
            int16_t points[12][3];
            const bg_rom_pose *pose = &bg_service_details[service];
            float t = service_loop ? fmodf(service_seconds, pose->duration) : service_seconds;
            bg_interaction_points(points, pose, t);
            if (bg_service_vents[service].vertices) {
                int16_t vents[3][3];
                bg_interaction_points(vents, &bg_service_vents[service], t);
                bg_fx_vent_pose(p, vents);
            }
            for (unsigned v = 0; v < detail->vertices; v++)
                memcpy(t3d_vertbuffer_get_pos(scope, v), points[v], sizeof(points[v]));
        }
        data_cache_hit_writeback(scope, sizeof(scope_vertices[slot][p]));
    }
    bg_fp_ammo_prepare(slot, p, w, clip, f0, f1, fraction, player->ammo, player->reserve,
                       player->reload > 0 ? seconds : -1, output);
}
static void ensure_player_animation(unsigned p) {
    unsigned bit = 1u << p;
    if (body_animation_ready & bit)
        return;
#ifdef BG_PROFILE
    uint64_t begin = get_ticks_us();
#endif
    /* Prepare the union needed by ALL views exactly once. This must precede
     * the first near/far body or held-weapon command that borrows its buffer. */
    animate_player(p);
    if (wanted_held & bit)
        data_cache_hit_writeback(&held_matrices[slot][p], sizeof(T3DMat4FP));
    body_animation_ready |= bit;
#ifdef BG_PROFILE
    animation_us += get_ticks_us() - begin;
#endif
}
static void ensure_firstperson_animation(unsigned p) {
    unsigned bit = 1u << p;
    if (fp_animation_ready & bit)
        return;
#ifdef BG_PROFILE
    uint64_t begin = get_ticks_us();
#endif
    animate_firstperson(p);
    fp_animation_ready |= bit;
#ifdef BG_PROFILE
    animation_us += get_ticks_us() - begin;
#endif
}
static void prepare_frame(void) {
#ifdef BG_PROFILE
    uint64_t begin = get_ticks_us();
#endif
    body_animation_ready = fp_animation_ready = 0;
    memset(wanted_lods, 0, sizeof(wanted_lods));
    wanted_held = 0;
    /* Matrix construction precedes visibility so culling uses the exact pose
     * later submitted, once per frame rather than once per viewport. */
    for (unsigned p = 0; p < views; p++)
        prepare_player_bounds(p);
    for (unsigned i = 0; i < bg_vehicle_count; i++)
        if (bg_vehicle_body_present(&bg_vehicles[i]))
            prepare_vehicle(i);
    prepare_pickup_bounds();
    if (views >= 3) {
        for (unsigned i = 0; i < bg_vehicle_count; i++)
            if (bg_vehicle_body_present(&bg_vehicles[i]) &&
                vehicle_micro_available[bg_vehicles[i].kind])
                bg_micro_sphere_from_bounds(&vehicle_micro_spheres[i], &vehicle_bounds[i]);
        for (unsigned i = 0; i < bg_pickup_count; i++)
            if (bg_pickups[i].active && pickup_micro_available[pickup_model(bg_pickups[i].weapon)])
                bg_micro_sphere_from_bounds(&pickup_micro_spheres[i], &pickup_bounds[i]);
    }
    for (unsigned p = 0; p < views; p++)
        prepare_view(p);
#ifdef BG_PROFILE
    camera_us = get_ticks_us() - begin;
    begin = get_ticks_us();
#endif
    for (unsigned i = 0; i < BG_MAX_PROJECTILES; i++) {
        bg_projectile *q = bg_projectile_at(i);
        if (!q || !q->active)
            continue;
        float scale = q->kind == BG_P_CANNON ? .09f : q->kind == BG_P_FLAME ? .18f : .045f;
        if (q->kind == BG_P_FRAG || q->kind == BG_P_PLASMA_GRENADE)
            scale = BG_SCALE / BG_OBJECT_SCALE;
        matrix(&projectile_matrices[slot][i], scale, game_time * 4, 0, q->pos);
        prepare_effect_bounds(&projectile_bounds[i], q->pos, .2f);
    }
    data_cache_hit_writeback(transforms[slot], sizeof(transforms[slot]));
    data_cache_hit_writeback(vehicle_matrices[slot], sizeof(vehicle_matrices[slot]));
    data_cache_hit_writeback(pickup_matrices[slot], sizeof(pickup_matrices[slot]));
    data_cache_hit_writeback(projectile_matrices[slot], sizeof(projectile_matrices[slot]));
    data_cache_hit_writeback(part_matrices[slot], sizeof(part_matrices[slot]));
#ifdef BG_PROFILE
    matrix_us = get_ticks_us() - begin;
#endif
}
static void update_effects(float dt) {
    if (bg_match_time() <= dt + .00001f)
        reset_view_state();
    bg_fx_update(dt);
    for (unsigned i = 0; i < bg_vehicle_count; i++)
        wheel_rotation[i] = bg_vehicles[i].wheel_phase;
    for (unsigned i = 0; i < bg_event_count; i++)
        if (bg_events[i].kind == BG_EVENT_FIRE && bg_events[i].player >= 0 &&
            bg_events[i].player < 4)
            fired_at[bg_events[i].player] = game_time;
}
static void prepare_view(unsigned p) {
    int w = views >= 3 ? 160 : 320, h = views == 1 ? 240 : 120, x = views >= 3 ? (p % 2) * 160 : 0,
        y = views == 1 ? 0 : (views >= 3 ? p / 2 : p) * 120;
    bg_player *player = &bg_players[p];
    float cp = cosf(player->pitch), sy = sinf(player->yaw), cy = cosf(player->yaw);
    float head = bg_eye_height(player);
    T3DVec3 eye = {
        {player->pos[0] * BG_SCALE, (player->pos[1] + head) * BG_SCALE, player->pos[2] * BG_SCALE}};
    T3DVec3 target = {{eye.v[0] + cy * cp, eye.v[1] + sinf(player->pitch), eye.v[2] - sy * cp}};
    if (player->vehicle >= 0 && !bg_player_third_person(player)) {
        float camera[3];
        bg_vehicle_camera_position(&bg_vehicles[player->vehicle], player->seat, camera);
        for (unsigned a = 0; a < 3; a++)
            eye.v[a] = camera[a] * BG_SCALE;
        target =
            (T3DVec3){{eye.v[0] + cy * cp, eye.v[1] + sinf(player->pitch), eye.v[2] - sy * cp}};
    }
    if (bg_player_third_person(player)) {
        const bg_vehicle *vehicle = &bg_vehicles[player->vehicle];
        const bg_camera_track *track = &bg_camera_tracks[vehicle->kind][player->seat];
        float origin[3], offset[3];
        /* units.c: unnamed vehicle camera markers use the hull origin. */
        bg_vehicle_transform(vehicle, track->origin, origin);
        bg_camera_track_offset(track, player->yaw, player->pitch, offset);
        float length = sqrtf(offset[0] * offset[0] + offset[1] * offset[1] + offset[2] * offset[2]);
        float direction[3];
        for (unsigned a = 0; a < 3; a++)
            direction[a] = offset[a] / fmaxf(length, .001f);
        /* Shared terrain search for five near-plane probes, plus neighboring hulls. */
        float distance = bg_camera_clearance(origin, direction, length, player->vehicle);
        for (unsigned a = 0; a < 3; a++)
            eye.v[a] = (origin[a] + direction[a] * distance) * BG_SCALE;
        /* Mounted weapons start one unit ahead of the player's aim origin.
         * Follow that pitch-aware trajectory so the reticle tracks the shot. */
        float aim_direction[3] = {cy * cp, sinf(player->pitch), -sy * cp};
        float muzzle[3] = {player->pos[0], player->pos[1] + bg_eye_height(player), player->pos[2]};
        for (unsigned a = 0; a < 3; a++)
            muzzle[a] += aim_direction[a];
        float aim_distance = fmaxf(2.f, bg_raycast(muzzle, aim_direction, 150.f));
        for (unsigned a = 0; a < 3; a++)
            target.v[a] = (muzzle[a] + aim_direction[a] * aim_distance) * BG_SCALE;
    } else if (player->health <= 0) {
        /* Pull the death view away from the corpse. If the wall behind it is
         * close, choose a clear shoulder direction before placing the camera. */
        const float directions[3][3] = {{-cy * .82f, .572f, sy * .82f},
                                        {sy * .82f, .572f, cy * .82f},
                                        {-sy * .82f, .572f, -cy * .82f}};
        float origin[3] = {player->pos[0], player->pos[1] + .5f, player->pos[2]};
        unsigned direction = 0;
        float distance = bg_raycast(origin, directions[0], 2.f) - .1f;
        if (distance < .75f)
            for (unsigned d = 1; d < 3; d++) {
                float candidate = bg_raycast(origin, directions[d], 2.f) - .1f;
                if (candidate > distance) {
                    direction = d;
                    distance = candidate;
                }
            }
        if (distance < .2f)
            distance = .2f;
        for (unsigned a = 0; a < 3; a++) {
            eye.v[a] = (origin[a] + directions[direction][a] * distance) * BG_SCALE;
            target.v[a] = player->pos[a] * BG_SCALE;
        }
        target.v[1] += .3f * BG_SCALE;
    }
#ifdef BG_MODEL_QA
    bg_qa_camera(p, &eye, &target);
#endif
#ifdef BG_INTERACTION_QA
    bg_qa_interaction_camera(p, &eye, &target);
#endif
#ifdef BG_SHIELD_QA
    const float angle = (BG_SHIELD_QA == 1 ? 2.5f : .6f);
    eye = (T3DVec3){{(player->pos[0] + cosf(angle) * 1.7f) * BG_SCALE,
                     (player->pos[1] + .7f) * BG_SCALE,
                     (player->pos[2] + sinf(angle) * 1.7f) * BG_SCALE}};
    target = (T3DVec3){
        {player->pos[0] * BG_SCALE, (player->pos[1] + .38f) * BG_SCALE, player->pos[2] * BG_SCALE}};
#endif
    T3DViewport *vp = &viewports[slot][p];
    t3d_viewport_set_area(vp, x, y, w, h);
#ifdef BG_GUARDBAND4
    /* Tiny3D supports factors 1–4. Enlarge only the clipping guard band;
     * projection, viewport scissor and full triangle clipping stay active. */
    vp->guardBandScale = views >= 3 ? 4 : 2;
#endif
    float fov = views == 2 ? .72f : 1.08f;
    bool scoped = player->health > 0 && player->zoom;
    if (scoped)
        fov = bg_camera_zoom_fov(fov, player->weapon == BG_W_SNIPER && player->zoom == 2 ? 10 : 2);
    float near, far;
    bg_camera_depth(scoped, &near, &far);
    t3d_viewport_set_projection(vp, fov, near, far);
    /* Tiny3D rounds viewport scales to integers after W normalization. At
     * far=6200, 160x120 becomes scales 3/-2; changing far changes framing.
     * 1/512 gives exact 20/-15 (40/-30 full screen) and exact 16-bit W/depth
     * factors. Keep it independent of clipping distance and zoom. */
    t3d_viewport_set_w_normalize(vp, 0, BG_CAMERA_NORMALIZE_SUM);
    bg_hud_aim_projection(vp->matProj.m, views, p);
    t3d_viewport_look_at(vp, &eye, &target, &(T3DVec3){{0, 1, 0}});
    bg_visibility_side_planes((float (*)[4])vp->viewFrustum.planes, vp->matCamProj.m, w, h);
    /* Camera-space arms cross the world's near plane. Give the foreground
     * its own projection and depth range, while preserving FOV and aim offset.
     * Separate slot storage keeps queued RSP camera matrices immutable. */
    T3DViewport *gun_vp = &gun_viewports[slot][p];
    *gun_vp = *vp;
    t3d_viewport_set_projection(gun_vp, fov, .125f, 128.f);
    t3d_viewport_set_w_normalize(gun_vp, 0, BG_CAMERA_NORMALIZE_SUM);
    bg_hud_aim_projection(gun_vp->matProj.m, views, p);
    view_eyes[p] = eye;
    held_masks[p] = 0;
    for (unsigned j = 0; j < views; j++) {
        bg_player *q = &bg_players[j];
        body_lods[p][j] = 0;
        if (bg_player_visibility(q) <= 0)
            continue;
#if !defined(BG_MODEL_QA) && !defined(BG_INTERACTION_QA) && !defined(BG_SHIELD_QA)
        if (j == p && !bg_player_third_person(player) && player->health > 0)
            continue;
#endif
        if (q->vehicle >= 0 && bg_vehicles[q->vehicle].kind == BG_V_BANSHEE &&
            q->seat_state == BG_SEAT_STABLE)
            continue;
        float distance = 0;
        for (unsigned a = 0; a < 3; a++) {
            float d = q->pos[a] - eye.v[a] / BG_SCALE;
            distance += d * d;
        }
        bool personal = bg_player_personal_weapon(q);
        bool held = (distance <= 16 || player->zoom) && q->health > 0 && personal;
        if (visible_bounds(vp, &body_bounds[j])) {
            unsigned lod = distance > (views >= 3 ? 4.f : 16.f) && player->zoom == 0;
            body_lods[p][j] = lod + 1;
            wanted_lods[j] |= 1u << lod;
        }
        if (held && visible_bounds(vp, &held_bounds[j])) {
            held_masks[p] |= 1u << j;
            wanted_held |= 1u << j;
        }
    }
    for (unsigned i = 0; i < bg_vehicle_count; i++) {
        const bg_vehicle *v = &bg_vehicles[i];
        vehicle_view_lods[p][i] = 0;
        if (!bg_vehicle_body_visible(v) || !visible_bounds(vp, &vehicle_bounds[i]))
            continue;
        float distance = 0;
        for (unsigned a = 0; a < 3; a++) {
            float d = v->pos[a] - eye.v[a] / BG_SCALE;
            distance += d * d;
        }
        unsigned lod = distance > 36 && player->zoom == 0;
        if (v->active && (v->kind == BG_V_BANSHEE || v->kind == BG_V_SCORPION) &&
            v->occupants[0] >= 0 && (!v->hatch_closing || v->hatch < 1))
            lod = 0;
        if (lod && vehicle_micro_available[v->kind] &&
            bg_micro_lod_below(&vehicle_micro_spheres[i], vp->matCamera.m, vp->matProj.m,
                               vp->size[0], vp->size[1], 1.4f, BG_MICRO_PIXELS, true,
                               player->zoom != 0, views))
            lod = 2;
        vehicle_view_lods[p][i] = lod + 1;
    }
    for (unsigned i = 0; i < bg_pickup_count; i++) {
        pickup_visible[p][i] = bg_pickups[i].active && visible_bounds(vp, &pickup_bounds[i]);
        if (pickup_visible[p][i])
            bg_pickup_mark_visible(i);
    }
}
static void draw_view(unsigned p) {
    T3DViewport *vp = &viewports[slot][p];
    T3DVec3 eye = view_eyes[p];
    bg_player *player = &bg_players[p];
#ifdef BG_PROFILE
    uint64_t begin = get_ticks_us();
    unsigned before = triangles, animation_before = animation_us;
#endif
    t3d_viewport_attach(vp);
    bg_sky_draw(vp);
    triangles += 16;
    t3d_frame_start();
    rdpq_mode_dithering(DITHER_NONE_NONE);
    t3d_light_set_ambient((uint8_t[]){255, 255, 255, 255});
    t3d_light_set_count(0);
    rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);
    rdpq_mode_persp(true);
    rdpq_mode_filter(FILTER_BILINEAR);
    t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_TEXTURED |
                            T3D_FLAG_CULL_FRONT);
    t3d_matrix_push(&terrain_matrix);
    unsigned bound = ~0u;
    bool palette_mode = false, overlay_mode = false;
    for (unsigned b = 0; b < bg_chunk_count; b++) {
        const bg_chunk *c = &bg_chunks[b];
        if (!t3d_frustum_vs_aabb_s16(&vp->viewFrustum, c->bounds, c->bounds + 3))
            continue;
        if (bound != c->material) {
            bool overlay = bg_texture_overlay[c->material];
            if (overlay != overlay_mode) {
                rdpq_mode_begin();
                rdpq_mode_zbuf(true, !overlay);
                rdpq_mode_alphacompare(overlay ? 128 : 0);
                rdpq_mode_blender(0);
                rdpq_mode_antialias(overlay ? AA_NONE : AA_STANDARD);
                __rdpq_mode_change_som(SOM_ZMODE_MASK,
                                       overlay ? SOM_ZMODE_TRANSPARENT : SOM_ZMODE_OPAQUE);
                rdpq_mode_end();
                overlay_mode = overlay;
            }
            bool paletted = bg_texture_ci4[c->material];
            if (paletted != palette_mode) {
                rdpq_mode_tlut(paletted ? TLUT_RGBA16 : TLUT_NONE);
                palette_mode = paletted;
            }
            if (paletted)
                rdpq_tex_upload_tlut((uint16_t *)bg_ground_palette, 0, 16);
            rdpq_tex_upload(
                TILE0, &textures[c->material],
                &(rdpq_texparms_t){.s.repeats = REPEAT_INFINITE, .t.repeats = REPEAT_INFINITE});
            bound = c->material;
        }
        rspq_block_run(world_blocks[b]);
        triangles += c->index_count / 3;
#ifdef BG_PROFILE
        submitted_vertices += (c->count + 1) & ~1u;
#endif
    }
    t3d_matrix_pop(1);
    if (overlay_mode) {
        rdpq_mode_begin();
        rdpq_mode_zbuf(true, true);
        rdpq_mode_alphacompare(0);
        rdpq_mode_blender(0);
        rdpq_mode_antialias(AA_STANDARD);
        __rdpq_mode_change_som(SOM_ZMODE_MASK, SOM_ZMODE_OPAQUE);
        rdpq_mode_end();
    }
    if (palette_mode)
        rdpq_mode_tlut(TLUT_NONE);
    /* Extracted model faces are outward-wound. Terrain uses its own winding. */
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK);
    /* Every object matrix below is already in world space, including vehicle
     * parts, held weapons and first person. Reserve one sibling stack entry:
     * matrix_set(...,true) always multiplies the unchanged camera entry below
     * it, avoiding a redundant camera reload/normalization between objects. */
    /* Writes do not wake a sleeping RSP. The depth-clear flush may have
     * drained before this terrain batch; start it while objects are queued. */
    rspq_flush();
    t3d_matrix_push_pos(1);
    bg_fx_draw_begin(slot, p, vp, &eye);
#ifdef BG_PROFILE
    world_us += get_ticks_us() - begin;
    begin = get_ticks_us();
    category_triangles[0] += triangles - before;
    before = triangles;
#endif
    for (unsigned i = 0; i < bg_vehicle_count; i++)
        if (vehicle_view_lods[p][i]) {
            bg_vehicle *v = &bg_vehicles[i];
            bool wreck = !v->active;
            if (wreck) {
                rdpq_sync_pipe();
                rdpq_set_prim_color(RGBA32(75, 70, 66, 255));
                rdpq_mode_combiner(RDPQ_COMBINER1((SHADE, 0, PRIM, 0), (0, 0, 0, 1)));
            }
            if (wreck && (v->kind == BG_V_GHOST || v->kind == BG_V_BANSHEE) &&
                vehicle_view_lods[p][i] < 3) {
                unsigned m = v->kind == BG_V_BANSHEE;
                /* Burned source shaders already supply the correct diffuse colors. */
                rdpq_sync_pipe();
                rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
                t3d_matrix_set(&vehicle_matrices[slot][i], true);
                rspq_block_run(covenant_wreck_blocks[m]);
                triangles += bg_covenant_wrecks[m].triangle_count;
#ifdef BG_PROFILE
                submitted_vertices +=
                    model_load_count(&bg_covenant_wrecks[m], bg_covenant_wrecks[m].vertex_count, 0,
                                     bg_covenant_wrecks[m].batch_count);
#endif
            } else if (vehicle_view_lods[p][i] >= 2) {
                bool micro = vehicle_view_lods[p][i] == 3;
                t3d_matrix_set(&vehicle_matrices[slot][i], true);
                rspq_block_run(micro ? vehicle_micro_blocks[v->kind] : vehicle_lods[v->kind]);
                triangles += micro ? bg_vehicle_micro_lods[v->kind]->triangle_count
                                   : bg_vehicle_lods[v->kind].triangle_count;
#ifdef BG_PROFILE
                submitted_vertices +=
                    micro ? vehicle_micro_vertex_loads[v->kind] : vehicle_vertex_loads[v->kind];
#endif
            } else {
                const bg_vehicle_rig *rig = &bg_vehicle_rigs[v->kind];
                for (unsigned j = 0; j < rig->count; j++) {
                    if (!visible_bounds(vp, &vehicle_part_bounds[i][j]))
                        continue;
                    t3d_matrix_set(&part_matrices[slot][i][j], true);
                    rspq_block_run(vehicle_parts[v->kind][j]);
                    triangles += rig->parts[j].count / 3;
#ifdef BG_PROFILE
                    submitted_vertices += part_vertex_loads[v->kind][j];
#endif
                }
            }
            if (wreck) {
                rdpq_sync_pipe();
                rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
            }
        }
#ifdef BG_PROFILE
    category_triangles[1] += triangles - before;
    before = triangles;
#endif
    for (unsigned j = 0; j < views; j++) {
        if (body_lods[p][j] || (held_masks[p] & (1u << j)))
            ensure_player_animation(j);
        float opacity = bg_player_visibility(&bg_players[j]);
        bool fading =
            opacity > 0 && opacity < 1 && (body_lods[p][j] || (held_masks[p] & (1u << j)));
        if (fading) {
            rdpq_sync_pipe();
            rdpq_set_env_color(RGBA32(255, 255, 255, (unsigned)(opacity * 255)));
            rdpq_mode_begin();
            rdpq_mode_antialias(AA_NONE);
            rdpq_mode_alphacompare(-1);
            rdpq_mode_combiner(RDPQ_COMBINER1((0, 0, 0, SHADE), (0, 0, 0, ENV)));
            rdpq_mode_end();
        }
        if (body_lods[p][j]) {
            bool lod = body_lods[p][j] == 2;
            float shield = bg_shield_glow(&bg_players[j]);
            if (shield > 0) {
                /* One-pass bounded color glow: no duplicate skinned shell,
                 * extra triangles, transparent sorting, or z fighting. */
                unsigned intensity =
                    (unsigned)(shield * (.48f + .04f * sinf(game_time * 31 + j)) * 255);
                rdpq_sync_pipe();
                rdpq_set_prim_color(RGBA32(255, 139, 62, intensity));
                if (fading)
                    rdpq_mode_combiner(
                        RDPQ_COMBINER1((PRIM, SHADE, PRIM_ALPHA, SHADE), (0, 0, 0, ENV)));
                else
                    rdpq_mode_combiner(
                        RDPQ_COMBINER1((PRIM, SHADE, PRIM_ALPHA, SHADE), (0, 0, 0, SHADE)));
            }
            t3d_matrix_set(&transforms[slot][j], true);
            rspq_block_run(lod ? armor_lod_blocks[slot][j] : player_blocks[slot][j]);
            triangles +=
                lod ? bg_spartan_lod.triangle_count : bg_model_assets[BG_M_SPARTAN].triangle_count;
            if (shield > 0) {
                rdpq_sync_pipe();
                if (fading)
                    rdpq_mode_combiner(RDPQ_COMBINER1((0, 0, 0, SHADE), (0, 0, 0, ENV)));
                else
                    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
            }
#ifdef BG_PROFILE
            submitted_vertices += lod ? spartan_lod_vertex_loads : model_vertex_loads[BG_M_SPARTAN];
#endif
        }
        if (held_masks[p] & (1u << j))
            small_model_instance(weapon_model(bg_players[j].weapon), &held_matrices[slot][j], vp,
                                 &eye, player->zoom != 0, NULL);
        if (fading) {
            rdpq_sync_pipe();
            rdpq_mode_begin();
            rdpq_mode_alphacompare(0);
            rdpq_mode_antialias(AA_STANDARD);
            rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
            rdpq_mode_end();
        }
    }
#ifdef BG_PROFILE
    category_triangles[2] += triangles - before;
    before = triangles;
#endif
    for (unsigned i = 0; i < bg_pickup_count; i++) {
        bg_pickup *q = &bg_pickups[i];
        if (!pickup_visible[p][i])
            continue;
        unsigned model = pickup_model(q->weapon);
        small_model_instance(model, &pickup_matrices[slot][i], vp, &eye, player->zoom != 0,
                             &pickup_micro_spheres[i]);
    }
#ifdef BG_PROFILE
    category_triangles[3] += triangles - before;
    before = triangles;
#endif
    t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH);
    for (unsigned i = 0; i < BG_MAX_PROJECTILES; i++) {
        bg_projectile *q = bg_projectile_at(i);
        if (!q || !q->active || !visible_bounds(vp, &projectile_bounds[i]))
            continue;
        if (q->kind == BG_P_FRAG || q->kind == BG_P_PLASMA_GRENADE) {
            instance(q->kind == BG_P_FRAG ? BG_M_FRAG : BG_M_PLASMA_GRENADE,
                     &projectile_matrices[slot][i]);
            continue;
        }
        t3d_matrix_set(&projectile_matrices[slot][i], true);
        rspq_block_run(particle_blocks[q->kind]);
        triangles += 8;
#ifdef BG_PROFILE
        submitted_vertices += 24;
#endif
    }
    unsigned fx_triangles = bg_fx_draw_blasts();
    fx_triangles += bg_fx_draw_trails(game_time);
    for (unsigned j = 0; j < views; j++)
        if (held_masks[p] & (1u << j))
            fx_triangles +=
                bg_fx_draw_weapon(j, &held_matrices[slot][j], BG_OBJECT_SCALE, false, game_time);
    fx_triangles += bg_fx_draw_vehicle_destruction();
    fx_triangles += bg_fx_draw_shield_breaks(p);
    triangles += fx_triangles;
#ifdef BG_PROFILE
    submitted_vertices += fx_triangles * 2;
#endif
#ifdef BG_PROFILE
    object_us += get_ticks_us() - begin - (animation_us - animation_before);
    begin = get_ticks_us();
    animation_before = animation_us;
    category_triangles[4] += triangles - before;
    before = triangles;
#endif
    if (player->health > 0 && bg_player_personal_weapon(player) &&
        !bg_player_third_person(player) && !player->zoom
#ifdef BG_INTERACTION_QA
        && BG_INTERACTION_QA < 2
#endif
#ifdef BG_SHIELD_QA
        && false
#endif
#ifdef BG_DESTRUCTION_QA
        && false /* Inspection cameras omit the viewmodel, preserving world effects. */
#endif
#ifdef BG_MODEL_QA
        && bg_qa_firstperson()
#endif
    ) {
        ensure_firstperson_animation(p);
        float pos[3] = {eye.v[0] / BG_SCALE, eye.v[1] / BG_SCALE + sinf(player->gait) * .007f,
                        eye.v[2] / BG_SCALE};
        matrix(&guns[slot][p], BG_SCALE / BG_FP_SCALE, player->yaw, player->pitch, pos);
        data_cache_hit_writeback(&guns[slot][p], sizeof(T3DMat4FP));
        /* Clear only this viewport's depth so the gun stays in front of the world,
         * while its own surfaces and hands still occlude each other. */
        rdpq_clear_z(ZBUF_MAX);
        t3d_viewport_attach(&gun_viewports[slot][p]);
        t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK);
        rdpq_mode_zbuf(true, true);
        t3d_segment_set(T3D_SEGMENT_1, firstperson[slot][p]);
        if (player->weapon == BG_W_PISTOL || player->weapon == BG_W_ROCKET) {
            surface_t atlas =
                surface_make_linear((void *)(player->weapon == BG_W_ROCKET ? bg_fp_rocket_texture
                                                                           : bg_fp_pistol_texture),
                                    FMT_RGBA16, 64, 32);
            rdpq_sync_pipe();
            rdpq_mode_tlut(TLUT_NONE);
            rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);
            rdpq_mode_persp(true);
            rdpq_mode_filter(FILTER_POINT);
            rdpq_mode_alphacompare(player->weapon == BG_W_ROCKET ? 128 : 0);
            rdpq_sync_tile();
            rdpq_sync_load();
            rdpq_tex_upload(TILE0, &atlas, NULL);
            t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK |
                                    T3D_FLAG_TEXTURED);
        }
        t3d_matrix_set(&guns[slot][p], true);
        rspq_block_run(firstperson_blocks[player->weapon]);
        triangles += bg_fp_models[player->weapon].triangle_count;
        if (player->weapon == BG_W_PISTOL || player->weapon == BG_W_ROCKET) {
            rdpq_sync_pipe();
            rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
            rdpq_mode_alphacompare(0);
            t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_DEPTH | T3D_FLAG_CULL_BACK);
        }
#ifdef BG_PROFILE
        submitted_vertices += fp_vertex_loads[player->weapon];
#endif
        if (player->weapon == BG_W_AR) {
            bg_fp_ammo_draw(slot, p);
            triangles += 4;
#ifdef BG_PROFILE
            submitted_vertices += 8;
#endif
        }
        const bg_fp_detail_asset *detail = &bg_fp_details[player->weapon];
        if (detail->vertices) {
            /* Thin weapon display topology, with finer coordinates and real
             * depth testing. It remains occluded by the gun/hands in motion. */
            matrix(&scope_matrices[slot][p], BG_SCALE / 4096.f, player->yaw, player->pitch, pos);
            data_cache_hit_writeback(&scope_matrices[slot][p], sizeof(T3DMat4FP));
            t3d_matrix_set(&scope_matrices[slot][p], true);
            t3d_vert_load(scope_vertices[slot][p], 0, (detail->vertices + 1) & ~1u);
            for (unsigned v = 0; v < detail->triangles * 3; v += 3)
                t3d_tri_draw(detail->indices[v], detail->indices[v + 1], detail->indices[v + 2]);
            t3d_tri_sync();
            triangles += detail->triangles;
#ifdef BG_PROFILE
            submitted_vertices += detail->vertices;
#endif
        }
        unsigned flash_triangles =
            bg_fx_draw_weapon(p, &guns[slot][p], BG_FP_SCALE, true, game_time);
        triangles += flash_triangles;
#ifdef BG_PROFILE
        submitted_vertices += flash_triangles * 2;
#endif
    }
#ifdef BG_PROFILE
    fp_us += get_ticks_us() - begin - (animation_us - animation_before);
    category_triangles[5] += triangles - before;
#endif
    /* Restore depth zero before the next viewport replaces camera/projection. */
    t3d_matrix_pop(1);
}

/* No wrapper changes numeric work or the order of recorded GPU commands. */
color_t bg_scene_team_color(unsigned player) {
    return colors[player];
}
void bg_scene_init(void) {
    init_scene();
}
void bg_scene_reset(void) {
    reset_view_state();
}
void bg_scene_fired(unsigned player, float seconds) {
    fired_at[player] = seconds;
}
void bg_scene_update(float dt, float seconds) {
    game_time = seconds;
    update_effects(dt);
}
void bg_scene_load_bodies(void) {
    body_buffers_load();
}
void bg_scene_load_firstperson(void) {
    firstperson_buffers_load();
}
void bg_scene_release_bodies(void) {
    body_buffers_release();
}
void bg_scene_release_firstperson(void) {
    firstperson_buffers_release();
}
void bg_scene_prepare(unsigned frame_slot, unsigned view_count, float seconds) {
    slot = frame_slot;
    views = view_count;
    game_time = seconds;
    prepare_frame();
    triangles = 0;
}
unsigned bg_scene_draw(unsigned player) {
    draw_view(player);
    return triangles;
}
const T3DViewport *bg_scene_viewport(unsigned player) {
    return &viewports[slot][player];
}
void bg_scene_profile_changed(unsigned player) {
    const bg_model_asset *spartan = &bg_model_assets[BG_M_SPARTAN];
    for (unsigned s = 0; s < BG_FRAME_SLOTS; s++) {
        memcpy(armor[s][player], spartan->vertices, ((spartan->vertex_count + 1) & ~1u) * 16);
        tint_team(armor[s][player], spartan->vertex_count, bg_spartan_team_mask, player);
        memcpy(armor_lod[s][player], bg_spartan_lod.vertices,
               ((bg_spartan_lod.vertex_count + 1) & ~1u) * 16);
        tint_team(armor_lod[s][player], bg_spartan_lod.vertex_count, bg_spartan_lod_team_mask,
                  player);
        firstperson_weapon[s][player] = -1;
    }
}
