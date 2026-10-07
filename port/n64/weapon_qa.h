#ifndef BG_WEAPON_QA_H
#define BG_WEAPON_QA_H
/* Remaining Xbox weapons: four animation poses, then four world viewpoints. */
static unsigned model_qa_page;
static float model_qa_floor;
static const char *const model_qa_labels[]={
 "AR POSES", "AR WORLD", "PLASMA RIFLE POSES", "PLASMA RIFLE WORLD",
 "NEEDLER POSES", "NEEDLER WORLD", "SHOTGUN POSES", "SHOTGUN WORLD",
 "SNIPER POSES", "SNIPER WORLD", "NEEDLER AMMO 0/5/10/20", "FRAG WORLD", "PLASMA GRENADE WORLD"};
static bool model_qa_firstperson(void){return model_qa_page==10||(model_qa_page<10&&!(model_qa_page&1));}
static void model_qa_stage(uint64_t now){
 static uint64_t started;static unsigned previous=~0u;
 if(!started)started=now;
 model_qa_page=(unsigned)((now-started)/6000000)%13;
 if(model_qa_page==previous)return;
 previous=model_qa_page;bg_reset();bg_set_players(4);reset_view_state();game_time=0;
 model_qa_floor=bg_floor(0,4,100)+.015f;
 for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
 for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
 const int weapons[]={BG_W_AR,BG_W_PLASMA_RIFLE,BG_W_NEEDLER,BG_W_SHOTGUN,BG_W_SNIPER};
 int weapon=model_qa_page<10?weapons[model_qa_page/2]:BG_W_NEEDLER;
 for(unsigned p=0;p<4;p++){
  bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=model_qa_floor;q->pos[2]=4;
  q->yaw=q->pitch=q->gait=0;q->invisibility=1;q->zoom=0;
  bg_give_weapon(p,weapon);q->weapon=weapon;q->ammo=bg_weapon_defs[weapon].magazine;
  q->animation=BG_ANIM_IDLE;q->anim_time=0;fired_at[p]=-100;
  if(model_qa_page==10)q->ammo=(int[]){0,5,10,20}[p];
  else if(model_qa_firstperson()){
   if(p==1)fired_at[p]=-.08f;
   if(p==2){q->animation=BG_ANIM_RELOAD;q->reload=.5f;
    q->anim_time=.35f*(weapon==BG_W_NEEDLER?bg_weapon_defs[weapon].reload:bg_fp_animations[weapon][BG_FP_RELOAD].duration);}
   if(p==3){q->animation=BG_ANIM_MELEE;q->melee_time=.7f-.35f*bg_fp_animations[weapon][BG_FP_MELEE].duration;}
  }
 }
 if(!model_qa_firstperson())bg_pickups[0]=(bg_pickup){.pos={0,model_qa_floor+.6f,4},
  .weapon=model_qa_page==11?BG_PICK_FRAG:model_qa_page==12?BG_PICK_PLASMA:weapon,.active=true};
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
 if(model_qa_firstperson())return;
 const float dirs[4][3]={{1,.12f,0},{-1,.12f,0},{0,.2f,1},{.25f,1,.25f}};
 float radius=model_qa_page>=11?.18f:.43f;
 for(unsigned a=0;a<3;a++){
  target->v[a]=(float[]){0,model_qa_floor+.6f,4}[a]*BG_SCALE;
  eye->v[a]=target->v[a]+dirs[p][a]*radius*BG_SCALE;
 }
}
#endif
