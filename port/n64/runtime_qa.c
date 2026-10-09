#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "runtime_config.h"
#include "game.h"
#include "combat.h"
#include "movement.h"
#include "view_camera.h"
#include "camouflage.h"
#include "asset_firstperson.h"
#include "blam/vehicle_physics.h"
#include "scene.h"
#include "runtime_qa.h"
#ifdef BG_RUNTIME_QA
static struct {
    unsigned *views;
    float *seconds;
} qa;
#ifdef BG_MODEL_QA
#if defined(BG_AIM_QA)
#include "aim_qa.h"
#elif defined(BG_HUD_QA)
#include "hud_qa.h"
#elif defined(BG_ENVIRONMENT_QA)
#include "environment_qa.h"
#elif defined(BG_GROUND_QA)
#include "ground_qa.h"
#elif defined(BG_GEOMETRY_QA)
#include "geometry_qa.h"
#elif defined(BG_PLASMA_QA)
#include "plasma_qa.h"
#elif defined(BG_WEAPON_QA)
#include "weapon_qa.h"
#else
#include "model_qa.h"
#endif
#endif
#ifdef BG_INTERACTION_QA
#include "interaction_qa.h"
#endif
#ifdef BG_SHIELD_QA
#include "shield_fixture.h"
#endif
#ifdef BG_MOVEMENT_QA
#include "movement_qa.h"
#endif
#ifdef BG_COMBAT_QA
#include "combat_qa.h"
#endif

#ifdef BG_RELOAD_QA
#include "reload_qa.h"
#endif
void bg_qa_bind(unsigned *views, float *seconds) {
    qa.views = views;
    qa.seconds = seconds;
}
#ifdef BG_MODEL_QA
void bg_qa_stage(uint64_t now) {
    model_qa_stage(now);
}
unsigned bg_qa_page(void) {
    return model_qa_page;
}
const char *bg_qa_label(void) {
    return model_qa_labels[model_qa_page];
}
bool bg_qa_firstperson(void) {
    return model_qa_firstperson();
}
void bg_qa_camera(unsigned player, T3DVec3 *eye, T3DVec3 *target) {
    model_qa_camera(player, eye, target);
}
#endif
#ifdef BG_INTERACTION_QA
void bg_qa_interaction_stage(void) {
    interaction_qa_stage();
}
void bg_qa_interaction_camera(unsigned player, T3DVec3 *eye, T3DVec3 *target) {
    interaction_qa_camera(player, eye, target);
}
#endif
#ifdef BG_SHIELD_QA
void bg_qa_shield_stage(void) {
    shield_fixture_stage(BG_SHIELD_QA);
    *qa.seconds = bg_match_time();
}
#endif
#ifdef BG_MOVEMENT_QA
void bg_qa_movement_input(bg_input in[4], float seconds) {
    movement_qa_input(in, seconds);
}
const char *bg_qa_movement_title(void) {
    return movement_qa_title();
}
#endif
#ifdef BG_COMBAT_QA
void bg_qa_combat_input(bg_input in[4], float seconds) {
    combat_qa_input(in, seconds);
}
const char *bg_qa_combat_title(void) {
    return combat_qa_title();
}
#endif
#ifdef BG_RELOAD_QA
void bg_qa_reload_input(bg_input in[4], float seconds) {
    reload_qa_input(in, seconds);
}
#endif

#endif /* BG_RUNTIME_QA */
