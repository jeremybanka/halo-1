/* Real controller edges through the production shell; encounter unchanged. */
#include "frontend_qa.h"
#include <assert.h>
#include <string.h>
#include <libdragon.h>
#include "pve.h"
#include "map.h"
typedef struct {bg_front_page page;unsigned ports;uint32_t button;} qa_step;
#define PORTS ((1u<<BG_FRONTEND_QA_PLAYERS)-1)
static const qa_step steps[]={
 {BG_FRONT_MAIN,1,BG_BUTTON_D_DOWN},{BG_FRONT_MAIN,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_MAIN,1,BG_BUTTON_A},
 {BG_FRONT_JOIN,PORTS,BG_BUTTON_START},{BG_FRONT_JOIN,PORTS,BG_BUTTON_A},
 {BG_FRONT_JOIN,1,BG_BUTTON_A},
 {BG_FRONT_MAP,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,BG_BUTTON_A},
 {BG_FRONT_MAP,1,BG_BUTTON_D_RIGHT},{BG_FRONT_MAP,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,BG_BUTTON_B},{BG_FRONT_MAP,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,BG_BUTTON_A},
 {BG_FRONT_PLAY,1,BG_BUTTON_START},{BG_FRONT_PLAY,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_PLAY,1,BG_BUTTON_A},{BG_FRONT_PLAY,1,BG_BUTTON_A}, /* restart */
 {BG_FRONT_PLAY,1,BG_BUTTON_START},{BG_FRONT_PLAY,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_PLAY,1,BG_BUTTON_A},{BG_FRONT_PLAY,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_PLAY,1,BG_BUTTON_A},{BG_FRONT_QUIT,1,BG_BUTTON_A}, /* cancel quit */
 {BG_FRONT_PLAY,1,BG_BUTTON_START},{BG_FRONT_PLAY,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_PLAY,1,BG_BUTTON_A},{BG_FRONT_PLAY,1,BG_BUTTON_D_DOWN},
 {BG_FRONT_PLAY,1,BG_BUTTON_A},{BG_FRONT_QUIT,1,BG_BUTTON_D_UP},
 {BG_FRONT_QUIT,1,BG_BUTTON_A},
 /* Verify a normal multiplayer launch after the squad has been cleared. */
 {BG_FRONT_MAIN,1,BG_BUTTON_A},{BG_FRONT_MULTIPLAYER,1,BG_BUTTON_A},
 {BG_FRONT_JOIN,1,BG_BUTTON_A},{BG_FRONT_MAP,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,BG_BUTTON_A},{BG_FRONT_PLAY,0,0}
};
static unsigned current;static uint64_t deadline;static bool done;
unsigned bg_front_qa_step(void){return current;}
unsigned bg_front_qa_steps(void){return sizeof(steps)/sizeof(*steps);}
bool bg_front_qa_done(void){return done;}
void bg_front_qa_resumed(void){assert(bg_pve_is_active());}
void bg_front_qa_input(const bg_frontend*f,bg_control_state raw[4],uint64_t now){
 memset(raw,0,4*sizeof(*raw));if(done)return;
#ifdef BG_FIREFIGHT_QA_PHOTO
 if(current==BG_FIREFIGHT_QA_PHOTO)return;
#endif
 const qa_step*s=&steps[current];
 if(!deadline){
   /* Hold the key appraisal screens long enough for native capture. */
   unsigned delay=current==2||current==5||current==9?5:1;
   if(current==14||current==18)delay=20; /* Enter with live actors and a departing transport. */
   deadline=now+delay*1000000u;return;
 }
 if(now<deadline)return;
 /* Input is sampled before the front-end update. Allow its next update to
    consume the final countdown tick, without hiding a stalled transition. */
 if((current==14||current==38)&&f->page==BG_FRONT_PREGAME&&
    now<f->deadline+2000000u)return;
 assertf(f->page==s->page,"Firefight QA step %u page %u expected %u",current,f->page,s->page);
 if(f->page==BG_FRONT_PLAY){
   bool expected=current<31;
   if(current==14||current==18)assertf(bg_pve_count>0,"Exercise live arrival before restart/quit");
   assertf(bg_pve_is_active()==expected,"Firefight session cleanup");
   assertf(bg_player_count()==BG_FRONTEND_QA_PLAYERS,"Firefight player count");
   assertf(bg_ff.active==expected&&bg_pve_count<=BG_PVE_MAX&&(!expected?bg_pve_count==0:true),"Firefight director/actor lifecycle");
 }
 for(unsigned p=0;p<4;p++)if(s->ports&(1u<<p))raw[p].pressed=raw[p].held=s->button;
 debugf("FIREFIGHT_QA step=%u page=%u players=%u npcs=%u active=%u\n",current,f->page,bg_player_count(),bg_pve_count,bg_pve_is_active());
 if(++current==bg_front_qa_steps()){done=true;current--;debugf("FIREFIGHT_QA PASS players=%u\n",BG_FRONTEND_QA_PLAYERS);}
 deadline=0;
}
void bg_front_qa_tick(bg_input in[4],float seconds){(void)in;(void)seconds;}
