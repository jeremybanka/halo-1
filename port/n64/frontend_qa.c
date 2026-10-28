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
 {BG_FRONT_JOIN,4,ALL,BG_BUTTON_START},{BG_FRONT_JOIN,3,ALL,BG_BUTTON_A},
 {BG_FRONT_JOIN,4,1,BG_BUTTON_A},
 {BG_FRONT_MAP,4,1,MAP_PROBE},{BG_FRONT_MAP,2,1,MAP_RETURN},
 {BG_FRONT_MAP,2,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,4,1,BG_BUTTON_D_RIGHT},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_D_LEFT},{BG_FRONT_TYPE,2,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,2,1,BG_BUTTON_C_LEFT},{BG_FRONT_PREGAME,2,1,BG_BUTTON_B},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_A},{BG_FRONT_PREGAME,2,1,BG_BUTTON_A},
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
#ifdef BG_MAPS_CYCLE
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
