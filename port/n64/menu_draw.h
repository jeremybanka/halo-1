#ifndef BG_MENU_DRAW_H
#define BG_MENU_DRAW_H
#include "menu.h"

void bg_menu_draw_init(void);
/* Fullscreen 320x240 overlay. Call after the scene's 3D triangles are flushed.
 * No gameplay state changes; owner/style/selection come only from menu. */
void bg_menu_draw(const bg_menu *menu);
#endif
