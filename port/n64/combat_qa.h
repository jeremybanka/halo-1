#ifndef BG_COMBAT_QA_H
#define BG_COMBAT_QA_H
/* Identical staging in before/after ROMs; all attacks use production input. */
static void combat_qa_input(bg_input in[4],float time){
    static int previous=-1;const float duration=BG_COMBAT_QA>=5?24:12;int cycle=(int)(time/duration);float t=time-cycle*duration;
#if BG_COMBAT_QA == 7
    if(cycle!=previous){
        previous=cycle;bg_set_players(4);bg_reset();bg_set_score_limit(1000);(*qa.views)=4;
        bg_vehicle_count=bg_pickup_count=0;bg_scene_reset();
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];q->pos[0]=-15+(p%2?3:0);q->pos[2]=5+(p/2)*6;
            q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
            q->yaw=p%2?1.57079633f:0;q->pitch=0;
            bg_give_weapon(p,BG_W_AR);q->weapon_ready=q->cooldown=0;
            memcpy(q->last_pos,q->pos,12);
        }
        bg_add_pickup(BG_PICK_CAMO,bg_players[1].pos);
        bg_add_pickup(BG_PICK_CAMO,bg_players[3].pos);
        bg_add_pickup(BG_PICK_OVERSHIELD,bg_players[3].pos);
        const bg_input quiet[4]={0};bg_tick(quiet,1.f/30);
        float pos[3]={-12,bg_floor(-12,11,100),11};int vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);
        bg_player*q=&bg_players[3];q->vehicle=vi;q->seat=1;q->seat_state=BG_SEAT_STABLE;bg_vehicles[vi].occupants[1]=3;
        bg_players[2].pitch=.14f;
    }
    memset(in,0,sizeof(bg_input)*4);
    in[1].fire=in[3].fire=(t>=3&&t<4.5f)||(t>=11&&t<11.05f);
    return;
#endif
#if BG_COMBAT_QA == 5
    if(cycle!=previous){
        previous=cycle;bg_set_players(4);bg_reset();bg_set_score_limit(1000);(*qa.views)=4;
        bg_vehicle_count=bg_pickup_count=0;bg_scene_reset();
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];q->pos[0]=-12+(p==1?1.2f:p==2?1.5f:p==3?-2.f:0);
            q->pos[2]=5+(p==3?2.f:0);q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
            q->yaw=p==2?3.14159265f:0;q->pitch=0;q->weapon_ready=q->cooldown=0;
            memcpy(q->last_pos,q->pos,12);
        }
        bg_give_weapon(0,BG_W_PISTOL);bg_players[0].cooldown=0;
        bg_give_weapon(1,BG_W_AR);bg_players[1].ammo=7;bg_players[1].reserve=19;
        bg_players[1].inventory[1]=BG_W_PLASMA_PISTOL;bg_players[1].magazines[1]=23;bg_players[1].reserves[1]=0;
        bg_players[1].grenades[0]=2;bg_players[1].grenades[1]=3;bg_players[1].health=1;bg_players[1].shield=0;bg_players[1].shield_delay=30;
        bg_players[0].pitch=atan2f(bg_players[1].pos[1]+.35f-bg_players[0].pos[1]-bg_eye_height(&bg_players[0]),1.2f);
        bg_players[3].yaw=atan2f(2.f,3.2f);
    }
    memset(in,0,sizeof(bg_input)*4);in[0].fire=t>=2&&t<2.05f;in[2].interact=t>=3&&t<4;
    return;
#endif
#if BG_COMBAT_QA == 6
    static int death_stage;
    if(cycle!=previous){
        previous=cycle;death_stage=-1;bg_set_players(4);bg_reset();bg_set_score_limit(1000);(*qa.views)=4;bg_scene_reset();
        unsigned point=0;
        for(unsigned p=1;p<4;p++){
            while(point<bg_spawn_count&&!bg_slayer_spawns[point])point++;
            memcpy(bg_players[p].pos,bg_spawns[point].pos,12);bg_players[p].yaw=bg_spawns[point].yaw;point++;
        }
    }
    memset(in,0,sizeof(bg_input)*4);
    int stage=(int)(t/6);if(t>=1&&stage!=death_stage){
        death_stage=stage;bg_players[0].health=0;bg_players[0].respawn=3;
    }
    return;
#endif
#if BG_COMBAT_QA == 4
    static bool tipped;
    if(cycle!=previous){
        previous=cycle;tipped=false;bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        (*qa.views)=4;bg_vehicle_count=bg_pickup_count=0;bg_scene_reset();
        float pos[3]={-12,bg_floor(-12,5,100)+.5f,5};
        bg_add_vehicle(BG_V_WARTHOG,pos,0);
        for(unsigned p=0;p<3;p++){
            bg_players[p].vehicle=0;bg_players[p].seat=p;bg_players[p].seat_state=BG_SEAT_STABLE;
            bg_vehicles[0].occupants[p]=p;bg_players[p].yaw=0;bg_players[p].pitch=0;
        }
        bg_players[3].pos[0]=-15;bg_players[3].pos[2]=5;
        bg_players[3].pos[1]=bg_floor(-15,5,100)+.015f;bg_players[3].yaw=0;bg_players[3].pitch=0;
    }
    memset(in,0,sizeof(bg_input)*4);
    if(t>=2&&!tipped){
        /* Staged inversion; seat release and recovery run unmodified. */
        tipped=true;bg_vehicles[0].pitch=3.14159265f;bg_vehicles[0].physics_valid=false;
        bg_vehicles[0].pos[1]+=.6f;
    }
    return;
#endif
    if(cycle!=previous){
        previous=cycle;bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        (*qa.views)=4;bg_vehicle_count=bg_pickup_count=0;bg_scene_reset();
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];unsigned pair=p/2;
            float distance=BG_COMBAT_QA==2?(pair?3.8f:.9f):BG_COMBAT_QA==3?.6f:1.4f;
            q->pos[0]=(p&1)?distance:0;q->pos[2]=4+pair*5;
            q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
            q->yaw=(p&1)?3.14159265f:0;q->pitch=0;
            if(BG_COMBAT_QA==3&&pair)q->yaw=0;
            int w=BG_COMBAT_QA==1?(pair?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL):BG_COMBAT_QA==2?BG_W_SHOTGUN:BG_W_PISTOL;
            bg_give_weapon(p,w);q->weapon=w;q->inventory[q->slot]=w;
            q->ammo=bg_weapon_defs[w].magazine;q->weapon_ready=q->cooldown=0;
            if(BG_COMBAT_QA==1&&p==1)q->shield=300; /* Staged charged overshield. */
            memcpy(q->last_pos,q->pos,12);
        }
        for(unsigned p=0;p<4;p+=2){
            bg_player*a=&bg_players[p],*b=&bg_players[p+1];
            float height=BG_COMBAT_QA==0&&p==2?.60f:.36f;
            a->pitch=atan2f(b->pos[1]+height-a->pos[1]-bg_eye_height(a),b->pos[0]-a->pos[0]);
        }
    }
    memset(in,0,sizeof(bg_input)*4);
    for(unsigned p=0;p<4;p+=2){
        if(t<1||t>7||bg_players[p+1].health<=0)continue;
        float phase=fmodf(t-1,1.05f);
        if(BG_COMBAT_QA==3)in[p].melee=phase<.035f;
        else if(BG_COMBAT_QA==1&&p==0)in[p].fire=t<3;
        else in[p].fire=phase<.05f;
    }
}
static const char*combat_qa_title(void){
    return (const char*[]){"PISTOL: BODY / HEAD","OVERCHARGE / PLASMA RIFLE","SHOTGUN: NEAR / FAR","MELEE: FRONT / BACK","ROLLOVER: THREE OCCUPANTS","DEATH DROP / P3 RECOVERY","STAGED DEATHS / SLAYER SPAWNS","CAMO: INFANTRY / TURRET"}[BG_COMBAT_QA];
}
#endif
