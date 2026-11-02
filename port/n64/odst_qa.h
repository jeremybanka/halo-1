#ifndef BG_ODST_QA_H
#define BG_ODST_QA_H
/* Production cameras/HUDs: identical VISR/normal zoom projections. */
static unsigned model_qa_page=BG_ODST_QA;
static const char *const model_qa_labels[]={"ODST FOUR PALETTES / NEAR AND FAR","VISR MIXED VIEWS / CLOAKED ENEMIES","ODST FIRST PERSON / WEAPON ACTIONS","VISR ALLIES / ENEMIES","VISR WEAPON / HUD","VISR PISTOL 2X","VISR SNIPER 2X","VISR SNIPER 10X","VISR ALLY PARTIAL / ENEMY HIDDEN","VISR ENEMY PARTIAL / ALLY HIDDEN","VISR THREE PLAYER GRID CACHE","ODST MUTED TEAM PLATES / NEAR AND FAR"};
static bool model_qa_firstperson(void){return BG_ODST_QA==2||(BG_ODST_QA>=4&&BG_ODST_QA<=10);}
static float odst_qa_eye[3],odst_qa_partial[3],odst_qa_hidden[3],odst_qa_yaw;
static unsigned odst_qa_blocked(const float eye[3],const float body[3]){
    unsigned blocked=0;
    for(unsigned i=0;i<9;i++){
        float p[3]={body[0]+((int)(i%3)-1)*.09f,body[1]+.12f+(i/3)*.23f,body[2]},dir[3],distance=0;
        for(unsigned a=0;a<3;a++){dir[a]=p[a]-eye[a];distance+=dir[a]*dir[a];}distance=sqrtf(distance);
        for(unsigned a=0;a<3;a++)dir[a]/=distance;
        float normal[3];blocked+=bg_world_raycast_normal(eye,dir,distance,normal)<distance-.015f;
    }
    return blocked;
}
static void odst_qa_occlusion(void){
    bool found=false;
    for(unsigned s=0;s<bg_spawn_count&&!found;s++)for(unsigned d=0;d<16&&!found;d++){
        float yaw=d*.3926990817f,dir[3]={cosf(yaw),0,-sinf(yaw)},normal[3];
        float eye[3]={bg_spawns[s].pos[0],bg_spawns[s].pos[1]+.62f,bg_spawns[s].pos[2]};
        float hit=bg_world_raycast_normal(eye,dir,4,normal);
        if(hit<1||hit>3.8f||fabsf(normal[1])>.2f)continue;
        float body[3]={eye[0]+dir[0]*(hit+.18f),eye[1]-.62f,eye[2]+dir[2]*(hit+.18f)};
        if(odst_qa_blocked(eye,body)!=9)continue;
        for(int side=-1;side<=1&&!found;side+=2)for(unsigned step=1;step<32&&!found;step++){
            float partial[3]={body[0]-dir[2]*step*.08f*side,body[1],body[2]+dir[0]*step*.08f*side};
            unsigned blocked=odst_qa_blocked(eye,partial);
            if(blocked>0&&blocked<=3){memcpy(odst_qa_eye,eye,12);memcpy(odst_qa_partial,partial,12);memcpy(odst_qa_hidden,body,12);odst_qa_yaw=yaw;found=true;}
        }
    }
    assertf(found,"VISR partial/total static-world occlusion fixture");
    debugf("VISR_OCCLUSION partial=%u/9 total=%u/9\n",odst_qa_blocked(odst_qa_eye,odst_qa_partial),odst_qa_blocked(odst_qa_eye,odst_qa_hidden));
}
static void model_qa_stage(uint64_t now){
    static uint64_t started;
    if(!started){
        started=now;for(unsigned p=0;p<4;p++)bg_set_player_armor(p,BG_ARMOR_ODST);
        bg_reset();*qa.views=BG_ODST_QA==10?3:4;bg_set_players(*qa.views);bg_scene_reset();
        if(BG_ODST_QA>=3){const uint8_t teams[4]={0,0,0,1};bg_configure_mode(BG_MODE_TEAM_SLAYER,teams);}
        for(unsigned p=0;p<4;p++){bg_player_profiles[p]=p;bg_scene_profile_changed(p);
            if(BG_ODST_QA==11){assertf(bg_player_color(p)==(p==3?1:0),"ODST team palette routing");debugf("ODST_TEAM_PLATES player=%u profile=%u color=%u\n",p,p,bg_player_color(p));}}
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        if(BG_ODST_QA==8||BG_ODST_QA==9)odst_qa_occlusion();
    }
    float seconds=(now-started)*.000001f;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=(float)(p%2)*1.1f;q->pos[2]=4+(p/2)*1.2f;
        q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;q->yaw=0;q->pitch=BG_ODST_QA==2?-.55f:0;
        q->armor=BG_ARMOR_ODST;q->shield=0;q->health=100;q->vehicle=-1;q->weapon=BG_W_AR;q->zoom=0;
        q->weapon_ready=0;q->reload=q->melee_time=q->flash=0;q->grenade_cooldown=0;q->crouch_amount=0;q->grounded=true;
        q->animation=BG_ANIM_IDLE;q->anim_time=seconds;q->invisibility=0;q->camo_opacity=1;
        q->flashlight_on=(BG_ODST_QA==1||(BG_ODST_QA>=3&&BG_ODST_QA<=10))&&(p==0||p==2);
        if(BG_ODST_QA==1||BG_ODST_QA==3){q->invisibility=10;q->camo_opacity=(p==1||p==3)?0:1;}
        if(BG_ODST_QA==2){unsigned phase=(unsigned)(seconds/3)%4;if(phase==1){q->reload=1;q->reload_duration=2.9f;q->anim_time=fmodf(seconds,2.9f);}if(phase==2)q->melee_time=.15f;}
        if((BG_ODST_QA>=4&&BG_ODST_QA<=7)||BG_ODST_QA==10){
            q->pos[1]=bg_floor(1.1f,5.2f,100)+2.5f;
            if(p<2){q->pos[0]=-7;q->pos[2]=-8;q->yaw=-atan2f(9.2f,6.1f);q->pitch=0;}
            if(BG_ODST_QA==5){q->weapon=BG_W_PISTOL;q->zoom=1;}
            if(BG_ODST_QA==6||BG_ODST_QA==7){q->weapon=BG_W_SNIPER;q->zoom=BG_ODST_QA==7?2:1;}
        }
        if(BG_ODST_QA==8||BG_ODST_QA==9){
            if(p==2||p==3)memcpy(q->pos,(p==2)^(BG_ODST_QA==9)?odst_qa_partial:odst_qa_hidden,12);
            else for(unsigned a=0;a<3;a++)q->pos[a]=odst_qa_eye[a]-(a==1?.62f:0);
            q->yaw=odst_qa_yaw;q->pitch=0;
        }
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(BG_ODST_QA==2)return;
    if(BG_ODST_QA==8||BG_ODST_QA==9){for(unsigned a=0;a<3;a++){eye->v[a]=odst_qa_eye[a]*BG_SCALE;target->v[a]=(odst_qa_partial[a]+(a==1?.4f:0))*BG_SCALE;}return;}
    if(BG_ODST_QA>=4&&BG_ODST_QA<=10){
        float pos[3]={-5,bg_floor(1.1f,5.2f,100)+2.92f,-4};
        for(unsigned a=0;a<3;a++){eye->v[a]=pos[a]*BG_SCALE;target->v[a]=(bg_players[3].pos[a]+(a==1?.4f:0))*BG_SCALE;}
        return;
    }
    bool palettes=BG_ODST_QA==0||BG_ODST_QA==11;
    unsigned subject=palettes?p:1;float radius=palettes?(p<2?1.25f:3.2f):2.2f;
    for(unsigned a=0;a<3;a++){target->v[a]=(bg_players[subject].pos[a]+(a==1?.40f:0))*BG_SCALE;eye->v[a]=target->v[a]+(float[]){.75f,.22f,.55f}[a]*radius*BG_SCALE;}
}
#endif
