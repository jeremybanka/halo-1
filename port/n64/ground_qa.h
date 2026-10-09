#ifndef BG_GROUND_QA_H
#define BG_GROUND_QA_H
/* Frozen matching terrain cameras; no simulation/timing claims. */
static unsigned model_qa_page;
static const char *const model_qa_labels[]={"GROUND: PLAYER VIEWS","GROUND: VALLEY VIEWS"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
 static uint64_t start;static bool ready;if(!start)start=now;
 model_qa_page=(unsigned)((now-start)/12000000)%2;
 if(ready)return;
 ready=true;bg_reset();bg_set_players(4);bg_scene_reset();(*qa.seconds)=0;
 for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
 for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
 for(unsigned p=0;p<4;p++){bg_players[p].invisibility=1;bg_players[p].pos[0]=0;bg_players[p].pos[2]=0;}
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
 static const float positions[4][4]={{-26,-31,0,0},{26,34,0,0},{-12,5,10,20},{16,-12,0,-28}};
 float x=positions[p][0],z=positions[p][1],h=bg_floor(x,z,100);
 if(!model_qa_page){
  *eye=(T3DVec3){{x*BG_SCALE,(h+.7f)*BG_SCALE,z*BG_SCALE}};
  *target=(T3DVec3){{positions[p][2]*BG_SCALE,(h-.8f)*BG_SCALE,positions[p][3]*BG_SCALE}};
 }else{
  *eye=(T3DVec3){{x*BG_SCALE,(h+13)*BG_SCALE,z*BG_SCALE}};
  *target=(T3DVec3){{positions[p][2]*BG_SCALE,(h-3)*BG_SCALE,positions[p][3]*BG_SCALE}};
 }
}
#endif
