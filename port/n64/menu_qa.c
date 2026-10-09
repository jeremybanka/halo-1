#include "menu_qa.h"
#include <assert.h>
#include <string.h>

typedef struct {
    unsigned port;uint32_t button;bool open;
    unsigned owner;bg_menu_page page;unsigned row,players,xbox_mask;
    bg_menu_action action;
} checkpoint;
#define ROOT BG_MENU_ROOT
#define SETUP BG_MENU_SETUP
#define CONTROLS BG_MENU_CONTROLS
#define B(name) BG_BUTTON_##name
#define NONE BG_MENU_ACTION_NONE
static const checkpoint script[]={
    {0,0,0,0,ROOT,0,4,0,NONE},
    {0,B(START),1,0,ROOT,0,4,0,NONE},
    {0,B(D_DOWN),1,0,ROOT,1,4,0,NONE},
    {0,B(A),1,0,SETUP,0,4,0,NONE},
    {0,B(D_RIGHT),1,0,SETUP,0,1,0,BG_MENU_ACTION_PLAYER_COUNT},
    {3,B(START),1,0,SETUP,0,1,0,NONE},
    {0,B(D_RIGHT),1,0,SETUP,0,2,0,BG_MENU_ACTION_PLAYER_COUNT},
    {0,B(D_RIGHT),1,0,SETUP,0,4,0,BG_MENU_ACTION_PLAYER_COUNT},
    {0,B(B),1,0,ROOT,1,4,0,NONE},
    {0,B(D_DOWN),1,0,ROOT,2,4,0,NONE},
    {0,B(A),1,0,CONTROLS,0,4,0,NONE},
    {0,B(D_RIGHT),1,0,CONTROLS,0,4,1,NONE},
    {1,B(START),1,1,ROOT,0,4,1,NONE},
    {1,B(D_DOWN),1,1,ROOT,2,4,1,NONE},
    {1,B(A),1,1,CONTROLS,0,4,1,NONE},
    {1,B(D_RIGHT),1,1,CONTROLS,0,4,3,NONE},
    {1,B(B),1,1,ROOT,2,4,3,NONE},
    {2,B(START),1,2,ROOT,0,4,3,NONE},
    {2,B(D_UP),1,2,ROOT,2,4,3,NONE},
    {2,B(A),1,2,CONTROLS,0,4,3,NONE},
    {2,B(D_LEFT),1,2,CONTROLS,0,4,7,NONE},
    {3,B(START),1,3,ROOT,0,4,7,NONE},
    {3,B(D_DOWN),1,3,ROOT,2,4,7,NONE},
    {3,B(A),1,3,CONTROLS,0,4,7,NONE},
    {3,B(A),1,3,CONTROLS,0,4,15,NONE},
    {3,B(D_LEFT),1,3,CONTROLS,0,4,7,NONE},
    {3,B(START),0,3,ROOT,0,4,7,NONE},
    {0,0,0,3,ROOT,0,4,7,NONE},
    {0,B(START),1,0,ROOT,0,4,7,NONE},
    {0,B(D_DOWN),1,0,ROOT,1,4,7,NONE},
    {0,B(A),1,0,SETUP,0,4,7,NONE},
    {0,B(D_DOWN),1,0,SETUP,1,4,7,NONE},
    {0,B(A),0,0,ROOT,0,4,7,BG_MENU_ACTION_RESTART},
    {0,B(START),1,0,ROOT,0,4,7,NONE},
    {0,B(D_UP),1,0,ROOT,2,4,7,NONE},
    {0,B(A),1,0,CONTROLS,0,4,7,NONE},
    {3,B(START),1,3,ROOT,0,4,7,NONE},
    {3,B(D_DOWN),1,3,ROOT,2,4,7,NONE},
    {3,B(A),1,3,CONTROLS,0,4,7,NONE},
    {3,0,1,3,CONTROLS,0,4,7,NONE}
};
#undef ROOT
#undef SETUP
#undef CONTROLS
#undef B
#undef NONE
static uint64_t deadline;
static unsigned step;
static bool started,edge,complete;
unsigned bg_menu_qa_step(void){return step;}
bool bg_menu_qa_done(void){return complete;}
void bg_menu_qa_input(bg_control_state raw[BG_PLAYERS],uint64_t now){
    memset(raw,0,sizeof(*raw)*BG_PLAYERS);edge=false;
    if(!started){started=true;deadline=now+2000000;edge=true;}
    else if(now>=deadline&&step+1<sizeof(script)/sizeof(script[0])){
        step++;deadline=now+(step==27?10000000:2000000);edge=true;
    }
    if(edge)raw[script[step].port].held=raw[script[step].port].pressed=script[step].button;
    /* A short actual simulation segment mixes Xbox movement/aim with N64
     * movement/aim, without direct player-state assignments. */
    if(step==27){
        raw[0]=(bg_control_state){.held=BG_BUTTON_D_UP|BG_BUTTON_Z|BG_BUTTON_R,
            .pressed=edge?BG_BUTTON_C_LEFT:0,.stick_x=20,.stick_y=10};
        raw[1]=(bg_control_state){.held=BG_BUTTON_D_RIGHT|BG_BUTTON_R,
            .pressed=edge?BG_BUTTON_C_UP:0,.stick_x=-20,.stick_y=-10};
        raw[2]=(bg_control_state){.pressed=edge?BG_BUTTON_C_UP:0};
        raw[3]=(bg_control_state){.held=BG_BUTTON_C_LEFT|BG_BUTTON_R,
            .pressed=edge?BG_BUTTON_R:0,.stick_x=20,.stick_y=60};
        for(unsigned p=0;p<BG_PLAYERS;p++)raw[p].held|=raw[p].pressed;
        assert(bg_controls_show_scores(&raw[0],BG_CONTROLS_XBOX));
        assert(bg_controls_show_scores(&raw[1],BG_CONTROLS_XBOX));
        assert(!bg_controls_show_scores(&raw[2],BG_CONTROLS_XBOX));
        assert(!bg_controls_show_scores(&raw[3],BG_CONTROLS_N64));
    }
}
static bool input_empty(const bg_input *in){
    return !in->forward&&!in->strafe&&!in->turn&&!in->look&&!in->jump&&!in->fire&&
        !in->reload&&!in->switch_weapon&&!in->grenade&&!in->switch_grenade&&
        !in->interact&&!in->melee&&!in->zoom&&!in->crouch&&!in->secondary_fire;
}
void bg_menu_qa_check(const bg_menu *m,unsigned views,const bg_menu_result *r,
    const bg_input in[BG_PLAYERS]){
    const checkpoint *s=&script[step];
    assert(m->open==s->open&&m->owner==s->owner&&m->page==s->page&&m->row==s->row);
    assert(views==s->players&&m->player_count==s->players);
    assert(r->action==(edge?s->action:BG_MENU_ACTION_NONE));
    for(unsigned p=0;p<BG_PLAYERS;p++){
        assert(m->styles[p]==((s->xbox_mask&(1u<<p))?BG_CONTROLS_XBOX:BG_CONTROLS_N64));
        if(r->consumed)assert(input_empty(&in[p]));
    }
    if(step==27){
        assert(!r->consumed&&in[0].forward==1&&in[0].fire&&in[0].turn<0&&in[0].look>0);
        assert(in[1].forward==0&&in[1].strafe==1&&in[1].turn>0&&in[1].look<0);
        assert(in[3].forward==.75f&&in[3].strafe==-1&&in[3].turn<0&&in[3].look==0);
        assert(in[0].reload==edge&&in[0].interact==edge&&!in[0].switch_weapon&&!in[0].zoom);
        assert(in[1].zoom==edge&&!in[1].switch_weapon&&!in[1].reload);
        assert(in[2].switch_weapon==edge&&!in[2].zoom&&!in[2].reload);
        assert(in[3].switch_weapon==edge&&!in[3].zoom&&!in[3].reload);
    }
    if(step+1==sizeof(script)/sizeof(script[0]))complete=true;
}
