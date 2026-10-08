#include "weapon_effects.h"
#include <math.h>
#include <string.h>
bg_fx_shot bg_fx_shots[4];
bg_fx_trail bg_fx_trails[BG_FX_TRAILS];
bg_fx_vehicle_burst bg_fx_vehicle_bursts[4];
static unsigned next_trail,next_burst;
void bg_fx_reset(void){
    memset(bg_fx_shots,0,sizeof(bg_fx_shots));memset(bg_fx_trails,0,sizeof(bg_fx_trails));next_trail=0;
    for(unsigned p=0;p<4;p++){bg_fx_shots[p].age=100;bg_fx_shots[p].weapon=-1;}
    memset(bg_fx_vehicle_bursts,0,sizeof(bg_fx_vehicle_bursts));next_burst=0;
    for(unsigned i=0;i<4;i++)bg_fx_vehicle_bursts[i].age=100;
}
void bg_fx_update(float dt){
    for(unsigned i=0;i<4;i++)bg_fx_vehicle_bursts[i].age=fminf(100,bg_fx_vehicle_bursts[i].age+dt);
    for(unsigned p=0;p<4;p++)bg_fx_shots[p].age=fminf(100,bg_fx_shots[p].age+dt);
    for(unsigned i=0;i<BG_FX_TRAILS;i++)if(bg_fx_trails[i].active){
        bg_fx_trails[i].age+=dt;if(bg_fx_trails[i].age>=BG_FX_TRAIL_LIFE)bg_fx_trails[i].active=false;
    }
    for(unsigned i=0;i<bg_event_count;i++){
        const bg_event*e=&bg_events[i];
        if(e->kind==BG_EVENT_VEHICLE_DESTROYED){
            bg_fx_vehicle_burst*b=&bg_fx_vehicle_bursts[next_burst++%4];
            memcpy(b->origin,e->pos,sizeof(b->origin));b->age=0;b->kind=e->weapon;b->vehicle=(int)e->amount;
        }
        if(e->kind!=BG_EVENT_FIRE||e->player<0||e->player>=4||e->weapon<0||e->weapon>=BG_WEAPON_COUNT)continue;
        /* Mounted guns have their own muzzle rigs; never attach their event to
         * the infantry weapon a driver happened to have before boarding. */
        if(!bg_player_personal_weapon(&bg_players[e->player]))continue;
        bg_fx_shot*s=&bg_fx_shots[e->player];s->age=0;s->weapon=e->weapon;s->sequence++;s->charged=e->amount>1;
        if(e->weapon==BG_W_SNIPER){
            const bg_shot_trace*trace=bg_sniper_trace(e->player);
            bg_fx_trail*t=&bg_fx_trails[next_trail++%BG_FX_TRAILS];
            memcpy(t->start,trace->start,sizeof(t->start));memcpy(t->end,trace->end,sizeof(t->end));t->age=0;t->active=true;
            /* Render from the firing pose's source muzzle toward the exact
             * hit, keeping the physical ray untouched. Starting at the eye
             * would make the whole streak disappear into one reticle pixel. */
            const bg_player*p=&bg_players[e->player];
            const int16_t*m=bg_fx_marker_poses[bg_fx_marker_offsets[BG_W_SNIPER][1]][0];
            float x=m[0]/4096.f,y=m[1]/4096.f,z=m[2]/4096.f;
            float cy=cosf(p->yaw),sy=sinf(p->yaw),cp=cosf(p->pitch),sp=sinf(p->pitch);
            t->muzzle[0]=trace->start[0]+cy*(cp*x-sp*y)+sy*z;
            t->muzzle[1]=trace->start[1]+sp*x+cp*y;
            t->muzzle[2]=trace->start[2]-sy*(cp*x-sp*y)+cy*z;
            float distance=0;for(unsigned a=0;a<3;a++){float d=trace->end[a]-trace->start[a];distance+=d*d;}
            if(distance<1.f)memcpy(t->muzzle,trace->start,sizeof(t->muzzle));
        }
    }
}
float bg_fx_flash(unsigned player){
    const bg_player*p=&bg_players[player];const bg_fx_shot*s=&bg_fx_shots[player];
    if(p->health<=0||!bg_player_personal_weapon(p)||p->weapon_ready>0||p->weapon!=s->weapon||s->weapon<0)return 0;
    float life=bg_fx_definitions[s->weapon].life;
    return s->age<life?1.f-s->age/life:0;
}
float bg_fx_charge(unsigned player){
    const bg_player*p=&bg_players[player];
    if(p->health<=0||!bg_player_personal_weapon(p)||p->weapon_ready>0||p->weapon!=BG_W_PLASMA_PISTOL||p->ammo<=0||!p->fire_held||p->overheated||p->reload>0||p->melee_time>0)return 0;
    /* Runtime release threshold is .7 s. Hold the corona at full size after
     * this point; it must not blink out while the player keeps charging. */
    return fminf(1.f,p->charge/.7f);
}
