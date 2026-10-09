#include "camouflage.h"
#include "movement.h"
#include "shield_fixture.h"
#include "pickup_rules.h"
#include <stdio.h>
static bg_input input[4];
static void tick(unsigned n){while(n--){bg_clear_events();bg_tick(input,1.f/30);}}
static void reset(void){shield_fixture_reset();memset(input,0,sizeof(input));for(unsigned i=0;i<4;i++){bg_players[i].yaw=1.57f;bg_players[i].pitch=.5f;}}
int main(void){
    reset();bg_player*p=&bg_players[1];bg_add_pickup(BG_PICK_CAMO,p->pos);tick(1);
    assert(p->invisibility==bg_camo_duration&&bg_player_visibility(p)==1);
    tick(31);assert(bg_player_visibility(p)==0);
    bg_give_weapon(1,BG_W_AR);p->weapon_ready=p->cooldown=0;
    input[1].fire=true;tick(1);assert(p->ammo==59&&p->camo_quiet==3);
    input[1].fire=false;tick(15);assert(p->camo_opacity>.49f&&p->camo_opacity<.51f);
    tick(15);assert(p->camo_opacity>.999f);tick(60);assert(p->camo_opacity>.99f);
    tick(16);assert(p->camo_opacity>.4f&&p->camo_opacity<.6f);tick(16);assert(bg_player_visibility(p)==0);
    /* A second pickup refreshes duration without erasing a shot reveal. */
    p->invisibility=2;p->camo_opacity=.5f;p->camo_quiet=2;
    bg_add_pickup(BG_PICK_CAMO,p->pos);tick(1);
    assert(p->invisibility==bg_camo_duration&&p->camo_opacity>.5f&&p->camo_quiet>1.9f);
    p->camo_quiet=p->camo_opacity=0;
    /* Empty trigger/reload/switch never renew the actual-shot timer. */
    p->ammo=p->reserve=0;input[1].fire=true;tick(35);assert(p->camo_quiet==0&&bg_player_visibility(p)==0);input[1].fire=false;
    p->invisibility=.5f;assert(fabsf(bg_player_visibility(p)-.5f)<.001f);tick(16);assert(bg_player_visibility(p)==1);
    /* Fully cloaked targets remain hittable; damage reveals, death clears all latches. */
    p->invisibility=30;p->camo_opacity=p->camo_quiet=0;shield_fixture_shot(1,20);tick(1);
    assert(p->shield<100&&p->camo_quiet==3);tick(30);assert(p->camo_opacity>.999f);
    shield_fixture_shot(1,1000);tick(1);assert(p->health==0&&p->invisibility==0&&bg_player_visibility(p)==1);
    tick(92);assert(p->health==100&&p->invisibility==0&&p->camo_quiet==0);
    reset();p=&bg_players[1];p->invisibility=30;p->velocity[0]=1;
    assert(bg_motion_sensor_visible(p));p->crouched=true;assert(!bg_motion_sensor_visible(p));
    p->fire_held=true;assert(bg_motion_sensor_visible(p));p->fire_held=false;p->crouched=false;p->velocity[0]=0;
    assert(!bg_motion_sensor_visible(p));p->vehicle=0;bg_vehicle_count=1;bg_vehicles[0].velocity[0]=1;
    assert(bg_motion_sensor_visible(p));bg_vehicles[0].velocity[0]=0;assert(!bg_motion_sensor_visible(p));
    /* Aim assist follows visible transitions, not the duration latch. */
    reset();p=&bg_players[1];bg_player*a=&bg_players[0];memcpy(p->pos,a->pos,12);p->pos[0]+=3;
    bg_players[2].health=bg_players[3].health=0;
    a->yaw=a->pitch=0;bg_give_weapon(0,BG_W_NEEDLER);p->invisibility=30;p->camo_opacity=0;
    assert(bg_aim_query(0).player<0);p->camo_opacity=.5f;assert(bg_aim_query(0).player==1);
    bg_projectile*q=bg_projectile_create();assert(q);q->kind=BG_P_NEEDLE;q->owner=0;q->tracked=1;q->life=5;q->velocity[0]=4;
    memcpy(q->pos,a->pos,12);q->pos[1]+=.35f;p->camo_opacity=0;tick(1);assert(bg_projectile_at(0)->tracked==-1);
    /* Mounted fire reveals the occupant, never cloaks the hull. */
    reset();float pos[3]={-12,bg_floor(-12,5,100),5};int vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);
    p=&bg_players[1];p->vehicle=vi;p->seat=1;bg_vehicles[vi].occupants[1]=1;p->invisibility=30;
    input[1].fire=true;tick(2);assert(p->camo_quiet>2.9f&&bg_vehicles[vi].active&&p->camo_opacity>0);
    puts("PASS: camo acquisition, shot fade/quiet delay, dry trigger, expiry, hit/death/respawn, radar, aim/Needler target loss and mounted firing");
}
