#include "frontend_qa.h"
#include <assert.h>
#include <math.h>
#include <string.h>
/* Separately named fixture: controller edges navigate production menus.
 * Combat is staged, but health, damage, respawn, score limit and game-over
 * dispatch are the normal simulation. No scores/winner are assigned. */
#ifndef BG_FRONTEND_QA_PLAYERS
#define BG_FRONTEND_QA_PLAYERS 4
#endif
#define ALL (BG_FRONTEND_QA_PLAYERS==3?11:15)
typedef struct {bg_front_page page;unsigned seconds,ports;uint32_t buttons;} step;
static const step script[]={
 {BG_FRONT_MAIN,4,1,BG_BUTTON_D_UP},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_MAIN,2,1,BG_BUTTON_D_DOWN},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_MULTIPLAYER,4,1,BG_BUTTON_A},
 {BG_FRONT_JOIN,4,ALL,BG_BUTTON_START},{BG_FRONT_JOIN,3,ALL,BG_BUTTON_A},
 {BG_FRONT_JOIN,4,1,BG_BUTTON_A},
 {BG_FRONT_MAP,4,1,BG_BUTTON_D_RIGHT},{BG_FRONT_MAP,3,1,BG_BUTTON_A},
 {BG_FRONT_MAP,2,1,BG_BUTTON_D_LEFT},{BG_FRONT_MAP,2,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,4,1,BG_BUTTON_D_RIGHT},{BG_FRONT_TYPE,3,1,BG_BUTTON_A},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_D_LEFT},{BG_FRONT_TYPE,2,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,2,1,BG_BUTTON_C_LEFT},{BG_FRONT_PREGAME,2,1,BG_BUTTON_B},
 {BG_FRONT_TYPE,2,1,BG_BUTTON_A},{BG_FRONT_PREGAME,2,1,BG_BUTTON_A},
 {BG_FRONT_PREGAME,1,1,BG_BUTTON_A},
 {BG_FRONT_RESULTS,6,1,BG_BUTTON_A},{BG_FRONT_MAP,3,1,BG_BUTTON_B},
 {BG_FRONT_JOIN,2,1,BG_BUTTON_B},{BG_FRONT_JOIN,2,1,BG_BUTTON_B},
 {BG_FRONT_JOIN,2,1,BG_BUTTON_B},{BG_FRONT_MULTIPLAYER,3,1,BG_BUTTON_B},
 {BG_FRONT_MAIN,3,1,BG_BUTTON_D_DOWN},{BG_FRONT_MAIN,2,1,BG_BUTTON_A},
 {BG_FRONT_SETTINGS,3,1,BG_BUTTON_D_RIGHT},{BG_FRONT_SETTINGS,3,1,BG_BUTTON_A},
 {BG_FRONT_PROFILE,3,1,BG_BUTTON_A},{BG_FRONT_CONTROLS,3,1,BG_BUTTON_D_RIGHT},
 {BG_FRONT_CONTROLS,3,1,BG_BUTTON_B},{BG_FRONT_PROFILE,2,1,BG_BUTTON_B},
 {BG_FRONT_SETTINGS,2,1,BG_BUTTON_B},{BG_FRONT_MAIN,3,0,0}
};
static unsigned current;static uint64_t entered;static bool complete;
unsigned bg_front_qa_step(void){return current;}
unsigned bg_front_qa_steps(void){return sizeof(script)/sizeof(script[0]);}
bool bg_front_qa_done(void){return complete;}
void bg_front_qa_input(const bg_frontend*f,bg_control_state raw[4],uint64_t now){
    memset(raw,0,4*sizeof(*raw));if(complete)return;
    const step*s=&script[current];
    if(f->page!=s->page){
        assert(current==21&&(f->page==BG_FRONT_PREGAME||f->page==BG_FRONT_PLAY));entered=0;return;
    }
    if(!entered)entered=now;
    if(now-entered<s->seconds*1000000ull)return;
    for(unsigned p=0;p<4;p++)if(s->ports&(1u<<p))raw[p].held=raw[p].pressed=s->buttons;
    if(current==21){assert(f->count==BG_FRONTEND_QA_PLAYERS&&f->final_scores[0]==15&&f->winner==0);}
    if(++current==sizeof(script)/sizeof(script[0])){complete=true;current--;}
    entered=0;
}
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
    a->pos[0]=0;a->pos[2]=4;a->pos[1]=bg_floor(0,4,100)+.015f;
    b->pos[0]=.8f;b->pos[2]=4;b->pos[1]=bg_floor(.8f,4,100)+.015f;
    a->yaw=0;b->yaw=3.14159265f;a->pitch=atan2f(b->pos[1]+.35f-(a->pos[1]+.62f),.8f);
    a->vy=b->vy=0;a->grounded=b->grounded=true;
    memcpy(a->last_pos,a->pos,sizeof(a->pos));memcpy(b->last_pos,b->pos,sizeof(b->pos));
    in[0].fire=!a->fire_held;
}
