#include <stdlib.h>
#include "benchmarks/firefight-zoom/combat.inc"
int main(int argc,char**argv){
    assert(bg_map_load(BG_MAP_BLOOD_GULCH));
    combat_fight=argc>1?strtoul(argv[1],NULL,10):BG_FF_ONSLAUGHT;
    unsigned ticks=argc>2?strtoul(argv[2],NULL,10):3600;
    bg_input input[4]={0};
    for(unsigned i=0;i<ticks;i++){bg_clear_events();bg_tick(input,1.f/30);}
    combat_report();
    assert(combat_counts.human_fire>100&&combat_counts.enemy_fire>100);
    assert(combat_counts.frags>5&&combat_counts.explosions>10&&combat_counts.enemy_deaths>5);
    assert(combat_counts.moving_aboard_ticks>300&&combat_counts.travel>30&&combat_counts.zoom_edges>20);
    assert(combat_counts.peak_moving_aboard_projectiles>=12&&combat_counts.busy_aboard_ticks>=90);
    assert(combat_counts.busy_scoped_ticks>=100&&combat_counts.explosion_zoom_edges>=5);
    puts("COMBAT_QA PASS: live combat, grenades, kills, three-player moving Warthog and repeated zoom");
}
