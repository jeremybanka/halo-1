#ifndef BG_WARTHOG_FLASH_QA_H
#define BG_WARTHOG_FLASH_QA_H
#include "weapon_effects.h"
static unsigned model_qa_page, muzzle_sample;
static float muzzle_floor;
static const char *const model_qa_labels[]={"WARTHOG: REST","WARTHOG: FLASH"};
static bool model_qa_firstperson(void){return muzzle_sample>=25;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){
        initialized=true;bg_set_players(4);bg_reset();bg_scene_reset();bg_fx_reset();
        bg_vehicle_count=bg_pickup_count=0;muzzle_floor=bg_floor(-12,5,100)+.25f;
        bg_add_vehicle(BG_V_WARTHOG,(float[]){-12,muzzle_floor,5},0);
    }
    muzzle_sample=frame++%50;model_qa_page=muzzle_sample%2;*qa.seconds=frame/30.f;
    bg_vehicle*v=&bg_vehicles[0];
    unsigned pose=(muzzle_sample/2)%5;
    v->yaw=.3f;v->turret_yaw=(float[]){0,-.8f,.8f,-.4f,.4f}[pose];
    v->pitch=pose==4?.12f:0;v->turret_pitch=(float[]){0,0,0,-.3f,.3f}[pose];
    v->physics_valid=false;v->occupants[1]=0;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->health=q->shield=100;q->vehicle=0;q->seat=1;
        q->seat_state=BG_SEAT_STABLE;q->weapon_ready=0;q->invisibility=p?1:0;
        q->yaw=v->yaw+v->turret_yaw;q->pitch=v->turret_pitch;
        bg_vehicle_seat_position(v,1,false,q->pos);q->animation=BG_ANIM_DRIVE;
    }
    bg_clear_events();
    if(model_qa_page){bg_event_count=1;bg_events[0]=(bg_event){.kind=BG_EVENT_FIRE,.player=0,.weapon=BG_W_AR};}
    bg_fx_update(1.f/30);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(muzzle_sample>=25)return; /* Retain the production gunner camera. */
    const float directions[4][3]={{1,.1f,0},{-1,.1f,0},{0,.1f,1},{0,.1f,-1}};
    for(unsigned a=0;a<3;a++){
        target->v[a]=(float[]){-12,muzzle_floor+.8f,5}[a]*BG_SCALE;
        eye->v[a]=target->v[a]+directions[p][a]*2.1f*BG_SCALE;
    }
}
#endif
