#ifndef BG_HUD_QA_H
#define BG_HUD_QA_H
/* Frozen gameplay states, using the production HUD and view renderer. */
static unsigned model_qa_page;
static const char *const model_qa_labels[]={
    "HUD: AR 60 / 59 / 20 / 0", "HUD: PISTOL / NEEDLER / SHOTGUN / SNIPER",
    "HUD: ENERGY / HEAT / ROCKET / RESPAWN", "HUD: SCOPES / WARNINGS",
    "HUD: ONE PLAYER", "HUD: TWO PLAYERS", "HUD: VEHICLE RETICLES",
    "PROMPTS: AR / PISTOL / PLASMA PISTOL / RIFLE",
    "PROMPTS: NEEDLER / SHOTGUN / SNIPER / ROCKET",
    "RECEIPTS: ROUNDS / WEAPONS / GRENADES / POWERUPS",
    "STAGED: KILL / DOUBLE / TRIPLE / SPREE / REJOIN",
    "PROMPTS: ONE PLAYER / RECEIPTS",
    "PROMPTS: TWO PLAYERS / RELOAD AND VENT"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3 *eye,T3DVec3 *target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
    static unsigned previous=~0u;
#ifdef BG_HUD_QA_PAGE
    (void)now;model_qa_page=BG_HUD_QA_PAGE;
#else
    static uint64_t start;if(!start)start=now;
    model_qa_page=(unsigned)((now-start)/20000000)%13;
#endif
    if(previous==model_qa_page)return;
    previous=model_qa_page;bg_reset();bg_hud_messages_reset();
    float prompt_positions[4][3];
    for(unsigned i=0;i<4;i++)memcpy(prompt_positions[i],bg_players[i].pos,sizeof(prompt_positions[i]));
    (*qa.views)=model_qa_page==4||model_qa_page==11?1:model_qa_page==5||model_qa_page==12?2:4;
    bg_set_players((*qa.views));bg_scene_reset();(*qa.seconds)=0;
    for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
    for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
    for(unsigned i=0;i<4;i++){
        bg_player *p=&bg_players[i];p->pos[0]=-12;p->pos[2]=5;
        p->pos[1]=bg_floor(-12,5,100)+.015f;p->yaw=-.6f;p->pitch=-.06f;
        p->invisibility=1;p->zoom=0;p->score=i==3?-1:12;
        p->grenades[0]=4;p->grenades[1]=2;p->grenade_kind=i%2;
        unsigned weapon=BG_W_AR;
        if(model_qa_page==1)weapon=(unsigned[]){BG_W_PISTOL,BG_W_NEEDLER,BG_W_SHOTGUN,BG_W_SNIPER}[i];
        if(model_qa_page==2)weapon=(unsigned[]){BG_W_PLASMA_PISTOL,BG_W_PLASMA_RIFLE,BG_W_ROCKET,BG_W_AR}[i];
        if(model_qa_page==3)weapon=i==0?BG_W_PISTOL:i==1?BG_W_SNIPER:BG_W_AR;
        bg_give_weapon(i,weapon);p->weapon=weapon;p->ammo=bg_weapon_defs[weapon].magazine;
        p->reserve=240;p->animation=BG_ANIM_IDLE;p->anim_time=0;bg_scene_fired(i,-100);
        if(!model_qa_page)p->ammo=(int[]){60,59,20,0}[i];
        if(model_qa_page==2){p->heat=i==1?1:.4f;p->overheated=i==1;if(i==3){p->health=0;p->respawn=3;}}
        if(model_qa_page==3){
            if(i<2)p->zoom=i+1;
            p->shield=(float[]){100,160,0,35}[i];p->health=(float[]){100,100,22,60}[i];
            if(i==2)p->reload=.5f;
        }
        if(model_qa_page==6)for(unsigned v=0;v<bg_vehicle_count;v++){
            if(bg_vehicles[v].kind!=(int)i)continue;
            bg_vehicles[v].active=true;p->vehicle=v;p->seat=i==BG_V_WARTHOG?1:0;
            bg_vehicles[v].occupants[p->seat]=i;memcpy(p->pos,bg_vehicles[v].pos,sizeof(p->pos));
            break;
        }
    }
    if(model_qa_page>=7){
        bg_pickup_count=0;bg_clear_events();
        for(unsigned i=0;i<4;i++){
            bg_player*p=&bg_players[i];memcpy(p->pos,prompt_positions[i],sizeof(p->pos));
            p->weapon_ready=p->cooldown=0;
            p->inventory[0]=p->weapon=BG_W_AR;p->inventory[1]=i&1?BG_W_NEEDLER:-1;
            p->ammo=60;p->reserve=240;p->overheated=false;p->reload=0;
            if(model_qa_page==7||model_qa_page==8||model_qa_page>=11){
                unsigned weapon=model_qa_page==7?(unsigned[]){BG_W_AR,BG_W_PISTOL,BG_W_PLASMA_PISTOL,BG_W_PLASMA_RIFLE}[i]:
                    (unsigned[]){BG_W_NEEDLER,BG_W_SHOTGUN,BG_W_SNIPER,BG_W_ROCKET}[i];
                if(model_qa_page==7&&i<2)p->inventory[0]=p->weapon=BG_W_PLASMA_PISTOL;
                float pos[3]={p->pos[0]+.6f,p->pos[1],p->pos[2]};bg_add_pickup(weapon,pos);
            }
        }
        if(model_qa_page==9||model_qa_page==11){
            const bg_event staged[]={
                {.kind=BG_EVENT_PICKUP,.player=0,.weapon=BG_W_AR,.amount=1},
                {.kind=BG_EVENT_AMMO,.player=0,.weapon=BG_W_AR,.amount=50},
                {.kind=BG_EVENT_AMMO,.player=1,.weapon=BG_W_ROCKET,.amount=4},
                {.kind=BG_EVENT_AMMO,.player=1,.weapon=BG_W_NEEDLER,.amount=19},
                {.kind=BG_EVENT_PICKUP,.player=2,.weapon=BG_PICK_FRAG,.amount=1},
                {.kind=BG_EVENT_PICKUP,.player=2,.weapon=BG_PICK_PLASMA,.amount=3},
                {.kind=BG_EVENT_PICKUP,.player=3,.weapon=BG_PICK_HEALTH,.amount=1},
                {.kind=BG_EVENT_PICKUP,.player=3,.weapon=BG_PICK_CAMO,.amount=1},
            };
            memcpy(bg_events,staged,sizeof(staged));bg_event_count=sizeof(staged)/sizeof(staged[0]);
            bg_hud_messages_update();bg_clear_events();
            if(model_qa_page==9){
                bg_players[0].ammo=bg_players[0].reserve=0;
                bg_players[0].inventory[1]=BG_W_PISTOL;
                bg_players[0].magazines[1]=8;bg_players[0].reserves[1]=24;
            }
        }
        if(model_qa_page==10){
            const bg_event staged[]={
                {.kind=BG_EVENT_KILL,.player=1,.weapon=0,.amount=1},
                {.kind=BG_EVENT_DOUBLE_KILL,.player=1,.amount=2},
                {.kind=BG_EVENT_TRIPLE_KILL,.player=2,.amount=3},
                {.kind=BG_EVENT_KILLING_SPREE,.player=3,.amount=5},
                {.kind=BG_EVENT_PICKUP,.player=3,.weapon=BG_PICK_OVERSHIELD,.amount=1},
            };
            memcpy(bg_events,staged,sizeof(staged));bg_event_count=sizeof(staged)/sizeof(staged[0]);
            bg_hud_messages_update();bg_clear_events();bg_players[0].health=0;bg_players[0].respawn=3;
        }
        if(model_qa_page==12){
            bg_players[0].reload=.5f;
            bg_players[1].weapon=bg_players[1].inventory[0]=BG_W_PLASMA_RIFLE;
            bg_players[1].ammo=73;bg_players[1].heat=1;bg_players[1].overheated=true;
        }
    }
}
#endif
