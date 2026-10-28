#ifndef BG_PVE_MODEL_QA_H
#define BG_PVE_MODEL_QA_H
#include "pve.h"
#include "asset_pve.h"
/* Frozen inspection only: four matched cameras, both LODs, articulated poses. */
unsigned bg_pve_model_qa_lod;
static unsigned model_qa_page;
static float model_floor,model_center[3];
static const char *const model_qa_labels[]={"GRUNT","ELITE","JACKAL","HUNTER","SPIRIT"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){
        initialized=true;*qa.views=4;bg_set_players(4);bg_reset();bg_pve_start(0);bg_scene_reset();
        /* Suspend inspection models above the sloping ground so every camera
         * can see the feet and underside; this never changes gameplay poses. */
        bg_pickup_count=bg_vehicle_count=0;model_floor=bg_floor(0,4,100)+1.015f;
    }
    unsigned page=frame++%52,clip=PVE_IDLE;float phase=0;bool shield=true;
    if(page<24){model_qa_page=BG_PVE_HUNTER;bg_pve_model_qa_lod=page/12;clip=(unsigned[]){PVE_IDLE,PVE_RUN,PVE_MELEE}[(page%12)/4];phase=(page%4)*.25f;}
    else if(page<32){model_qa_page=BG_PVE_SPIRIT;bg_pve_model_qa_lod=(page-24)/4;phase=(page%4)/3.f;}
    else if(page<40){model_qa_page=BG_PVE_JACKAL;bg_pve_model_qa_lod=(page-32)/4;shield=(page%2)==0;clip=(page%4)<2?PVE_IDLE:PVE_FIRE;phase=.35f;}
    else if(page<48){model_qa_page=page<44?BG_PVE_GRUNT:BG_PVE_ELITE;bg_pve_model_qa_lod=(page%4)/2;clip=(page%2)?PVE_RUN:PVE_IDLE;phase=.35f;}
    else{model_qa_page=BG_PVE_JACKAL;bg_pve_model_qa_lod=(page-48)/2;shield=(page%2)==0;phase=.35f;}
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[1]=model_floor;q->pos[2]=4;
        q->health=100;q->invisibility=1;q->weapon_ready=q->flash=0;q->vehicle=-1;
    }
    if(page>=48){
        /* A later-submitted opaque Spartan behind the shield exercises the
         * transparency/depth ordering, in addition to isolated model views. */
        bg_players[1].pos[0]=-.28f;bg_players[1].pos[2]=4.18f;
        bg_players[1].invisibility=0;bg_players[1].yaw=0;
    }
    model_center[0]=0;model_center[1]=model_floor+(model_qa_page==BG_PVE_SPIRIT?6.5f:model_qa_page==BG_PVE_HUNTER?.52f:.38f);model_center[2]=4;
    bg_pve_count=model_qa_page==BG_PVE_SPIRIT?0:1;memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));
    if(!bg_pve_count){bg_ff_dropship.phase=1;bg_ff_dropship.pos[0]=0;bg_ff_dropship.pos[1]=model_floor+5;bg_ff_dropship.pos[2]=4;bg_ff_dropship.yaw=0;bg_ff_dropship.door=phase;}
    else{
        bg_pve_actor*a=&bg_pve_actors[0];memset(a,0,sizeof(*a));a->occupied=true;a->kind=model_qa_page;a->clip=clip;
        a->time=phase*bg_pve_animations[a->kind][0][clip].duration;
        bg_player*p=&bg_players[BG_PLAYERS];memset(p,0,sizeof(*p));p->pos[1]=model_floor;p->pos[2]=4;p->health=100;p->shield=shield?100:0;p->vehicle=-1;
        p->weapon=a->kind==BG_PVE_ELITE?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL;
    }
    *qa.seconds=phase;
    debugf("MODEL_PHOTO page=%u kind=%u lod=%u clip=%u phase=%.6f shield=%u pos=0,%.6f,4 yaw=0 crouch=0\n",page,model_qa_page,bg_pve_model_qa_lod,clip,phase,shield,model_floor);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.16f,0},{-1,.16f,0},{.3f,.16f,1},{.3f,-.25f,-1}};
    float radius=model_qa_page==BG_PVE_SPIRIT?13:model_qa_page==BG_PVE_HUNTER?1.7f:1.25f;
    for(unsigned a=0;a<3;a++){target->v[a]=model_center[a]*BG_SCALE;eye->v[a]=(model_center[a]+dirs[p][a]*radius)*BG_SCALE;}
}
#endif
