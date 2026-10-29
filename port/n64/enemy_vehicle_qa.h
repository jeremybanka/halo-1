/* Frozen source seat/hatch inspection: four cameras, three actor tiers. */
#include "enemy_pilots.h"
unsigned bg_pve_model_qa_lod,bg_pve_vehicle_qa_lod;
static unsigned model_qa_page;
static float model_floor,model_center[3],model_radius;
static const char*model_qa_labels[]={"Ghost pilot","Banshee pilot","Wraith pilot","Shade gunner","Shade Spartan","Wraith Spartan"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){initialized=true;*qa.views=4;bg_set_players(4);bg_reset();bg_pve_start(0);bg_scene_reset();model_floor=bg_floor(0,4,100)+1.015f;}
    unsigned page=frame++%BG_PVE_MODEL_QA_FRAMES;bool human=page>=36;
    unsigned group=human?4+(page-36)/3:page/9,state=human?(page-36)%3:(page%9)/3;
    unsigned kind=(unsigned[]){BG_V_GHOST,BG_V_BANSHEE,BG_V_WRAITH,BG_V_SHADE,BG_V_SHADE,BG_V_WRAITH}[group];
    bg_pve_model_qa_lod=human?0:page%3;bg_pve_vehicle_qa_lod=0;model_qa_page=group;
    bg_clear_events();bg_pickup_count=0;bg_vehicle_count=1;bg_pve_count=human?0:1;memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));
    for(unsigned h=0;h<4;h++){bg_player*p=&bg_players[h];memset(p,0,sizeof(*p));p->pos[1]=model_floor;p->pos[2]=4;p->health=100;p->invisibility=1;p->vehicle=-1;}
    bg_vehicle*v=&bg_vehicles[0];memset(v,0,sizeof(*v));v->active=true;v->kind=kind;v->health=100;v->pos[1]=model_floor;v->pos[2]=4;
    for(unsigned n=0;n<BG_VEHICLE_SEATS;n++)v->occupants[n]=-1;
    unsigned unit=human?0:4;v->occupants[0]=unit;
    bg_player*p=&bg_players[unit];memset(p,0,sizeof(*p));p->health=p->shield=100;p->vehicle=0;p->seat_state=state;p->animation=BG_ANIM_DRIVE;p->camo_opacity=1;
    if(!human){bg_pve_actor*a=&bg_pve_actors[0];uint16_t generation=a->generation+1;memset(a,0,sizeof(*a));a->occupied=true;a->kind=BG_PVE_ELITE;a->generation=generation;
        p->pve_height=bg_pve_definitions[BG_PVE_ELITE].height;p->pve_radius=bg_pve_definitions[BG_PVE_ELITE].radius;p->weapon=BG_W_PLASMA_RIFLE;}
    const bg_seat_definition*s=bg_player_seat(p);float phase=.5f;p->anim_time=phase*(state==1?s->enter_time:state==2?s->exit_time:1);
    bg_vehicle_seat_position(v,0,false,p->pos);v->hatch_closing=state==0;v->hatch=state==0?1:state==1?1:.5f;
    model_center[0]=0;model_center[1]=model_floor+.55f;model_center[2]=4;model_radius=kind==BG_V_WRAITH?5.f:kind==BG_V_BANSHEE?4.5f:kind==BG_V_SHADE?2.5f:3.f;*qa.seconds=.5f;
    debugf("MODEL_PHOTO page=%u vehicle=%u human=%u lod=%u seat=%u phase=%.6f pos=0,%.6f,4 yaw=0 crouch=0 radius=%.3f\n",page,kind,human,bg_pve_model_qa_lod,state,phase,model_floor,model_radius);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.3f,0},{-1,.3f,0},{.3f,.3f,1},{.3f,.8f,-1}};
    for(unsigned k=0;k<3;k++){target->v[k]=model_center[k]*BG_SCALE;eye->v[k]=(model_center[k]+dirs[p][k]*model_radius)*BG_SCALE;}
}
