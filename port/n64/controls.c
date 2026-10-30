#include "controls.h"
#include <math.h>

bool bg_control_style_valid(bg_control_style style) {
    return (unsigned)style < BG_CONTROLS_COUNT;
}

const char *bg_control_style_name(bg_control_style style) {
    return style == BG_CONTROLS_DUKE ? "Duke" : "Bond";
}

bg_control_style bg_control_style_next(bg_control_style style) {
    return style == BG_CONTROLS_BOND ? BG_CONTROLS_DUKE : BG_CONTROLS_BOND;
}

bool bg_controls_show_scores(const bg_control_state *raw, bg_control_style style) {
    return style == BG_CONTROLS_DUKE && (raw->held & (BG_BUTTON_Z | BG_BUTTON_C_UP)) == (BG_BUTTON_Z | BG_BUTTON_C_UP);
}

void bg_controls_map(bg_input *out, const bg_control_state *raw, bg_control_style style,
                     bool mounted) {
    float x = raw->stick_x / 80.f, y = raw->stick_y / 80.f;
    if (fabsf(x) < .12f)
        x = 0;
    if (fabsf(y) < .12f)
        y = 0;
    const uint32_t held = raw->held, pressed = raw->pressed;
    *out = (bg_input){.turn = -x,
                      .jump = mounted ? (held & BG_BUTTON_A) != 0 : (pressed & BG_BUTTON_A) != 0,
                      .fire = (held & BG_BUTTON_Z) != 0,
                      .grenade = (pressed & BG_BUTTON_L) != 0,
                      /* The simulation consumes held secondary fire only while mounted.
                       * Preserve the old raw mapping even when the player is on foot. */
                      .secondary_fire = (held & BG_BUTTON_L) != 0};
    if (style == BG_CONTROLS_DUKE) {
        out->forward = ((held & BG_BUTTON_D_UP) != 0) - ((held & BG_BUTTON_D_DOWN) != 0);
        out->strafe = ((held & BG_BUTTON_D_RIGHT) != 0) - ((held & BG_BUTTON_D_LEFT) != 0);
        out->look = y;
        out->reload = (pressed & BG_BUTTON_C_LEFT) != 0;
        out->interact = (held & BG_BUTTON_C_LEFT) != 0;
        out->fire = (held & BG_BUTTON_R) != 0;
        out->jump = (held & BG_BUTTON_Z) == 0 &&
            ((mounted ? held : pressed) & BG_BUTTON_C_DOWN) != 0;
        out->melee = (pressed & BG_BUTTON_C_RIGHT) != 0;
        out->switch_weapon = (pressed & BG_BUTTON_C_UP) != 0 && !(held & BG_BUTTON_Z);
        out->switch_grenade = (pressed & BG_BUTTON_A) != 0;
        out->flashlight = (pressed & BG_BUTTON_B) != 0;
        /* Zoom and toggle-crouch are resolved by the per-player gesture state. */
    } else {
        out->forward = y;
        out->strafe = ((held & BG_BUTTON_C_RIGHT) != 0) - ((held & BG_BUTTON_C_LEFT) != 0);
        out->look = ((held & BG_BUTTON_C_UP) != 0) - ((held & BG_BUTTON_C_DOWN) != 0);
        out->reload = (pressed & BG_BUTTON_B) != 0;
        out->interact = (held & BG_BUTTON_B) != 0;
        out->switch_weapon = (pressed & BG_BUTTON_R) != 0;
        out->switch_grenade = (pressed & BG_BUTTON_D_LEFT) != 0;
        out->melee = (pressed & BG_BUTTON_D_DOWN) != 0;
        out->zoom = (pressed & BG_BUTTON_D_UP) != 0;
        out->crouch = (held & BG_BUTTON_D_RIGHT) != 0;
    }
}

void bg_controls_reset(bg_control_gesture *state) {
    *state = (bg_control_gesture){0};
}
void bg_controls_update(bg_input *out, bg_control_gesture *state,
                        const bg_control_state *raw, bg_control_style style,
                        bool mounted, bool active, uint64_t now_us) {
    if (!state->initialized || state->style != style) {
        bg_controls_reset(state);
        state->style = style;
        state->initialized = true;
        state->previous = raw->held & ~raw->pressed;
        state->blocked = state->previous & (BG_BUTTON_C_UP | BG_BUTTON_C_DOWN);
        /* A scheme change cannot turn an already-held modifier into a tap. */
        state->used = (raw->held & BG_BUTTON_Z) && !(raw->pressed & BG_BUTTON_Z);
    }
    if (!active) {
        state->previous = raw->held;
        state->used = true;
        state->blocked |= raw->held & (BG_BUTTON_C_UP | BG_BUTTON_C_DOWN);
        *out = (bg_input){0};
        return;
    }
    bg_controls_map(out,raw,style,mounted);
    if (style == BG_CONTROLS_DUKE) {
        bool z = (raw->held & BG_BUTTON_Z) != 0;
        bool old_z = (state->previous & BG_BUTTON_Z) != 0;
        uint32_t chords = raw->held & (BG_BUTTON_C_UP | BG_BUTTON_C_DOWN);
        state->blocked &= raw->held;
        if (z && !old_z) {
            state->since = now_us;
            state->used = !(raw->pressed & BG_BUTTON_Z);
        }
        if (z && chords) {
            state->used = true;
            state->blocked |= chords;
            if ((chords & BG_BUTTON_C_DOWN) &&
                (!old_z || !(state->previous & BG_BUTTON_C_DOWN)))
                state->crouched = !state->crouched;
        }
        if (!z && old_z && !state->used && now_us - state->since < 250000)
            out->zoom = true;
        if (state->blocked & BG_BUTTON_C_DOWN) out->jump = false;
        if (state->blocked & BG_BUTTON_C_UP) out->switch_weapon = false;
        out->crouch = state->crouched;
    }
    state->previous = raw->held;
}
