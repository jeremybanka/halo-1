#ifndef BG_SHIELD_FIXTURE_H
#define BG_SHIELD_FIXTURE_H
/* Deterministic QA only. Shots enter the production collision/damage path;
 * overshield comes from a real world pickup, never a presentation override. */
#include "game.h"
#include "rifle_fixture.h"
#include <string.h>
#include <assert.h>
static void shield_fixture_ticks(unsigned count){
    const bg_input in[4]={0};
    while(count--){bg_clear_events();bg_tick(in,1.f/30);}
}
static void shield_fixture_shot(unsigned victim,float damage){
    bg_projectile*q=bg_projectile_create();assert(q);
    q->kind=BG_P_FLAME;q->owner=(victim+1)%4;q->life=1;q->damage=damage;q->radius=0;
    memcpy(q->pos,bg_players[victim].pos,12);q->pos[0]-=.5f;q->pos[1]+=.35f;
    q->velocity[0]=30;
}
static void shield_fixture_reset(void){
    bg_set_players(4);bg_reset();for(unsigned f=0;f<4;f++)bg_fixture_rifle_loadout(f);bg_set_score_limit(1000);bg_pickup_count=bg_vehicle_count=0;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=p*6;q->pos[2]=4;
        q->pos[1]=bg_floor(q->pos[0],4,100)+.015f;q->yaw=0;q->pitch=0;
    }
    shield_fixture_ticks(2);bg_clear_events();
}
static void shield_fixture_stage(unsigned page){
    shield_fixture_reset();bg_add_pickup(BG_PICK_OVERSHIELD,bg_players[3].pos);
    shield_fixture_ticks(62);
    shield_fixture_shot(1,75);shield_fixture_shot(2,100);
    if(page==0)shield_fixture_shot(3,40);
    shield_fixture_ticks(4);
    if(page==1)shield_fixture_ticks(193); /* p1/p2 actively recharging. */
    if(page==2){shield_fixture_ticks(72);shield_fixture_shot(2,10);shield_fixture_ticks(1);}
}
#endif
