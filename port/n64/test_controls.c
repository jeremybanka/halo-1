#include "controls.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static unsigned comparisons;
static void equal(const bg_input *a,const bg_input *b,bool exact_axes) {
    if(exact_axes) {
        assert(memcmp(&a->forward,&b->forward,sizeof(float))==0);
        assert(memcmp(&a->strafe,&b->strafe,sizeof(float))==0);
        assert(memcmp(&a->turn,&b->turn,sizeof(float))==0);
        assert(memcmp(&a->look,&b->look,sizeof(float))==0);
    } else {
        assert(a->forward==b->forward&&a->strafe==b->strafe);
        assert(a->turn==b->turn&&a->look==b->look);
    }
#define SAME(field) assert(a->field==b->field)
    SAME(jump);SAME(fire);SAME(reload);SAME(switch_weapon);SAME(grenade);
    SAME(switch_grenade);SAME(interact);SAME(melee);SAME(zoom);SAME(crouch);
    SAME(secondary_fire);
#undef SAME
    comparisons++;
}

typedef struct {
    bool a,b,l,r,z,start,d_up,d_down,d_left,d_right,c_up,c_down,c_left,c_right;
} legacy_buttons;

static legacy_buttons legacy(uint32_t mask) {
    return (legacy_buttons){
        .a=(mask&BG_BUTTON_A)!=0,.b=(mask&BG_BUTTON_B)!=0,
        .l=(mask&BG_BUTTON_L)!=0,.r=(mask&BG_BUTTON_R)!=0,
        .z=(mask&BG_BUTTON_Z)!=0,.start=(mask&BG_BUTTON_START)!=0,
        .d_up=(mask&BG_BUTTON_D_UP)!=0,.d_down=(mask&BG_BUTTON_D_DOWN)!=0,
        .d_left=(mask&BG_BUTTON_D_LEFT)!=0,.d_right=(mask&BG_BUTTON_D_RIGHT)!=0,
        .c_up=(mask&BG_BUTTON_C_UP)!=0,.c_down=(mask&BG_BUTTON_C_DOWN)!=0,
        .c_left=(mask&BG_BUTTON_C_LEFT)!=0,.c_right=(mask&BG_BUTTON_C_RIGHT)!=0
    };
}

/* Verbatim field mapping from the existing main.c input() implementation,
 * adapted only from libdragon button structs to this test's decoded booleans. */
static bg_input original_n64(const bg_control_state *raw,bool mounted) {
    legacy_buttons held=legacy(raw->held),pressed=legacy(raw->pressed);
    float x=raw->stick_x/80.f,y=raw->stick_y/80.f;
    if(fabsf(x)<.12f)x=0;if(fabsf(y)<.12f)y=0;
    return (bg_input){.forward=y,.turn=-x,.strafe=held.c_right-held.c_left,
        .look=held.c_up-held.c_down,.jump=mounted?held.a:pressed.a,
        .fire=held.z,.reload=pressed.b,.interact=pressed.b,.switch_weapon=pressed.r,
        .grenade=pressed.l,.secondary_fire=held.l,.switch_grenade=pressed.d_left,
        .melee=pressed.d_down,.zoom=pressed.d_up,.crouch=held.d_right};
}

static void check(const bg_control_state *raw,bg_control_style style,
        bool mounted,bg_input expected) {
    bg_control_state unchanged=*raw;
    bg_input actual;memset(&actual,0xa5,sizeof(actual));
    bg_controls_map(&actual,raw,style,mounted);
    equal(&actual,&expected,false);
    assert(memcmp(raw,&unchanged,sizeof(unchanged))==0);
}

static void xbox_buttons(void) {
    /* A single edge must activate only its designated actions. Held-only
     * checks separately establish jump edges, repeat fire, rise and crouch. */
    const struct { uint32_t button;bg_input edge,held,mounted; } cases[]={
        {BG_BUTTON_A,{.jump=true},{0},{.jump=true}},
        {BG_BUTTON_B,{.melee=true},{0},{0}},
        {BG_BUTTON_L,{.grenade=true,.secondary_fire=true},
            {.secondary_fire=true},{.secondary_fire=true}},
        {BG_BUTTON_R,{.reload=true,.interact=true},{0},{0}},
        {BG_BUTTON_Z,{.fire=true},{.fire=true},{.fire=true}},
        {BG_BUTTON_C_LEFT,{.switch_weapon=true},{0},{0}},
        {BG_BUTTON_C_RIGHT,{.switch_grenade=true},{0},{0}},
        {BG_BUTTON_C_UP,{.zoom=true},{0},{0}},
        {BG_BUTTON_C_DOWN,{.crouch=true},{.crouch=true},{.crouch=true}},
        {BG_BUTTON_D_UP,{.forward=1},{.forward=1},{.forward=1}},
        {BG_BUTTON_D_DOWN,{.forward=-1},{.forward=-1},{.forward=-1}},
        {BG_BUTTON_D_LEFT,{.strafe=-1},{.strafe=-1},{.strafe=-1}},
        {BG_BUTTON_D_RIGHT,{.strafe=1},{.strafe=1},{.strafe=1}},
        {BG_BUTTON_START,{0},{0},{0}}
    };
    for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);i++) {
        bg_control_state raw={.held=cases[i].button,.pressed=cases[i].button};
        check(&raw,BG_CONTROLS_XBOX,false,cases[i].edge);
        raw.pressed=0;
        check(&raw,BG_CONTROLS_XBOX,false,cases[i].held);
        check(&raw,BG_CONTROLS_XBOX,true,cases[i].mounted);
    }
    bg_control_state raw={.held=BG_BUTTON_D_UP|BG_BUTTON_D_DOWN|
        BG_BUTTON_D_LEFT|BG_BUTTON_D_RIGHT};
    check(&raw,BG_CONTROLS_XBOX,false,(bg_input){0});
    raw.held=BG_BUTTON_D_UP|BG_BUTTON_D_RIGHT;
    raw.stick_x=40;raw.stick_y=-60;
    check(&raw,BG_CONTROLS_XBOX,false,(bg_input){.forward=1,.strafe=1,.turn=-.5f,.look=-.75f});
    /* Pressed edges may be latched independently of the current held sample. */
    raw=(bg_control_state){.pressed=BG_BUTTON_A|BG_BUTTON_R|BG_BUTTON_B|
        BG_BUTTON_L|BG_BUTTON_C_LEFT|BG_BUTTON_C_RIGHT|BG_BUTTON_C_UP};
    check(&raw,BG_CONTROLS_XBOX,false,(bg_input){.jump=true,.reload=true,
        .interact=true,.melee=true,.grenade=true,.switch_weapon=true,
        .switch_grenade=true,.zoom=true});
    check(&raw,BG_CONTROLS_XBOX,true,(bg_input){.reload=true,.interact=true,
        .melee=true,.grenade=true,.switch_weapon=true,.switch_grenade=true,.zoom=true});
}

static void axes(void) {
    const float values[]={-128,-80,-40,-9.6f,-9.5f,-0.f,0,9.5f,9.6f,40,80,127};
    for(unsigned i=0;i<sizeof(values)/sizeof(*values);i++)
        for(unsigned j=0;j<sizeof(values)/sizeof(*values);j++) {
            bg_control_state raw={.stick_x=values[i],.stick_y=values[j]};
            float x=values[i]/80.f,y=values[j]/80.f;
            if(fabsf(x)<.12f)x=0;if(fabsf(y)<.12f)y=0;
            check(&raw,BG_CONTROLS_XBOX,false,(bg_input){.turn=-x,.look=y});
            check(&raw,BG_CONTROLS_N64,false,(bg_input){.turn=-x,.forward=y});
        }
    /* No new clamping/diagonal normalization: preserve the old controller
     * adapter's values even at the ends of its signed eight-bit range. */
    bg_control_state raw={.stick_x=127,.stick_y=-128};
    check(&raw,BG_CONTROLS_XBOX,false,(bg_input){.turn=-127.f/80,.look=-128.f/80});
}

static void n64_regression(void) {
    const uint32_t all=(1u<<14)-1;
    for(uint32_t held=0;held<=all;held++) {
        const uint32_t edges[]={0,held,all^held};
        for(unsigned e=0;e<3;e++)for(unsigned mounted=0;mounted<2;mounted++) {
            bg_control_state raw={.held=held,.pressed=edges[e],
                .stick_x=(int)(held%256)-128,.stick_y=(int)((held*19)%256)-128};
            bg_input expected=original_n64(&raw,mounted!=0),actual;
            bg_controls_map(&actual,&raw,BG_CONTROLS_N64,mounted!=0);
            equal(&actual,&expected,true);
        }
    }
}

static void isolation_and_styles(void) {
    assert(bg_control_style_valid(BG_CONTROLS_N64));
    assert(bg_control_style_valid(BG_CONTROLS_XBOX));
    assert(!bg_control_style_valid((bg_control_style)-1));
    assert(!bg_control_style_valid(BG_CONTROLS_COUNT));
    assert(strcmp(bg_control_style_name(BG_CONTROLS_N64),"N64")==0);
    assert(strcmp(bg_control_style_name(BG_CONTROLS_XBOX),"Xbox")==0);
    assert(bg_control_style_next(BG_CONTROLS_N64)==BG_CONTROLS_XBOX);
    assert(bg_control_style_next(BG_CONTROLS_XBOX)==BG_CONTROLS_N64);
    assert(bg_control_style_next(BG_CONTROLS_COUNT)==BG_CONTROLS_N64);
    const bg_control_state raw[4]={
        {.stick_x=80,.stick_y=80,.held=BG_BUTTON_D_UP|BG_BUTTON_Z,.pressed=BG_BUTTON_B},
        {.stick_x=-40,.stick_y=-80,.held=BG_BUTTON_C_LEFT,.pressed=BG_BUTTON_R},
        {.held=BG_BUTTON_A|BG_BUTTON_L,.pressed=BG_BUTTON_C_UP},
        {.held=BG_BUTTON_D_RIGHT|BG_BUTTON_C_DOWN,.pressed=BG_BUTTON_C_RIGHT}
    };
    bg_input out[4];
    for(unsigned p=0;p<4;p++)bg_controls_map(&out[p],&raw[p],p&1?BG_CONTROLS_N64:BG_CONTROLS_XBOX,p==2);
    const bg_input expected[4]={
        {.forward=1,.turn=-1,.look=1,.fire=true,.melee=true},
        {.forward=-1,.turn=.5f,.strafe=-1,.switch_weapon=true},
        {.jump=true,.secondary_fire=true,.zoom=true},
        {.look=-1,.crouch=true}
    };
    for(unsigned p=0;p<4;p++)equal(&out[p],&expected[p],false);
    bg_input saved[4];memcpy(saved,out,sizeof(out));
    bg_controls_map(&out[1],&raw[1],BG_CONTROLS_XBOX,false);
    for(unsigned p=0;p<4;p++)if(p!=1)assert(memcmp(&out[p],&saved[p],sizeof(out[p]))==0);
    /* Invalid persisted preferences fall back to N64; unknown button bits
     * and START never leak into any gameplay action. */
    bg_control_state unknown={.held=BG_BUTTON_START|UINT32_C(0xffffc000),
        .pressed=BG_BUTTON_START|UINT32_C(0xffffc000)};
    check(&unknown,BG_CONTROLS_COUNT,false,(bg_input){0});
    bg_input expected_n64=original_n64(&raw[0],false),actual;
    bg_controls_map(&actual,&raw[0],(bg_control_style)-1,false);
    equal(&actual,&expected_n64,true);
}

int main(void) {
    xbox_buttons();axes();n64_regression();isolation_and_styles();
    printf("PASS: %u controls comparisons; all N64 held masks preserve original fields/float bits; "
        "Xbox actions/edges/holds, mounted A, aim axes, deadzone and player isolation\n",comparisons);
    return 0;
}
