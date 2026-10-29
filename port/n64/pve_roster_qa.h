/* Four saved viewpoints per variant/tier. The final pages straddle the source
 * sword hit key and exercise cloak damage/regrowth appearances. */
unsigned bg_pve_model_qa_lod,bg_pve_vehicle_qa_lod;
static unsigned model_qa_page;
static float model_floor,model_center[3];
static const char *model_qa_labels[PVE_R_COUNT];
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){initialized=true;*qa.views=4;bg_set_players(4);bg_reset();bg_pve_start(0);bg_scene_reset();bg_pickup_count=bg_vehicle_count=0;model_floor=bg_floor(0,4,100)+1.015f;
        for(unsigned v=1;v<PVE_R_COUNT;v++)model_qa_labels[v]=bg_pve_variants[v].name;
    }
    unsigned page=frame++%BG_PVE_MODEL_QA_FRAMES;
    unsigned variant=page<42?1+page/3:(page<44?PVE_R_ZEALOT_SWORD:PVE_R_STEALTH_SWORD);
    unsigned clip=page<42?PVE_IDLE:PVE_MELEE;float phase=page<42?.35f:page%2?.7f:.4f;
    bg_pve_model_qa_lod=page<42?page%3:0;bg_pve_vehicle_qa_lod=0;model_qa_page=variant;
    for(unsigned h=0;h<4;h++){bg_player*p=&bg_players[h];p->pos[0]=0;p->pos[1]=model_floor;p->pos[2]=4;p->health=100;p->invisibility=1;p->camo_opacity=0;p->weapon_ready=p->flash=0;p->vehicle=-1;}
    bg_pve_count=1;memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));
    bg_pve_actor*a=&bg_pve_actors[0];uint16_t generation=a->generation+1;memset(a,0,sizeof(*a));a->occupied=true;a->generation=generation;a->kind=bg_pve_variants[variant].kind;
    bg_player*p=&bg_players[4];memset(p,0,sizeof(*p));p->pos[1]=model_floor;p->pos[2]=4;p->vehicle=-1;
    bg_pve_set_variant(0,variant);a->clip=clip;a->time=phase*bg_pve_animations[a->kind][0][bg_pve_render_clip(a)].duration;
    /* Near shows full source armor; middle shows partially revealed cloak;
     * distant shows settled regular/super camouflage. */
    if(page<42&&bg_pve_variants[variant].flags&PVE_R_CAMO)a->camouflage=page%3*.5f;
    model_center[0]=0;model_center[1]=model_floor+.38f;model_center[2]=4;*qa.seconds=phase;
    debugf("MODEL_PHOTO page=%u kind=%u variant=%u lod=%u clip=%u render_clip=%u phase=%.6f shield=%.3f pos=0,%.6f,4 yaw=0 crouch=0 camo=%.3f super=%.3f\n",page,a->kind,variant,bg_pve_model_qa_lod,clip,bg_pve_render_clip(a),phase,p->shield,model_floor,a->camouflage,a->super_camouflage);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.16f,0},{-1,.16f,0},{.3f,.16f,1},{.3f,-.25f,-1}};
    for(unsigned a=0;a<3;a++){target->v[a]=model_center[a]*BG_SCALE;eye->v[a]=(model_center[a]+dirs[p][a]*1.25f)*BG_SCALE;}
}
