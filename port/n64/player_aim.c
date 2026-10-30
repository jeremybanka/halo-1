#include "player_aim.h"
#include "player_animation.h"
#include "blam/runtime.h"
#include "interaction.h"
#include "movement.h"
#include <assert.h>
#include <math.h>
#include <string.h>
#ifdef N64
#include <libdragon.h>
#else
#include <stdio.h>
#endif

/* Two small node frames, independent of mesh complexity. The ROM bank never
 * becomes resident, and skinning is deferred until a view actually needs it. */
static uint8_t frames[544] __attribute__((aligned(16)));
static void read_frames(uint32_t offset, unsigned bytes) {
    static uint32_t previous = UINT32_MAX;
    static unsigned previous_bytes;
    assert(bytes <= sizeof(frames));
    if (offset == previous && bytes == previous_bytes)
        return;
#ifdef N64
    static uint32_t rom, size;
    if (!rom) {
        rom = dfs_rom_addr("player-animation.bin");
        size = dfs_rom_size("player-animation.bin");
    }
    assert(rom && offset + bytes <= size);
    data_cache_hit_invalidate(frames, bytes);
    dma_read(frames, rom + offset, bytes);
#else
    static FILE *file;
    if (!file)
        file = fopen("build/n64/frontend-files/player-animation.bin", "rb");
    assert(file && !fseek(file, offset, SEEK_SET));
    assert(fread(frames, 1, bytes, file) == bytes);
#endif
    previous = offset;
    previous_bytes = bytes;
}
static int short_at(const uint8_t *p) { return (int16_t)((unsigned)p[0] * 256 + p[1]); }
static float pin(float x, float lo, float hi) { return fminf(hi, fmaxf(lo, x)); }
static void blend_channels(bg_node_pose *a, const bg_node_pose *b, float weight,
                           uint32_t rotations, uint32_t translations) {
    for (unsigned i = 0; i < BG_PLAYER_NODES; i++) {
        if (rotations & (1u << i))
            blam_quaternions_interpolate_and_normalize(a[i].q, b[i].q, weight, a[i].q);
        if (translations & (1u << i))
            for (unsigned k = 0; k < 3; k++)
                a[i].p[k] += (b[i].p[k] - a[i].p[k]) * weight;
    }
}
static void sample_channels(int index, float frame, bg_node_pose *out,
                            uint32_t rotations, uint32_t translations) {
    assert(index >= 0);
    const bg_node_clip *clip = &bg_player_node_clips[index];
    frame = pin(frame, 0, clip->frames - 1);
    unsigned f0 = frame;
    float fraction = frame - f0;
    unsigned f1 = fraction > 0 && f0 + 1 < clip->frames ? f0 + 1 : f0;
    read_frames(clip->offset + f0 * clip->stride, clip->stride * (f0 == f1 ? 1 : 2));
    for (unsigned i = 0; i < BG_PLAYER_NODES; i++) {
        const uint8_t *a = frames + i * 14, *b = a + (f0 == f1 ? 0 : clip->stride);
        if (rotations & (1u << i)) {
            float q0[4], q1[4];
            for (unsigned k = 0; k < 4; k++) {
                q0[k] = short_at(a + k * 2) / 32767.f;
                q1[k] = short_at(b + k * 2) / 32767.f;
            }
            blam_quaternions_interpolate_and_normalize(q0, q1, fraction, out[i].q);
        }
        if (translations & (1u << i))
            for (unsigned k = 0; k < 3; k++) {
                int lo = short_at(a + 8 + k * 2), hi = short_at(b + 8 + k * 2);
                out[i].p[k] = (lo + (hi - lo) * fraction) / 4096.f;
            }
    }
}
void bg_player_sample_nodes(int index, float frame, bg_node_pose *out) {
    sample_channels(index, frame, out, UINT32_MAX, UINT32_MAX);
}
static void sample_action(int index, float frame, bg_node_pose *out) {
    const bg_node_clip *clip = &bg_player_node_clips[index];
    sample_channels(index, frame, out, clip->rotations, clip->translations);
}
static void multiply_quaternions(const float a[4], const float b[4], float out[4]) {
    float x = a[0], y = a[1], z = a[2], w = a[3];
    float X = b[0], Y = b[1], Z = b[2], W = b[3];
    out[0] = w * X + x * W + y * Z - z * Y;
    out[1] = w * Y + y * W + z * X - x * Z;
    out[2] = w * Z + z * W + x * Y - y * X;
    out[3] = w * W - x * X - y * Y - z * Z;
}
void bg_player_apply_nodes(bg_node_pose *base, const bg_node_pose *delta, int index) {
    if (index < 0)
        return;
    const bg_node_clip *clip = &bg_player_node_clips[index];
    for (unsigned i = 0; i < BG_PLAYER_NODES; i++) {
        if (clip->rotations & (1u << i)) {
            if (clip->type == 1)
                multiply_quaternions(delta[i].q, base[i].q, base[i].q);
            else
                memcpy(base[i].q, delta[i].q, sizeof(base[i].q));
        }
        if (clip->translations & (1u << i))
            for (unsigned k = 0; k < 3; k++)
                base[i].p[k] = clip->type == 1 ? base[i].p[k] + delta[i].p[k] : delta[i].p[k];
    }
}
/* source/models/model_animations.c:aiming_screen_apply. Negative angles
 * floor toward the preceding cell; interpolation is yaw, then pitch. */
static float screen_frame(float angle, const float delta[2], const uint8_t count[2]) {
    float step = delta[angle >= 0];
    return pin(step == 0 ? 0 : angle / step, -(float)count[0], count[1]) + count[0];
}
void bg_player_apply_aim(bg_node_pose *base, int index, const bg_aim_screen *screen,
                         float yaw, float pitch) {
    if (index < 0)
        return;
    unsigned width = screen->yaw_count[0] + screen->yaw_count[1] + 1;
    unsigned height = screen->pitch_count[0] + screen->pitch_count[1] + 1;
    const bg_node_clip *clip = &bg_player_node_clips[index];
    if (clip->type != 1 || clip->frames < width * height)
        return;
    float x = screen_frame(yaw, screen->yaw, screen->yaw_count);
    float y = screen_frame(pitch, screen->pitch, screen->pitch_count);
    unsigned y0 = y, y1 = y0 + 1 < height ? y0 + 1 : y0;
    bg_node_pose lower[BG_PLAYER_NODES], upper[BG_PLAYER_NODES];
    /* A fractional row index samples adjacent yaw cells with CE's nlerp. */
    sample_action(index, y0 * width + x, lower);
    if (y != y0) {
        sample_action(index, y1 * width + x, upper);
        blend_channels(lower, upper, y - y0, clip->rotations, clip->translations);
    }
    bg_player_apply_nodes(base, lower, index);
}
static void matrix_from_pose(bg_node_matrix *out, const bg_node_pose *p) {
    const float x = p->q[0], y = p->q[1], z = p->q[2], w = p->q[3];
    /* JMS rotations are conjugated at the model boundary. */
    *out = (bg_node_matrix){{{1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w), p->p[0]},
                            {2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w), p->p[1]},
                            {2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y), p->p[2]}}};
}
static void matrix_multiply(bg_node_matrix *out, const bg_node_matrix *a, const bg_node_matrix *b) {
    bg_node_matrix result;
    for (unsigned r = 0; r < 3; r++)
        for (unsigned c = 0; c < 4; c++) {
            result.m[r][c] = c == 3 ? a->m[r][3] : 0;
            for (unsigned k = 0; k < 3; k++)
                result.m[r][c] += a->m[r][k] * b->m[k][c];
        }
    *out = result;
}
typedef struct {
    int base[2], action[2], aim[2];
    float base_frame[2], action_frame[2], crouch, pitch;
} pose_key;
typedef struct { bool valid; uint32_t revision; pose_key key; bg_node_matrix nodes[BG_PLAYER_NODES]; } pose_cache;
static pose_cache cache[BG_PLAYERS];
bool bg_player_uses_node_pose(const bg_player *p) { return p->health > 0 && p->vehicle < 0; }
static float time_frame(int index, float seconds, bool loop) {
    if (index < 0)
        return 0;
    const bg_node_clip *clip = &bg_player_node_clips[index];
    float phase = fmaxf(0, seconds / clip->duration);
    phase = loop ? phase - floorf(phase) : fminf(phase, 1);
    return phase * (clip->frames - 1);
}
static pose_key select_pose(const bg_player *p) {
    pose_key key = {0};
    bool moving = hypotf(p->velocity[0], p->velocity[2]) > .15f;
    unsigned state = BG_PA_IDLE;
    float seconds = p->locomotion_time;
    bool loop = true;
    if (!p->grounded) {
        state = BG_PA_AIR;
        seconds = p->airborne_time;
    } else if (p->landing_time > 0) {
        state = p->hard_landing ? BG_PA_HARD : BG_PA_SOFT;
        seconds = p->landing_duration - p->landing_time;
        loop = false;
    } else if (moving) {
        state = BG_PA_FRONT;
        seconds = p->locomotion_time;
    }
    int action = -1;
    float progress = -1;
    if (p->weapon_ready > 0) {
        action = BG_PA_READY;
        progress = 1 - p->weapon_ready / bg_ready_times[p->weapon];
    } else if (p->melee_time > 0) {
        action = BG_PA_MELEE;
        progress = p->anim_time / fmaxf(.001f, p->anim_time + p->melee_time);
    } else if (p->grenade_cooldown > .55f) {
        action = BG_PA_THROW;
        progress = (.9f - p->grenade_cooldown) / .35f;
    } else if (p->reload > 0) {
        action = BG_PA_RELOAD;
        if (p->reload_duration > 0)
            progress = 1 - p->reload / p->reload_duration;
    } else if (bg_player_body_firing(p)) {
        action = BG_PA_FIRE;
        progress = bg_player_body_fire_frame(p) / (BG_BODY_FIRE_FRAMES - 1);
    }
    for (unsigned stance = 0; stance < 2; stance++) {
        const bg_player_anim_set *set = &bg_player_anim_sets[stance][p->weapon];
        key.base[stance] = set->clips[state];
        key.base_frame[stance] = time_frame(key.base[stance], seconds, loop);
        key.action[stance] = action < 0 ? -1 : set->clips[action];
        int index = key.action[stance];
        key.action_frame[stance] = index < 0 ? 0 : progress < 0 ? time_frame(index, p->anim_time, false)
                                                : pin(progress, 0, 1) * (bg_player_node_clips[index].frames - 1);
        key.aim[stance] = action == BG_PA_THROW || action == BG_PA_MELEE ? -1
                            : set->clips[moving && p->grounded ? BG_PA_AIM_MOVE : BG_PA_AIM_STILL];
    }
    key.crouch = pin(p->crouch_amount, 0, 1);
    key.pitch = p->pitch;
    return key;
}
const bg_node_matrix *bg_player_node_matrices(unsigned player) {
    const bg_player *p = &bg_players[player];
    pose_key key = select_pose(p);
    pose_cache *c = &cache[player];
    if (c->valid && !memcmp(&c->key, &key, sizeof(key)))
        return c->nodes;
    bg_node_pose pose[2][BG_PLAYER_NODES], delta[BG_PLAYER_NODES];
    for (unsigned stance = 0; stance < 2; stance++) {
        if ((stance == 0 && key.crouch == 1) || (stance == 1 && key.crouch == 0))
            continue;
        bg_player_sample_nodes(key.base[stance], key.base_frame[stance], pose[stance]);
        if (key.action[stance] >= 0) {
            sample_action(key.action[stance], key.action_frame[stance], delta);
            bg_player_apply_nodes(pose[stance], delta, key.action[stance]);
        }
        bg_player_apply_aim(pose[stance], key.aim[stance], &bg_player_anim_sets[stance][p->weapon].aim, 0, key.pitch);
        /* CE's look screen receives look minus aim, so normal aiming does
         * not tilt the head twice. Melee/throw have no weapon aiming screen. */
        bg_player_apply_aim(pose[stance], bg_player_look_clip, &bg_player_look_screen,
                             0, key.aim[stance] < 0 ? key.pitch : 0);
    }
    if (key.crouch == 1)
        memcpy(pose[0], pose[1], sizeof(pose[0]));
    else if (key.crouch > 0)
        blend_channels(pose[0], pose[1], key.crouch, UINT32_MAX, UINT32_MAX);
    for (unsigned i = 0; i < BG_PLAYER_NODES; i++) {
        matrix_from_pose(&c->nodes[i], &pose[0][i]);
        if (bg_player_parents[i] >= 0)
            matrix_multiply(&c->nodes[i], &c->nodes[bg_player_parents[i]], &c->nodes[i]);
    }
    c->key = key;
    c->valid = true;
    if (++c->revision == 0) c->revision = 1;
    return c->nodes;
}
uint32_t bg_player_pose_revision(unsigned player) {
    bg_player_node_matrices(player);
    return cache[player].revision;
}
static void transform(float out[3], const bg_node_matrix *m, const float p[3]) {
    for (unsigned a = 0; a < 3; a++)
        out[a] = m->m[a][3] + m->m[a][0] * p[0] + m->m[a][1] * p[1] + m->m[a][2] * p[2];
}
static int16_t round_point(float x) {
    /* Finite model coordinates are bounded far inside int16 range. Use the
     * hardware float-to-int instruction instead of libm's general lroundf. */
    return (int32_t)(x + (x < 0 ? -.5f : .5f));
}
static void quantize(int16_t out[3], const float p[3], float scale) {
    out[0] = round_point(p[0] * scale);
    out[1] = round_point(p[2] * scale);
    out[2] = round_point(-p[1] * scale);
}
void bg_player_skin_points(unsigned player, unsigned lod, int16_t (*out)[3]) {
    const bg_node_matrix *nodes = bg_player_node_matrices(player);
    const bg_player_skin *mesh = &bg_player_skins[lod];
    for (unsigned i = 0; i < mesh->count; i++) {
        const bg_skin_vertex *v = &mesh->vertices[i];
        if (!v->count) {
            memcpy(out[i], out[v->first], sizeof(out[i]));
            continue;
        }
        const bg_skin_weight *first = &mesh->weights[v->first];
        float result[3];
        transform(result, &nodes[first->node], first->p);
        if (v->count > 1)
            for (unsigned a = 0; a < 3; a++) result[a] *= first->weight;
        for (unsigned j = 1; j < v->count; j++) {
            const bg_skin_weight *w = &mesh->weights[v->first + j];
            float point[3];
            transform(point, &nodes[w->node], w->p);
            for (unsigned a = 0; a < 3; a++)
                result[a] += point[a] * w->weight;
        }
        quantize(out[i], result, 128);
    }
}
void bg_player_animated_hits(unsigned player, int16_t (*out)[3], unsigned count) {
    const bg_node_matrix *nodes = bg_player_node_matrices(player);
    for (unsigned i = 0; i < count; i++) {
        float point[3];
        transform(point, &nodes[bg_player_hit_bind[i].node], bg_player_hit_bind[i].p);
        quantize(out[i], point, 1024);
    }
}
void bg_player_hand_transform(unsigned player, bg_node_matrix *out) {
    const bg_node_matrix *nodes = bg_player_node_matrices(player);
    bg_node_matrix hand;
    matrix_multiply(&hand, &nodes[bg_player_hand_node], &bg_player_hand_marker);
    const unsigned axis[3] = {0, 2, 1};
    const float sign[3] = {1, 1, -1};
    for (unsigned a = 0; a < 3; a++) {
        for (unsigned b = 0; b < 3; b++)
            out->m[a][b] = hand.m[axis[a]][axis[b]] * sign[a] * sign[b];
        out->m[a][3] = hand.m[axis[a]][3] * sign[a];
    }
}
