#ifndef BG_SPARTAN_MOTION_QA_H
#define BG_SPARTAN_MOTION_QA_H
/* Render-only treadmill: one exact gait cycle per stance, four cameras.
 * The game test separately exercises actual automatic fire + movement. */
static unsigned model_qa_page;
static float motion_floor;
static const char *const model_qa_labels[]={"RUN + SUSTAINED FIRE","CROUCH + SUSTAINED FIRE"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){
        initialized=true;bg_set_players(4);bg_reset();bg_scene_reset();
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        motion_floor=bg_floor(0,4,100)+.015f;
    }
    unsigned sample=frame++%51,tick=sample<21?sample:sample-21;model_qa_page=sample>=21;
    *qa.seconds=tick/30.f;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=motion_floor;q->pos[2]=4;
        q->yaw=q->pitch=0;q->invisibility=p?1:0;q->vehicle=-1;q->health=100;q->grounded=true;
        q->weapon=BG_W_AR;q->slot=0;q->weapon_ready=q->melee_time=q->reload=q->landing_time=q->grenade_cooldown=0;
        q->crouched=model_qa_page;q->crouch_amount=model_qa_page;q->velocity[0]=1;
        q->animation=BG_ANIM_FIRE;q->fire_ticks[0]=tick%3;q->anim_time=(tick%3)/30.f;
        q->locomotion_time=tick/30.f;q->flash=.05f;q->gait=tick*.2f;
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.1f,0},{-1,.1f,0},{0,.1f,1},{0,.1f,-1}};
    for(unsigned a=0;a<3;a++){
        target->v[a]=(float[]){0,motion_floor+.42f,4}[a]*BG_SCALE;
        eye->v[a]=target->v[a]+dirs[p][a]*1.25f*BG_SCALE;
    }
}
#endif
