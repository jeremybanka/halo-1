#include "movement.h"
#include "controls.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static void near(float a,float b){assert(fabsf(a-b)<.0001f);}
static void scene(void){
    bg_set_players(2);bg_reset();bg_vehicle_count=bg_pickup_count=0;
    for(unsigned i=0;i<2;i++){
        bg_player*p=&bg_players[i];p->pos[0]=-12.f+7.f*i;p->pos[1]=4;p->pos[2]=5;
        p->yaw=p->pitch=0;p->weapon=BG_W_PISTOL;p->invisibility=0;p->crouch_amount=0;
    }
}
int main(void){
    const float dt=1.f/30;bg_player p={.grounded=true};
    for(unsigned i=1;i<=8;i++){bg_walk_velocity(&p,1,0,dt);near(p.velocity[0],fminf(i*.32f,2.25f));}
    for(unsigned i=1;i<=8;i++){bg_walk_velocity(&p,0,0,dt);near(p.velocity[0],fmaxf(2.25f-i*.32f,0));}
    for(unsigned i=0;i<10;i++)bg_walk_velocity(&p,-1,0,dt);near(p.velocity[0],-2);
    p=(bg_player){.grounded=true,.crouch_amount=1};for(unsigned i=0;i<10;i++)bg_walk_velocity(&p,0,1,dt);near(p.velocity[2],.6f);
    p=(bg_player){.velocity={2.25f,0,0}};
    for(unsigned i=1;i<=30;i++){bg_walk_velocity(&p,-1,0,dt);near(p.velocity[0],2.25f-i*.035f);}
    near(bg_look_curve(.2f),.05f);near(bg_look_curve(-.4f),-.1f);near(bg_look_curve(.5f),.175f);near(bg_look_curve(2),1);
    bg_input in={.turn=1};p=(bg_player){0};float yaw,pitch;
    bg_look_input(&p,&in,1,dt,&yaw,&pitch);near(yaw,120.f*3.14159265f/180*dt);
    for(unsigned i=0;i<30;i++)bg_look_input(&p,&in,1,dt,&yaw,&pitch);
    near(yaw,360.f*3.14159265f/180*dt);in.turn=0;bg_look_input(&p,&in,1,dt,&yaw,&pitch);near(p.look_peg_time,0);
    in=(bg_input){.turn=.5f,.look=0};float base;
    bg_look_input(&p,&in,1,dt,&base,&pitch);
    bg_look_input(&p,&in,2,dt,&yaw,&pitch);near(yaw,base/2);
    bg_look_input(&p,&in,10,dt,&yaw,&pitch);near(yaw,base/10);
    p.crouch_amount=1;near(bg_eye_height(&p),.35f);
    float vy=bg_movement.jump,y=0,peak=0;unsigned airborne=0;
    do{vy-=bg_movement.gravity*dt;y+=vy*dt;peak=fmaxf(peak,y);airborne++;}while(y>0&&airborne<100);
    assert(peak>.64f&&peak<.66f&&airborne==39);
    for(unsigned style=0;style<2;style++){
        bg_control_state raw={.stick_x=40,.stick_y=0};bg_controls_map(&in,&raw,style,false);
        p=(bg_player){0};bg_look_input(&p,&in,1,dt,&yaw,&pitch);assert(yaw<0&&fabsf(yaw)<.02f);
    }
    scene();bg_aim_target target=bg_aim_query(0);assert(target.player==1&&target.auto_level>.99f&&target.mag_level>.99f);
    bg_players[1].invisibility=1;assert(bg_aim_query(0).player<0);bg_players[1].invisibility=0;
    bg_players[1].health=0;assert(bg_aim_query(0).player<0);bg_players[1].health=100;
    bg_players[0].yaw=.3f;assert(bg_aim_query(0).player<0);bg_players[0].yaw=0;
    bg_players[1].pos[0]=40;assert(bg_aim_query(0).player<0);
    bg_players[0].zoom=1;assert(bg_aim_query(0).player<0); /* Ridge still blocks scoped assist. */
    bg_players[0].pos[1]=bg_players[1].pos[1]=20;assert(bg_aim_query(0).player==1);
    scene();bg_add_vehicle(BG_V_SCORPION,(float[]){-8,4,5},0);bg_vehicles[0].pos[1]=4;assert(bg_aim_query(0).player<0);
    /* No-input aim must not follow a moving target. Input enables original
     * friction/adhesion; mirrored horizontal target velocities reverse yaw. */
    scene();bg_players[1].velocity[2]=1;bg_input inputs[4]={0};float initial=bg_players[0].yaw;
    bg_tick(inputs,dt);near(bg_players[0].yaw,initial);
    scene();bg_players[1].velocity[2]=1;inputs[0].forward=.01f;bg_tick(inputs,dt);assert(bg_players[0].yaw<0);
    scene();bg_players[1].velocity[2]=-1;bg_tick(inputs,dt);assert(bg_players[0].yaw>0);
    printf("PASS movement: source acceleration, air inertia, crouch, 39-tick jump / %.6f apex, response curve, peg ramp, zoom, both layouts, targeting eligibility, vehicle cover and adhesion direction\n",peak);
}
