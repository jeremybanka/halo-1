#ifndef BG_HUD_QA_H
#define BG_HUD_QA_H
/* Frozen gameplay states, using the production HUD and view renderer. */
static unsigned model_qa_page;
static const char *const model_qa_labels[]={
    "HUD: AR 60 / 59 / 20 / 0", "HUD: PISTOL / NEEDLER / SHOTGUN / SNIPER",
    "HUD: ENERGY / HEAT / ROCKET / RESPAWN", "HUD: SCOPES / WARNINGS",
    "HUD: ONE PLAYER", "HUD: TWO PLAYERS", "HUD: VEHICLE RETICLES"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3 *eye,T3DVec3 *target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
    static unsigned previous=~0u;
#ifdef BG_HUD_QA_PAGE
    (void)now;model_qa_page=BG_HUD_QA_PAGE;
#else
    static uint64_t start;if(!start)start=now;
    model_qa_page=(unsigned)((now-start)/20000000)%7;
#endif
    if(previous==model_qa_page)return;
    previous=model_qa_page;bg_reset();views=model_qa_page==4?1:model_qa_page==5?2:4;
    bg_set_players(views);reset_view_state();game_time=0;
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
        p->reserve=240;p->animation=BG_ANIM_IDLE;p->anim_time=0;fired_at[i]=-100;
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
}
#endif
