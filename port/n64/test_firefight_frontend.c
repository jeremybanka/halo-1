#include "frontend.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t now;
static bg_front_action press(bg_frontend*f,unsigned p,uint32_t b){
 bg_control_state raw[4]={0};raw[p].pressed=raw[p].held=b;now+=20000;
 return bg_front_update(f,raw,now);
}
static void enter(bg_frontend*f,unsigned host){
 bg_front_init(f);press(f,host,BG_BUTTON_D_DOWN);press(f,host,BG_BUTTON_D_DOWN);
 press(f,host,BG_BUTTON_A);assert(f->firefight&&f->page==BG_FRONT_JOIN);
}
int main(void){
 bg_frontend f;bg_control_state raw[4]={0};unsigned rosters=0;
 bg_front_set_memory_size(4*1024*1024);assert(!bg_front_available(BG_FRONT_MAIN,3));
 bg_front_set_memory_size(8*1024*1024);assert(bg_front_available(BG_FRONT_MAIN,3));
 for(unsigned mask=1;mask<16;mask++)for(unsigned host=0;host<4;host++)if(mask&(1u<<host)){
  enter(&f,host);for(unsigned p=0;p<4;p++)if(mask&(1u<<p)){press(&f,p,BG_BUTTON_START);press(&f,p,BG_BUTTON_A);}
  press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_MAP&&f.count==(unsigned)__builtin_popcount(mask));
  assert(f.ports[0]==host);
  unsigned seen=0;for(unsigned i=0;i<f.count;i++)seen|=1u<<f.ports[i];assert(seen==mask);
  for(unsigned map=0;map<13;map++){
   f.map=map;assert(bg_front_session_available(&f,BG_FRONT_MAP,map)==(map==9));
   if(map!=9){press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_MAP);}
  }
  f.map=9;press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_FIGHT&&f.fight==BG_FF_ONSLAUGHT);
  press(&f,host,BG_BUTTON_B);assert(f.page==BG_FRONT_MAP);
  press(&f,host,BG_BUTTON_A);
  for(unsigned fight=0;fight<BG_FF_FIGHTS;fight++){
   assert(f.fight==fight);bool available=bg_ff_fight_available(fight);
   assert(bg_front_session_available(&f,BG_FRONT_FIGHT,fight)==available);
   press(&f,host,BG_BUTTON_A);
   if(available){
    assert(f.page==BG_FRONT_PREGAME);press(&f,host,BG_BUTTON_B);assert(f.page==BG_FRONT_FIGHT&&f.fight==fight);
    press(&f,host,BG_BUTTON_A);assert(bg_front_update(&f,raw,f.deadline)==BG_FRONT_START_MATCH&&f.fight==fight);
    bg_front_results(&f,(int[4]){0},0);press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_MAP);
    press(&f,host,BG_BUTTON_A);assert(f.page==BG_FRONT_FIGHT&&f.fight==fight);
   }else assert(f.page==BG_FRONT_FIGHT);
   press(&f,host,BG_BUTTON_D_DOWN);
  }
  assert(f.fight==BG_FF_ONSLAUGHT);press(&f,host,BG_BUTTON_D_UP);assert(f.fight==BG_FF_GAUNTLET);
  press(&f,host,BG_BUTTON_D_DOWN);press(&f,host,BG_BUTTON_A);assert(bg_front_update(&f,raw,f.deadline)==BG_FRONT_START_MATCH);
  bg_front_quit(&f);assert(press(&f,host,BG_BUTTON_A)==BG_FRONT_RESUME_MATCH);
  bg_front_quit(&f);press(&f,host,BG_BUTTON_D_UP);assert(press(&f,host,BG_BUTTON_A)==BG_FRONT_LEAVE_MATCH);
  assert(f.page==BG_FRONT_MAIN);press(&f,host,BG_BUTTON_A);assert(!f.firefight&&f.page==BG_FRONT_MULTIPLAYER);
  for(unsigned map=0;map<13;map++)assert(bg_front_session_available(&f,BG_FRONT_MAP,map));
  rosters++;
 }
 enter(&f,3);press(&f,3,BG_BUTTON_B);assert(f.page==BG_FRONT_MAIN);
 enter(&f,2);press(&f,2,BG_BUTTON_START);for(unsigned n=0;n<4;n++)press(&f,2,BG_BUTTON_A);
 f.map=1;assert(bg_front_update(&f,raw,f.deadline)==BG_FRONT_NONE&&f.page==BG_FRONT_JOIN);
 enter(&f,0);press(&f,0,BG_BUTTON_START);for(unsigned n=0;n<4;n++)press(&f,0,BG_BUTTON_A);
 f.fight=BG_FF_FIGHTS;assert(bg_front_update(&f,raw,f.deadline)==BG_FRONT_NONE&&f.page==BG_FRONT_JOIN);
 enter(&f,0);press(&f,0,BG_BUTTON_START);for(unsigned n=0;n<4;n++)press(&f,0,BG_BUTTON_A);
 bg_front_set_memory_size(4*1024*1024);assert(bg_front_update(&f,raw,f.deadline)==BG_FRONT_NONE&&f.page==BG_FRONT_JOIN);
 printf("PASS Firefight %u roster/host combinations, both fights, selection wrap/back/results, P3/P4, 1–4 players, cancel/resume/quit and launch guards\n",rosters);
}
