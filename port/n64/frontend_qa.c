#include "frontend_qa.h"
#include <assert.h>
#include <math.h>
#include <string.h>
#include "map.h"
#include "terrain.h"
#include "pickup_rules.h"
#include "movement.h"
#include "game.h"
#include "blam/vehicle_physics.h"
#ifdef BG_GUNGNIR_FRONTEND_QA
#include "gungnir.h"
#include "autopilot_nav.h"
#endif
/* Separately named fixture: controller edges navigate production menus.
 * Combat is staged, but health, damage, respawn, score limit and game-over
 * dispatch are the normal simulation. No scores/winner are assigned. */
#ifndef BG_FRONTEND_QA_PLAYERS
#define BG_FRONTEND_QA_PLAYERS 4
#endif
#define ALL (BG_FRONTEND_QA_PLAYERS==3?11:15)
#if defined(BG_INITIAL_MAP) && BG_INITIAL_MAP == 10
#define MAP_PROBE BG_BUTTON_D_RIGHT
#define MAP_RETURN BG_BUTTON_D_LEFT
#define WIZARD_CYCLE 1
#else
#define MAP_PROBE BG_BUTTON_D_LEFT
#define MAP_RETURN BG_BUTTON_D_RIGHT
#endif
#ifdef WIZARD_CYCLE
/* Pause -> Setup -> Quit -> No, through normal physical button edges. */
#define RESUME_CHECK \
 {BG_FRONT_PLAY,4,1,BG_BUTTON_START},{BG_FRONT_PLAY,1,1,BG_BUTTON_D_DOWN}, \
 {BG_FRONT_PLAY,1,1,BG_BUTTON_A},{BG_FRONT_PLAY,1,1,BG_BUTTON_D_DOWN}, \
 {BG_FRONT_PLAY,1,1,BG_BUTTON_A},{BG_FRONT_QUIT,4,1,BG_BUTTON_A},
#else
#define RESUME_CHECK
#endif
typedef struct {bg_front_page page;unsigned seconds,ports;uint32_t buttons;} step;
static const step script[]={
 {BG_FRONT_MAIN,4,1,BG_BUTTON_D_UP},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_MAIN,2,1,BG_BUTTON_D_DOWN},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_MULTIPLAYER,4,1,BG_BUTTON_A},
 {BG_FRONT_JOIN,4,ALL,BG_BUTTON_START},
 {BG_FRONT_JOIN,3,ALL,BG_BUTTON_A},
 {BG_FRONT_JOIN,4,1,BG_BUTTON_A},
 {BG_FRONT_MAP,4,1,MAP_PROBE},{BG_FRONT_MAP,2,1,MAP_RETURN},
 {BG_FRONT_MAP,2,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,4,1,BG_BUTTON_D_RIGHT},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_D_LEFT},{BG_FRONT_TYPE,2,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,2,1,BG_BUTTON_C_LEFT},{BG_FRONT_PREGAME,2,1,BG_BUTTON_B},
 {BG_FRONT_ARMOR,2,1,BG_BUTTON_A},{BG_FRONT_PREGAME,2,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,6,1,BG_BUTTON_A},
#ifdef WIZARD_CYCLE
 /* Wizard -> Blood Gulch -> Wizard. Each match loads all eight first-person
  * meshes, survives quit/resume, and reaches its live 15-kill result. */
 {BG_FRONT_MAP,2,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,2,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,4,1,BG_BUTTON_A},
 {BG_FRONT_MAP,2,1,BG_BUTTON_D_RIGHT},{BG_FRONT_MAP,2,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,4,1,BG_BUTTON_A},
#endif
#ifdef BG_MAPS_CYCLE
 /* Existing Wizard/Blood/Wizard proof, then the three new maps. */
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,2,1,BG_BUTTON_A},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_RIGHT},{BG_FRONT_MAP,1,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,2,1,BG_BUTTON_A},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},
 {BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,1,1,BG_BUTTON_D_LEFT},
 {BG_FRONT_MAP,1,1,BG_BUTTON_A},{BG_FRONT_TYPE,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},{BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 RESUME_CHECK
 {BG_FRONT_RESULTS,2,1,BG_BUTTON_A},
#include "remaining_maps_cycle.h"
#endif
 {BG_FRONT_MAP,3,1,BG_BUTTON_B},
 {BG_FRONT_JOIN,2,1,BG_BUTTON_B},{BG_FRONT_JOIN,2,1,BG_BUTTON_B},
 {BG_FRONT_JOIN,2,1,BG_BUTTON_B},{BG_FRONT_MULTIPLAYER,3,1,BG_BUTTON_B},
 {BG_FRONT_MAIN,3,1,BG_BUTTON_D_DOWN},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_SETTINGS,3,1,BG_BUTTON_D_RIGHT},{BG_FRONT_SETTINGS,3,1,BG_BUTTON_A},
 {BG_FRONT_PROFILE,3,1,BG_BUTTON_A},{BG_FRONT_CONTROLS,3,1,BG_BUTTON_D_RIGHT},
 {BG_FRONT_CONTROLS,3,1,BG_BUTTON_B},{BG_FRONT_PROFILE,2,1,BG_BUTTON_B},
 {BG_FRONT_SETTINGS,2,1,BG_BUTTON_B},{BG_FRONT_MAIN,3,0,0}
};
#undef RESUME_CHECK
static unsigned current;static uint64_t entered;static bool complete;
#ifdef WIZARD_CYCLE
static bool quit_pending;
static unsigned resumed;
static bg_player saved_players[4];
#endif
unsigned bg_front_qa_step(void){return current;}
unsigned bg_front_qa_steps(void){return sizeof(script)/sizeof(script[0]);}
bool bg_front_qa_done(void){return complete;}
void bg_front_qa_resumed(void){
#ifdef WIZARD_CYCLE
    if(!quit_pending)return;
    /* Check at the resume boundary. A later input poll can legitimately
     * follow the first resumed simulation tick in the paced presenter. */
    for(unsigned p=0;p<4;p++){
        const bg_player*a=&saved_players[p],*b=&bg_players[p];
        assert(!memcmp(a->pos,b->pos,sizeof(a->pos))&&a->health==b->health&&
               a->shield==b->shield&&a->ammo==b->ammo&&a->score==b->score);
    }
    quit_pending=false;resumed++;
#endif
}
void bg_front_qa_input(const bg_frontend*f,bg_control_state raw[4],uint64_t now){
    memset(raw,0,4*sizeof(*raw));if(complete)return;
#ifdef WIZARD_CYCLE
    if(f->page==BG_FRONT_PLAY||f->page==BG_FRONT_QUIT){
        assert(bg_map_loaded()&&bg_map_id()==f->map);
        if(f->page==BG_FRONT_QUIT&&!quit_pending){
            memcpy(saved_players,bg_players,sizeof(saved_players));quit_pending=true;
        }
    }
    if(f->page==BG_FRONT_RESULTS)assert(!bg_map_loaded()&&bg_map_resident_bytes()==0);
#endif
    const step*s=&script[current];
    /* Every normal setup run now chooses armor between mode and countdown.
     * Keep existing map-cycle scripts focused on map/quit behavior, but drive
     * this page through production per-controller input too. */
    static uint64_t armor_entered, armor_selected;
    if (f->page!=BG_FRONT_ARMOR) armor_entered=armor_selected=0;
    if (f->page==BG_FRONT_ARMOR && s->page!=BG_FRONT_ARMOR) {
        if (!armor_entered) armor_entered=now;
        if (now-armor_entered<3000000) return;
        bool ready=true;
        for (unsigned p=0;p<4;p++) if(f->joined[p]) {
#if defined(BG_GUNGNIR_FRONTEND_QA)
            unsigned wanted=p==f->host?BG_ARMOR_GUNGNIR:(p+BG_ARMOR_COUNT-1)%BG_ARMOR_COUNT;
#elif defined(BG_ODST_FRONTEND_QA)
            unsigned wanted=BG_ARMOR_ODST;
#elif defined(BG_JORGE_FRONTEND_QA)
            unsigned wanted=BG_ARMOR_JORGE;
#else
            unsigned wanted=BG_ARMOR_SPARTAN;
#endif
            uint32_t button=0;
            if (f->armor[p]!=wanted) button=f->armor_ready[p]?BG_BUTTON_B:BG_BUTTON_D_RIGHT;
            else if (!f->armor_ready[p]) button=BG_BUTTON_A;
            if (button) {raw[p].held=raw[p].pressed=button;ready=false;}
        }
        if(ready) {
            if(!armor_selected) armor_selected=now;
            if(now-armor_selected>=8000000) raw[f->host].held=raw[f->host].pressed=BG_BUTTON_A;
        }
        return;
    }

#ifdef BG_ODST_FRONTEND_QA
    if(f->page==BG_FRONT_PREGAME || f->page==BG_FRONT_PLAY || f->page==BG_FRONT_RESULTS)
        assert(f->armor[f->host]==BG_ARMOR_ODST);
#endif
#ifdef BG_JORGE_FRONTEND_QA
    if(f->page==BG_FRONT_PREGAME || f->page==BG_FRONT_PLAY || f->page==BG_FRONT_RESULTS)
        assert(f->armor[f->host]==BG_ARMOR_JORGE);
#endif
#ifdef BG_GUNGNIR_FRONTEND_QA
    if(f->page==BG_FRONT_PREGAME || f->page==BG_FRONT_PLAY || f->page==BG_FRONT_RESULTS)
        assert(f->armor[f->host]==BG_ARMOR_GUNGNIR);
#endif
    if(f->page!=s->page){
        /* Countdown completion may beat a final optional acceleration edge.
         * Do not misdiagnose that ordinary launch as a map-loader failure. */
        if(s->page==BG_FRONT_PREGAME&&s->buttons==BG_BUTTON_A&&f->page==BG_FRONT_PLAY){
            current++;entered=0;return;
        }
        assert((s->page==BG_FRONT_RESULTS&&(f->page==BG_FRONT_PREGAME||f->page==BG_FRONT_PLAY))||
               (s->page==BG_FRONT_PLAY&&f->page==BG_FRONT_PREGAME));entered=0;return;
    }
    if(!entered)entered=now;
    unsigned dwell=s->seconds;
#if defined(BG_MAPS_CYCLE) || defined(BG_JORGE_FRONTEND_QA) || defined(BG_ODST_FRONTEND_QA) || defined(BG_GUNGNIR_FRONTEND_QA)
    if(s->page!=BG_FRONT_PLAY&&s->page!=BG_FRONT_QUIT&&dwell>1)dwell=1;
#endif
    if(now-entered<dwell*1000000ull)return;
    for(unsigned p=0;p<4;p++)if(s->ports&(1u<<p))raw[p].held=raw[p].pressed=s->buttons;
    if(s->page==BG_FRONT_RESULTS){assert(f->count==BG_FRONTEND_QA_PLAYERS&&f->final_scores[0]==15&&f->winner==0);}
    if(++current==sizeof(script)/sizeof(script[0])){
#ifdef WIZARD_CYCLE
        assert(resumed==
#ifdef BG_MAPS_CYCLE
 14
#else
 3
#endif
 &&!quit_pending);
#endif
        complete=true;current--;
    }
    entered=0;
}
#ifdef BG_STREAM_MAPS
static bool new_map_duel(bg_player*a,bg_player*b) {
    static unsigned selected=~0u;static float pair[2][3];
    unsigned id=bg_map_id();if(id==BG_MAP_BLOOD_GULCH||id==BG_MAP_WIZARD)return false;
    if(selected!=id){
        bool found=false;
        for(unsigned s=0;s<bg_spawn_count&&!found;s++)if(bg_slayer_spawns[s])for(unsigned d=0;d<4&&!found;d++){
            bg_player x=*a,y=*b;memcpy(x.pos,bg_spawns[s].pos,12);
            x.pos[1]=bg_floor(x.pos[0],x.pos[2],x.pos[1]+.5f)+.015f;memcpy(y.pos,x.pos,12);
            y.pos[d/2?2:0]+=(d&1)?-.8f:.8f;y.pos[1]=bg_floor(y.pos[0],y.pos[2],x.pos[1]+.5f)+.015f;
            if(fabsf(x.pos[1]-y.pos[1])>.05f||!bg_terrain_clearance(&x)||!bg_terrain_clearance(&y))continue;
            float origin[3]={x.pos[0],x.pos[1]+bg_eye_height(&x),x.pos[2]},dir[3];float length=0;
            for(unsigned k=0;k<3;k++){dir[k]=y.pos[k]-origin[k]+(k==1?.35f:0);length+=dir[k]*dir[k];}
            length=sqrtf(length);for(unsigned k=0;k<3;k++)dir[k]/=length;
            if(bg_world_raycast(origin,dir,length)<length-.01f)continue;
            memcpy(pair[0],x.pos,12);memcpy(pair[1],y.pos,12);found=true;
        }
        assert(found);selected=id;
    }
    memcpy(a->pos,pair[0],12);memcpy(b->pos,pair[1],12);
    float dx=b->pos[0]-a->pos[0],dz=b->pos[2]-a->pos[2];
    a->yaw=-atan2f(dz,dx);b->yaw=a->yaw+3.14159265f;
    a->pitch=atan2f(b->pos[1]+.35f-a->pos[1]-bg_eye_height(a),hypotf(dx,dz));
    return true;
}
#endif
#ifdef BG_GUNGNIR_FRONTEND_QA
static bool gungnir_live_inputs(bg_input in[4],float seconds) {
    static bool began,complete,follow_sent;static float entered,start[3],yaw,pitch;static int previous=-1,ammo;
    if(complete)return false;
    bg_player *a=&bg_players[0],*b=&bg_players[1];
    /* The host map suite also uses the ordinary combat fixture before its
     * frontend cycle has selected armor. Start this probe only in that cycle. */
    if(a->armor!=BG_ARMOR_GUNGNIR)return false;
    if(!began){
        assert(a->armor==BG_ARMOR_GUNGNIR);
        assert(bg_autonav_load());
        uint16_t source=bg_autonav_node(a->pos);assert(source!=BG_NAV_NONE);float origin[3];bg_autonav_position(source,origin);bool found=false;
        float saved_health[2]={bg_players[2].health,bg_players[3].health};bg_players[2].health=bg_players[3].health=0;
        for(unsigned k=0;k<8&&!found;k++){
            float angle=k*.78539816f,direction[3]={cosf(angle),0,sinf(angle)};uint16_t goal=bg_autonav_goal(origin,direction,4);
            if(goal==BG_NAV_NONE||goal==source)continue;
            memcpy(a->pos,origin,sizeof(origin));bg_autonav_position(goal,b->pos);float x=b->pos[0]-a->pos[0],z=b->pos[2]-a->pos[2];if(hypotf(x,z)<2)continue;
            a->yaw=atan2f(-z,x);a->pitch=atan2f(b->pos[1]+bg_body_height(b)*.7f-a->pos[1]-bg_eye_height(a),hypotf(x,z));found=bg_gungnir_target(0).player==1;
        }
        bg_players[2].health=saved_health[0];bg_players[3].health=saved_health[1];assert(found);
        a->vy=b->vy=0;a->grounded=b->grounded=true;memset(a->velocity,0,sizeof(a->velocity));memset(b->velocity,0,sizeof(b->velocity));memcpy(a->last_pos,a->pos,sizeof(a->pos));memcpy(b->last_pos,b->pos,sizeof(b->pos));
        bg_give_weapon(0,BG_W_AR);a->weapon=a->inventory[a->slot]=BG_W_AR;a->ammo=bg_weapon_defs[BG_W_AR].magazine;a->reload=a->weapon_ready=a->cooldown=0;
        memcpy(start,a->pos,sizeof(start));yaw=a->yaw;pitch=a->pitch;ammo=a->ammo;entered=seconds;began=true;
    }
    float time=seconds-entered;unsigned phase=(unsigned)(time/3);bool changed=(int)phase!=previous;
    if(changed){
        if(phase==0)in[0].flashlight=true;
        if(phase==1){float x=a->pos[0]-start[0],z=a->pos[2]-start[2];assert(x*x+z*z>.01f&&a->ammo==ammo&&a->yaw==yaw&&a->pitch==pitch);in[0].autopilot_command=4;}
        if(phase==2)in[0].autopilot_command=2;
        if(phase==3){in[0].autopilot_command=8;in[0].fire=true;}
        if(phase==4)in[0].flashlight=true;
        previous=(int)phase;
    }
    if(!phase&&a->autopilot_on&&!follow_sent){in[0].autopilot_command=1;follow_sent=true;}
    if(time>.3f&&phase==0)assert(a->autopilot_on&&a->autopilot_style==BG_AUTOPILOT_FOLLOW&&a->autopilot_follow==1);
    if(phase==4){in[0].forward=.35f;in[0].turn=.15f;if(time>12.2f)assert(!a->autopilot_on);}
    if(phase>=5){assert(!a->autopilot_on);complete=true;return false;}
    return true;
}
#endif
void bg_front_qa_tick(bg_input in[4],float seconds){
    memset(in,0,4*sizeof(*in));if(bg_match_finished()||seconds<2)return;
    /* Exercise both fenced workspaces for all four players, including the
     * largest Needler mesh, before completing the ordinary staged match. */
    if(seconds<12){
        unsigned weapon=((unsigned)seconds-2)%8;
        for(unsigned p=0;p<bg_player_count();p++)if(bg_players[p].weapon!=(int)weapon){
            bg_give_weapon(p,weapon);bg_players[p].weapon=bg_players[p].inventory[bg_players[p].slot]=weapon;
            bg_players[p].ammo=bg_weapon_defs[weapon].magazine;
        }
        return;
    }
#ifdef BG_GUNGNIR_FRONTEND_QA
    if(gungnir_live_inputs(in,seconds))return;
#endif
    bg_player*a=&bg_players[0],*b=&bg_players[1];
    if(b->health<=0)return;
    if(a->weapon!=BG_W_SHOTGUN||a->ammo==0)bg_give_weapon(0,BG_W_SHOTGUN);
    bool staged=false;
#ifdef BG_STREAM_MAPS
    staged=new_map_duel(a,b);
#endif
    if(!staged){
    float ceiling=100;
#ifdef BG_STREAM_MAPS
    if(bg_map_current()->id==BG_MAP_WIZARD)ceiling=-3;
#endif
    a->pos[0]=0;a->pos[2]=4;a->pos[1]=bg_floor(0,4,ceiling)+.015f;
    b->pos[0]=.8f;b->pos[2]=4;b->pos[1]=bg_floor(.8f,4,ceiling)+.015f;
    a->yaw=0;b->yaw=3.14159265f;a->pitch=atan2f(b->pos[1]+.35f-(a->pos[1]+.62f),.8f);
    }
    a->vy=b->vy=0;a->grounded=b->grounded=true;
    memcpy(a->last_pos,a->pos,sizeof(a->pos));memcpy(b->last_pos,b->pos,sizeof(b->pos));
    in[0].fire=!a->fire_held;
}
