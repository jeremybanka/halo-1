#include "destruction_qa.h"
#include <math.h>
#include <string.h>
static unsigned page;
const char*bg_destruction_qa_label(void){return (const char*[]){"SCRIPTED: WARTHOG DESTRUCTION","SCRIPTED: GHOST DESTRUCTION","SCRIPTED: SCORPION DESTRUCTION","SCRIPTED: BANSHEE DESTRUCTION"}[page];}
void bg_destruction_qa_input(bg_input input[4],float seconds){
    static unsigned previous=~0u;page=(unsigned)(seconds/26)%4;
    memset(input,0,4*sizeof(*input));float time=fmodf(seconds,26);
    if(page!=previous){
        previous=page;bg_reset();bg_set_players(4);bg_set_score_limit(1000);bg_vehicle_count=0;bg_pickup_count=0;
        float pos[3]={0,bg_floor(0,4,100)+.4f,4};bg_add_vehicle((bg_vehicle_kind)page,pos,.6f);
        bg_vehicles[0].health=1;
        const float offsets[4][2]={{-4.5f,0},{4.5f,0},{-3.2f,3.2f},{3.2f,-3.2f}};
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];q->pos[0]=offsets[p][0];q->pos[2]=4+offsets[p][1];q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
            memcpy(q->last_pos,q->pos,sizeof(q->pos));q->vehicle=-1;
            bg_give_weapon(p,BG_W_ROCKET);q->weapon=BG_W_ROCKET;q->inventory[q->slot]=BG_W_ROCKET;q->ammo=2;
        }
    }
    bg_vehicle*v=&bg_vehicles[0];
    /* Only the pre-shot airborne staging is held; after death the actual
     * unpowered solver must carry the Banshee down to the terrain. */
    if(page==BG_V_BANSHEE&&time<3.1f&&v->active){v->pos[1]=bg_floor(0,4,100)+3;memset(v->velocity,0,sizeof(v->velocity));v->physics_valid=false;}
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];float dx=v->pos[0]-q->pos[0],dz=v->pos[2]-q->pos[2];
        q->yaw=atan2f(-dz,dx);q->pitch=atan2f(v->pos[1]+.35f-(q->pos[1]+.62f),sqrtf(dx*dx+dz*dz));
    }
    input[0].fire=time>=3&&time<3.12f;
}
