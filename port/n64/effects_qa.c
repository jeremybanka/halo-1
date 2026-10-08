#include "effects_qa.h"
#include <math.h>
#include <string.h>
static unsigned page;
const char*bg_effects_qa_label(void){return (const char*[]){"SCRIPTED: AR / MAGNUM / SHOTGUN / SNIPER","SCRIPTED: PLASMA / RIFLE / NEEDLER / ROCKET","SCRIPTED: CHARGE / HOLD / RELEASE","SCRIPTED: WORLD MUZZLES / SNIPER TRAILS"}[page];}
void bg_effects_qa_input(bg_input input[4],float seconds){
    static unsigned previous=~0u;
    page=(unsigned)(seconds/10)%4;
    memset(input,0,4*sizeof(*input));
    if(page!=previous){
        previous=page;bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];q->pos[0]=p*1.8f;q->pos[2]=4;q->pos[1]=bg_floor(q->pos[0],4,100)+.015f;
            q->yaw=-1.5707963f;q->pitch=.04f;q->vehicle=-1;
            int w=page==0?(int[]){BG_W_AR,BG_W_PISTOL,BG_W_SHOTGUN,BG_W_SNIPER}[p]:page==1?(int[]){BG_W_PLASMA_PISTOL,BG_W_PLASMA_RIFLE,BG_W_NEEDLER,BG_W_ROCKET}[p]:page==2?BG_W_PLASMA_PISTOL:(int[]){BG_W_AR,BG_W_SNIPER,BG_W_PLASMA_PISTOL,BG_W_NEEDLER}[p];
            bg_give_weapon(p,w);q->weapon=w;q->inventory[q->slot]=w;q->ammo=bg_weapon_defs[w].magazine;
            if(page==3){
                q->pos[0]=(float[]){0,1.2f,3,4.6f}[p];q->pos[2]=(float[]){4,6,5.4f,7}[p];
                q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;q->yaw=(float[]){-1.1f,0,-1.5707963f,-.3f}[p];
            }
            memcpy(q->last_pos,q->pos,sizeof(q->pos));
        }
    }
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->health=100;q->shield=100;q->ammo=bg_weapon_defs[q->weapon].magazine;q->reserve=999;
        if(q->heat>.85f){q->heat=0;q->overheated=false;}
        float phase=fmodf(seconds+(page==2?p*.45f:0),page==2?3.5f:1.5f);
        input[p].fire=page==3&&p==0?false:page==2?phase<2.5f:page==1&&p==0?phase<.8f:page==3&&p==2?phase<1.2f:phase<(bg_weapon_defs[q->weapon].automatic?.5f:.16f);
    }
}
