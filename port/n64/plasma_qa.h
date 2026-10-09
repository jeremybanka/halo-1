#ifndef BG_PLASMA_QA_H
#define BG_PLASMA_QA_H
/* Frozen production-renderer poses: idle / firing / overheat / melee. */
static unsigned model_qa_page=BG_PLASMA_QA;
static const char *const model_qa_labels[]={"PLASMA PISTOL POSES","PLASMA RIFLE POSES","PLASMA PISTOL READY","PLASMA RIFLE READY"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
 (void)now;static bool initialized;if(initialized)return;initialized=true;
 bg_reset();bg_set_players(4);bg_scene_reset();(*qa.seconds)=0;
 for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
 for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
 for(unsigned p=0;p<4;p++){
  bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=bg_floor(0,4,100)+.015f;q->pos[2]=4;
  q->yaw=q->pitch=q->gait=0;q->invisibility=1;q->zoom=0;
  int w=(BG_PLASMA_QA%2)?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL;
  bg_give_weapon(p,w);q->weapon=w;q->ammo=bg_weapon_defs[w].magazine;
  q->animation=BG_ANIM_IDLE;q->anim_time=0;bg_scene_fired(p,-100);
  if(BG_PLASMA_QA>=2){q->weapon_ready=bg_ready_times[w]*(1-(float[]){.15f,.4f,.7f,.9f}[p]);continue;}
  if(p==1)bg_scene_fired(p,-.08f);
  if(p==2){q->animation=BG_ANIM_RELOAD;q->reload=.5f;q->anim_time=.35f*bg_fp_animations[w][BG_FP_RELOAD].duration;}
  if(p==3){q->animation=BG_ANIM_MELEE;q->melee_time=.7f-.35f*bg_fp_animations[w][BG_FP_MELEE].duration;}
 }
}
#endif
