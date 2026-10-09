#include "destruction_qa.h"
#include "weapon_effects.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void){
    bg_fx_reset();unsigned deaths[4]={0},hidden[4]={0},visible[4]={0},gone[4]={0},respawn[4]={0};float air=0,fallen=0;
    for(unsigned tick=0;tick<26*4*30;tick++){
        float time=tick/30.f;unsigned kind=(unsigned)(time/26);bg_input in[4];bg_destruction_qa_input(in,time);
        bg_clear_events();bg_tick(in,1.f/30);bg_fx_update(1.f/30);const bg_vehicle*v=&bg_vehicles[0];
        for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_VEHICLE_DESTROYED){deaths[kind]++;assert(bg_events[e].weapon==(int)kind);if(kind==BG_V_BANSHEE)air=v->pos[1];}
        if(v->wreck_time>0){
            assert(!v->active);for(unsigned p=0;p<3;p++)assert(v->occupants[p]<0);
            if(v->wreck_time<2){if(bg_vehicle_body_visible(v))visible[kind]++;else hidden[kind]++;}
            if(kind==BG_V_BANSHEE&&v->wreck_time<5)fallen=v->pos[1];
            for(unsigned a=0;a<3;a++)assert(isfinite(v->pos[a])&&isfinite(v->velocity[a]));
        }else if(!v->active){assert(!bg_vehicle_body_present(v));gone[kind]++;}
        if(deaths[kind]&&v->active)respawn[kind]++;
        for(unsigned p=0;p<4;p++)assert(bg_players[p].health>0);
    }
    for(unsigned k=0;k<4;k++){printf("kind %u: deaths %u blink visible/hidden %u/%u removed %u respawned %u\n",k,deaths[k],visible[k],hidden[k],gone[k],respawn[k]);assert(deaths[k]==1&&hidden[k]>0&&visible[k]>0&&gone[k]>0&&respawn[k]>0);}
    printf("Banshee destroyed at %.3f, settled to %.3f\n",air,fallen);assert(air-fallen>1);
    puts("PASS: four real rocket kills, unpowered falling wreck, four blink cycles, expiry, healthy respawn and surviving observers");
}
