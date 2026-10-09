#include "game.h"
#include "pickup_rules.h"
#include "shield_fixture.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static bg_input in[4];
static void ticks(unsigned n){while(n--){bg_clear_events();bg_tick(in,1.f/30);}}
static void reset(void){bg_set_players(4);bg_reset();bg_vehicle_count=bg_pickup_count=0;memset(in,0,sizeof(in));
 for(unsigned i=0;i<4;i++){bg_player*p=&bg_players[i];p->pos[0]=-12.f+i*8;p->pos[2]=5;p->pos[1]=bg_floor(p->pos[0],5,100)+.015f;p->weapon_ready=p->cooldown=0;}}
static void use(unsigned p){in[p].interact=true;ticks(12);in[p].interact=false;ticks(1);}
static void eligibility(void){
 bg_set_players(4);bg_reset();assert(bg_players[0].weapon==BG_W_PLASMA_PISTOL&&bg_players[0].inventory[1]==-1);
 assert(bg_players[0].grenades[0]==0&&bg_players[0].grenades[1]==0);
 assert(bg_pickup_count==39);unsigned eligible=0;for(unsigned i=0;i<bg_spawn_count;i++)eligible+=bg_slayer_spawns[i];assert(eligible==16);
 for(unsigned p=0;p<4;p++){unsigned nearest=0;float best=1e9f;for(unsigned i=0;i<bg_spawn_count;i++){float dx=bg_players[p].pos[0]-bg_spawns[i].pos[0],dz=bg_players[p].pos[2]-bg_spawns[i].pos[2];float d=dx*dx+dz*dz;if(d<best){best=d;nearest=i;}}assert(bg_slayer_spawns[nearest]&&best<.001f);}
 bg_vehicle_count=0;for(unsigned p=0;p<4;p++)bg_players[p].health=0;
 unsigned index=0;while(!bg_slayer_spawns[index])index++;
 assert(bg_spawn_rating(0,index)==1);bg_players[1].health=100;memcpy(bg_players[1].pos,bg_spawns[index].pos,12);
 bg_players[1].pos[0]+=1.99f;assert(bg_spawn_rating(0,index)==0);
 bg_players[1].pos[0]+=.51f;assert(fabsf(bg_spawn_rating(0,index)-1.f/6)<.0001f);
 for(unsigned n=0;n<300;n++){int i=bg_select_spawn(0);assert(i>=0&&bg_slayer_spawns[i]&&bg_spawn_rating(0,i)>0);}
 bg_players[1].health=0;bg_add_vehicle(BG_V_WARTHOG,bg_spawns[index].pos,0);memcpy(bg_vehicles[0].pos,bg_spawns[index].pos,12);assert(bg_spawn_rating(0,index)==0);
}
static void conservation(void){
 reset();bg_player*p=&bg_players[0];int i=bg_add_pickup(BG_W_AR,p->pos);assert(bg_pickups[i].ammo==60&&bg_pickups[i].reserve==180);
 use(0);assert(p->weapon==BG_W_AR&&p->inventory[0]==BG_W_PLASMA_PISTOL&&p->inventory[1]==BG_W_AR);assert(p->ammo==60&&p->reserve==180);
 ticks(35);p->ammo=7;p->reserve=595;i=bg_add_pickup(BG_W_AR,p->pos);bg_pickup*q=&bg_pickups[i];q->ammo=11;q->reserve=3;
 ticks(1);assert(p->ammo==7&&p->reserve==600&&q->ammo==9&&q->reserve==0&&q->active);ticks(10);assert(q->ammo==9);
 p->reserve=0;ticks(1);assert(p->reserve==9&&p->ammo==7&&!q->active);
 /* A full inventory swap drops the outgoing partial magazine and reserve. */
 i=bg_add_pickup(BG_W_SNIPER,p->pos);use(0);assert(p->weapon==BG_W_SNIPER&&p->ammo==4&&p->reserve==8);
 unsigned dropped=0;for(unsigned j=0;j<bg_pickup_count;j++)if(bg_pickups[j].dropped&&bg_pickups[j].active){assert(bg_pickups[j].weapon==BG_W_AR&&bg_pickups[j].ammo==7&&bg_pickups[j].reserve==9);dropped++;}assert(dropped==1);
 /* Battery pickup requires use and swaps rather than refilling. */
 reset();p=&bg_players[0];p->ammo=23;p->heat=.8f;p->overheated=true;i=bg_add_pickup(BG_W_PLASMA_PISTOL,p->pos);bg_pickups[i].ammo=61;ticks(2);assert(p->ammo==23);use(0);assert(p->ammo==61);
 assert(bg_pickups[1].dropped&&bg_pickups[1].ammo==23&&bg_pickups[1].heat>.5f);
 reset();p=&bg_players[0];p->grenades[0]=3;i=bg_add_pickup(BG_PICK_FRAG,p->pos);bg_pickups[i].quantity=3;ticks(1);assert(p->grenades[0]==4&&bg_pickups[i].quantity==2&&bg_pickups[i].active);
 p->grenades[0]=0;ticks(1);assert(p->grenades[0]==2&&!bg_pickups[i].active);
}
static void death_and_cleanup(void){
 reset();bg_player*p=&bg_players[0];p->ammo=33;p->inventory[1]=BG_W_PISTOL;p->magazines[1]=5;p->reserves[1]=17;p->grenades[0]=2;p->grenades[1]=3;p->shield=0;p->health=1;
 shield_fixture_shot(0,20);ticks(1);assert(p->health==0&&bg_pickup_count==4&&p->ammo==0&&p->respawn==3);
 unsigned rounds=0,grenades=0;for(unsigned i=0;i<4;i++){assert(bg_pickups[i].dropped);rounds+=bg_pickups[i].ammo+bg_pickups[i].reserve;grenades+=bg_pickups[i].quantity*(bg_pickups[i].weapon>=BG_WEAPON_COUNT);}
 assert(rounds==55&&grenades==5);p->respawn=100;
 for(unsigned i=1;i<4;i++)bg_players[i].pos[0]=60;
 for(unsigned t=0;t<360;t++){bg_pickup_mark_visible(0);ticks(1);}assert(bg_pickups[0].active);
 assert(!bg_pickups[1].active&&!bg_pickups[2].active&&!bg_pickups[3].active);
 ticks(90);assert(!bg_pickups[0].active);
 /* Cleanup never revives dropped objects or affects map schedules. */
 ticks(1000);for(unsigned i=0;i<4;i++)assert(!bg_pickups[i].active);
}
static void schedules(void){
 reset();int i=bg_add_pickup(BG_W_ROCKET,(float[]){-30,2,-30});bg_pickup*q=&bg_pickups[i];q->period=90;q->respawn=90;
 ticks(300);q->active=false;ticks(2398);assert(!q->active);ticks(3);assert(q->active&&q->ammo==2&&q->reserve==2);
 bg_set_players(4);bg_reset();unsigned frag=0,plasma=0,rocket=0,sniper=0;
 for(unsigned j=0;j<35;j++){q=&bg_pickups[j];if(q->weapon==BG_PICK_FRAG)frag++;if(q->weapon==BG_PICK_PLASMA){plasma++;assert(q->period==180);}if(q->weapon==BG_W_ROCKET){rocket++;assert(q->period==90);}if(q->weapon==BG_W_SNIPER){sniper++;assert(q->period==120);}}
 assert(frag==8&&plasma==8&&rocket==1&&sniper==2);
}
static void respawn_penalty(void){
 reset();bg_player*p=&bg_players[0];p->pos[1]=-10;ticks(1);assert(p->health==0&&p->respawn==10);ticks(299);assert(p->health==0);ticks(2);assert(p->health>0&&p->weapon==BG_W_PLASMA_PISTOL&&p->inventory[1]==-1);
}
static void capacity(void){
 bg_set_players(4);bg_reset();bg_set_score_limit(1000);bg_vehicle_count=0;memset(in,0,sizeof(in));
 for(unsigned p=1;p<4;p++)bg_players[p].pos[0]=60;
 for(unsigned death=0;death<40;death++){
   bg_player*p=&bg_players[0];p->health=1;p->shield=0;p->weapon=BG_W_PLASMA_PISTOL;p->inventory[0]=BG_W_PLASMA_PISTOL;
   p->inventory[1]=BG_W_PISTOL;p->magazines[1]=5;p->reserves[1]=17;p->ammo=33;p->reserve=0;p->grenades[0]=p->grenades[1]=4;
   p->pos[0]=-12;p->pos[2]=5;p->pos[1]=bg_floor(-12,5,100)+.015f;
   shield_fixture_shot(0,20);ticks(1);assert(p->health==0&&bg_pickup_count<=BG_MAX_PICKUPS);
   for(unsigned i=0;i<bg_map_item_count;i++)assert(!bg_pickups[i].dropped&&bg_pickups[i].period==bg_map_items[i].period);
 }
 assert(bg_pickup_count==BG_MAX_PICKUPS);unsigned active=0;for(unsigned i=0;i<bg_pickup_count;i++)active+=bg_pickups[i].active&&bg_pickups[i].dropped;
 assert(active==17&&sizeof(bg_pickup)*BG_MAX_PICKUPS<=6000);
 puts("PASS: 40 repeated deaths, fixed 56-slot capacity, map slots protected, oldest-drop pressure fallback");
}
int main(void){eligibility();conservation();death_and_cleanup();schedules();respawn_penalty();capacity();puts("PASS: Slayer eligibility/threat ratings, map loadout, ammunition/battery/grenade conservation, death drops, view-aware cleanup, independent schedules");}
