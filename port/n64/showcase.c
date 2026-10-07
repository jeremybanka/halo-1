#include "showcase.h"
#include <math.h>
#include <string.h>

#define PI 3.14159265358979323846f
static bg_showcase_kind scenario;
static bg_showcase_stats stats;
static float now,previous_position[3],needle_direction[3];
static bool previous_valid,needle_valid,frag_thrown;
static unsigned shots_requested;
static int vehicle_index,tracked_needle;
static float clamp(float x,float lo,float hi){return x<lo?lo:x>hi?hi:x;}
static float angle_delta(float target,float current){float d=fmodf(target-current+PI,2*PI);if(d<0)d+=2*PI;return d-PI;}
static float floor_at(float x,float z){float y=bg_floor(x,z,100);return y>-999?y:0;}
static void place(unsigned p,float x,float z,float yaw){
    bg_player*q=&bg_players[p];q->pos[0]=x;q->pos[1]=floor_at(x,z)+.015f;q->pos[2]=z;
    q->yaw=yaw;q->pitch=0;q->vy=0;q->grounded=true;memcpy(q->last_pos,q->pos,sizeof(q->pos));
}
static void face(unsigned p,float x,float y,float z){
    bg_player*q=&bg_players[p];float dx=x-q->pos[0],dz=z-q->pos[2];
    q->yaw=atan2f(-dz,dx);q->pitch=atan2f(y-(q->pos[1]+.62f),sqrtf(dx*dx+dz*dz));
}
static void steer_aim(bg_input*in,unsigned p,float x,float y,float z){
    bg_player*q=&bg_players[p];float dx=x-q->pos[0],dz=z-q->pos[2];
    float yaw=atan2f(-dz,dx),pitch=atan2f(y-(q->pos[1]+.62f),sqrtf(dx*dx+dz*dz));
    in->turn=clamp(angle_delta(yaw,q->yaw)*4,-1,1);in->look=clamp((pitch-q->pitch)*4,-1,1);
}
static void setup_vehicle(bg_vehicle_kind kind){
    float pos[3]={-6,floor_at(-6,4)+.03f,4};vehicle_index=bg_add_vehicle(kind,pos,0);
    bg_vehicle*v=&bg_vehicles[vehicle_index];float entry[3];
    bg_vehicle_seat_position(v,0,true,entry);place(0,entry[0],entry[2],0);
    if(scenario==BG_SHOWCASE_WARTHOG_PASSENGER){
        bg_vehicle_seat_position(v,2,true,entry);place(1,entry[0],entry[2],0);
    }
}
void bg_showcase_begin(bg_showcase_kind kind){
    scenario=kind<BG_SHOWCASE_COUNT?kind:BG_SHOWCASE_BANSHEE;
    memset(&stats,0,sizeof(stats));shots_requested=0;now=0;
    previous_valid=needle_valid=frag_thrown=false;vehicle_index=tracked_needle=-1;
    bg_reset();bg_set_players(scenario==BG_SHOWCASE_BANSHEE?1:scenario==BG_SHOWCASE_FRAG_DOUBLE_KILL?4:2);
    /* Each recorded scene begins with ordinary full-health players and a
     * deliberately arranged local encounter. All subsequent motion, damage,
     * boarding and deaths run through the same live simulation. */
    bg_vehicle_count=bg_pickup_count=0;
    for(unsigned p=0;p<4;p++)place(p,-10-p*2,8,0);
    if(scenario==BG_SHOWCASE_BANSHEE||scenario==BG_SHOWCASE_WARTHOG_PASSENGER){
        setup_vehicle(scenario==BG_SHOWCASE_BANSHEE?BG_V_BANSHEE:BG_V_WARTHOG);
    }else if(scenario==BG_SHOWCASE_FRAG_DOUBLE_KILL){
        place(0,-4,4,0);
#ifdef BG_BLAM_BSP
        /* The original central terrain bank gives this throw a longer first
         * bounce than the reduced mesh. Stage both full-shield targets around
         * its actual landing; grenade physics and damage remain live. */
        place(1,2.61144f,3.8f,PI);place(2,2.61144f,4.2f,PI);
#else
        place(1,2.295127f,3.77f,PI);place(2,2.295127f,4.23f,PI);
#endif
        place(3,2.3f,7.2f,PI/2);face(3,2.295127f,.45f,4);
    }else if(scenario==BG_SHOWCASE_SHOTGUN_KILL){
        place(0,0,4,0);place(1,.8f,4,PI);bg_give_weapon(0,BG_W_SHOTGUN);
        face(0,bg_players[1].pos[0],bg_players[1].pos[1]+.35f,bg_players[1].pos[2]);
    }else if(scenario==BG_SHOWCASE_NEEDLER_SUPERCOMBINE){
        place(0,-1.5f,4,0);place(1,1.5f,4,PI);bg_give_weapon(0,BG_W_NEEDLER);
        face(0,bg_players[1].pos[0],bg_players[1].pos[1]+.4f,bg_players[1].pos[2]);
    }else{
        place(0,-4,4,0);place(1,2.5f,4,PI);bg_give_weapon(0,BG_W_NEEDLER);
        face(0,bg_players[1].pos[0],bg_players[1].pos[1]+.4f,bg_players[1].pos[2]);
    }
    bg_clear_events();
}
void bg_showcase_input(bg_input input[BG_PLAYERS],float seconds){
    memset(input,0,sizeof(bg_input)*BG_PLAYERS);now=seconds;
    if(scenario==BG_SHOWCASE_BANSHEE){
        if(seconds>=2&&bg_players[0].vehicle<0){input[0].interact=true;return;}
        if(bg_players[0].vehicle>=0&&seconds>=3&&seconds<20){
            bg_vehicle*v=&bg_vehicles[bg_players[0].vehicle];float altitude=v->pos[1]-floor_at(v->pos[0],v->pos[2]);
            input[0].forward=.7f;input[0].turn=.28f;
            float pitch=clamp((4-altitude)*.25f-.26f,-.65f,.45f);
            input[0].look=clamp((pitch-bg_players[0].pitch)*2,-1,1);input[0].fire=seconds>9&&seconds<10;
        }
    }else if(scenario==BG_SHOWCASE_WARTHOG_PASSENGER){
        for(unsigned p=0;p<2;p++)if(seconds>=2&&bg_players[p].vehicle<0)input[p].interact=true;
        if(bg_players[0].vehicle>=0&&seconds>=3&&seconds<20){input[0].forward=.45f;input[0].turn=.5f;}
        if(bg_players[1].vehicle>=0&&seconds>7&&seconds<9){input[1].turn=.3f;input[1].fire=true;}
    }else if(scenario==BG_SHOWCASE_FRAG_DOUBLE_KILL){
        if(seconds>=2&&!frag_thrown){input[0].grenade=true;frag_thrown=true;}
    }else if(scenario==BG_SHOWCASE_SHOTGUN_KILL){
        if(stats.kills==0&&seconds>=2+shots_requested*1.3f&&shots_requested<4){input[0].fire=true;shots_requested++;}
    }else if(scenario==BG_SHOWCASE_NEEDLER_SUPERCOMBINE){
        input[0].fire=seconds>=2&&seconds<5&&stats.supercombines==0;
    }else{
        if(seconds>=2&&shots_requested==0){input[0].fire=true;shots_requested++;}
        if(seconds>=2.4f&&seconds<2.72f)input[1].strafe=-1;
        /* The shooter follows the moving target with the camera after the
         * launch; this cannot affect a projectile that is already in flight. */
        if(seconds>2.4f)steer_aim(&input[0],0,bg_players[1].pos[0],bg_players[1].pos[1]+.4f,bg_players[1].pos[2]);
    }
}
void bg_showcase_observe(void){
    for(unsigned e=0;e<bg_event_count;e++){
        bg_event*v=&bg_events[e];
        if(v->kind==BG_EVENT_FIRE&&v->player==0)stats.shots++;
        if(v->kind==BG_EVENT_DIE&&v->player!=0)stats.kills++;
        if(v->kind==BG_EVENT_GRENADE&&v->player==0)stats.grenades++;
        if(v->kind==BG_EVENT_ENTER)stats.boardings++;
        if(v->kind==BG_EVENT_DOUBLE_KILL&&v->player==0)stats.double_kills++;
        if(v->kind==BG_EVENT_SUPERCOMBINE&&v->player==0)stats.supercombines++;
        if(v->kind==BG_EVENT_NEEDLE_HIT&&v->player==0)stats.needle_hits++;
    }
    if(vehicle_index>=0){
        bg_vehicle*v=&bg_vehicles[vehicle_index];
        if(v->active){
            if(previous_valid){float d=0;for(unsigned a=0;a<3;a++){float x=v->pos[a]-previous_position[a];d+=x*x;}stats.traveled+=sqrtf(d);}
            memcpy(previous_position,v->pos,sizeof(previous_position));previous_valid=true;
            float altitude=v->pos[1]-floor_at(v->pos[0],v->pos[2]);stats.maximum_altitude=fmaxf(stats.maximum_altitude,altitude);
            if(altitude>1)stats.airborne_frames++;
        }
        if(bg_players[0].vehicle==vehicle_index&&bg_players[0].seat==0)stats.driver_frames++;
        if(bg_players[1].vehicle==vehicle_index&&bg_players[1].seat==2&&v->occupants[1]==-1)stats.passenger_frames++;
    }
    if(scenario==BG_SHOWCASE_NEEDLER_HOMING){
        if(tracked_needle<0)for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
            const bg_projectile*q=bg_projectile_at(i);
            if(q&&q->active&&q->kind==BG_P_NEEDLE&&q->owner==0){tracked_needle=i;break;}
        }
        const bg_projectile*needle=tracked_needle>=0?bg_projectile_at(tracked_needle):NULL;
        if(needle&&needle->active){
            float d[3];memcpy(d,needle->velocity,sizeof(d));float length=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);
            if(length>.001f){for(unsigned a=0;a<3;a++)d[a]/=length;
                if(!needle_valid){memcpy(needle_direction,d,sizeof(d));needle_valid=true;}
                float dot=d[0]*needle_direction[0]+d[1]*needle_direction[1]+d[2]*needle_direction[2];
                stats.maximum_homing_turn=fmaxf(stats.maximum_homing_turn,acosf(clamp(dot,-1,1)));}
        }
    }
    switch(scenario){
        case BG_SHOWCASE_BANSHEE:stats.passed=stats.airborne_frames>200&&stats.traveled>30&&stats.maximum_altitude>2.5f;break;
        case BG_SHOWCASE_FRAG_DOUBLE_KILL:stats.passed=stats.grenades==1&&stats.kills==2&&stats.double_kills==1&&bg_players[0].score==2;break;
        case BG_SHOWCASE_WARTHOG_PASSENGER:stats.passed=stats.driver_frames>150&&stats.passenger_frames>150&&stats.traveled>10;break;
        case BG_SHOWCASE_SHOTGUN_KILL:stats.passed=stats.kills>=1&&bg_players[0].score>=1;break;
        case BG_SHOWCASE_NEEDLER_SUPERCOMBINE:stats.passed=stats.supercombines>=1&&stats.kills>=1&&bg_players[0].score>=1;break;
        case BG_SHOWCASE_NEEDLER_HOMING:stats.passed=stats.needle_hits>=1&&stats.maximum_homing_turn>.1f;break;
        default:break;
    }
}
unsigned bg_showcase_views(void){return scenario==BG_SHOWCASE_BANSHEE?1:scenario==BG_SHOWCASE_FRAG_DOUBLE_KILL?4:2;}
float bg_showcase_duration(void){return scenario==BG_SHOWCASE_BANSHEE||scenario==BG_SHOWCASE_WARTHOG_PASSENGER?24:scenario==BG_SHOWCASE_NEEDLER_HOMING?18:16;}
const char*bg_showcase_title(void){
    static const char*names[BG_SHOWCASE_COUNT]={"BANSHEE FLIGHT","FRAG DOUBLE KILL","RIDING SHOTGUN","SHOTGUN KILL","NEEDLER SUPERCOMBINE","NEEDLE HOMING"};return names[scenario];
}
const char*bg_showcase_caption(void){
    if(stats.passed){static const char*results[BG_SHOWCASE_COUNT]={"BANSHEE AIRBORNE","FRAG DOUBLE KILL CONFIRMED","DRIVER + FRONT PASSENGER","SHOTGUN KILL CONFIRMED","SUPERCOMBINE KILL CONFIRMED","CURVED NEEDLE HIT CONFIRMED"};return results[scenario];}
    if(scenario==BG_SHOWCASE_BANSHEE)return stats.driver_frames?"CLIMBING / FLYING":"BOARDING BANSHEE";
    if(scenario==BG_SHOWCASE_WARTHOG_PASSENGER)return stats.passenger_frames?"FRONT PASSENGER / GUNNER EMPTY":"BOARDING FRONT SEATS";
    if(scenario==BG_SHOWCASE_FRAG_DOUBLE_KILL)return stats.grenades?"ONE LIVE FRAG GRENADE":"TWO FULL-SHIELD TARGETS";
    if(scenario==BG_SHOWCASE_NEEDLER_HOMING)return stats.shots?"ONE NEEDLE / MOVING TARGET":"FULL-SHIELD MOVING TARGET";
    return now<2?"FULL SHIELDS / LIVE DAMAGE":"LIVE WEAPON FIRE";
}
const bg_showcase_stats*bg_showcase_telemetry(void){return &stats;}
