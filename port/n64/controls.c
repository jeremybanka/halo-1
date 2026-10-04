#include "controls.h"
#include <math.h>

bool bg_control_style_valid(bg_control_style style) {
    return (unsigned)style<BG_CONTROLS_COUNT;
}

const char *bg_control_style_name(bg_control_style style) {
    return style==BG_CONTROLS_XBOX?"Xbox":"N64";
}

bg_control_style bg_control_style_next(bg_control_style style) {
    return style==BG_CONTROLS_N64?BG_CONTROLS_XBOX:BG_CONTROLS_N64;
}

bool bg_controls_show_scores(const bg_control_state *raw,bg_control_style style) {
    return style==BG_CONTROLS_XBOX&&(raw->held&BG_BUTTON_R)!=0;
}

void bg_controls_map(bg_input *out,const bg_control_state *raw,
        bg_control_style style,bool mounted) {
    float x=raw->stick_x/80.f,y=raw->stick_y/80.f;
    if(fabsf(x)<.12f)x=0;
    if(fabsf(y)<.12f)y=0;
    const uint32_t held=raw->held,pressed=raw->pressed;
    *out=(bg_input){
        .turn=-x,
        .jump=mounted?(held&BG_BUTTON_A)!=0:(pressed&BG_BUTTON_A)!=0,
        .fire=(held&BG_BUTTON_Z)!=0,
        .grenade=(pressed&BG_BUTTON_L)!=0,
        /* The simulation consumes held secondary fire only while mounted.
         * Preserve the old raw mapping even when the player is on foot. */
        .secondary_fire=(held&BG_BUTTON_L)!=0
    };
    if(style==BG_CONTROLS_XBOX) {
        out->forward=((held&BG_BUTTON_D_UP)!=0)-((held&BG_BUTTON_D_DOWN)!=0);
        out->strafe=((held&BG_BUTTON_D_RIGHT)!=0)-((held&BG_BUTTON_D_LEFT)!=0);
        out->look=y;
        out->reload=out->interact=(pressed&BG_BUTTON_C_LEFT)!=0;
        out->melee=(pressed&BG_BUTTON_B)!=0;
        out->switch_weapon=(pressed&BG_BUTTON_C_UP)!=0&&(held&BG_BUTTON_R)==0;
        out->switch_grenade=(pressed&BG_BUTTON_C_RIGHT)!=0;
        out->zoom=(pressed&BG_BUTTON_C_UP)!=0&&(held&BG_BUTTON_R)!=0;
        out->crouch=(held&BG_BUTTON_C_DOWN)!=0;
    } else {
        out->forward=y;
        out->strafe=((held&BG_BUTTON_C_RIGHT)!=0)-((held&BG_BUTTON_C_LEFT)!=0);
        out->look=((held&BG_BUTTON_C_UP)!=0)-((held&BG_BUTTON_C_DOWN)!=0);
        out->reload=out->interact=(pressed&BG_BUTTON_B)!=0;
        out->switch_weapon=(pressed&BG_BUTTON_R)!=0;
        out->switch_grenade=(pressed&BG_BUTTON_D_LEFT)!=0;
        out->melee=(pressed&BG_BUTTON_D_DOWN)!=0;
        out->zoom=(pressed&BG_BUTTON_D_UP)!=0;
        out->crouch=(held&BG_BUTTON_D_RIGHT)!=0;
    }
}
