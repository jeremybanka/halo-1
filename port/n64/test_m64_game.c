#include <assert.h>
#include <stdio.h>
#include "game.c"
int main(void) {
    assert(bg_map_load(9));bg_ff_start(2);
    /* Accepted PvE damage updates only its victim; friendly fire, shield
     * charge protection, ownerless falling and self damage do not point at
     * an unrelated unit. Timers advance in simulation, never per viewport. */
    float pos[3]={bg_players[0].pos[0]+2,bg_players[0].pos[1],bg_players[0].pos[2]};
    pve_spawn_actor(0,BG_PVE_ELITE,BG_W_PLASMA_RIFLE,0,pos,0);
    bg_players[0].yaw=0;bg_players[0].pitch=0;
    damage_player_profile(0,4,5,false,false,0,false,false,1);
    assert(bg_players[0].damage_indicator[0]>0);
    for(unsigned i=0;i<4;i++)assert(bg_players[1].damage_indicator[i]==0);
    float old=bg_players[0].damage_indicator[0];tick_player_timers(0,1.f/30);
    assert(fabsf(bg_players[0].damage_indicator[0]-(old-1.f/30))<.00001f);
    for(unsigned i=0;i<30;i++)tick_player_timers(0,1.f/30);
    for(unsigned i=0;i<4;i++)assert(bg_players[0].damage_indicator[i]==0);
    damage_player_profile(0,1,5,false,false,0,false,false,1);
    damage_player_profile(0,-1,5,false,false,0,false,false,1);
    damage_player_profile(0,0,5,false,false,0,false,false,1);
    for(unsigned i=0;i<4;i++)assert(bg_players[0].damage_indicator[i]==0);
    bg_players[0].shield_overcharging=true;
    damage_player_profile(0,4,5,false,false,0,false,false,1);
    for(unsigned i=0;i<4;i++)assert(bg_players[0].damage_indicator[i]==0);
    bg_players[0].shield_overcharging=false;
    bg_input in={.flashlight=true};tick_player_resources(0,&in,1.f/30);
    assert(bg_players[0].flashlight_on&&!bg_players[1].flashlight_on);
    in.flashlight=false;tick_player_resources(0,&in,1.f/30);assert(bg_players[0].flashlight_on);
    in.flashlight=true;tick_player_resources(0,&in,1.f/30);assert(!bg_players[0].flashlight_on);
    damage_player_profile(0,4,5,false,false,0,false,false,1);
    bg_players[0].flashlight_on=true;bg_reset();
    assert(!bg_players[0].flashlight_on);
    for(unsigned i=0;i<4;i++)assert(bg_players[0].damage_indicator[i]==0);
    bg_player flash={0};
    bg_damage_flash_start(&flash,BG_D_AR,1);
    assert(fabsf(flash.damage_flash_time-.1f)<.000001f);
    float peak=bg_damage_flash_intensity(&flash);
    assert(peak>.44f&&peak<.45f); /* CE evaluates early(scaled remaining time). */
    flash.damage_flash_time=.05f;assert(bg_damage_flash_intensity(&flash)<peak);
    flash.damage_flash_time=0;assert(bg_damage_flash_intensity(&flash)==0);
    bg_damage_flash_start(&flash,BG_D_OVERCHARGE,1);
    bg_damage_flash_start(&flash,BG_D_AR,1);assert(flash.damage_flash_profile==BG_D_OVERCHARGE);
    flash.damage_flash_time=.05f;bg_damage_flash_start(&flash,BG_D_AR,1);assert(flash.damage_flash_profile==BG_D_AR);
    flash.damage_flash_time=0;bg_damage_flash_start(&flash,BG_D_ROCKET,1);assert(bg_damage_flash_intensity(&flash)>0);
    bg_damage_flash_start(&flash,BG_D_DISTANCE,1);assert(flash.damage_flash_profile==BG_D_ROCKET);
    bg_players[0].shield_overcharging=false;
    damage_player_profile(0,4,5,false,false,BG_D_AR,false,false,1);
    assert(bg_players[0].damage_flash_time>0&&bg_players[1].damage_flash_time==0);
    for(unsigned i=0;i<4;i++)tick_player_timers(0,1.f/30);
    assert(bg_damage_flash_intensity(&bg_players[0])==0);
    puts("PASS source screen-flash duration/fade/priority, zero-duration pulse, victim isolation and expiry");
    puts("PASS actual damage admission, victim isolation, duration, friendly fire, immunity, ownerless/self damage, flashlight toggle and reset");
}
