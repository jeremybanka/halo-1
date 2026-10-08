/* Real simulation events feed the bounded presentation state. */
#include "weapon_effects.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static bg_input input[4];
static void tick(void){bg_clear_events();bg_tick(input,1.f/30);bg_fx_update(1.f/30);}
static void reset(void){
    bg_reset();bg_set_players(1);bg_vehicle_count=bg_pickup_count=0;bg_fx_reset();memset(input,0,sizeof(input));
    bg_players[0].pos[0]=0;bg_players[0].pos[2]=4;bg_players[0].pos[1]=bg_floor(0,4,100)+.015f;
    bg_players[0].yaw=0;bg_players[0].pitch=0;
}
static void equip(unsigned weapon){
    reset();assert(bg_give_weapon(0,weapon));
    if(bg_players[0].weapon!=(int)weapon){input[0].switch_weapon=true;tick();input[0].switch_weapon=false;}
    for(unsigned i=0;i<15;i++)tick();
}
static float length(const float v[3]){return sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);}
int main(void){
    for(unsigned w=0;w<8;w++){
        equip(w);assert(bg_fx_flash(0)==0);input[0].fire=true;tick();
        if(w==BG_W_PLASMA_PISTOL){input[0].fire=false;tick();}
        assert(bg_fx_shots[0].weapon==(int)w&&bg_fx_flash(0)>0);
        input[0].fire=false;for(unsigned i=0;i<8;i++)tick();assert(bg_fx_flash(0)==0);
        bg_players[0].ammo=0;unsigned shots=bg_fx_shots[0].sequence;input[0].fire=true;tick();input[0].fire=false;tick();assert(bg_fx_shots[0].sequence==shots);
    }
    equip(BG_W_PLASMA_PISTOL);input[0].fire=true;float old=0;
    for(unsigned i=0;i<90;i++){tick();float now=bg_fx_charge(0);assert(now>=old&&now<=1);old=now;}
    assert(bg_fx_charge(0)==1);input[0].fire=false;tick();assert(bg_fx_charge(0)==0&&bg_fx_shots[0].charged);
    bg_players[0].charge=1;bg_players[0].fire_held=true;bg_players[0].heat=0;bg_players[0].overheated=false;
    assert(bg_fx_charge(0)==1);bg_players[0].weapon=BG_W_AR;assert(bg_fx_charge(0)==0);
    bg_players[0].weapon=BG_W_PLASMA_PISTOL;bg_players[0].health=0;assert(bg_fx_charge(0)==0&&bg_fx_flash(0)==0);
    equip(BG_W_SNIPER);input[0].fire=true;tick();assert(bg_fx_trails[0].active);
    const bg_shot_trace*t=bg_sniper_trace(0);float direction[3];for(unsigned a=0;a<3;a++)direction[a]=t->end[a]-t->start[a];
    float distance=length(direction);assert(distance>1&&distance<=bg_weapon_defs[BG_W_SNIPER].range);
    for(unsigned a=0;a<3;a++)direction[a]/=distance;
    assert(fabsf(bg_raycast(t->start,direction,bg_weapon_defs[BG_W_SNIPER].range)-distance)<.01f);
    assert(!memcmp(bg_fx_trails[0].start,t->start,12)&&!memcmp(bg_fx_trails[0].end,t->end,12));
    input[0].fire=false;for(unsigned i=0;i<40;i++)tick();assert(!bg_fx_trails[0].active);
    /* A target intercepts the ray before the far wall. */
    equip(BG_W_SNIPER);bg_set_players(2);bg_players[0].pitch=-.14f;
    memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=2;
    input[0].fire=true;tick();t=bg_sniper_trace(0);for(unsigned a=0;a<3;a++)direction[a]=t->end[a]-t->start[a];
    assert(length(direction)<2.5f&&bg_players[1].shield<100);
    /* New events replace bounded slots; no lingering glow after reset. */
    for(unsigned n=0;n<30;n++){bg_event_count=1;bg_events[0]=(bg_event){.kind=BG_EVENT_FIRE,.player=n%4,.weapon=BG_W_SNIPER,.amount=1};bg_players[n%4].vehicle=-1;bg_fx_update(0);}
    unsigned active=0;for(unsigned i=0;i<BG_FX_TRAILS;i++)active+=bg_fx_trails[i].active;assert(active==BG_FX_TRAILS);
    bg_fx_reset();for(unsigned i=0;i<BG_FX_TRAILS;i++)assert(!bg_fx_trails[i].active);
    puts("PASS: eight live firing events, empty weapons, charge growth/hold/release/cancellation, exact terrain/target sniper hits and bounded trail reuse");
}
