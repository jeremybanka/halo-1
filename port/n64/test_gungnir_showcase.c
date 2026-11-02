#include "map.h"
#include "gungnir_showcase.inc"
#include <assert.h>
#include <stdio.h>
int main(void){
    assert(bg_map_load(BG_MAP_BLOOD_GULCH));
    for(unsigned mode=0;mode<4;mode++){
        bg_showcase_begin((bg_showcase_kind)(BG_SHOWCASE_COUNT+mode));
        assert(bg_players[0].shield==150&&bg_players[0].health==100);
        unsigned follow_frames=0;float max_distance=0;
        for(unsigned f=0;f<900;f++){
            bg_input in[4];bg_showcase_input(in,f/30.f);
            if(!mode)assert(!in[0].turn&&!in[0].look&&!in[0].forward&&!in[0].strafe);
            else if(f<780)assert(!in[0].forward&&!in[0].strafe);
            bg_clear_events();bg_tick(in,1.f/30);bg_showcase_observe();
            if(bg_players[0].autopilot_on&&bg_players[0].autopilot_style==BG_AUTOPILOT_FOLLOW&&bg_players[0].autopilot_follow==1)follow_frames++;
            max_distance=fmaxf(max_distance,hypotf(bg_players[0].pos[0]-demo_start[0],bg_players[0].pos[2]-demo_start[2]));
        }
        printf("%s shots=%u kills=%u travel=%.2f displacement=%.2f aim=%u auto=%u manual_auto_shots=%u follow=%u alive=%.1f pass=%u\n",bg_showcase_title(),demo_stats.shots,demo_stats.kills,demo_stats.traveled,max_distance,demo_aim_frames,demo_auto_frames,demo_auto_shots,follow_frames,bg_players[0].health,demo_stats.passed);fflush(stdout);
        assert(demo_stats.passed);
        if(!mode)assert(bg_players[0].yaw==demo_yaw&&bg_players[0].pitch==demo_pitch&&max_distance<.001f);
        if(mode==1)assert(follow_frames>150);
        if(mode)assert(demo_auto_frames>150&&demo_auto_shots>3&&max_distance>2);
    }
    puts("PASS: four live GUNGNIR recording encounters, real weapons/damage/nav, aim camera fixed and manual weapons during all movement modes");
}
