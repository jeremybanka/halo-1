#ifndef BG_SPARTAN_RELOAD_QA_H
#define BG_SPARTAN_RELOAD_QA_H
/* Four matched views; sample every three ticks through a complete reload and
 * its return to walking. Actual movement/ammo timing are tested on the host. */
static unsigned model_qa_page;
static float motion_floor;
static const char *const model_qa_labels[]={"WALK + RELOAD","CROUCH WALK + RELOAD"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){
        initialized=true;bg_set_players(4);bg_reset();bg_scene_reset();
        bg_vehicle_count=bg_pickup_count=0;motion_floor=bg_floor(0,4,100)+.015f;
    }
    unsigned sample=frame++%72,tick=(sample%36)*3;model_qa_page=sample/36;
    float seconds=tick/30.f,duration=bg_trigger_profiles[BG_W_AR].reload_empty/30.f;
    *qa.seconds=seconds;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=motion_floor;q->pos[2]=4;
        q->yaw=q->pitch=0;q->invisibility=p?1:0;q->vehicle=-1;q->health=100;q->grounded=true;
        q->weapon=BG_W_AR;q->slot=0;q->weapon_ready=q->melee_time=q->landing_time=q->grenade_cooldown=0;
        q->crouched=model_qa_page;q->crouch_amount=model_qa_page;q->velocity[0]=1;
        q->reload_duration=duration;q->reload=fmaxf(0,duration-seconds);
        q->animation=q->reload>0?BG_ANIM_RELOAD:BG_ANIM_RUN;q->fire_ticks[0]=100;q->anim_time=seconds;
        q->locomotion_time=.13f+seconds;q->flash=0;q->gait=tick*.2f;
    }
    debugf("RELOAD_PHOTO page=%u tick=%u crouch=%u action=%.6f gait=%.6f duration=%.6f\n",sample,tick,model_qa_page,seconds,.13f+seconds,duration);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.1f,0},{-1,.1f,0},{0,.1f,1},{0,.1f,-1}};
    for(unsigned a=0;a<3;a++){
        target->v[a]=(float[]){0,motion_floor+.42f,4}[a]*BG_SCALE;
        eye->v[a]=target->v[a]+dirs[p][a]*1.25f*BG_SCALE;
    }
}
#endif
