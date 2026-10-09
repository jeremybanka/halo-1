#include "menu.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static bg_menu_result press(bg_menu *m,unsigned active,unsigned player,uint32_t buttons){
    bg_menu_input in[BG_PLAYERS]={0};in[player].pressed=buttons;
    return bg_menu_update(m,in,active);
}

static void open_menu(bg_menu *m,unsigned active,unsigned player){
    assert(!m->open);
    bg_menu_result r=press(m,active,player,BG_BUTTON_START|BG_BUTTON_A);
    assert(r.consumed&&r.action==BG_MENU_ACTION_NONE);
    assert(m->open&&m->owner==player&&m->page==BG_MENU_ROOT&&m->row==0);
}

static void enter_controls(bg_menu *m,unsigned active){
    press(m,active,m->owner,BG_BUTTON_D_UP);
    assert(m->row==BG_MENU_CONTROLS_ROW);
    press(m,active,m->owner,BG_BUTTON_A);
    assert(m->page==BG_MENU_CONTROLS&&m->row==0);
}

static void transitions_test(void){
    bg_menu m;bg_menu_init(&m,4);
    assert(!m.open&&m.player_count==4&&bg_menu_row_count(&m)==3);
    for(unsigned p=0;p<4;p++)assert(m.styles[p]==BG_CONTROLS_N64);
    assert(!press(&m,4,0,BG_BUTTON_A).consumed);
    open_menu(&m,4,0);
    press(&m,4,0,BG_BUTTON_D_DOWN|BG_BUTTON_A);
    assert(m.page==BG_MENU_ROOT&&m.row==BG_MENU_SETUP_ROW&&m.player_count==4);
    bg_menu_result r=press(&m,4,0,BG_BUTTON_A|BG_BUTTON_D_RIGHT);
    assert(m.page==BG_MENU_SETUP&&m.row==0&&m.player_count==4);
    assert(r.action==BG_MENU_ACTION_NONE); /* entry A cannot change setup */
    r=press(&m,4,0,BG_BUTTON_B|BG_BUTTON_A);
    assert(m.page==BG_MENU_ROOT&&m.row==BG_MENU_SETUP_ROW&&r.action==BG_MENU_ACTION_NONE);
    press(&m,4,0,BG_BUTTON_D_DOWN);press(&m,4,0,BG_BUTTON_A);
    assert(m.page==BG_MENU_CONTROLS&&m.styles[0]==BG_CONTROLS_N64);
    press(&m,4,0,BG_BUTTON_B);
    assert(m.page==BG_MENU_ROOT&&m.row==BG_MENU_CONTROLS_ROW);
    r=press(&m,4,0,BG_BUTTON_B|BG_BUTTON_A);
    assert(!m.open&&r.consumed&&r.action==BG_MENU_ACTION_NONE);
    assert(!press(&m,4,0,0).consumed);
    open_menu(&m,4,0);r=press(&m,4,0,BG_BUTTON_A);
    assert(!m.open&&r.consumed&&r.action==BG_MENU_ACTION_NONE);
    open_menu(&m,4,0);enter_controls(&m,4);
    r=press(&m,4,0,BG_BUTTON_START|BG_BUTTON_A);
    assert(!m.open&&m.page==BG_MENU_ROOT&&m.styles[0]==BG_CONTROLS_N64&&r.consumed);
}

static void ownership_test(void){
    for(unsigned owner=0;owner<4;owner++){
        bg_menu m;bg_menu_init(&m,4);open_menu(&m,4,owner);
        assert(bg_menu_row_enabled(&m,BG_MENU_SETUP_ROW)==(owner==0));
        assert(!bg_menu_row_enabled(&m,3));
        press(&m,4,owner,BG_BUTTON_D_DOWN);
        assert(m.row==(owner==0?BG_MENU_SETUP_ROW:BG_MENU_CONTROLS_ROW));
        press(&m,4,owner,BG_BUTTON_D_DOWN);
        assert(m.row==(owner==0?BG_MENU_CONTROLS_ROW:BG_MENU_RESUME));
        if(owner!=0){
            m.row=BG_MENU_SETUP_ROW; /* dispatch is protected as well */
            bg_menu_result r=press(&m,4,owner,BG_BUTTON_A);
            assert(r.action==BG_MENU_ACTION_NONE&&m.page==BG_MENU_ROOT);
            m.page=BG_MENU_SETUP;m.row=BG_MENU_RESTART_ROW;
            r=press(&m,4,owner,BG_BUTTON_A);
            assert(r.action==BG_MENU_ACTION_NONE&&m.page==BG_MENU_ROOT&&m.open);
        }
        for(unsigned other=0;other<4;other++)if(other!=owner){
            const bg_menu before=m;
            bg_menu_result r=press(&m,4,other,
                BG_BUTTON_A|BG_BUTTON_B|BG_BUTTON_D_DOWN|BG_BUTTON_D_RIGHT);
            assert(!memcmp(&m,&before,sizeof(m))&&r.consumed&&r.action==BG_MENU_ACTION_NONE);
        }
    }
    bg_menu m;bg_menu_init(&m,4);open_menu(&m,4,0);
    press(&m,4,0,BG_BUTTON_D_DOWN);press(&m,4,0,BG_BUTTON_A);
    assert(m.page==BG_MENU_SETUP);
    bg_menu_result r=press(&m,4,2,BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_D_DOWN);
    assert(m.open&&m.owner==2&&m.page==BG_MENU_ROOT&&m.row==0);
    assert(r.consumed&&r.action==BG_MENU_ACTION_NONE&&!bg_menu_row_enabled(&m,1));
    press(&m,4,2,BG_BUTTON_D_DOWN);assert(m.row==BG_MENU_CONTROLS_ROW);
    r=press(&m,4,2,BG_BUTTON_START|BG_BUTTON_A);
    assert(!m.open&&r.consumed&&r.action==BG_MENU_ACTION_NONE);
}

static void simultaneous_start_test(void){
    const unsigned counts[]={1,2,4};
    for(unsigned c=0;c<3;c++)for(unsigned mask=1;mask<16;mask++)
    for(unsigned owner=0;owner<counts[c];owner++)for(unsigned open=0;open<2;open++){
        bg_menu m;bg_menu_init(&m,counts[c]);m.open=open;m.owner=owner;
        m.page=BG_MENU_CONTROLS;
        bg_menu_input in[BG_PLAYERS]={0};unsigned first=4;
        for(unsigned p=0;p<4;p++)if(mask&(1u<<p)){
            in[p].pressed=BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_D_DOWN;
            if(first==4&&p<counts[c])first=p;
        }
        bg_menu_result r=bg_menu_update(&m,in,counts[c]);
        assert(r.action==BG_MENU_ACTION_NONE);
        if(first==4){assert(m.open==(bool)open&&m.owner==owner);continue;}
        assert(r.consumed&&m.page==BG_MENU_ROOT&&m.row==0);
        assert(m.open==!(open&&owner==first));
        if(m.open)assert(m.owner==first);
        for(unsigned p=0;p<4;p++)assert(m.styles[p]==BG_CONTROLS_N64);
    }
}

static void count_and_preferences_test(void){
    bg_menu m;bg_menu_init(&m,4);
    for(unsigned p=0;p<4;p++){
        open_menu(&m,4,p);enter_controls(&m,4);
        press(&m,4,p,BG_BUTTON_D_RIGHT);
        for(unsigned q=0;q<4;q++)assert(m.styles[q]==(q<=p?BG_CONTROLS_XBOX:BG_CONTROLS_N64));
        press(&m,4,p,BG_BUTTON_D_LEFT);assert(m.styles[p]==BG_CONTROLS_N64);
        press(&m,4,p,BG_BUTTON_A);assert(m.styles[p]==BG_CONTROLS_XBOX);
        press(&m,4,p,BG_BUTTON_START);
    }
    open_menu(&m,4,0);press(&m,4,0,BG_BUTTON_D_DOWN);press(&m,4,0,BG_BUTTON_A);
    const unsigned right[]={1,2,4,1,2,4};
    unsigned active=4;
    for(unsigned n=0;n<6;n++){
        bg_menu_result r=press(&m,active,0,n%2?BG_BUTTON_A:BG_BUTTON_D_RIGHT);
        assert(r.action==BG_MENU_ACTION_PLAYER_COUNT&&r.player_count==right[n]);
        assert(m.player_count==right[n]&&m.open&&m.page==BG_MENU_SETUP);active=r.player_count;
        for(unsigned p=0;p<4;p++)assert(m.styles[p]==BG_CONTROLS_XBOX);
    }
    const unsigned left[]={2,1,4};
    for(unsigned n=0;n<3;n++){
        bg_menu_result r=press(&m,active,0,BG_BUTTON_D_LEFT);
        assert(r.action==BG_MENU_ACTION_PLAYER_COUNT&&r.player_count==left[n]);active=r.player_count;
    }
    press(&m,4,0,BG_BUTTON_D_DOWN);assert(m.row==BG_MENU_RESTART_ROW);
    assert(press(&m,4,0,BG_BUTTON_D_RIGHT).action==BG_MENU_ACTION_NONE);
    bg_menu_result r=press(&m,4,0,BG_BUTTON_A);
    assert(r.action==BG_MENU_ACTION_RESTART&&r.consumed&&!m.open);
    for(unsigned p=0;p<4;p++)assert(m.styles[p]==BG_CONTROLS_XBOX);
    open_menu(&m,1,0);enter_controls(&m,1);press(&m,1,0,BG_BUTTON_A);
    assert(m.styles[0]==BG_CONTROLS_N64);
    for(unsigned p=1;p<4;p++)assert(m.styles[p]==BG_CONTROLS_XBOX);
    const bg_menu before=m;
    for(unsigned p=1;p<4;p++){
        r=press(&m,1,p,BG_BUTTON_START|BG_BUTTON_A);
        assert(!memcmp(&m,&before,sizeof(m))&&r.action==BG_MENU_ACTION_NONE);
    }
    press(&m,1,0,BG_BUTTON_START);open_menu(&m,4,3);
    r=press(&m,2,3,0);assert(r.consumed&&!m.open); /* removed owner */
    assert(!press(&m,0,0,BG_BUTTON_START).consumed&&!m.open);
}

static void analog_test(void){
    bg_menu m;bg_menu_init(&m,4);
    bg_control_state raw[BG_PLAYERS]={0};bg_menu_input in[BG_PLAYERS];
    bg_menu_inputs(&m,raw,in); /* neutral arms every axis */
    raw[0].pressed=BG_BUTTON_START;raw[0].stick_y=-80;
    raw[1].stick_y=-80;
    bg_menu_inputs(&m,raw,in);assert(in[0].nav_vertical==1&&in[1].nav_vertical==1);
    bg_menu_update(&m,in,4);assert(m.open&&m.row==0);
    raw[0].pressed=0;
    for(unsigned n=0;n<4;n++){
        bg_menu_inputs(&m,raw,in);assert(!in[0].nav_vertical&&!in[1].nav_vertical);
        bg_menu_update(&m,in,4);assert(m.row==0);
    }
    raw[0].stick_y=80;bg_menu_inputs(&m,raw,in);assert(!in[0].nav_vertical);
    raw[0].stick_y=21;bg_menu_inputs(&m,raw,in);assert(!in[0].nav_vertical);
    raw[0].stick_y=20;bg_menu_inputs(&m,raw,in);assert(!in[0].nav_vertical);
    raw[0].stick_y=-39;bg_menu_inputs(&m,raw,in);assert(!in[0].nav_vertical);
    raw[0].stick_y=-40;raw[0].stick_x=40;
    bg_menu_inputs(&m,raw,in);assert(in[0].nav_vertical==1&&in[0].nav_horizontal==1);
    bg_menu_update(&m,in,4);assert(m.row==BG_MENU_SETUP_ROW&&m.page==BG_MENU_ROOT);
    /* A + analog down moves only. Repeated held input never moves again. */
    raw[0].stick_y=0;bg_menu_inputs(&m,raw,in);
    raw[0].stick_y=-80;raw[0].pressed=BG_BUTTON_A;
    bg_menu_inputs(&m,raw,in);bg_menu_update(&m,in,4);
    assert(m.row==BG_MENU_CONTROLS_ROW&&m.page==BG_MENU_ROOT);
    raw[0].pressed=0;raw[1].pressed=BG_BUTTON_START;
    bg_menu_inputs(&m,raw,in);bg_menu_update(&m,in,4);
    assert(m.owner==1&&m.row==0);
    raw[1].pressed=0;bg_menu_inputs(&m,raw,in);bg_menu_update(&m,in,4);
    assert(m.row==0); /* P2's pre-held stick stays suppressed after transfer */
    raw[1].stick_y=0;bg_menu_inputs(&m,raw,in);
    raw[1].stick_y=-80;bg_menu_inputs(&m,raw,in);bg_menu_update(&m,in,4);
    assert(m.row==BG_MENU_CONTROLS_ROW); /* skips forbidden Setup */
    in[1]=(bg_menu_input){.pressed=BG_BUTTON_D_UP|BG_BUTTON_D_DOWN,.nav_vertical=1};
    bg_menu_update(&m,in,4);assert(m.row==BG_MENU_CONTROLS_ROW);
    in[1]=(bg_menu_input){.pressed=BG_BUTTON_D_DOWN,.nav_vertical=-1};
    bg_menu_update(&m,in,4);assert(m.row==BG_MENU_RESUME); /* D-pad priority */
}

static void shell_setup_test(void){
    bg_menu m;bg_menu_init(&m,3);m.shell_session=true;
    open_menu(&m,3,0);press(&m,3,0,BG_BUTTON_D_DOWN);press(&m,3,0,BG_BUTTON_A);
    assert(m.page==BG_MENU_SETUP&&m.row==0);
    bg_menu_result r=press(&m,3,0,BG_BUTTON_D_RIGHT);
    assert(r.action==BG_MENU_ACTION_NONE&&m.player_count==3);
    r=press(&m,3,0,BG_BUTTON_A);assert(r.consumed&&r.action==BG_MENU_ACTION_RESTART&&!m.open);
    open_menu(&m,3,0);press(&m,3,0,BG_BUTTON_D_DOWN);press(&m,3,0,BG_BUTTON_A);
    press(&m,3,0,BG_BUTTON_D_DOWN);r=press(&m,3,0,BG_BUTTON_A);
    assert(r.consumed&&r.action==BG_MENU_ACTION_QUIT&&!m.open&&m.player_count==3);
    open_menu(&m,3,2);press(&m,3,2,BG_BUTTON_D_DOWN);assert(m.row==BG_MENU_CONTROLS_ROW);
}
int main(void){
    shell_setup_test();
    transitions_test();ownership_test();simultaneous_start_test();
    count_and_preferences_test();analog_test();
    puts("PASS: menu ownership, setup permissions, independent preferences, input consumption, count cycling, simultaneous Start and analog rearm");
    return 0;
}
