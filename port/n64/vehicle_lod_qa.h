/* 2 hulls × 3 poses × 2 four-angle sets × 3 requested tiers. */
#include "enemy_pilots.h"
unsigned bg_pve_model_qa_lod,bg_pve_vehicle_qa_lod;
static unsigned model_qa_page,vehicle_lod_angles;
static float model_floor,model_center[3],model_radius;
static const char*model_qa_labels[]={"Wraith distance LOD","Shade distance LOD"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){initialized=true;*qa.views=4;bg_set_players(4);bg_reset();bg_pve_start(0);bg_scene_reset();model_floor=bg_floor(0,4,100)+1.3f;}
    unsigned page=frame++%BG_PVE_MODEL_QA_FRAMES,group=page/18,pose=(page%18)/6,tier=page%3;
    vehicle_lod_angles=(page%6)/3;model_qa_page=group;bg_pve_model_qa_lod=0;
#ifdef BG_VEHICLE_DISTANCE_LODS
    bg_pve_vehicle_qa_lod=tier+1;
#else
    bg_pve_vehicle_qa_lod=1; /* Detailed articulated reference at every requested tier. */
#endif
    bg_clear_events();bg_pickup_count=0;bg_vehicle_count=1;bg_pve_count=1;memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));
    for(unsigned h=0;h<4;h++){bg_player*p=&bg_players[h];memset(p,0,sizeof(*p));p->pos[1]=model_floor;p->pos[2]=4;p->health=100;p->invisibility=1;p->vehicle=-1;}
    bg_vehicle*v=&bg_vehicles[0];memset(v,0,sizeof(*v));v->active=true;v->kind=group?BG_V_SHADE:BG_V_WRAITH;v->health=100;v->pos[1]=model_floor;v->pos[2]=4;
    for(unsigned n=0;n<BG_VEHICLE_SEATS;n++)v->occupants[n]=-1;
    v->occupants[0]=4;v->turret_yaw=(float[]){0,.6f,-.8f}[pose];v->turret_pitch=(float[]){0,.3f,-.2f}[pose];v->pitch=pose==2?.15f:0;
    v->hatch_closing=pose!=1;v->hatch=pose==0?1:.5f;
    bg_player*p=&bg_players[4];memset(p,0,sizeof(*p));p->health=p->shield=100;p->vehicle=0;p->animation=BG_ANIM_DRIVE;p->camo_opacity=1;
    bg_pve_actor*a=&bg_pve_actors[0];uint16_t generation=a->generation+1;memset(a,0,sizeof(*a));a->occupied=true;a->kind=BG_PVE_ELITE;a->generation=generation;
    p->pve_height=bg_pve_definitions[BG_PVE_ELITE].height;p->pve_radius=bg_pve_definitions[BG_PVE_ELITE].radius;p->weapon=BG_W_PLASMA_RIFLE;p->anim_time=.5f;
    bg_vehicle_seat_position(v,0,false,p->pos);
    model_center[0]=0;model_center[1]=model_floor+.55f;model_center[2]=4;model_radius=group?2.5f:5.f;*qa.seconds=.5f;
    debugf("LOD_PHOTO page=%u kind=%u tier=%u pose=%u angles=%u center=0,%.6f,4 radius=%.6f yaw=0 pitch=%.6f turret_yaw=%.6f turret_pitch=%.6f hatch=%.6f closing=%u crouch=0\n",page,v->kind,tier,pose,vehicle_lod_angles,model_center[1],model_radius,v->pitch,v->turret_yaw,v->turret_pitch,v->hatch,v->hatch_closing);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[2][4][3]={{{1,.22f,0},{-1,.22f,0},{0,.22f,1},{0,.22f,-1}},{{1,.55f,1},{-1,.55f,-1},{1,.55f,-1},{-1,.55f,1}}};
    for(unsigned k=0;k<3;k++){target->v[k]=model_center[k]*BG_SCALE;eye->v[k]=(model_center[k]+dirs[vehicle_lod_angles][p][k]*model_radius)*BG_SCALE;}
}
