#ifndef BG_GUNGNIR_QA_H
#define BG_GUNGNIR_QA_H
#include "gungnir.h"
#ifndef BG_GUNGNIR_QA_VIEWS
#define BG_GUNGNIR_QA_VIEWS (BG_GUNGNIR_QA==1?1:4)
#endif
static unsigned model_qa_page=BG_GUNGNIR_QA;
static const char *const model_qa_labels[]={"GUNGNIR / FOUR PALETTES / TWO LODS","GUNGNIR / OFF-AXIS ENEMY / FRIENDLY","GUNGNIR / NORMAL 2X AND 10X ZOOM","GUNGNIR / PERSONAL ARMS / WEAPON SERVICES"};
static bool model_qa_firstperson(void){return BG_GUNGNIR_QA!=0;}
static void model_qa_stage(uint64_t now){
    static uint64_t began;
    if(!began){began=now;for(unsigned p=0;p<4;p++)bg_set_player_armor(p,BG_ARMOR_GUNGNIR);bg_reset();*qa.views=BG_GUNGNIR_QA_VIEWS;bg_set_players(*qa.views==1?4:*qa.views);bg_scene_reset();
        for(unsigned p=0;p<4;p++){bg_player_profiles[p]=p;bg_scene_profile_changed(p);}
        if(BG_GUNGNIR_QA==1)bg_configure_mode(BG_MODE_TEAM_SLAYER,*qa.views==2?(uint8_t[]){0,1,1,1}:(uint8_t[]){0,0,1,1});
        debugf("GUNGNIR_QA page=%u views=%u\n",BG_GUNGNIR_QA,*qa.views);
    }
    float seconds=(now-began)*.000001f;bg_vehicle_count=bg_pickup_count=0;
    for(unsigned p=0;p<4;p++){
        bg_player *q=&bg_players[p];q->pos[0]=(p%2)*1.1f;q->pos[2]=4+(p/2)*1.2f;q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
        q->health=100;q->shield=150;q->armor=BG_ARMOR_GUNGNIR;q->vehicle=q->seat=-1;q->yaw=q->pitch=0;q->weapon=BG_W_AR;q->zoom=0;q->weapon_ready=q->reload=q->melee_time=q->flash=0;q->crouch_amount=0;q->grounded=true;q->animation=BG_ANIM_IDLE;q->anim_time=seconds;q->autopilot_on=false;
        if(BG_GUNGNIR_QA==1){q->pos[0]=p?5+(p==3):0;q->pos[2]=p==1?.7f:p==2?1.4f:p==3?3.f:0;q->pos[1]=bg_floor(0,0,100)+.015f;}
        if(BG_GUNGNIR_QA==2){q->pos[0]=-5;q->pos[2]=-4;q->pos[1]=bg_floor(0,4,100)+.015f;q->yaw=-.8f;if(p<3){q->weapon=p?BG_W_SNIPER:BG_W_PISTOL;q->zoom=p==2?2:1;}}
        if(BG_GUNGNIR_QA==3){q->weapon=(unsigned[]){BG_W_AR,BG_W_PISTOL,BG_W_PLASMA_RIFLE,BG_W_SNIPER}[p];q->pitch=-.45f;if(((unsigned)seconds/4)%2){q->reload=1;q->reload_duration=2.9f;q->anim_time=fmodf(seconds,2.9f);}}
    }
}
static void model_qa_camera(unsigned p,T3DVec3 *eye,T3DVec3 *target){
    if(BG_GUNGNIR_QA!=0)return;
    float radius=p<2?1.25f:3.3f,angle=p%2?.7f:2.4f;
    for(unsigned a=0;a<3;a++){target->v[a]=(bg_players[p].pos[a]+(a==1?.40f:0))*BG_SCALE;eye->v[a]=target->v[a]+(float[]){cosf(angle),.2f,sinf(angle)}[a]*radius*BG_SCALE;}
}
#endif
