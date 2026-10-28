#include <assert.h>
#include <stdio.h>
#include "game.c"
#include "player_animation.h"
static void sustained(bool crouch){
    bg_set_players(2);bg_reset();bg_vehicle_count=bg_pickup_count=0;
    bg_player*p=&bg_players[0];p->pos[0]=0;p->pos[2]=4;p->pos[1]=bg_floor(0,4,100)+.015f;
    p->yaw=0;p->pitch=.4f;p->weapon=BG_W_AR;p->inventory[0]=BG_W_AR;p->slot=0;p->ammo=60;p->weapon_ready=0;
    bg_players[1].pos[0]=20;bg_players[1].pos[2]=20;bg_players[1].pos[1]=bg_floor(20,20,100)+.015f;
    unsigned shots=0;float start=p->pos[0];
    for(unsigned tick=0;tick<60;tick++){
        float previous=p->locomotion_time;bg_input input[4]={0};input[0].forward=1;input[0].fire=true;input[0].crouch=crouch;
        bg_clear_events();bg_tick(input,1.f/30);
        assert(fabsf(p->locomotion_time-previous-1.f/30)<1e-6f);
        for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_FIRE&&bg_events[e].player==0){
            shots++;assert(p->anim_time==0&&p->fire_ticks[0]==0&&p->locomotion_time>0);
        }
    }
    assert(shots>=15&&p->pos[0]>start+.3f&&p->health>0);
    printf("PASS %s: %u automatic shots, %.3f seconds uninterrupted gait, %.3f world units moved\n",crouch?"crouched":"standing",shots,p->locomotion_time,p->pos[0]-start);
}
static void hit_motion(bool crouch){
    bg_reset();bg_player*p=&bg_players[0];p->pos[0]=p->pos[2]=0;p->pos[1]=0;p->yaw=0;
    p->vehicle=-1;p->grounded=true;p->weapon_ready=p->reload=p->melee_time=p->landing_time=p->grenade_cooldown=0;
    p->crouch_amount=crouch;p->crouched=crouch;p->velocity[0]=1;p->animation=BG_ANIM_FIRE;p->anim_time=0;p->fire_ticks[p->slot]=0;
    unsigned changed=0;float dir[3]={1,0,0};
    for(unsigned y=0;y<24;y++)for(int z=-16;z<=16;z++){
        float o[3]={-2,y*.025f,z*.025f};int region;
        p->locomotion_time=0;float a=bg_player_hit_ray(0,o,dir,4,&region);
        p->locomotion_time=.25f;float b=bg_player_hit_ray(0,o,dir,4,&region);
        changed+=(a<4)!=(b<4);
    }
    assert(changed>10);printf("PASS %s firing collision follows gait: %u changing silhouette rays\n",crouch?"crouched":"standing",changed);
    assert(bg_player_body_firing(p));p->reload=1;assert(!bg_player_body_firing(p));p->reload=0;
    p->melee_time=1;assert(!bg_player_body_firing(p));p->melee_time=0;
    p->weapon_ready=1;assert(!bg_player_body_firing(p));p->weapon_ready=0;
    p->vehicle=0;assert(!bg_player_body_firing(p));p->vehicle=-1;
    p->grounded=false;assert(!bg_player_body_firing(p));p->grounded=true;
    p->fire_ticks[p->slot]=5;assert(!bg_player_body_firing(p));p->fire_ticks[p->slot]=0;
    p->health=0;assert(!bg_player_body_firing(p));
}
int main(void){assert(bg_map_load(9));sustained(false);sustained(true);hit_motion(false);hit_motion(true);puts("PASS separate firing/gait clocks, original animated collision and action priority");}
