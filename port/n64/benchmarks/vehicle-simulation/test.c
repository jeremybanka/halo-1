#include <stdio.h>
#include <stdlib.h>
#include "game.c"
#ifndef QUERY_REFERENCE
#include "query_reference.inc"
static uint32_t test_seed=0x6e3634;
static float random01(void){test_seed=test_seed*1664525u+1013904223u;return (test_seed>>8)*(1.f/16777216);}
static void query_tests(void){
 unsigned checked=0,blocked=0;
 for(unsigned map=0;map<13;map++){
  assert(bg_map_load(map));
  for(unsigned n=0;n<10000;n++){
   const float*spawn=bg_spawns[n%bg_spawn_count].pos;
   float origins[5][3],direction[3],reach=(n%19==0?.003f:n%23==0?0:random01()*25),width=random01()*4;
   for(unsigned k=0;k<3;k++)direction[k]=random01()-.5f;
   if(n%4==0){memset(direction,0,12);direction[n%3]=n%2?1:-1;}else normalize(direction);
   float right[3]={direction[2],0,-direction[0]};normalize(right);
   float center[3]={spawn[0]+(random01()-.5f)*15,spawn[1]+(random01()-.3f)*8,spawn[2]+(random01()-.5f)*15};
   for(unsigned i=0;i<5;i++)for(unsigned k=0;k<3;k++)origins[i][k]=center[k]+right[k]*width*((int)i-2)*.5f;
   float hits[5];bg_world_clearance_rays(origins,direction,reach,hits);
   for(unsigned i=0;i<5;i++){
    float expected=bg_world_raycast(origins[i],direction,reach);
    if(memcmp(&hits[i],&expected,4)){fprintf(stderr,"packet mismatch map=%u case=%u lane=%u got=%.9g expected=%.9g\n",map,n,i,hits[i],expected);abort();}
    checked++;blocked+=hits[i]<reach;
   }
  }
 }
 printf("PASS %u bit-identical clearance rays across all 13 maps (%u hits), zero/short/axis/oblique rays\n",checked,blocked);
 assert(bg_map_load(9));
 for(unsigned n=0;n<20000;n++){
  float o[3],target[3],a[3]={1,2,3},b[3]={1,2,3},aim[3]={1,2,3};
  for(unsigned k=0;k<3;k++){o[k]=(random01()-.5f)*40;target[k]=(random01()-.5f)*40;}
  float speed=n%13==0?.05f:4+random01()*40,gravity=1+random01()*12;bool high=n%2;
  bool expected=oracle_arc(o,target,speed,gravity,high,a),actual=pve_ballistic_arc(o,target,speed,gravity,high,b);
  bool aiming=pve_ballistic_arc_checked(o,target,speed,gravity,high,aim,false);(void)aiming;
  assert(expected==actual&&!memcmp(a,b,12)&&!memcmp(a,aim,12));
 }
 puts("PASS 20000 split trajectory/obstruction results and cooldown aim vectors versus frozen original");
 bg_ff_qa_stage(4,8);bg_pve_count=4;
 /* Isolate visible Wraith targeting, including cooldown expiry, ongoing burst,
  * unseen/unaware gates, range changes and both ballistic branches. */
 for(unsigned n=0;n<3000;n++){
  bg_pve_actor*a=&bg_pve_actors[2];bg_player*p=&bg_players[6];bg_vehicle*v=&bg_vehicles[2];
  for(unsigned i=0;i<4;i++)bg_pve_actors[i].occupied=i==2;
  a->visible=true;a->aware=n%7!=0;a->target=0;a->burst_pause=(float[]){-1,0,1.f/30,nextafterf(1.f/30,0),nextafterf(1.f/30,FLT_MAX),3}[n%6];
  a->burst_time=(n%3)*.04f;a->shot_time=n%2?.1f:0;
  bg_players[0].health=100;bg_players[0].pos[0]=v->pos[0]+1+random01()*60;bg_players[0].pos[1]=v->pos[1]+(random01()-.5f)*10;bg_players[0].pos[2]=v->pos[2]+(random01()-.5f)*30;
  bg_player players[BG_UNITS];bg_pve_actor actors[BG_PVE_MAX];memcpy(players,bg_players,sizeof(players));memcpy(actors,bg_pve_actors,sizeof(actors));uint32_t seed=pve_random;
  bg_input expected[BG_UNITS]={0},actual[BG_UNITS]={0};oracle_inputs(expected,1.f/30);
  bg_player expected_players[BG_UNITS];bg_pve_actor expected_actors[BG_PVE_MAX];memcpy(expected_players,bg_players,sizeof(players));memcpy(expected_actors,bg_pve_actors,sizeof(actors));uint32_t expected_seed=pve_random;
  memcpy(bg_players,players,sizeof(players));memcpy(bg_pve_actors,actors,sizeof(actors));pve_random=seed;
  pve_vehicle_inputs(actual,1.f/30);
  assert(!memcmp(expected,actual,sizeof(actual))&&!memcmp(expected_players,bg_players,sizeof(players))&&!memcmp(expected_actors,bg_pve_actors,sizeof(actors))&&expected_seed==pve_random);
  (void)p;
 }
 puts("PASS 3000 Wraith gate/burst/cooldown boundary decisions: exact control, aim, timers, actor state and RNG");
}
#endif
static uint64_t state_hash=14695981039346656037ull;
static void add(const void*data,size_t size){const uint8_t*p=data;for(size_t i=0;i<size;i++){state_hash^=p[i];state_hash*=1099511628211ull;}}
static void trace_state(void){
#define SAVE(x) add(&(x),sizeof(x))
 SAVE(bg_players);SAVE(bg_vehicles);SAVE(bg_pve_actors);SAVE(bg_vehicle_count);SAVE(bg_pickups);SAVE(bg_pickup_count);SAVE(bg_event_count);add(bg_events,sizeof(*bg_events)*bg_event_count);
 SAVE(pve_random);SAVE(random_state);SAVE(item_random);SAVE(spawn_random);SAVE(bg_ff);
 for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){const bg_projectile*q=bg_projectile_at(i);bool present=q!=NULL;SAVE(present);if(q)add(q,sizeof(*q));}
#undef SAVE
}
int main(int argc,char**argv){
 setvbuf(stdout,NULL,_IONBF,0);assert(argc==2);
#ifndef QUERY_REFERENCE
 if(!strcmp(argv[1],"queries")){query_tests();return 0;}
#endif
 assert(bg_map_load(9));
 for(unsigned fixture=8;fixture<=9;fixture++)for(unsigned players=1;players<=4;players++){
  bg_ff_qa_stage(players,fixture);
  for(unsigned tick=0;tick<1200;tick++){
   if(fixture==8&&bg_ff.tick>=600)bg_ff_qa_stage(players,fixture);
   bg_input input[4]={0};bg_ff_qa_input(input);bg_clear_events();bg_tick(input,1.f/30);trace_state();
   if(tick%30==29)printf("TRACE fixture=%u players=%u tick=%u hash=%016llx\n",fixture,players,tick+1,(unsigned long long)state_hash);
  }
 }
}
