/* Autopilot supplies only the ordinary biped movement inputs. Camera and all
 * weapon/service inputs continue through the human's production controls. */
#include "gungnir.h"
#include "autopilot_nav.h"
#include "autopilot_strategy.h"
#include "combat_geometry.h"
#include "camouflage.h"
#include <math.h>
#include <string.h>
static struct {
    float decision,seen,previous[3],last_seen[3],vitality,stuck,wander;
    int target;uint32_t random;uint16_t goal;bool move;
} pilots[BG_PLAYERS];
static float distance2(const float *a,const float *b){float x=a[0]-b[0],y=a[1]-b[1],z=a[2]-b[2];return x*x+y*y+z*z;}
static bool line(unsigned owner,unsigned target){
    const bg_player *p=&bg_players[owner],*q=&bg_players[target];float o[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]},d[3]={q->pos[0]-o[0],q->pos[1]+bg_body_height(q)*.7f-o[1],q->pos[2]-o[2]};float length=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);if(length<.01f)return true;
    for(unsigned a=0;a<3;a++)d[a]/=length;
    if(bg_raycast(o,d,length)<length-.02f)return false;
    for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicle_body_present(&bg_vehicles[v])&&bg_vehicle_hit_ray(&bg_vehicles[v],o,d,length)<length-.02f)return false;
    return true;
}
static int looked_at(unsigned owner){
    const bg_player *p=&bg_players[owner];float cp=cosf(p->pitch),forward[3]={cosf(p->yaw)*cp,sinf(p->pitch),-sinf(p->yaw)*cp},best=.96f;int result=-1;
    for(unsigned q=0;q<bg_player_count();q++)if(q!=owner&&bg_players[q].health>0&&bg_player_visibility(&bg_players[q])>0){float d[3]={bg_players[q].pos[0]-p->pos[0],bg_players[q].pos[1]+bg_body_height(&bg_players[q])*.7f-p->pos[1]-bg_eye_height(p),bg_players[q].pos[2]-p->pos[2]},length=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);if(length<.01f)continue;
    float cosine=(d[0]*forward[0]+d[1]*forward[1]+d[2]*forward[2])/length;if(cosine>best&&line(owner,q)){best=cosine;result=q;}}
    return result;
}
void bg_gungnir_reset(unsigned p){
    if(p>=BG_PLAYERS)return;
    memset(&pilots[p],0,sizeof(pilots[p]));pilots[p].target=-1;pilots[p].random=0x676e6972u+p*7919;pilots[p].goal=BG_NAV_NONE;
    bg_players[p].autopilot_on=false;bg_players[p].autopilot_style=BG_AUTOPILOT_ELITE;bg_players[p].autopilot_follow=-1;bg_players[p].autopilot_side=1;bg_autopilot_strategy_reset(p);bg_autonav_cancel(p);
}
void bg_gungnir_toggle(unsigned p){
    if(p>=BG_PLAYERS)return;
    bg_player *player=&bg_players[p];player->autopilot_on=!player->autopilot_on;player->flashlight_on=false;pilots[p].decision=0;pilots[p].vitality=player->health+player->shield;pilots[p].stuck=0;memcpy(pilots[p].previous,player->pos,12);bg_autonav_cancel(p);
    if(player->autopilot_on)bg_autonav_load();
}
const char *bg_gungnir_status(unsigned p){
    if(p>=BG_PLAYERS||!bg_players[p].autopilot_on)return "AUTO OFF";
    if(bg_players[p].vehicle>=0)return "AUTO PAUSED";
    if(!bg_autonav_memory())return "AUTO WAITING";
    switch(bg_players[p].autopilot_style){case BG_AUTOPILOT_FOLLOW:return bg_players[p].autopilot_follow<0?"AUTO FOLLOW: AIM + UP":"AUTO FOLLOW";case BG_AUTOPILOT_PANIC:return "AUTO PANIC";default:return "AUTO ELITE";}
}
static uint32_t random_next(unsigned p){uint32_t x=pilots[p].random;x^=x<<13;x^=x>>17;x^=x<<5;return pilots[p].random=x;}
static void decide(unsigned p){
    bg_player *player=&bg_players[p];bool panic=player->autopilot_style==BG_AUTOPILOT_PANIC,visible=false,danger=false;int nearest=-1;float closest=40*40;
    for(unsigned q=0;q<bg_unit_count();q++)if(bg_players[q].health>0&&!bg_players_allied(p,q)&&bg_player_visibility(&bg_players[q])>0){float d=distance2(player->pos,bg_players[q].pos);if(d<closest&&line(p,q)){closest=d;nearest=q;}}
    if(nearest>=0){pilots[p].target=nearest;pilots[p].seen=8;memcpy(pilots[p].last_seen,bg_players[nearest].pos,12);visible=true;}
    else if(pilots[p].seen<=0)pilots[p].target=-1;
    float threat[3];memcpy(threat,pilots[p].last_seen,12);
    for(unsigned q=0;q<BG_MAX_PROJECTILES;q++){bg_projectile *shot=bg_projectile_at(q);if(shot&&shot->active&&shot->owner!=(int)p&&(shot->kind==BG_P_ROCKET||shot->kind==BG_P_FRAG||shot->kind==BG_P_PLASMA_GRENADE||shot->kind==BG_P_CANNON||shot->kind==BG_P_FUEL||shot->kind==BG_P_GRUNT_FUEL)&&distance2(player->pos,shot->pos)<9){danger=true;memcpy(threat,shot->pos,12);break;}}
    float vitality=player->health+player->shield,damage=fmaxf(0,pilots[p].vitality-vitality)/100;pilots[p].vitality=vitality;
    bg_autopilot_strategy strategy=bg_autopilot_decide(p,panic,visible,pilots[p].target>=0,danger,damage);
    uint16_t start=bg_autonav_node(player->pos),goal=BG_NAV_NONE;pilots[p].move=false;
    if(player->autopilot_style==BG_AUTOPILOT_FOLLOW){
        int q=player->autopilot_follow;if(q>=0&&q<(int)bg_player_count()&&bg_players[q].health>0&&distance2(player->pos,bg_players[q].pos)>1.1f*1.1f)goal=bg_autonav_node(bg_players[q].pos);
    }else if((panic||strategy.retreat||strategy.evade)&&(pilots[p].target>=0||danger)){
        float away[3]={player->pos[0]-threat[0],0,player->pos[2]-threat[2]},length=hypotf(away[0],away[2]);if(length<.01f){away[0]=player->autopilot_side;length=1;}away[0]/=length;away[2]/=length;goal=bg_autonav_goal(player->pos,away,panic?7:5);
    }else if(pilots[p].target>=0){
        float distance=sqrtf(distance2(player->pos,pilots[p].last_seen));if(!visible||distance>strategy.far_range||(strategy.charge&&distance>1.4f))goal=bg_autonav_node(pilots[p].last_seen);
    }else if(pilots[p].wander<=0||pilots[p].goal==BG_NAV_NONE){
        float angle=(random_next(p)%6284)/1000.f,direction[3]={cosf(angle),0,sinf(angle)};goal=bg_autonav_goal(player->pos,direction,panic?5:9);pilots[p].wander=panic?1.2f:3;
    }else goal=pilots[p].goal;
    if(goal!=BG_NAV_NONE&&goal!=start){pilots[p].goal=goal;pilots[p].move=true;bg_autonav_request(p,start,goal);}else{pilots[p].goal=BG_NAV_NONE;bg_autonav_cancel(p);}
}
void bg_gungnir_move(unsigned p,bg_input *input,float dt){
    bg_player *player=&bg_players[p];if(!(bg_armor_def(player->armor)->abilities&BG_ARMOR_AUTOPILOT)||!player->autopilot_on||player->health<=0)return;
    if(input->autopilot_command){
        bg_autonav_cancel(p);bg_autopilot_strategy_reset(p);pilots[p].decision=0;pilots[p].goal=BG_NAV_NONE;
        if(input->autopilot_command&1){player->autopilot_style=BG_AUTOPILOT_FOLLOW;player->autopilot_follow=looked_at(p);}
        else if(input->autopilot_command&2)player->autopilot_style=BG_AUTOPILOT_PANIC;
        else{player->autopilot_style=BG_AUTOPILOT_ELITE;player->autopilot_side=(input->autopilot_command&4)?-1:1;}
    }
    /* Vehicle controls stay manual; the selected on-foot mode resumes after
     * exit. No movement planner can activate a vehicle or weapon service. */
    if(player->vehicle>=0)return;
    input->forward=input->strafe=0;input->jump=input->crouch=false;
    pilots[p].decision-=dt;pilots[p].seen=fmaxf(0,pilots[p].seen-dt);pilots[p].wander-=dt;
    if(pilots[p].decision<=0){decide(p);pilots[p].decision+=.2f;}
    float waypoint[3];bool jump=false;
    if(pilots[p].move&&bg_autonav_waypoint(p,player->pos,waypoint,&jump)){
        float x=waypoint[0]-player->pos[0],z=waypoint[2]-player->pos[2],length=hypotf(x,z);
        if(length>.025f){
            x/=length;z/=length;
            /* Brake for corners instead of cutting a capsule-certified edge
             * with full-speed inertia. The ordinary acceleration still owns
             * velocity; this only scales the requested input. */
            float speed=fminf(1.f,fmaxf(.15f,sqrtf(fmaxf(0,length-.025f)*bg_movement.accel[0])*.35f));
            float along=player->velocity[0]*x+player->velocity[2]*z,side=fabsf(player->velocity[0]*z-player->velocity[2]*x);
            if(side>fmaxf(.3f,along))speed*=.55f;
            input->forward=(x*cosf(player->yaw)-z*sinf(player->yaw))*speed;input->strafe=(x*sinf(player->yaw)+z*cosf(player->yaw))*speed;input->jump=jump&&player->grounded;
        }
        if(distance2(player->pos,pilots[p].previous)<.0001f)pilots[p].stuck+=dt;else pilots[p].stuck=0;
        if(pilots[p].stuck>1){bg_autonav_cancel(p);pilots[p].decision=0;pilots[p].wander=0;pilots[p].goal=BG_NAV_NONE;pilots[p].stuck=0;}
    }
    memcpy(pilots[p].previous,player->pos,12);
}
