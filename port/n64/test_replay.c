#include "replay.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void){
    unsigned shots=0,kills=0,boarding=0,weapon_mask=0,vehicle_mask=0,gunner=0;
    for(unsigned frame=0;frame<4500;frame++){
        bg_input in[4];bg_replay_input(in,frame/30.f);bg_tick(in,1.f/30);
        for(unsigned e=0;e<bg_event_count;e++){
            bg_event*event=&bg_events[e];if(event->kind==BG_EVENT_FIRE){shots++;weapon_mask|=1u<<event->weapon;}
            if(event->kind==BG_EVENT_DIE)kills++;
            if(event->kind==BG_EVENT_ENTER)boarding++;
        }
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];for(int a=0;a<3;a++)assert(isfinite(q->pos[a]));
            if(q->vehicle>=0){vehicle_mask|=1u<<bg_vehicles[q->vehicle].kind;if(q->seat==1&&bg_vehicles[q->vehicle].kind==BG_V_WARTHOG)gunner++;}
        }
        bg_clear_events();
        if(frame%450==0)printf("%3u s seats %d/%d/%d/%d health %d/%d/%d/%d shots %u deaths %u\n",frame/30,
            bg_players[0].vehicle,bg_players[1].vehicle,bg_players[2].vehicle,bg_players[3].vehicle,
            bg_players[0].health,bg_players[1].health,bg_players[2].health,bg_players[3].health,shots,kills);
    }
    printf("Replay: %u shots, %u deaths, %u boardings, weapon mask 0x%x, vehicle mask 0x%x, gunner frames %u\n",shots,kills,boarding,weapon_mask,vehicle_mask,gunner);
    assert(shots>100&&kills>5&&boarding>=8);assert((weapon_mask&255)==255);assert(vehicle_mask==15);assert(gunner>0);
    puts("PASS: two replay loops, eight Xbox weapons, four vehicles, actual combat/deaths/boarding, Warthog gunner");
}
