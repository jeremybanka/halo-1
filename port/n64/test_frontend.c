#include "frontend.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t now;
static bg_front_action press(bg_frontend*f,unsigned p,uint32_t button){
    bg_control_state in[4]={0};in[p].held=in[p].pressed=button;now+=20000;
    return bg_front_update(f,in,now);
}
static void joins(bg_frontend*f,unsigned mask,unsigned host){
    bg_front_init(f);press(f,host,BG_BUTTON_A);assert(f->page==BG_FRONT_MULTIPLAYER);
    press(f,host,BG_BUTTON_A);assert(f->page==BG_FRONT_JOIN);
    for(unsigned p=0;p<4;p++)if(mask&(1u<<p)){
        press(f,p,BG_BUTTON_START);assert(f->joined[p]&&!f->ready[p]);
        press(f,p,BG_BUTTON_A);assert(f->ready[p]&&f->page==BG_FRONT_JOIN);
    }
    press(f,host,BG_BUTTON_A);assert(f->page==BG_FRONT_MAP);
}
int main(void){
    bg_frontend f;
    for(unsigned mask=1;mask<16;mask++)for(unsigned host=0;host<4;host++)if(mask&(1u<<host)){
        joins(&f,mask,host);assert(f.count==(unsigned)__builtin_popcount(mask));assert(f.ports[0]==host);
        bg_control_state physical[4],mapped[4];
        for(unsigned p=0;p<4;p++)physical[p]=(bg_control_state){.stick_x=13+p,.stick_y=-25+p,.held=1u<<p,.pressed=16u<<p};
        bg_front_map_controls(&f,physical,mapped);
        for(unsigned p=0;p<f.count;p++)assert(!memcmp(&mapped[p],&physical[f.ports[p]],sizeof(mapped[p])));
        for(unsigned p=f.count;p<4;p++){const bg_control_state zero={0};assert(!memcmp(&mapped[p],&zero,sizeof(zero)));}
        bg_front_map_controls(&f,physical,physical);assert(!memcmp(mapped,physical,sizeof(mapped)));
        unsigned packed=0;for(unsigned p=0;p<f.count;p++)packed|=1u<<f.ports[p];assert(packed==mask);
        press(&f,host,BG_BUTTON_D_LEFT);assert(f.map==8);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_MAP);
        press(&f,host,BG_BUTTON_D_RIGHT);assert(f.map==9);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_TYPE&&f.type==0);
        for(unsigned i=1;i<26;i++){press(&f,host,BG_BUTTON_D_RIGHT);assert(f.type==i);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_TYPE);}
        press(&f,host,BG_BUTTON_D_RIGHT);assert(f.type==0);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_PREGAME);
        uint64_t deadline=f.deadline;press(&f,host,BG_BUTTON_C_LEFT);assert(f.deadline==deadline+5000000);
        press(&f,host,BG_BUTTON_A);assert(f.deadline==deadline);press(&f,host,BG_BUTTON_A);press(&f,host,BG_BUTTON_A);assert(f.deadline==now+999000);
        bg_control_state empty[4]={0};assert(bg_front_update(&f,empty,f.deadline-1)==BG_FRONT_NONE);
        assert(bg_front_update(&f,empty,f.deadline)==BG_FRONT_START_MATCH&&f.page==BG_FRONT_PLAY);
        bg_front_quit(&f);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_PLAY);
        const int scores[4]={15,4,-1,7};bg_front_results(&f,scores,0);assert(!memcmp(scores,f.final_scores,sizeof(scores)));
        press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_MAP);press(&f,host,BG_BUTTON_A);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_PREGAME);
        press(&f,host,BG_BUTTON_B);assert(f.page==BG_FRONT_TYPE&&f.deadline==0);
    }
    bg_front_init(&f);press(&f,0,BG_BUTTON_D_UP);press(&f,0,BG_BUTTON_A);assert(f.page==BG_FRONT_MAIN);
    press(&f,0,BG_BUTTON_D_DOWN);press(&f,0,BG_BUTTON_D_DOWN);press(&f,0,BG_BUTTON_A);assert(f.page==BG_FRONT_SETTINGS);
    press(&f,0,BG_BUTTON_A);assert(f.page==BG_FRONT_PROFILE);press(&f,0,BG_BUTTON_A);press(&f,0,BG_BUTTON_D_RIGHT);assert(f.styles[0]==BG_CONTROLS_XBOX);
    press(&f,0,BG_BUTTON_B);press(&f,0,BG_BUTTON_B);assert(f.styles[0]==BG_CONTROLS_XBOX);
    joins(&f,3,0);press(&f,0,BG_BUTTON_A);press(&f,0,BG_BUTTON_A);f.map=0;
    bg_control_state empty[4]={0};assert(bg_front_update(&f,empty,f.deadline)==BG_FRONT_NONE&&f.page==BG_FRONT_JOIN);
    puts("front-end: all rosters/hosts, 26 presets, capability guards, countdown, cancel, results, controls PASS");
}
