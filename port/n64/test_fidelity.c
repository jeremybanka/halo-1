#include "game.h"
#include "combat.h"
#include "combat_geometry.h"
#include "movement.h"
#include "terrain.h"
#include "blam/vehicle_physics.h"
#include "rifle_fixture.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static bg_input input[4];
static void tick(unsigned n){while(n--){bg_clear_events();bg_tick(input,1.f/30);}}
static void reset(void){bg_set_players(4);bg_reset();bg_set_score_limit(1000);bg_vehicle_count=bg_pickup_count=0;memset(input,0,sizeof(input));for(unsigned i=0;i<4;i++){bg_fixture_rifle_loadout(i);bg_players[i].pos[0]=4.f+i*4.f;bg_players[i].pos[2]=5;bg_players[i].pos[1]=bg_floor(bg_players[i].pos[0],5,100)+.015f;}}
static void near(float a,float b){assert(fabsf(a-b)<.003f);}
static void mounted(void){
 near(bg_mounted_profiles[0].trigger.rate_min,8);near(bg_mounted_profiles[0].trigger.rate_max,15);
 near(bg_mounted_profiles[2].chamber,4);near(bg_mounted_profiles[5].chamber,4);near(bg_mounted_profiles[1].chamber,0);
 near(bg_damage_profiles[BG_D_GHOST].shield,2);near(bg_damage_profiles[BG_D_GHOST].body,.5f);
 near(bg_damage_profiles[BG_D_HOG].vehicle_material[0],.25f);near(bg_damage_profiles[BG_D_HOG].vehicle_material[3],1);
 for(unsigned kind=0;kind<4;kind++){
  reset();float pos[3]={-12,bg_floor(-12,5,100),5};bg_add_vehicle(kind,pos,0);tick(30);
  bg_vehicle*v=&bg_vehicles[0];unsigned seat=kind==BG_V_WARTHOG?1:0;
  v->occupants[seat]=0;bg_players[0].vehicle=0;bg_players[0].seat=seat;bg_players[0].pitch=.6f;input[0].fire=true;
  unsigned fired=0;for(unsigned t=0;t<60;t++){tick(1);for(unsigned e=0;e<bg_event_count;e++)fired+=bg_events[e].kind==BG_EVENT_FIRE;}
  if(kind==BG_V_SCORPION)assert(fired==1);else if(kind==BG_V_WARTHOG)assert(fired>=23&&fired<=27);else assert(fired>=9&&fired<=12);
  if(kind==BG_V_GHOST||kind==BG_V_BANSHEE){bool found=false;for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){bg_projectile*q=bg_projectile_at(i);if(q&&q->owner==0){assert(q->damage_profile==(kind==BG_V_GHOST?BG_D_GHOST:BG_D_BANSHEE));assert(hypotf(q->velocity[0],hypotf(q->velocity[1],q->velocity[2]))>24);found=true;}}assert(found);}
  printf("Mounted kind %u: %u primary shots in 60 ticks\n",kind,fired);
 }
}
static void rider_damage(void){
 reset();float position[3]={-12,0,5};bg_add_vehicle(BG_V_WARTHOG,position,0);tick(30);
 bg_vehicle*v=&bg_vehicles[0];v->pos[1]=20;v->physics_valid=false;
 v->occupants[0]=1;bg_players[1].vehicle=0;bg_players[1].seat=0;
 bg_projectile*q=bg_projectile_create();assert(q);q->kind=BG_P_PLASMA;q->owner=0;q->damage_profile=BG_D_AR;q->life=2;
 q->pos[0]=v->pos[0]-3;q->pos[1]=v->pos[1]+.12f;q->pos[2]=v->pos[2];q->velocity[0]=324;
 float dir[3]={1,0,0};unsigned material=99;bool found=false;
 for(int y=-10;y<=10&&!found;y++)for(int z=-10;z<=10&&!found;z++){
  q->pos[1]=v->pos[1]+y*.025f;q->pos[2]=v->pos[2]+z*.025f;
  found=bg_vehicle_hit_ray_material(v,q->pos,dir,6,&material)<6&&material<3;
 }assert(found);
 tick(1);
 near(v->health,400-10*.25f*(100.f/75));near(bg_players[1].shield,100-10*.18f*(100.f/75));near(bg_players[1].health,100);
 puts("Direct hull hit: material resistance and fractional rider transfer applied independently");
}
static void contacts(void){
 reset();memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.1f;tick(1);
 float dx=bg_players[1].pos[0]-bg_players[0].pos[0],dz=bg_players[1].pos[2]-bg_players[0].pos[2];assert(hypotf(dx,dz)>=2*bg_movement.radius-.003f);
 reset();float pos[3]={-12,bg_floor(-12,5,100),5};bg_add_vehicle(BG_V_SCORPION,pos,0);tick(60);
 bg_vehicle*v=&bg_vehicles[0];bg_player*p=&bg_players[0];float top[3]={v->pos[0]-.3f,v->pos[1]+3,v->pos[2]},down[3]={0,-1,0};
 float d=bg_vehicle_hit_ray(v,top,down,4);assert(d<4);memcpy(p->pos,top,12);p->pos[1]-=d-.015f;p->velocity[1]=p->vy=-.2f;p->grounded=false;tick(3);
 assert(p->grounded&&p->support_vehicle==1&&p->health==100);
 v->occupants[0]=1;bg_players[1].vehicle=0;bg_players[1].seat=0;input[1].forward=.4f;float local[3];memcpy(local,p->support_local,12);
 tick(10);assert(p->health==100&&p->support_vehicle==1);float expected[3];bg_vehicle_transform(v,p->support_local,expected);for(unsigned a=0;a<3;a++)near(p->pos[a],expected[a]);
 input[0].jump=true;tick(1);assert(!p->support_vehicle&&!p->grounded&&p->vy>0);
 puts("Contacts: symmetric player separation, tank support/carry, jump detach");
}
static void hit_regions(void){
 reset();bg_player*p=&bg_players[0];p->weapon_ready=0;p->animation=BG_ANIM_IDLE;p->pos[1]=20;p->yaw=0;
 unsigned regions[3]={0};float dir[3]={1,0,0};
 for(unsigned y=0;y<30;y++)for(int z=-12;z<=12;z++){
  float origin[3]={p->pos[0]-2,p->pos[1]+y*.025f,p->pos[2]+z*.025f};int region=-1;
  if(bg_player_hit_ray(0,origin,dir,4,&region)<4){assert(region>=0&&region<3);regions[region]++;}
 }
 assert(regions[0]&&regions[1]&&regions[2]);
 /* A ray through the gap between the calves must no longer hit the old
  * origin-centered leg sphere. Animating the run changes the hit silhouette. */
 unsigned changed=0;p->animation=BG_ANIM_RUN;
 for(unsigned y=0;y<28;y++)for(int z=-10;z<=10;z++){
  float o[3]={p->pos[0]-2,p->pos[1]+y*.025f,p->pos[2]+z*.025f};int region;
  p->anim_time=0;float a=bg_player_hit_ray(0,o,dir,4,&region);p->anim_time=.25f;float b=bg_player_hit_ray(0,o,dir,4,&region);changed+=(a<4)!=(b<4);
 }assert(changed>10);printf("Animated collision: %u leg / %u body / %u head rays; %u silhouette changes\n",regions[0],regions[1],regions[2],changed);
}
int main(void){mounted();rider_damage();contacts();hit_regions();puts("PASS: mounted profiles, dynamic contacts and animated original player hit geometry");}
