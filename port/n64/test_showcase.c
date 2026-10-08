#include "showcase.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void){
    for(unsigned kind=0;kind<BG_SHOWCASE_COUNT;kind++){
        bg_showcase_begin(kind);unsigned active=bg_player_count();
        for(unsigned p=0;p<active;p++)assert(bg_players[p].health==100&&bg_players[p].shield==100);
        unsigned frames=(unsigned)(bg_showcase_duration()*30),victims=0,needle_hits=0,needle_bursts=0;
        float passed_at=-1;int first_death_frame=-1;
        for(unsigned f=0;f<frames;f++){
            bg_input in[4];bg_showcase_input(in,f/30.f);bg_clear_events();bg_tick(in,1.f/30);bg_showcase_observe();
            for(unsigned p=0;p<active;p++)for(unsigned a=0;a<3;a++)assert(isfinite(bg_players[p].pos[a]));
            for(unsigned e=0;e<bg_event_count;e++){
                const bg_event*event=&bg_events[e];
                if(event->kind==BG_EVENT_DIE){
                    victims|=1u<<event->player;
                    if(first_death_frame<0)first_death_frame=f;
                    if(kind==BG_SHOWCASE_FRAG_DOUBLE_KILL)assert((int)f==first_death_frame);
                }
                if(event->kind==BG_EVENT_SUPERCOMBINE||event->kind==BG_EVENT_NEEDLE_HIT)assert(event->player==0&&event->amount==1);
                if(event->kind==BG_EVENT_NEEDLE_HIT)needle_hits++;
                if(event->kind==BG_EVENT_EXPLOSION&&event->weapon==BG_EXPLOSION_NEEDLER){
                    assert(kind==BG_SHOWCASE_NEEDLER_SUPERCOMBINE&&needle_hits==7);
                    assert(event->player==0&&event->amount==1.25f);needle_bursts++;
                }
            }
            if(passed_at<0&&bg_showcase_telemetry()->passed)passed_at=f/30.f;
            if(kind==BG_SHOWCASE_WARTHOG_PASSENGER&&bg_players[1].vehicle>=0){assert(bg_players[1].seat==2);assert(bg_vehicles[bg_players[1].vehicle].occupants[1]==-1);}
        }
        const bg_showcase_stats*s=bg_showcase_telemetry();
        printf("%s: pass %.2fs, shots%u kills%u score%d grenade%u boards%u super%u hits%u turn%.3f travel%.2f altitude%.2f seats%u/%u\n",bg_showcase_title(),passed_at,s->shots,s->kills,bg_players[0].score,s->grenades,s->boardings,s->supercombines,s->needle_hits,s->maximum_homing_turn,s->traveled,s->maximum_altitude,s->driver_frames,s->passenger_frames);
        assert(s->passed);assert(passed_at<=bg_showcase_duration()-6);
        if(kind==BG_SHOWCASE_FRAG_DOUBLE_KILL)assert(s->double_kills==1&&s->grenades==1&&s->kills==2&&victims==6&&bg_players[0].score==2);
        if(kind==BG_SHOWCASE_SHOTGUN_KILL)assert(s->shots==1&&victims==2&&bg_players[0].score==1);
        if(kind==BG_SHOWCASE_NEEDLER_SUPERCOMBINE)assert(s->supercombines==1&&s->needle_hits==7&&victims==2&&bg_players[0].score==1);
        assert(needle_bursts==(kind==BG_SHOWCASE_NEEDLER_SUPERCOMBINE?1u:0u));
        if(kind==BG_SHOWCASE_NEEDLER_HOMING)assert(s->shots==1&&s->needle_hits==1&&victims==0);
        for(unsigned p=1;p<active;p++)assert(bg_players[p].score==0);
    }
    puts("PASS: six live-rule showcases, full starting shields/health, actual projectile/kill/seat/flight telemetry");
}
