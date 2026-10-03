#ifndef BG_CONTROLS_H
#define BG_CONTROLS_H

#include "game.h"

typedef enum {
    BG_CONTROLS_N64,
    BG_CONTROLS_XBOX,
    BG_CONTROLS_COUNT
} bg_control_style;

/* Portable N64 button names; no libdragon bit layout or controller ownership
 * is exposed here. START belongs to the pause/menu layer, not gameplay. */
enum {
    BG_BUTTON_A       = 1u << 0,
    BG_BUTTON_B       = 1u << 1,
    BG_BUTTON_L       = 1u << 2,
    BG_BUTTON_R       = 1u << 3,
    BG_BUTTON_Z       = 1u << 4,
    BG_BUTTON_START   = 1u << 5,
    BG_BUTTON_D_UP    = 1u << 6,
    BG_BUTTON_D_DOWN  = 1u << 7,
    BG_BUTTON_D_LEFT  = 1u << 8,
    BG_BUTTON_D_RIGHT = 1u << 9,
    BG_BUTTON_C_UP    = 1u << 10,
    BG_BUTTON_C_DOWN  = 1u << 11,
    BG_BUTTON_C_LEFT  = 1u << 12,
    BG_BUTTON_C_RIGHT = 1u << 13
};

typedef struct {
    /* Raw stick units as supplied by the controller adapter, not normalized.
     * Both styles retain the existing /80 scale and per-axis .12 deadzone. */
    float stick_x,stick_y;
    uint32_t held,pressed;
} bg_control_state;

bool bg_control_style_valid(bg_control_style style);
const char *bg_control_style_name(bg_control_style style);
bg_control_style bg_control_style_next(bg_control_style style);

/* Stateless, per-player conversion. Preferences, pause/menu handling and
 * edge latching across fixed simulation ticks remain with the caller.
 * Unknown style values safely use the original N64 layout. */
void bg_controls_map(bg_input *out,const bg_control_state *raw,
    bg_control_style style,bool mounted);

#endif
