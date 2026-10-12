#ifndef HALO_N64_HUD_H
#define HALO_N64_HUD_H
#include "hud_layout.h"
#include "controls.h"
#include "hud_messages.h"
void bg_hud_init(void);
void bg_hud_draw(unsigned player,int x,int y,int width,int height,bg_control_style style);
#ifdef BG_FRONTEND_QA
/* Diagnostic labels reuse the resident pixel atlas instead of linking a
 * second text renderer into the constrained native map-cycle fixture. */
void bg_hud_qa_text(const char *text,int x,int y);
#endif
#endif
