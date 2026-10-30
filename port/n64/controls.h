#ifndef BG_CONTROLS_H
#define BG_CONTROLS_H

#include "game.h"

typedef enum {
    BG_CONTROLS_BOND,
    BG_CONTROLS_DUKE,
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

/* Gesture state belongs to a local player, never to a physical controller.
 * Cancel pending taps when menus consume input. Reset on match/death. */
typedef struct {
    uint64_t since;
    uint32_t previous, blocked;
    bg_control_style style;
    bool initialized, used, crouched;
} bg_control_gesture;
void bg_controls_reset(bg_control_gesture *state);
void bg_controls_update(bg_input *out, bg_control_gesture *state,
                        const bg_control_state *raw, bg_control_style style,
                        bool mounted, bool active, uint64_t now_us);
bool bg_controls_show_scores(const bg_control_state *raw,bg_control_style style);
/* Base mapping; Duke's Z gestures require bg_controls_update. */
void bg_controls_map(bg_input *out,const bg_control_state *raw,
    bg_control_style style,bool mounted);
#endif
