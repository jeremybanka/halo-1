#ifndef BG_JORGE_FIELD_QA_H
#define BG_JORGE_FIELD_QA_H
/* Jorge and CE reference through production weapon and seat state machines. */
#include "asset_jorge.h"
#ifndef BG_JORGE_FIELD_START
#define BG_JORGE_FIELD_START 0
#endif
static unsigned model_qa_page;
static float model_qa_floor;
static const char *const model_qa_labels[]={
 "JORGE FP: AR", "JORGE FP: PISTOL", "JORGE FP: PLASMA PISTOL", "JORGE FP: PLASMA RIFLE",
 "JORGE FP: NEEDLER", "JORGE FP: SHOTGUN", "JORGE FP: SNIPER", "JORGE FP: ROCKET", "JORGE FP: FLAMETHROWER",
 "HELD AR", "HELD PISTOL", "HELD PLASMA PISTOL", "HELD PLASMA RIFLE", "HELD NEEDLER", "HELD SHOTGUN", "HELD SNIPER", "HELD ROCKET", "HELD FLAMETHROWER",
 "WARTHOG DRIVER", "WARTHOG GUNNER", "WARTHOG PASSENGER", "GHOST", "SCORPION DRIVER", "SCORPION PASSENGER", "BANSHEE", "PASSENGER FIRST PERSON",
 "LOOK DOWN: STANDING", "LOOK DOWN: WALKING", "LOOK DOWN: CROUCHING",
 "1P: AR", "1P: PISTOL", "1P: PLASMA PISTOL", "1P: PLASMA RIFLE", "1P: NEEDLER", "1P: SHOTGUN", "1P: SNIPER", "1P: ROCKET", "1P: FLAMETHROWER",
 "4P: MIXED AR", "4P: ALL JORGE PISTOL", "4P: MIXED PLASMA PISTOL", "4P: ALL JORGE PLASMA RIFLE", "4P: MIXED NEEDLER", "4P: ALL JORGE SHOTGUN", "4P: MIXED SNIPER", "4P: ALL JORGE ROCKET", "4P: MIXED FLAMETHROWER",
 "4P LOOK DOWN: STANDING", "4P LOOK DOWN: WALKING", "4P LOOK DOWN: CROUCHING"};
static int field_vehicles[2];
static bool model_qa_firstperson(void){return model_qa_page<9 || model_qa_page>=25;}
static void field_tick(bg_input in[4]){
    bg_clear_events();bg_tick(in,1.f/30);*qa.seconds+=1.f/30;
    bg_hud_messages_update();bg_scene_update(1.f/30,*qa.seconds);
}
static void field_reset(void){
    bg_scene_release_firstperson();bg_set_players(model_qa_page>=26&&model_qa_page<38?1:4);bg_reset();bg_scene_reset();bg_set_score_limit(1000);
    bg_pickup_count=bg_vehicle_count=0;*qa.seconds=0;
    for(unsigned p=0;p<4;p++)bg_player_profiles[p]=p;
    bg_player_profiles[0]=BG_PROFILE_JORGE;bg_player_profiles[1]=3;
    if(model_qa_page>=38)
        for(unsigned p=0;p<4;p++)bg_player_profiles[p]=(model_qa_page%2||p%2==0)?BG_PROFILE_JORGE:p;
    for(unsigned p=0;p<4;p++)bg_scene_profile_changed(p);
    *qa.views=model_qa_page>=38?4:model_qa_page>=26?1:model_qa_firstperson()?2:4;model_qa_floor=bg_floor(0,4,100)+.015f;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=0;q->pos[2]=4+p*7;q->pos[1]=bg_floor(0,q->pos[2],100)+.015f;
        q->yaw=q->pitch=0;q->invisibility=model_qa_page<38&&p>=2?1:0;q->weapon_ready=0;q->zoom=0;
        unsigned weapon=model_qa_page<18?model_qa_page%9:BG_W_AR;
        if(model_qa_page>=29&&model_qa_page<38)weapon=model_qa_page-29;
        if(model_qa_page>=38)weapon=(model_qa_page-38+(unsigned[]){0,1,5,7}[p])%9;
        /* Looking down must not turn a rocket/flamethrower pose check into
         * self-damage and replace the remaining samples with a death camera. */
        if(model_qa_page>=47)weapon=(unsigned[]){BG_W_AR,BG_W_PISTOL,BG_W_SHOTGUN,BG_W_SNIPER}[p];
        bg_give_weapon(p,weapon);q->weapon=weapon;q->ammo=bg_weapon_defs[weapon].magazine;
        q->weapon_ready=0;q->reserve=bg_weapon_defs[weapon].reserve;
        if((model_qa_page>=26&&model_qa_page<=28)||model_qa_page>=47)q->pitch=-1.48f;
    }
    if(model_qa_page>=18&&model_qa_page<=25){
        unsigned row=model_qa_page==25?2:model_qa_page-18;
        unsigned kind=(unsigned[]){BG_V_WARTHOG,BG_V_WARTHOG,BG_V_WARTHOG,BG_V_GHOST,BG_V_SCORPION,BG_V_SCORPION,BG_V_BANSHEE}[row];
        unsigned seat=(unsigned[]){0,1,2,0,0,1,0}[row];
        bg_input input[4]={0};
        for(unsigned p=0;p<2;p++){
            field_vehicles[p]=bg_add_vehicle(kind,bg_players[p].pos,0);bg_players[p].pos[2]+=5;
        }
        for(unsigned t=0;t<45;t++)field_tick(input);
        for(unsigned p=0;p<2;p++){
            bg_vehicle*v=&bg_vehicles[field_vehicles[p]];
            if(kind==BG_V_SCORPION&&seat){v->occupants[0]=p+2;bg_players[p+2].vehicle=field_vehicles[p];bg_players[p+2].seat=0;}
            bg_vehicle_seat_position(v,seat,true,bg_players[p].pos);
            bg_players[p].pos[1]=bg_floor(bg_players[p].pos[0],bg_players[p].pos[2],100)+.015f;
            bg_use_target target=bg_interaction_target(p);
            assertf(target.kind==BG_USE_ENTER&&target.seat==(int)seat,"Jorge seat staging %u/%u",kind,seat);
        }
        if(model_qa_page==25){
            input[0].interact=input[1].interact=true;
            for(unsigned t=0;t<65;t++)field_tick(input);
        }
    }
}
static void model_qa_stage(uint64_t now){
    static uint64_t started;static unsigned previous=~0u,ticked;
    if(!started)started=now;
    /* Seven seconds covers entry, firing and exit even for the Scorpion. */
    model_qa_page=((unsigned)((now-started)/7000000)+BG_JORGE_FIELD_START)%(sizeof(model_qa_labels)/sizeof(*model_qa_labels));
    unsigned desired=(unsigned)(((now-started)%7000000)*30/1000000);
    if(previous!=model_qa_page){previous=model_qa_page;ticked=0;field_reset();}
    while(ticked<desired){
        bg_input input[4]={0};
        for(unsigned p=0;p<(model_qa_page>=38?4:2);p++){
            if(model_qa_page>=18&&model_qa_page<25)input[p].interact=ticked<8||(ticked>=135&&ticked<145);
            else{
                unsigned phase=ticked-(model_qa_page>=38?p*5:0);
                input[p].fire=phase>=30&&phase<48;
                input[p].reload=phase==65;input[p].melee=phase==150;
                if(model_qa_page<9)input[p].turn=sinf(ticked*.04f)*.12f;
                if(model_qa_page==27||model_qa_page==48)input[p].forward=.6f;
                if(model_qa_page==28||model_qa_page==49)input[p].crouch=true;
            }
        }
        field_tick(input);ticked++;
    }
}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(model_qa_firstperson())return;
    unsigned subject=p%2;const float*pos=bg_players[subject].pos;
    float radius=1.3f,height=.42f;
    if(model_qa_page>=18){pos=bg_vehicles[field_vehicles[subject]].pos;radius=model_qa_page==22||model_qa_page==23?3.7f:2.3f;height=.45f;}
    const float dirs[2][3]={{.8f,.25f,.6f},{-.7f,.25f,-.7f}};
    for(unsigned a=0;a<3;a++){
        target->v[a]=(pos[a]+(a==1?height:0))*BG_SCALE;
        eye->v[a]=target->v[a]+dirs[p/2][a]*radius*BG_SCALE;
    }
}
#endif
