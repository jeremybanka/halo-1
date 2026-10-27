#ifndef BG_PHOTO_TOUR_H
#define BG_PHOTO_TOUR_H
/* Diagnostic single-player walks. Starts are original Sidewinder placements;
 * every subsequent position comes from the production movement/collision tick.
 * Each photo is reconstructed from reset, inputs, and a fixed simulation tick. */
#include "game.h"
#include "map.h"
#include "terrain.h"
#include "movement.h"
#include <string.h>
typedef struct { unsigned start; float yaw, pitch; const char *label; } bg_photo_station;
static const bg_photo_station bg_photo_stations[]={
    {14,1.3f,-.04f,"WEST BASE EXIT"}, {28,1.8f,-.04f,"EAST BASE EXIT"},
    {71,1.1f,.10f,"WEST APPROACH"}, {70,2.0f,.10f,"EAST APPROACH"},
    {65,-.25f,.08f,"WEST CANYON"}, {63,3.0f,.08f,"EAST CANYON"},
    {66,-.6f,.02f,"WEST BEND"}, {64,-2.55f,.02f,"EAST BEND"},
    {54,1.45f,-.08f,"UPPER WEST PASS"}, {55,1.7f,-.08f,"UPPER EAST PASS"},
    {0,1.5f,-.18f,"WEST BASE ROOF"}, {62,1.6f,-.18f,"EAST BASE ROOF"}
};
#define BG_PHOTO_COUNT (sizeof(bg_photo_stations)/sizeof(bg_photo_stations[0])*2)
static unsigned bg_photo_ticks(unsigned photo){return (photo&1)?180:90;}
static void bg_photo_begin(unsigned photo){
    const bg_photo_station*s=&bg_photo_stations[photo/2];
    bg_set_players(1);bg_reset();bg_set_score_limit(1000);
    bg_player*q=&bg_players[0];
    memcpy(q->pos,bg_spawns[s->start].pos,12);
    q->pos[1]=bg_floor(q->pos[0],q->pos[2],q->pos[1]+.5f)+.015f;
    memcpy(q->last_pos,q->pos,12);memset(q->velocity,0,12);
    q->yaw=s->yaw;q->pitch=s->pitch;q->vy=0;q->grounded=true;
    q->climbing=false;q->vehicle=-1;q->zoom=0;
}
static void bg_photo_input(unsigned photo,unsigned tick,bg_input in[4]){
    memset(in,0,sizeof(bg_input)*4);
    unsigned walk=bg_photo_ticks(photo)-30;
    if(tick<walk){in[0].forward=.65f;in[0].strafe=(photo/2&1)?.1f:-.1f;}
    /* The second frame is a crouched, oblique inspection after a longer walk. */
    if(photo&1){
        in[0].crouch=tick>=walk;
        if(tick>=walk&&tick<walk+15)in[0].turn=(photo/2&1)?-.18f:.18f;
    }
}
#endif
