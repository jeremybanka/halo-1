#ifndef BG_ENVIRONMENT_QA_H
#define BG_ENVIRONMENT_QA_H
/* Matching slow camera sweeps through the production terrain renderer. */
static unsigned model_qa_page;
static float environment_qa_time;
static const char *const model_qa_labels[]={"BASE PANELS / CANYON SEAMS"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
 static uint64_t start;static bool ready;if(!start)start=now;
 environment_qa_time=(now-start)*.000001f;
 if(ready)return;
 ready=true;bg_reset();bg_set_players(4);bg_scene_reset();(*qa.seconds)=0;
 for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
 for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
 for(unsigned p=0;p<4;p++){bg_players[p].invisibility=1;bg_players[p].pos[0]=0;bg_players[p].pos[2]=0;}
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
 const float targets[4][3]={{24.1f,2.5f,38.3f},{-24.4f,2.5f,-35.6f},{34.7f,3,-9},{0,6,-28.6f}};
 const float offsets[4][3]={{2.4f,.1f,2.4f},{-2.4f,.1f,-2.4f},{5,-.2f,-2.5f},{6,-2,5}};
 float pan=sinf(environment_qa_time*.45f)*.7f;
 for(unsigned a=0;a<3;a++){
  target->v[a]=targets[p][a]*BG_SCALE;
  eye->v[a]=(targets[p][a]+offsets[p][a]+(a==0?pan:0))*BG_SCALE;
 }
}
#endif
