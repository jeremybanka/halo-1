#ifndef BG_MODEL_QA_H
#define BG_MODEL_QA_H
/* Render-only fixture: normal model, animation, culling and depth paths.
 * Four fixed viewpoints per page; no simulation or performance claims. */
static unsigned model_qa_page;
static float model_qa_floor;
static const char *const model_qa_labels[]={
    "SPARTAN NEAR", "SPARTAN FAR", "SCORPION OCCLUSION",
    "PISTOLS / ROCKET / AR", "RELOAD POSE", "MELEE POSE",
    "WORLD WEAPONS", "OTHER VEHICLES"};
static bool model_qa_firstperson(void){return model_qa_page>=3&&model_qa_page<=5;}
static void model_qa_stage(uint64_t now){
    static uint64_t started;static unsigned previous=~0u;
    if(!started)started=now;
    model_qa_page=(unsigned)((now-started)/6000000)%8;
    if(model_qa_page==previous)return;
    previous=model_qa_page;bg_reset();bg_set_players(4);reset_view_state();
    model_qa_floor=bg_floor(0,4,100)+.015f;
    for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
    for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
    const int weapons[]={BG_W_PISTOL,BG_W_PLASMA_PISTOL,BG_W_ROCKET,BG_W_AR};
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=model_qa_floor;q->pos[2]=4;
        q->yaw=0;q->pitch=0;q->invisibility=p?1:0;
        q->animation=BG_ANIM_IDLE;q->anim_time=0;q->gait=0;q->zoom=0;
        bg_give_weapon(p,weapons[p]);q->weapon=weapons[p];q->ammo=bg_weapon_defs[weapons[p]].magazine;
        q->weapon_ready=0; /* Static pose pages must not freeze the ready animation. */
        if(model_qa_page>=3&&model_qa_page<=5){
            q->invisibility=1;
            if(model_qa_page==4){q->animation=BG_ANIM_RELOAD;q->anim_time=.55f;q->reload=.5f;}
            if(model_qa_page==5){q->animation=BG_ANIM_MELEE;q->anim_time=.15f;q->melee_time=.2f;}
        }
    }
    if(model_qa_page==2||model_qa_page==7){
        unsigned count=model_qa_page==2?1:3;
        for(unsigned i=0;i<count;i++){
            bg_vehicle*v=&bg_vehicles[i];v->active=true;v->kind=model_qa_page==2?BG_V_SCORPION:(int[]){BG_V_WARTHOG,BG_V_GHOST,BG_V_BANSHEE}[i];
            v->pos[0]=0;v->pos[1]=model_qa_floor+.35f;v->pos[2]=4+(model_qa_page==7?(int)i*5:0);
            v->yaw=v->pitch=0;v->physics_valid=false;
        }
        bg_players[0].vehicle=0;bg_players[0].seat=0;bg_players[0].animation=BG_ANIM_DRIVE;
        bg_vehicles[0].occupants[0]=0;
        bg_players[0].pos[0]=.1f;bg_players[0].pos[1]=model_qa_floor+.55f;
    }
    if(model_qa_page==6){
        bg_players[0].invisibility=1;
        for(unsigned p=0;p<4;p++)bg_pickups[p]=(bg_pickup){.pos={0,model_qa_floor+.5f,4+2.f*p},.weapon=weapons[p],.active=true};
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(model_qa_page>=3&&model_qa_page<=5)return;
    const float dirs[4][3]={{1,.12f,0},{-1,.12f,0},{.7f,.25f,.7f},{-.7f,.25f,-.7f}};
    float radius=model_qa_page==2?3.5f:model_qa_page==1?3.f:model_qa_page==6?.75f:model_qa_page==7?4:1.15f;
    float y=model_qa_floor+(model_qa_page==2?.6f:model_qa_page==6?.5f:.55f),z=4;
    if(model_qa_page==6)z+=p*2.f;
    if(model_qa_page==7)z+=(p%3)*5.f;
    for(unsigned a=0;a<3;a++){
        target->v[a]=(float[]){0,y,z}[a]*BG_SCALE;
        eye->v[a]=target->v[a]+dirs[p][a]*radius*BG_SCALE;
    }
}
#endif
