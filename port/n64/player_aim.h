#ifndef BG_PLAYER_AIM_H
#define BG_PLAYER_AIM_H
#include "game.h"
#include "render_bounds.h"

/* CE node-local XYZW quaternions, with the original (Z-up) node basis.
 * Only the final skin/marker/collision output is converted to N64 Y-up. */
#define BG_PLAYER_NODES 19
typedef struct { float q[4], p[3]; } bg_node_pose;
typedef struct { float m[3][4]; } bg_node_matrix;
typedef struct {
    uint32_t offset, rotations, translations;
    uint16_t frames, stride;
    float duration;
    uint8_t type; /* 0 base, 1 overlay, 2 replacement */
} bg_node_clip;
typedef struct {
    float yaw[2], pitch[2];
    uint8_t yaw_count[2], pitch_count[2];
} bg_aim_screen;
enum { BG_PA_IDLE, BG_PA_FRONT, BG_PA_BACK, BG_PA_LEFT, BG_PA_RIGHT,
       BG_PA_AIR, BG_PA_SOFT, BG_PA_HARD, BG_PA_THROW, BG_PA_READY,
       BG_PA_AIM_STILL, BG_PA_AIM_MOVE, BG_PA_FIRE, BG_PA_RELOAD,
       BG_PA_MELEE, BG_PA_COUNT };
typedef struct { int16_t clips[BG_PA_COUNT]; bg_aim_screen aim; } bg_player_anim_set;
/* count == 0 reuses an earlier output vertex (normal/color seams). Each
 * influence is stored in its bone's bind space, avoiding inverse-bind work. */
typedef struct { uint16_t first; uint8_t count; } bg_skin_vertex;
typedef struct { float p[3], weight; uint8_t node; } bg_skin_weight;
typedef struct {
    const bg_skin_vertex *vertices;
    const bg_skin_weight *weights;
    unsigned count;
} bg_player_skin;
typedef struct { float p[3]; uint8_t node; } bg_hit_bind_vertex;
extern const int8_t bg_player_parents[BG_PLAYER_NODES];
extern const bg_node_matrix bg_player_inverse_bind[BG_PLAYER_NODES], bg_player_hand_marker;
extern const unsigned bg_player_hand_node;
extern const bg_node_clip bg_player_node_clips[];
extern const bg_player_anim_set bg_player_anim_sets[2][9];
extern const bg_player_skin bg_player_skins[2];
extern const bg_hit_bind_vertex bg_player_hit_bind[];
extern const int bg_player_look_clip;
extern const bg_aim_screen bg_player_look_screen;
extern const bg_bounds bg_player_aim_bounds;

/* Live on-foot poses only. Seated and dead bodies retain their authored clips. */
bool bg_player_uses_node_pose(const bg_player *player);
const bg_node_matrix *bg_player_node_matrices(unsigned player);
uint32_t bg_player_pose_revision(unsigned player);
void bg_player_skin_points(unsigned player, unsigned lod, int16_t (*out)[3]);
void bg_player_animated_hits(unsigned player, int16_t (*out)[3], unsigned count);
void bg_player_hand_transform(unsigned player, bg_node_matrix *out);

/* Exposed for source-equivalence/asset verification; no renderer dependency. */
void bg_player_sample_nodes(int clip, float frame, bg_node_pose *out);
void bg_player_apply_nodes(bg_node_pose *base,
                           const bg_node_pose *delta, int clip);
void bg_player_apply_aim(bg_node_pose *base, int clip,
                         const bg_aim_screen *screen, float yaw, float pitch);
#endif
