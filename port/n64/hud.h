#ifndef HALO_N64_HUD_H
#define HALO_N64_HUD_H
#include "hud_layout.h"
#include "controls.h"
void bg_hud_init(void);
void bg_hud_draw(unsigned player,int x,int y,int width,int height,bg_control_style style);
#endif
