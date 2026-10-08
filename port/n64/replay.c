#include "replay.h"
#include <math.h>
#include <string.h>

#define REPLAY_PI 3.14159265358979323846f
#define REPLAY_DURATION 75.f
static int cycle=-1,phase=-1,loadout=-1;
static int was_alive[BG_PLAYERS],vehicle_for[BG_PLAYERS];
static unsigned frame;
static float previous_time=-1;
static const float center[2]={0,4};
static float clamp(float v,float lo,float hi){return v<lo?lo:v>hi?hi:v;}
static float angle_delta(float target,float current){
    float d=fmodf(target-current+REPLAY_PI,2*REPLAY_PI);
    if(d<0)d+=2*REPLAY_PI;
    return d-REPLAY_PI;
}
static float ground(float x,float z){float y=bg_floor(x,z,100);return y>-999?y+.015f:0;}
static void place_player(unsigned p,float x,float z){
    bg_player*q=&bg_players[p];q->pos[0]=x;q->pos[2]=z;q->pos[1]=ground(x,z);
    q->vy=0;q->grounded=true;q->pitch=0;
    q->yaw=atan2f(-(center[1]-z),center[0]-x);
    memcpy(q->last_pos,q->pos,sizeof(q->pos));
}
static void arena_spawn(unsigned p){
    const float positions[4][2]={{-1.9f,2.1f},{1.9f,2.1f},{1.9f,5.9f},{-1.9f,5.9f}};
    place_player(p,positions[p][0],positions[p][1]);
}
static int requested_weapon(unsigned p,int segment){return (segment+(int)p*2)%8;}
static void equip(unsigned p,int weapon,bg_input*in){
    bg_give_weapon(p,weapon);
    /* Existing inventory weapons receive ammunition without changing the
     * active slot. Use the same switch action available to a human player. */
    if(bg_players[p].weapon!=weapon)in->switch_weapon=true;
}
static void start_vehicles(void){
    const float locations[4][2]={{-5,4},{5,4},{0,-1},{0,9}};
    const float yaw[4]={0,REPLAY_PI,-REPLAY_PI/2,REPLAY_PI/2};
    for(unsigned p=0;p<4;p++){
        vehicle_for[p]=-1;
        for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].kind==(int)p&&bg_vehicles[i].active){vehicle_for[p]=i;break;}
        if(vehicle_for[p]<0)continue;
        bg_vehicle*v=&bg_vehicles[vehicle_for[p]];
        v->pos[0]=locations[p][0];v->pos[2]=locations[p][1];v->pos[1]=ground(v->pos[0],v->pos[2])+(p==BG_V_GHOST?.18f:0);
        v->yaw=yaw[p];v->pitch=v->speed=0;v->physics_valid=false;memset(v->angular_velocity,0,sizeof(v->angular_velocity));memset(v->velocity,0,sizeof(v->velocity));
        memcpy(v->home,v->pos,sizeof(v->home));v->home_yaw=v->yaw;
        if(bg_players[p].health>0){
            float entry[3];bg_vehicle_seat_position(v,0,true,entry);
            place_player(p,entry[0],entry[2]);bg_players[p].interact_cooldown=0;
        }
    }
}
static void aim_at(bg_player*q,bg_input*in,float x,float y,float z){
    float dx=x-q->pos[0],dz=z-q->pos[2],horizontal=sqrtf(dx*dx+dz*dz);
    float wanted_yaw=atan2f(-dz,dx),wanted_pitch=atan2f(y-(q->pos[1]+.62f),horizontal);
    float scale=q->zoom?(q->zoom==2?.15f:.35f):1;
    in->turn=clamp(angle_delta(wanted_yaw,q->yaw)/(2.25f*scale*.16f),-1,1);
    in->look=clamp((wanted_pitch-q->pitch)/(1.35f*scale*.16f),-1,1);
}
static void combat_input(bg_input input[BG_PLAYERS],float t,int segment){
    float within=t-segment*8;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];bg_input*in=&input[p];if(q->health<=0)continue;
        unsigned target=(p+1)%4;float nearest=100000;
        for(unsigned j=0;j<4;j++)if(j!=p&&bg_players[j].health>0){
            float dx=q->pos[0]-bg_players[j].pos[0],dz=q->pos[2]-bg_players[j].pos[2],d=dx*dx+dz*dz;
            if(d<nearest){nearest=d;target=j;}}
        bg_player*v=&bg_players[target];
        aim_at(q,in,v->pos[0],v->pos[1]+.5f,v->pos[2]);
        float dx=v->pos[0]-q->pos[0],dz=v->pos[2]-q->pos[2];
        float error=fabsf(angle_delta(atan2f(-dz,dx),q->yaw));
        float radius2=q->pos[0]*q->pos[0]+(q->pos[2]-center[1])*(q->pos[2]-center[1]);
        if(radius2>25){aim_at(q,in,center[0],ground(center[0],center[1])+.6f,center[1]);in->forward=.7f;}
        else{in->strafe=sinf(t*.8f+p*REPLAY_PI*.5f)*.28f;in->forward=nearest>12?.25f:nearest<2?-.2f:0;}
        /* Give the first sniper a brief aiming interval before the firefight
         * so the original scope can be inspected in the gameplay capture. */
        bool attack=within>(segment==0?2.5f:.7f)&&within<5&&v->health>0&&error<.14f;
        const bg_weapon_def*w=&bg_weapon_defs[q->weapon];
        if(q->weapon==BG_W_PLASMA_PISTOL)in->fire=attack&&fmodf(t+p*.25f,1.2f)<.9f;
        else in->fire=attack&&(w->automatic||frame%12==p*2);
        in->reload=within>5.2f&&within<5.24f&&q->ammo<w->magazine;
        in->jump=(frame+p*43)%240==120;
        in->grenade=(frame+p*81)%450==240;
        if((q->weapon==BG_W_SNIPER||q->weapon==BG_W_PISTOL)&&q->zoom==0&&within>1.2f&&within<1.24f)in->zoom=true;
        if(q->zoom&&within>4.7f&&within<4.74f)in->zoom=true;
    }
}
static void driving_input(bg_input input[BG_PLAYERS],float t){
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];bg_input*in=&input[p];if(q->health<=0)continue;
        if(vehicle_for[p]<0)continue;
        bg_vehicle*v=&bg_vehicles[vehicle_for[p]];
        if(q->vehicle<0){
            if(v->active&&(v->occupants[0]<0||p==0)){
                float entry[3];bg_vehicle_seat_position(v,0,true,entry);
                aim_at(q,in,entry[0],entry[1]+.5f,entry[2]);
                float dx=entry[0]-q->pos[0],dz=entry[2]-q->pos[2];
                in->forward=.7f;if(dx*dx+dz*dz<.08f)in->interact=true;
            }else{
                unsigned target=(p+1)%4;bg_player*other=&bg_players[target];
                aim_at(q,in,other->pos[0],other->pos[1]+.4f,other->pos[2]);
                in->fire=frame%3!=0;in->reload=q->ammo==0;in->strafe=.3f;
            }
            continue;
        }
        v=&bg_vehicles[q->vehicle];
        if(v->kind==BG_V_WARTHOG&&q->seat==1){
            bg_player*target=&bg_players[2];aim_at(q,in,target->pos[0],target->pos[1]+.5f,target->pos[2]);
            in->fire=fmodf(t,3)<2;continue;
        }
        if(v->kind==BG_V_WARTHOG&&q->seat==0&&t>9){in->forward=0;in->turn=0;continue;}
        /* Each controller follows a different orbit; altitude remains under
         * the original Banshee desired-facing control. */
        float theta=t*.22f+p*REPLAY_PI*.5f;
        float radius=p==BG_V_SCORPION?4:6;
        float waypoint_x=center[0]+cosf(theta)*radius,waypoint_z=center[1]+sinf(theta)*radius;
        float desired=atan2f(-(waypoint_z-v->pos[2]),waypoint_x-v->pos[0]);
        float error=angle_delta(desired,q->yaw);
        in->turn=clamp(error*1.6f,-1,1);in->forward=fabsf(error)>1?.2f:.5f;
        if(p==BG_V_GHOST)in->strafe=sinf(t*.7f)*.3f;
        if(p==BG_V_BANSHEE){
            float floor=ground(v->pos[0],v->pos[2]);
            float pitch=clamp((floor+2.5f-v->pos[1])*.2f-.26f,-.65f,.45f);
            in->look=clamp((pitch-q->pitch)*2,-1,1);
        }else in->look=-q->pitch*2;
        if(p==BG_V_SCORPION){in->strafe=in->turn;bg_player*target=&bg_players[3];
            aim_at(q,in,target->pos[0],target->pos[1]+.4f,target->pos[2]);}
        /* Start with an unarmed driving lap so every vehicle is visible before
         * the mounted duel. This changes input only, never damage or health. */
        in->fire=t>9&&fmodf(t+p,4)<2.5f;
        in->secondary_fire=t>9&&((p==BG_V_BANSHEE&&frame%150==0)||(p==BG_V_SCORPION&&fmodf(t,4)>2.5f));
        /* Leave a short repositioning interval before the mounted duel. */
        if(p==BG_V_SCORPION&&t>9&&t<18){in->fire=false;in->secondary_fire=false;}
        /* After the driving overview, the Ghost pilot boards the Warthog's
         * actual gunner seat. Its driver slows to make this possible. */
        if(t>9&&p==0){in->forward=0;in->turn=0;}
        if(t>10&&p==1&&q->vehicle==vehicle_for[1])in->interact=frame%30<9;
    }
    if(t>10&&vehicle_for[0]>=0&&bg_players[1].health>0){
        bg_player*q=&bg_players[1];bg_input*in=&input[1];bg_vehicle*hog=&bg_vehicles[vehicle_for[0]];
        if(q->vehicle<0&&hog->active){
            in->interact=false;in->strafe=0;
            float entry[3];bg_vehicle_seat_position(hog,1,true,entry);
            aim_at(q,in,entry[0],entry[1]+.5f,entry[2]);
            float dx=entry[0]-q->pos[0],dz=entry[2]-q->pos[2];in->forward=.85f;
            if(dx*dx+dz*dz<.12f)in->interact=true;
        }else if(q->vehicle==vehicle_for[0]&&q->seat==1){
            bg_player*target=&bg_players[2];aim_at(q,in,target->pos[0],target->pos[1]+.5f,target->pos[2]);
            in->interact=false;in->fire=fmodf(t,3)<2;
        }
    }
}
void bg_replay_input(bg_input input[BG_PLAYERS],float time){
    memset(input,0,sizeof(bg_input)*BG_PLAYERS);
    int next_cycle=(int)(time/REPLAY_DURATION);float t=fmodf(fmaxf(0,time),REPLAY_DURATION);
    if(time<previous_time||next_cycle!=cycle){
        bg_set_players(4);bg_reset();cycle=next_cycle;phase=loadout=-1;frame=0;
        memset(was_alive,0,sizeof(was_alive));for(unsigned p=0;p<4;p++)vehicle_for[p]=-1;
    }
    previous_time=time;frame++;
    int next_phase=t<36?0:1;
    if(next_phase!=phase){phase=next_phase;if(phase==1)start_vehicles();}
    int segment=(int)(t/8);
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];bool fresh=q->health>0&&!was_alive[p];
        if(fresh){
            if(phase==0)arena_spawn(p);
            else if(vehicle_for[p]>=0){
                bg_vehicle*v=&bg_vehicles[vehicle_for[p]];float entry[3];
                bg_vehicle_seat_position(v,0,true,entry);place_player(p,entry[0],entry[2]);
            }
        }
        if(q->health>0&&phase==0&&(fresh||segment!=loadout))equip(p,requested_weapon(p,segment),&input[p]);
        was_alive[p]=q->health>0;
    }
    loadout=segment;
    if(phase==0)combat_input(input,t,segment);else driving_input(input,t-36);
    if(phase==1&&t-36>9&&t-36<18)for(unsigned p=0;p<4;p++){
        input[p].fire=false;input[p].secondary_fire=false;
    }
}
