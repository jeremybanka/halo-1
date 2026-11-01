#ifndef BG_ODST_QA_H
#define BG_ODST_QA_H
/* Real armor buffers and per-view VISR, including zero-opacity opponents. */
static unsigned model_qa_page=BG_ODST_QA;
static const char *const model_qa_labels[]={"ODST FOUR PALETTES / NEAR AND FAR","VISR MIXED VIEWS / CLOAKED ENEMIES","ODST FIRST PERSON / SHARED WEAPON ACTIONS","VISR TEAM FILTER / CLOAKED ALLY"};
static bool model_qa_firstperson(void){return BG_ODST_QA==2;}
static void model_qa_stage(uint64_t now){
    static uint64_t started;
    if(!started){
        started=now;
        for(unsigned p=0;p<4;p++)bg_set_player_armor(p,BG_ARMOR_ODST);
        bg_reset();bg_set_players(4);bg_scene_reset();
        if(BG_ODST_QA==3){const uint8_t teams[4]={0,0,1,1};bg_configure_mode(BG_MODE_TEAM_SLAYER,teams);}
        for(unsigned p=0;p<4;p++){bg_player_profiles[p]=p;bg_scene_profile_changed(p);}
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
    }
    float seconds=(now-started)*.000001f;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=(float)(p%2)*1.1f;q->pos[2]=4+(p/2)*1.2f;
        q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;q->yaw=0;q->pitch=BG_ODST_QA==2?-.55f:0;
        q->armor=BG_ARMOR_ODST;q->shield=0;q->health=100;q->vehicle=-1;q->weapon=BG_W_AR;
        q->weapon_ready=0;q->reload=q->melee_time=q->flash=0;q->grenade_cooldown=0;q->crouch_amount=0;q->grounded=true;
        q->animation=BG_ANIM_IDLE;q->anim_time=seconds;
        q->flashlight_on=(BG_ODST_QA==1||BG_ODST_QA==3)&&(p==0||p==2);
        q->invisibility=BG_ODST_QA==1||BG_ODST_QA==3?10:0;
        q->camo_opacity=(p==1||p==3)?0:1;
        if(BG_ODST_QA==2){unsigned phase=(unsigned)(seconds/3)%4;if(phase==1){q->reload=1;q->reload_duration=2.9f;q->anim_time=fmodf(seconds,2.9f);}if(phase==2)q->melee_time=.15f;}
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(BG_ODST_QA==2)return;
    unsigned subject=BG_ODST_QA==0?p:1;float radius=BG_ODST_QA==0?(p<2?1.25f:3.2f):2.2f;
    for(unsigned a=0;a<3;a++){
        target->v[a]=(bg_players[subject].pos[a]+(a==1?.40f:0))*BG_SCALE;
        eye->v[a]=target->v[a]+(float[]){.75f,.22f,.55f}[a]*radius*BG_SCALE;
    }
}
#endif
