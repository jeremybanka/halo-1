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
    SAME(secondary_fire);SAME(flashlight);
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

/* N64 field mapping, with held use and edge-triggered reload,
 * adapted only from libdragon button structs to this test's decoded booleans. */
static bg_input original_n64(const bg_control_state *raw,bool mounted) {
    legacy_buttons held=legacy(raw->held),pressed=legacy(raw->pressed);
    float x=raw->stick_x/80.f,y=raw->stick_y/80.f;
    if(fabsf(x)<.12f)x=0;if(fabsf(y)<.12f)y=0;
    return (bg_input){.forward=y,.turn=-x,.strafe=held.c_right-held.c_left,
        .look=held.c_up-held.c_down,.jump=mounted?held.a:pressed.a,
        .fire=held.z,.reload=pressed.b,.interact=held.b,.switch_weapon=pressed.r,
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

static void duke_buttons(void) {
    const struct {uint32_t button;bg_input edge,held,mounted;} cases[]={
      {BG_BUTTON_A,{.switch_grenade=true},{0},{0}},
      {BG_BUTTON_B,{.flashlight=true},{0},{0}},
      {BG_BUTTON_R,{.fire=true},{.fire=true},{.fire=true}},
      {BG_BUTTON_L,{.grenade=true,.secondary_fire=true},{.secondary_fire=true},{.secondary_fire=true}},
      {BG_BUTTON_Z,{0},{0},{0}},
      {BG_BUTTON_C_UP,{.switch_weapon=true},{0},{0}},
      {BG_BUTTON_C_DOWN,{.jump=true},{0},{.jump=true}},
      {BG_BUTTON_C_RIGHT,{.melee=true},{0},{0}},
      {BG_BUTTON_C_LEFT,{.reload=true,.interact=true},{.interact=true},{.interact=true}},
      {BG_BUTTON_D_UP,{.forward=1},{.forward=1},{.forward=1}},
      {BG_BUTTON_D_DOWN,{.forward=-1},{.forward=-1},{.forward=-1}},
      {BG_BUTTON_D_RIGHT,{.strafe=1},{.strafe=1},{.strafe=1}},
      {BG_BUTTON_D_LEFT,{.strafe=-1},{.strafe=-1},{.strafe=-1}},
      {BG_BUTTON_START,{0},{0},{0}}};
    for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);i++) {
      bg_control_state raw={.held=cases[i].button,.pressed=cases[i].button};
      check(&raw,BG_CONTROLS_DUKE,false,cases[i].edge);raw.pressed=0;
      check(&raw,BG_CONTROLS_DUKE,false,cases[i].held);
      check(&raw,BG_CONTROLS_DUKE,true,cases[i].mounted);
    }
}
static void axes(void) {
    const float values[]={-128,-80,-40,-9.6f,-9.5f,-0.f,0,9.5f,9.6f,40,80,127};
    for(unsigned i=0;i<sizeof(values)/sizeof(*values);i++)
        for(unsigned j=0;j<sizeof(values)/sizeof(*values);j++) {
            bg_control_state raw={.stick_x=values[i],.stick_y=values[j]};
            float x=values[i]/80.f,y=values[j]/80.f;
            if(fabsf(x)<.12f)x=0;if(fabsf(y)<.12f)y=0;
            check(&raw,BG_CONTROLS_DUKE,false,(bg_input){.turn=-x,.look=y});
            check(&raw,BG_CONTROLS_BOND,false,(bg_input){.turn=-x,.forward=y});
        }
    /* No new clamping/diagonal normalization: preserve the old controller
     * adapter's values even at the ends of its signed eight-bit range. */
    bg_control_state raw={.stick_x=127,.stick_y=-128};
    check(&raw,BG_CONTROLS_DUKE,false,(bg_input){.turn=-127.f/80,.look=-128.f/80});
}

static bg_input poll(bg_control_gesture *g,uint32_t held,uint32_t pressed,uint64_t us,bool active) {
    bg_input out;bg_control_state raw={.held=held,.pressed=pressed};
    bg_controls_update(&out,g,&raw,BG_CONTROLS_DUKE,true,active,us);return out;
}
static void gestures(void) {
    bg_control_gesture g={0};bg_input out;
    const unsigned Z=BG_BUTTON_Z,U=BG_BUTTON_C_UP,D=BG_BUTTON_C_DOWN;
    for(unsigned duration=0;duration<=500000;duration+=1000) {
        bg_controls_reset(&g);out=poll(&g,Z,Z,100,true);assert(!out.zoom);
        out=poll(&g,0,0,100+duration,true);assert(out.zoom==(duration<250000));
        out=poll(&g,0,0,600100,true);assert(!out.zoom);
    }
    bg_controls_reset(&g);
    out=poll(&g,Z|D,0,0,true);assert(!out.crouch&&!out.jump&&!out.zoom);
    out=poll(&g,0,0,10,true);assert(!out.zoom);
    bg_controls_reset(&g);
    out=poll(&g,Z|D,Z|D,100,true);assert(out.crouch&&!out.jump&&!out.zoom);
    out=poll(&g,Z|D,0,100000,true);assert(out.crouch&&!out.jump);
    out=poll(&g,D,0,120000,true);assert(out.crouch&&!out.jump&&!out.zoom);
    out=poll(&g,0,0,140000,true);assert(out.crouch);
    out=poll(&g,Z|D,Z|D,160000,true);assert(!out.crouch&&!out.jump);
    out=poll(&g,0,0,170000,true);assert(!out.zoom);
    out=poll(&g,Z,Z,200000,true);out=poll(&g,Z|U,U,220000,true);
    assert(!out.switch_weapon&&!out.zoom);
    out=poll(&g,U,0,230000,true);assert(!out.switch_weapon&&!out.zoom);
    out=poll(&g,0,0,240000,true);
    out=poll(&g,Z,Z,300000,true);out=poll(&g,Z,0,310000,false);
    out=poll(&g,0,0,320000,true);assert(!out.zoom);
    /* Cancellation while held, scheme changes and players remain independent. */
    bg_control_gesture others[4]={{0}};
    out=poll(&others[2],Z|D,Z|D,400000,true);assert(out.crouch);
    for(unsigned i=0;i<4;i++)if(i!=2){out=poll(&others[i],0,0,410000,true);assert(!out.crouch);}
    bg_controls_reset(&others[2]);out=poll(&others[2],0,0,420000,true);assert(!out.crouch);
    out=poll(&g,Z,Z,500000,true);
    bg_control_state raw={.held=Z};bg_controls_update(&out,&g,&raw,BG_CONTROLS_BOND,false,true,510000);
    out=poll(&g,Z,0,520000,true);out=poll(&g,0,0,530000,true);assert(!out.zoom);
    for(unsigned mask=0;mask<(1u<<14);mask++) {
        raw=(bg_control_state){.held=mask};
        assert(bg_controls_show_scores(&raw,BG_CONTROLS_DUKE)==((mask&(Z|U))==(Z|U)));
        assert(!bg_controls_show_scores(&raw,BG_CONTROLS_BOND));
    }
}
static void n64_regression(void) {
    const uint32_t all=(1u<<14)-1;
    for(uint32_t held=0;held<=all;held++) {
        const uint32_t edges[]={0,held,all^held};
        for(unsigned e=0;e<3;e++)for(unsigned mounted=0;mounted<2;mounted++) {
            bg_control_state raw={.held=held,.pressed=edges[e],
                .stick_x=(int)(held%256)-128,.stick_y=(int)((held*19)%256)-128};
            bg_input expected=original_n64(&raw,mounted!=0),actual;
            bg_controls_map(&actual,&raw,BG_CONTROLS_BOND,mounted!=0);
            equal(&actual,&expected,true);
        }
    }
}

int main(void) {
    assert(!strcmp(bg_control_style_name(BG_CONTROLS_DUKE),"Duke"));
    assert(!strcmp(bg_control_style_name(BG_CONTROLS_BOND),"Bond"));
    duke_buttons();axes();n64_regression();gestures();
    printf("PASS %u mapping comparisons; Bond unchanged; Duke buttons, tap threshold, chords, cancellation, isolation and 32768 score-mask checks\n",comparisons);
}
