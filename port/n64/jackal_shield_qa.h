/* Identical camera/actor states with the restoration compiled on or off. */
unsigned bg_pve_model_qa_lod,bg_pve_vehicle_qa_lod;
static unsigned model_qa_page;
static float model_floor,model_center[3];
static const char*model_qa_labels[]={"full","quarter","hit","depleted","14.9s down","15.1s recharged","run","fire","behind up","behind down","front up","front down"};
static bool model_qa_firstperson(void){return false;}
static void model_qa_stage(uint64_t now){
    (void)now;static unsigned frame;static bool initialized;
    if(!initialized){initialized=true;*qa.views=4;bg_set_players(4);bg_reset();bg_pve_start(0);bg_scene_reset();bg_pickup_count=bg_vehicle_count=0;model_floor=bg_floor(0,4,100)+1.015f;}
    unsigned page=frame++%BG_PVE_MODEL_QA_FRAMES,state=page%12,rank=page/36;bg_pve_model_qa_lod=(page/12)%3;bg_pve_vehicle_qa_lod=0;model_qa_page=state;
    bg_clear_events();bg_pve_count=1;memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));
    for(unsigned h=0;h<4;h++)bg_players[h].health=0; /* No targets while testing recharge. */
    bg_pve_actor*a=&bg_pve_actors[0];uint16_t generation=a->generation+(state!=2);memset(a,0,sizeof(*a));a->occupied=true;a->generation=generation;a->kind=BG_PVE_JACKAL;a->target=-1;
    const bg_pve_definition*d=&bg_pve_definitions[BG_PVE_JACKAL];bg_player*p=&bg_players[4];memset(p,0,sizeof(*p));
    p->health=d->health;p->shield=d->shield*bg_pve_difficulties[1].shield;p->pve_radius=d->radius;p->pve_height=d->height;
    p->pos[1]=model_floor;p->pos[2]=4;p->vehicle=-1;p->weapon=BG_W_PLASMA_PISTOL;
    if(rank){bg_pve_set_variant(0,PVE_R_JACKAL_MAJOR);d=&bg_pve_variants[PVE_R_JACKAL_MAJOR].def;}
    float maximum=d->shield*bg_pve_difficulties[1].shield;
    if(state==1)p->shield=maximum*.25f;
    if(state==2){p->shield=maximum*.125f;p->hurt=.65f;} /* a new shield hit after the quarter-strength page */
    if(state==3||state==4||state==5||state==9||state==11){p->shield=0;p->shield_delay=d->shield_delay;}
    if(state==4||state==5){
        /* Real production ticks prove the source 15-second stun and instant
         * restoration (source recharge_time=0); no invented fade-in clock. */
        unsigned ticks=state==4?447:453;for(unsigned t=0;t<ticks;t++)bg_pve_tick(1.f/30);
        assertf((p->shield>0)==(state==5),"Jackal source recharge fixture");
    }
    unsigned clip=state==6?PVE_RUN:state==7?PVE_FIRE:PVE_IDLE;float phase=.35f;
    a->clip=clip;a->time=phase*bg_pve_animations[BG_PVE_JACKAL][0][clip].duration;
    p->pos[0]=0;p->pos[1]=model_floor;p->pos[2]=4;p->yaw=0;
    if(state>=8){
        bg_pve_count=2;bg_pve_actor*b=&bg_pve_actors[1];memset(b,0,sizeof(*b));b->kind=BG_PVE_ELITE;b->occupied=true;b->generation=page+1;b->clip=PVE_IDLE;b->time=.35f*bg_pve_animations[BG_PVE_ELITE][0][PVE_IDLE].duration;
        bg_player*q=&bg_players[5];memset(q,0,sizeof(*q));q->health=q->shield=100;q->pos[0]=state<10?-.5f:.6f;q->pos[1]=model_floor;q->pos[2]=4;q->weapon=BG_W_PLASMA_RIFLE;q->vehicle=-1;
    }
    for(unsigned h=0;h<4;h++){bg_player*q=&bg_players[h];q->pos[0]=0;q->pos[1]=model_floor;q->pos[2]=4;q->health=100;q->invisibility=1;q->camo_opacity=0;q->weapon_ready=q->flash=0;q->vehicle=-1;}
    bg_clear_events();model_center[0]=0;model_center[1]=model_floor+.38f;model_center[2]=4;*qa.seconds=phase;
    debugf("MODEL_PHOTO page=%u kind=2 rank=%u lod=%u state=%u clip=%u phase=%.6f shield=%.6f delay=%.6f pos=0,%.6f,4 yaw=0 crouch=0 blocker=%u\n",page,rank,bg_pve_model_qa_lod,state,clip,phase,p->shield,p->shield_delay,model_floor,state>=8);
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    const float dirs[4][3]={{1,.16f,0},{-1,.16f,0},{.3f,.16f,1},{.3f,-.25f,-1}};
    for(unsigned k=0;k<3;k++){target->v[k]=model_center[k]*BG_SCALE;eye->v[k]=(model_center[k]+dirs[p][k]*1.25f)*BG_SCALE;}
}
