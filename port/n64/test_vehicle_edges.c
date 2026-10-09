#include "game.h"
#include "combat_geometry.h"
#include "terrain.h"
#include "blam/vehicle_physics.h"
#include "rifle_fixture.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static bg_input input[4];
static void tick(unsigned n){while(n--){bg_clear_events();bg_tick(input,1.f/30);}}
static void reset(void){bg_set_players(4);bg_reset();bg_set_score_limit(1000);bg_pickup_count=bg_vehicle_count=0;memset(input,0,sizeof(input));
 for(unsigned i=0;i<4;i++){bg_fixture_rifle_loadout(i);bg_players[i].pos[0]=i*4;bg_players[i].pos[2]=4;bg_players[i].pos[1]=bg_floor(bg_players[i].pos[0],4,100)+.015f;}}
static void exposure(void){
 unsigned exposed=0,covered=0;
 for(unsigned kind=0;kind<4;kind++)for(unsigned seat=0;seat<bg_seat_counts[kind];seat++)for(unsigned side=0;side<4;side++){
  reset();float pos[3]={-12,bg_floor(-12,5,100),5};int vi=bg_add_vehicle(kind,pos,0);tick(45);
  bg_vehicle*v=&bg_vehicles[vi];bg_player*p=&bg_players[0];p->vehicle=vi;p->seat=seat;v->occupants[seat]=0;tick(1);
  float dir[3]={side==0?1:side==1?-1:0,0,side==2?1:side==3?-1:0};
  float origin[3]={p->pos[0]-dir[0]*2,p->pos[1]+.58f,p->pos[2]-dir[2]*2};
  if(bg_raycast(origin,dir,2)<1.88f)continue;
  bool blocked=bg_vehicle_hit_ray(v,origin,dir,2)<1.88f;
  float shield=p->shield;bg_projectile*q=bg_projectile_create();assert(q);
  q->kind=BG_P_FLAME;q->owner=3;q->life=1;q->damage=10;memcpy(q->pos,origin,12);
  for(unsigned a=0;a<3;a++)q->velocity[a]=dir[a]*60;tick(1);
  if(blocked){assert(p->shield==shield);covered++;}else{assert(p->shield<shield);exposed++;}
 }
 assert(exposed&&covered);printf("Seat exposure: %u exposed rays / %u hull-blocked rays across all seats\n",exposed,covered);
 reset();float pos[3]={-12,bg_floor(-12,5,100),5};int vi=bg_add_vehicle(BG_V_SCORPION,pos,0);tick(45);
 bg_vehicle*v=&bg_vehicles[vi];bg_player*p=&bg_players[0];memcpy(p->pos,v->pos,12);p->pos[0]+=2;p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
 float blast[3]={v->pos[0]-2,v->pos[1]+.4f,v->pos[2]};
 for(unsigned pass=0;pass<2;pass++){
  bg_projectile*q=bg_projectile_create();assert(q);q->kind=BG_P_CANNON;q->owner=3;q->life=.001f;q->attached=-2;q->damage=40;q->radius=10;memcpy(q->pos,blast,12);
  if(pass)bg_vehicle_count=0;tick(1);
  if(!pass)assert(p->shield==100);else assert(p->shield<100);
 }
}
int main(void){
 exposure();
 /* Batched near-plane rays must agree with five independent original queries. */
 for(unsigned n=0;n<240;n++){
  float o[3]={-30+(n%13)*5.f,0,-40+(n%17)*5.f};o[1]=bg_floor(o[0],o[2],100)+.1f+(n%7)*.2f;
  float yaw=n*.71f,base[3]={cosf(yaw),((int)(n%5)-2)*.15f,sinf(yaw)},rays[5][3],reach[5],hits[5];
  for(unsigned i=0;i<5;i++){
   for(unsigned a=0;a<3;a++)rays[i][a]=base[a]*(.5f+n%4);
   if(i==1)rays[i][0]+=.1f;if(i==2)rays[i][0]-=.1f;if(i==3)rays[i][1]+=.1f;if(i==4)rays[i][1]-=.1f;
   reach[i]=sqrtf(rays[i][0]*rays[i][0]+rays[i][1]*rays[i][1]+rays[i][2]*rays[i][2]);
   for(unsigned a=0;a<3;a++)rays[i][a]/=reach[i];
  }
  bg_world_camera_rays(o,rays,reach,hits);
  for(unsigned i=0;i<5;i++)assert(fabsf(hits[i]-bg_world_raycast(o,rays[i],reach[i]))<.001f);
 }
 puts("Camera packet: 1,200 rays match independent original polygon queries");
 reset();float pos[3]={-12,bg_floor(-12,5,100),5};int vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);tick(45);
 bg_vehicle*v=&bg_vehicles[vi];bg_player*p=&bg_players[0];p->vehicle=vi;p->seat=0;v->occupants[0]=0;
 float exit[3];assert(bg_vehicle_exit_position(0,exit));bg_player probe=*p;memcpy(probe.pos,exit,12);
 assert(bg_terrain_clearance(&probe)&&!bg_vehicle_contacts_player(v,&probe));
 /* A neighboring hull blocks every candidate; use cannot free/teleport the rider. */
 float obstruction[3]={v->pos[0],v->pos[1],v->pos[2]-.7f};bg_add_vehicle(BG_V_SCORPION,obstruction,0);
 bg_add_vehicle(BG_V_SCORPION,(float[]){v->pos[0],v->pos[1],v->pos[2]+.7f},0);
 assert(!bg_vehicle_exit_position(0,exit));input[0].interact=true;tick(1);
 assert(p->vehicle==vi&&p->seat_state==BG_SEAT_STABLE&&v->occupants[0]==0);
 bg_vehicle_count=1;input[0].interact=false;tick(1);input[0].interact=true;tick(1);assert(p->seat_state==BG_SEAT_EXITING);
 /* Obstruction arriving during the animation must also preserve the seat. */
 bg_add_vehicle(BG_V_SCORPION,obstruction,0);bg_add_vehicle(BG_V_SCORPION,(float[]){v->pos[0],v->pos[1],v->pos[2]+.7f},0);
 assert(!bg_vehicle_exit_position(0,exit));p->seat_time=.001f;
 tick(1);assert(p->vehicle==vi&&p->seat_state==BG_SEAT_STABLE&&v->occupants[0]==0);
 reset();vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);v=&bg_vehicles[vi];
 float origin[3]={pos[0]-3,pos[1]+.4f,pos[2]},dir[3]={1,0,0};
 float clear=bg_camera_clearance(origin,dir,6,vi),blocked=bg_camera_clearance(origin,dir,6,-1);
 assert(blocked<clear&&blocked>0);assert(bg_camera_clearance(origin,dir,.1f,vi)==0);
 /* A capsule above the hull is safe, while front/side geometry outside the
  * old 0.8-unit kill sphere is real contact. */
 probe=bg_players[0];bool found=false;
 for(int x=-18;x<=18&&!found;x++)for(int z=-12;z<=12&&!found;z++){
  memcpy(probe.pos,pos,12);probe.pos[0]+=x*.1f;probe.pos[2]+=z*.1f;
  if((x*x+z*z)>.8f*.8f*100&&bg_vehicle_contacts_player(v,&probe))found=true;
 }
 assert(found);probe.pos[1]+=5;assert(!bg_vehicle_contacts_player(v,&probe));
 /* A fast hull contact outside the old center sphere damages a victim;
  * a nearby player above it is not hit by the former proximity shortcut. */
 reset();vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);v=&bg_vehicles[vi];tick(45);
 p=&bg_players[1];memcpy(p->pos,v->pos,12);p->pos[0]+=1.15f;p->pos[2]+=.35f;p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
 v->velocity[0]=4;v->physics_valid=false;float vitality=p->shield+p->health;
 tick(1);assert(p->shield+p->health<vitality);
 reset();vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);v=&bg_vehicles[vi];
 /* Plasma attachments stay on the authored hull under yaw/roll, not a
  * fixed world offset. The production update transforms the attachment. */
 bg_projectile*q=bg_projectile_create();assert(q);q->kind=BG_P_PLASMA_GRENADE;q->owner=3;q->attached=BG_PLAYERS+vi;
 q->life=20;q->countdown=true;q->attached_offset[0]=.5f;q->attached_offset[1]=.3f;q->attached_offset[2]=.2f;
 v->yaw=1.2f;v->pitch=.4f;v->physics_valid=false;tick(1);q=bg_projectile_at(0);
 float expected[3];bg_vehicle_transform(v,q->attached_offset,expected);for(unsigned a=0;a<3;a++)assert(fabsf(q->pos[a]-expected[a])<.0001f);
 puts("PASS: safe/blocked/interrupted exits, hull camera obstruction, source-hull capsule contact and rotating plasma attachment");
}
