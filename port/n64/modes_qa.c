/* Native acceptance route: normal controller/menu transitions, then staged
 * positions and real firing/pickup/scoring. Never linked into a playable ROM. */
#include <libdragon.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "frontend_qa.h"
#include "mode_map.h"
#include "map.h"
#include "movement.h"
#include "terrain.h"
#ifdef BG_MODES_PREVIEW
static unsigned mode=BG_MODES_PREVIEW,completed;
#else
static unsigned mode,completed;
#endif
static bool hill_found;static unsigned hill_mode=~0u;static float hill_position[3];
static uint64_t edge,result_entered;
static bool result_seen,done;
unsigned bg_front_qa_step(void){return completed;}
unsigned bg_front_qa_steps(void){return BG_MODE_COUNT;}
bool bg_front_qa_done(void){return done;}
void bg_front_qa_resumed(void){}
void bg_front_qa_input(const bg_frontend *f,bg_control_state raw[4],uint64_t now){
    memset(raw,0,sizeof(*raw)*4);if(done)return;
    if(f->page==BG_FRONT_RESULTS&&!result_seen){
        assert(bg_match_finished()&&bg_match_winner()>=0);
        heap_stats_t heap;sys_get_heap_stats(&heap);
        debugf("MODE_QA PASS mode=%u name=%s winner=%d score=%d free=%u\n",mode,bg_current_rules()->name,bg_match_winner(),bg_display_score(bg_match_winner()),(unsigned)(heap.total-heap.used));
        result_seen=true;result_entered=now;completed++;
        if(completed==BG_MODE_COUNT){done=true;debugf("MODE_QA COMPLETE 26 presets\n");return;}
        mode++;
    }
    if(f->page!=BG_FRONT_RESULTS)result_seen=false;
    if(now-edge<350000)return;
    edge=now;
    unsigned p=f->host;uint32_t button=BG_BUTTON_A;
    switch(f->page){
    case BG_FRONT_MAIN:case BG_FRONT_MULTIPLAYER:break;
    case BG_FRONT_JOIN:
        for(p=0;p<4;p++)if(!f->joined[p]||!f->ready[p])break;
        if(p<4)button=f->joined[p]?BG_BUTTON_A:BG_BUTTON_START;else p=f->host;
        break;
    case BG_FRONT_MAP:if(f->map!=BG_MAP_WIZARD)button=BG_BUTTON_D_RIGHT;break;
    case BG_FRONT_TYPE:if(f->type!=mode)button=BG_BUTTON_D_RIGHT;break;
    case BG_FRONT_PREGAME:if(f->deadline<=now+1500000)return;break;
    case BG_FRONT_RESULTS:if(now-result_entered<2000000)return;break;
    default:return;
    }
    raw[p].held=raw[p].pressed=button;
}
static void place(unsigned p,const float pos[3]){
    bg_player *q=&bg_players[p];memcpy(q->pos,pos,12);q->vehicle=-1;q->seat=-1;
    q->pos[1]=bg_floor(q->pos[0],q->pos[2],q->pos[1]+.7f)+.015f;
    memset(q->velocity,0,12);memcpy(q->last_pos,q->pos,12);q->grounded=true;
}
static void duel(unsigned victim,bg_input in[4]){
    bg_player *a=&bg_players[0],*b=&bg_players[victim];
    if(b->health<=0)return;
    /* Wizard's tested centre duel, used by the existing native map route. */
    float pos[3]={0,-3,4};place(0,pos);pos[0]+=.8f;place(victim,pos);
    a->yaw=0;b->yaw=3.14159265f;a->pitch=atan2f(b->pos[1]+.35f-a->pos[1]-bg_eye_height(a),.8f);
    if(a->weapon!=BG_W_SHOTGUN||a->ammo==0)bg_give_weapon(0,BG_W_SHOTGUN);
    a->weapon_ready=0;in[0].fire=!a->fire_held;
}
void bg_front_qa_tick(bg_input in[4],float seconds){
    memset(in,0,4*sizeof(*in));if(bg_match_finished())return;
    const bg_mode_rules *r=bg_current_rules();
    if(seconds<3)return;
#ifdef BG_MODES_PREVIEW
    bg_set_score_limit(100000);
#else
    bg_set_score_limit(1);
#endif
    for(unsigned p=1;p<4;p++)if(!bg_players_allied(0,p)&&bg_players[p].health>0){
        /* Keep observers away from the staged objective. */
        const bg_mode_map *map=bg_current_mode_map();
        const float *pos=map?map->spawn_positions[p*3]:bg_spawns[p*3].pos;place(p,pos);
    }
    if(r->engine==BG_ENGINE_CTF){
        int carried=bg_player_objective(0);
        const bg_objective *enemy=NULL,*home=NULL;
        for(unsigned i=0;i<bg_objective_count;i++){
            if(bg_objectives[i].team==(int)bg_player_team(0))home=&bg_objectives[i];else enemy=&bg_objectives[i];
        }
        if(carried<0)place(0,enemy->pos);else if(seconds>7) {
#ifndef BG_MODES_PREVIEW
            place(0,home->home);
#else
            (void)home;
#endif
        }
    }else if(r->engine==BG_ENGINE_KING){
        if(hill_mode!=mode){
            float lo[3]={1e9,1e9,1e9},hi[3]={-1e9,-1e9,-1e9},point[3];unsigned count=0;
            while(bg_mode_hill_point(count++,point))for(unsigned a=0;a<3;a++){lo[a]=fminf(lo[a],point[a]);hi[a]=fmaxf(hi[a],point[a]);}
            hill_found=false;
            for(float x=lo[0];x<=hi[0]&&!hill_found;x+=.125f)for(float z=lo[2];z<=hi[2]&&!hill_found;z+=.125f){
                float pos[3]={x,hi[1],z};place(0,pos);
                if(bg_player_in_hill(0)&&bg_terrain_clearance(&bg_players[0])){memcpy(hill_position,bg_players[0].pos,12);hill_found=true;}
            }
            assertf(hill_found,"No playable hill in QA map");hill_mode=mode;
        }
        place(0,hill_position);
    }else if(r->engine==BG_ENGINE_RACE){
        for(unsigned p=0;p<4;p++)if(p==0||bg_players_allied(0,p)){
            float pos[3];unsigned kind,team;
            if(bg_mode_navpoint(p,0,pos,&kind,&team))place(p,pos);
        }
    }else if(r->engine==BG_ENGINE_BALL&&!r->ball_type){
        if(bg_objective_count&&bg_objectives[0].active&&bg_objectives[0].owner<0)place(0,bg_objectives[0].pos);
    }else{
        int target=bg_player_target(0);
        if(target<0)for(unsigned p=1;p<4;p++)if(!bg_players_allied(0,p)&&!bg_player_eliminated(p)){target=p;break;}
        if(target>=0)duel(target,in);
    }
#ifdef BG_MODES_PREVIEW
    if(bg_player_objective(0)>=0){
        float photo[3]={0,-3,4};place(0,photo);photo[0]+=1.6f;place(1,photo);
        bg_players[0].yaw=0;bg_players[1].yaw=3.14159265f;
        bg_players[0].pitch=bg_players[1].pitch=0;
        bg_players[0].gait=bg_players[1].gait=0;
    }
#else
    assertf(seconds<100,"Mode acceptance timed out: %u %s",mode,r->name);
#endif
}
