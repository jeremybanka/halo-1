#ifndef BG_GEOMETRY_QA_H
#define BG_GEOMETRY_QA_H
/* Fixed render-only views for menu-adjacent geometry regression work. */
static unsigned model_qa_page;
static const char *const model_qa_labels[]={"PISTOL SLEEVES", "SNIPER SCOPE", "SNIPER POSES", "BLUE BASE", "RED BASE", "BLUE RAMPS", "RED RAMPS"};
static bool model_qa_firstperson(void){return model_qa_page<3;}
static void model_qa_stage(uint64_t now){
 static uint64_t started;static unsigned previous=~0u;if(!started)started=now;
 model_qa_page=(unsigned)((now-started)/6000000)%7;if(previous==model_qa_page)return;
 previous=model_qa_page;bg_reset();bg_set_players(4);reset_view_state();game_time=0;
 for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
 for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
 for(unsigned p=0;p<4;p++){
  bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=bg_floor(0,4,100)+.015f;q->pos[2]=4;
  q->yaw=q->pitch=q->gait=0;q->invisibility=1;q->zoom=0;
  int w=model_qa_page==0?(p%2?BG_W_PLASMA_PISTOL:BG_W_PISTOL):BG_W_SNIPER;
  bg_give_weapon(p,w);q->weapon=w;q->ammo=bg_weapon_defs[w].magazine;
  q->animation=BG_ANIM_IDLE;q->anim_time=0;fired_at[p]=-100;
  if(model_qa_page==0&&p>=2){q->animation=BG_ANIM_RELOAD;q->reload=.5f;q->anim_time=.35f*bg_fp_animations[w][BG_FP_RELOAD].duration;}
  if(model_qa_page==1&&p)fired_at[p]=-(float[]){0,.03f,.08f,.12f}[p];
  if(model_qa_page==2){
   if(p<3){q->animation=BG_ANIM_RELOAD;q->reload=.5f;q->anim_time=(.15f+.3f*p)*bg_fp_animations[w][BG_FP_RELOAD].duration;}
   else{q->animation=BG_ANIM_MELEE;q->melee_time=.7f-.35f*bg_fp_animations[w][BG_FP_MELEE].duration;}
  }
 }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
 if(model_qa_firstperson())return;
 bool red=model_qa_page==4||model_qa_page==6;bool close=model_qa_page>=5;
 float x=red?27.54f:-27.86f,z=red?41.18f:-38.55f;
 const float dirs[4][3]={{.6f,.4f,-1},{-.6f,.4f,1},{1,.65f,.35f},{-.35f,1.3f,-.35f}};
 if(close){
  float side=(p%2)?-1:1;
  *eye=(T3DVec3){{(x+(p>=2?3.3f:0))*BG_SCALE,(p>=2?3.6f:.8f)*BG_SCALE,(z+side*(p>=2?2.7f:6.7f))*BG_SCALE}};
  *target=(T3DVec3){{x*BG_SCALE,(p>=2?1.4f:.45f)*BG_SCALE,(z+side*2)*BG_SCALE}};
 }else for(unsigned a=0;a<3;a++){target->v[a]=(float[]){x,1,z}[a]*BG_SCALE;eye->v[a]=target->v[a]+dirs[p][a]*11*BG_SCALE;}
}
#endif
