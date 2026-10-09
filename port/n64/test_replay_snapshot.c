/* Run in separate fresh processes with and without the "snapshot" argument.
 * Byte hashes include all gameplay records and the per-tick event stream, so
 * equivalent final positions cannot conceal different intervening effects. */
#include "replay_snapshot.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t hash=14695981039346656037ull;
static void add(const void*data,size_t size){
    const unsigned char*p=data;
    for(size_t i=0;i<size;i++){hash^=p[i];hash*=1099511628211ull;}
}
static void state(float time){
    add(&time,sizeof(time));add(bg_players,sizeof(bg_players));
    add(&bg_vehicle_count,sizeof(bg_vehicle_count));add(bg_vehicles,sizeof(bg_vehicles));
    add(&bg_pickup_count,sizeof(bg_pickup_count));add(bg_pickups,sizeof(bg_pickups));
    add(&bg_event_count,sizeof(bg_event_count));add(bg_events,bg_event_count*sizeof(bg_events[0]));
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        const bg_projectile*q=bg_projectile_at(i);bool present=q!=NULL;
        add(&present,sizeof(present));if(q)add(q,sizeof(*q));
    }
}
int main(int argc,char**argv){
    assert(argc==1||(argc==2&&!strcmp(argv[1],"snapshot")));
    bool snapshot=argc==2;float time=0;bg_reset();bg_set_players(4);
    state(time);printf("0 %.9g %016llx\n",time,(unsigned long long)hash);
    for(unsigned tick=0;tick<2400;tick++){
        if(snapshot)bg_replay_snapshot_tick(&time);
        else{
            bg_input in[BG_PLAYERS]={0};bg_replay_input(in,time);bg_set_players(4);
            bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);time+=BLAM_TICK_SECONDS;
        }
        state(time);
        if(tick==0||tick==89||tick==1079||tick==1349||tick==2249||tick==2399)
            printf("%u %.9g %016llx\n",tick+1,time,(unsigned long long)hash);
    }
}
