#ifndef BG_RUNTIME_QA_H
#define BG_RUNTIME_QA_H
#include <t3d/t3d.h>
#include "game.h"
/* QA can change only the explicitly bound application clock/view count and
 * production game APIs. It never reaches into renderer buffers or fences. */
#if defined(BG_MODEL_QA) || defined(BG_INTERACTION_QA) || defined(BG_SHIELD_QA) ||                 \
    defined(BG_MOVEMENT_QA) || defined(BG_COMBAT_QA) || defined(BG_RELOAD_QA)
#define BG_RUNTIME_QA
void bg_qa_bind(unsigned *views, float *seconds);
#else
static inline void bg_qa_bind(unsigned *views, float *seconds) {
    (void)views;
    (void)seconds;
}
#endif
#ifdef BG_MODEL_QA
void bg_qa_stage(uint64_t now);
unsigned bg_qa_page(void);
const char *bg_qa_label(void);
bool bg_qa_firstperson(void);
void bg_qa_camera(unsigned player, T3DVec3 *eye, T3DVec3 *target);
#endif
#ifdef BG_INTERACTION_QA
void bg_qa_interaction_stage(void);
void bg_qa_interaction_camera(unsigned player, T3DVec3 *eye, T3DVec3 *target);
#endif
#ifdef BG_SHIELD_QA
void bg_qa_shield_stage(void);
#endif
#ifdef BG_MOVEMENT_QA
void bg_qa_movement_input(bg_input in[4], float seconds);
const char *bg_qa_movement_title(void);
#endif
#ifdef BG_COMBAT_QA
void bg_qa_combat_input(bg_input in[4], float seconds);
const char *bg_qa_combat_title(void);
#endif
#ifdef BG_RELOAD_QA
void bg_qa_reload_input(bg_input in[4], float seconds);
#endif
#endif
