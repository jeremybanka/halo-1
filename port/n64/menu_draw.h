#ifndef BG_MENU_DRAW_H
#define BG_MENU_DRAW_H
#include "menu.h"

void bg_menu_draw_init(void);
/* Fullscreen 320x240 overlay. Call after the scene's 3D triangles are flushed.
 * No gameplay state changes; owner/style/selection come only from menu. */
void bg_menu_draw(const bg_menu *menu);
/* Held-score display for one player's viewport. Presentation only: does not
 * pause simulation or change input/state. Restores the full-screen scissor. */
void bg_scores_draw(unsigned owner,int x,int y,int width,int height);
#endif
