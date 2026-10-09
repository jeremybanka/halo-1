#ifndef BG_SCENE_H
#define BG_SCENE_H
#include <t3d/t3d.h>
#include "runtime_config.h"
/* Renderer owns slot-local vertices/matrices/viewports and ROM pose residency.
 * Caller MUST retire the slot's RSP fence before prepare; view drawing and HUD
 * reads finish before that slot is reused. Display ownership is independent. */
void bg_scene_init(void);
color_t bg_scene_team_color(unsigned player);
void bg_scene_reset(void);
void bg_scene_fired(unsigned player, float seconds);
void bg_scene_update(float dt, float seconds);
void bg_scene_load_bodies(void);
void bg_scene_load_firstperson(void);
void bg_scene_release_bodies(void);
void bg_scene_release_firstperson(void);
void bg_scene_profile_changed(unsigned player);
void bg_scene_prepare(unsigned frame_slot, unsigned views, float seconds);
unsigned bg_scene_draw(unsigned player);
const T3DViewport *bg_scene_viewport(unsigned player);
#ifdef BG_PROFILE
typedef struct {
    unsigned camera_us, animation_us, matrix_us, world_us, object_us, fp_us;
    unsigned submitted_vertices, animated_vertices, animated_tracks;
    unsigned category_triangles[6]; /* terrain, vehicles, bodies, pickups, effects, first person */
} bg_scene_metrics;
extern bg_scene_metrics bg_scene_profile;
#endif
#endif
