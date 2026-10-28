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
static void walking_reload(bool crouch,unsigned weapon){
    bg_set_players(2);bg_reset();bg_vehicle_count=bg_pickup_count=0;
    bg_player*p=&bg_players[0];p->pos[0]=0;p->pos[2]=4;p->pos[1]=bg_floor(0,4,100)+.015f;
    p->yaw=0;p->pitch=.4f;p->weapon=weapon;p->inventory[0]=weapon;p->slot=0;p->ammo=0;p->reserve=100;p->weapon_ready=0;
    p->crouched=crouch;p->crouch_amount=crouch;p->locomotion_time=.13f;
    bg_players[1].pos[0]=20;bg_players[1].pos[2]=20;bg_players[1].pos[1]=bg_floor(20,20,100)+.015f;
    unsigned active=0,cycles=0;float start=p->pos[0],last_frame=0;
    for(unsigned tick=0;tick<180;tick++){
        float previous=p->locomotion_time;bg_input in[4]={0};in[0].forward=1;in[0].crouch=crouch;in[0].reload=tick==0;
        bg_clear_events();bg_tick(in,1.f/30);
        assert(fabsf(p->locomotion_time-previous-1.f/30)<2e-6f);
        if(bg_player_body_reloading(p)){
            float f=bg_player_body_reload_frame(p);assert(f>=0&&f<=BG_BODY_RELOAD_FRAMES-1);
            if(!active||f<last_frame)cycles++;last_frame=f;active++;
            assert(!bg_player_body_firing(p));
        }
        if(tick>0&&p->reload==0)break;
    }
    assert(active>15&&p->ammo>0&&p->pos[0]>start+.3f&&p->health>0);
    if(weapon!=BG_W_SHOTGUN)assert(p->ammo==bg_weapon_defs[weapon].magazine&&cycles==1);
    else assert(cycles>=2);
    printf("PASS %s weapon %u reload: %u moving layered ticks, %u cycles, ammo %u, moved %.3f\n",crouch?"crouched":"standing",weapon,active,cycles,p->ammo,p->pos[0]-start);
}
static void reload_hits(bool crouch){
    bg_reset();bg_player*p=&bg_players[0];p->pos[0]=p->pos[1]=p->pos[2]=p->yaw=0;
    p->vehicle=-1;p->grounded=true;p->weapon_ready=p->melee_time=p->landing_time=p->grenade_cooldown=0;
    p->crouch_amount=crouch;p->crouched=crouch;p->velocity[0]=1;p->animation=BG_ANIM_RELOAD;
    p->reload_duration=3;p->reload=2;p->anim_time=1;unsigned changed=0;float dir[3]={1,0,0};
    for(unsigned y=0;y<24;y++)for(int z=-16;z<=16;z++){
        float o[3]={-2,y*.025f,z*.025f};int region;
        p->locomotion_time=0;float a=bg_player_hit_ray(0,o,dir,4,&region);
        p->locomotion_time=.25f;float b=bg_player_hit_ray(0,o,dir,4,&region);changed+=(a<4)!=(b<4);
    }
    assert(changed>10);printf("PASS %s reload collision follows independent gait: %u silhouette rays\n",crouch?"crouched":"standing",changed);
    assert(bg_player_body_reloading(p));p->weapon_ready=1;assert(!bg_player_body_reloading(p));p->weapon_ready=0;
    p->melee_time=1;assert(!bg_player_body_reloading(p));p->melee_time=0;
    p->landing_time=1;assert(!bg_player_body_reloading(p));p->landing_time=0;
    p->vehicle=0;assert(!bg_player_body_reloading(p));p->vehicle=-1;
    p->grounded=false;assert(!bg_player_body_reloading(p));p->grounded=true;
    p->health=0;assert(!bg_player_body_reloading(p));p->health=100;
    p->reload_duration=0;assert(!bg_player_body_reloading(p));
}
int main(void){
    assert(bg_map_load(9));sustained(false);sustained(true);hit_motion(false);hit_motion(true);
    for(unsigned stance=0;stance<2;stance++)for(unsigned w=0;w<6;w++)walking_reload(stance,(unsigned[]){BG_W_AR,BG_W_PISTOL,BG_W_SNIPER,BG_W_ROCKET,BG_W_NEEDLER,BG_W_SHOTGUN}[w]);
    reload_hits(false);reload_hits(true);
    puts("PASS independent firing/reload/gait clocks, animated collision, source weapon timing and action priorities");
}
