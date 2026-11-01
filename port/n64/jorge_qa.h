#ifndef BG_JORGE_QA_H
#define BG_JORGE_QA_H
#include "asset_jorge.h"
static unsigned model_qa_page;
static float model_qa_floor;
static const char *const model_qa_labels[]={"JORGE / SPARTAN: IDLE", "RUN", "FIRE", "RELOAD", "DEATH", "JUMP", "MELEE", "THROW", "CROUCH", "READY"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    static uint64_t started;
    if(!started){
        started=now;bg_reset();bg_set_players(4);bg_scene_reset();
        model_qa_floor=bg_floor(0,4,100)+.015f;
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        bg_player_profiles[0]=BG_PROFILE_JORGE;bg_scene_profile_changed(0);
        bg_player_profiles[1]=3;bg_scene_profile_changed(1);
    }
    float seconds=(now-started)*.000001f;model_qa_page=(unsigned)(seconds/4)%10;
    unsigned clips[]={BG_ANIM_IDLE,BG_ANIM_RUN,BG_ANIM_FIRE,BG_ANIM_RELOAD,BG_ANIM_DIE,BG_ANIM_JUMP,BG_ANIM_MELEE,BG_ANIM_IDLE,BG_ANIM_IDLE,BG_ANIM_IDLE};
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=model_qa_floor;q->pos[2]=4+(p?1.2f:0);
        q->yaw=q->pitch=0;q->invisibility=p>=2?1:0;q->animation=clips[model_qa_page];q->anim_time=fmodf(seconds,model_qa_page<8?bg_animations[model_qa_page].duration:1.5f);
        q->vehicle=-1;q->health=100;q->weapon=BG_W_AR;q->weapon_ready=0;q->reload=q->flash=q->melee_time=0;q->grenade_cooldown=0;q->crouch_amount=0;q->grounded=true;
        if(model_qa_page==7)q->grenade_cooldown=.9f-fmodf(seconds,.35f);
        if(model_qa_page==8)q->crouch_amount=1;
        if(model_qa_page==9)q->weapon_ready=(1-fmodf(seconds,1))*bg_ready_times[BG_W_AR];
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.12f,0},{-1,.12f,0},{.7f,.25f,.7f},{-.7f,.25f,-.7f}};
    unsigned subject=p%2;float radius=1.35f;
    for(unsigned a=0;a<3;a++){
        target->v[a]=(float[]){0,model_qa_floor+.42f,4+subject*1.2f}[a]*BG_SCALE;
        eye->v[a]=target->v[a]+dirs[p/2*2][a]*radius*BG_SCALE;
    }
}
#endif
