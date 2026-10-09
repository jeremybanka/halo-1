#include <assert.h>
#include <stdio.h>
#include "firstperson_service.h"
int main(void){
    bg_player p={0};float seconds;bool loop;
    p.weapon=BG_W_AR;p.reload=1;p.anim_time=1.25;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_AR&&!loop&&seconds==1.25f);
    p.weapon=BG_W_ROCKET;p.ammo=0;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_ROCKET_EMPTY);
    p.ammo=1;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_ROCKET_FULL);
    p.weapon=BG_W_PISTOL;p.ammo=0;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_PISTOL_EMPTY);
    p.ammo=3;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_PISTOL_FULL);
    p.weapon=BG_W_SNIPER;p.ammo=0;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_SNIPER_EMPTY);
    p.ammo=2;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_SNIPER_FULL);
    p.reload=0;p.weapon=BG_W_PLASMA_PISTOL;p.overheated=true;p.heat=1;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_ENTER&&seconds==0&&!loop);
    p.overheat_charged[0]=true;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_CHARGED);
    p.heat=.65f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_LOOP&&loop);
    p.heat=.2f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_EXIT&&!loop&&seconds>0);
    p.overheated=false;assert(bg_firstperson_service(&p,&seconds,&loop)==-1);
    p.overheated=true;p.weapon=BG_W_AR;assert(bg_firstperson_service(&p,&seconds,&loop)==-1);
    p.weapon=BG_W_PLASMA_RIFLE;p.heat=1;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_RIFLE_ENTER&&seconds==0&&!loop);
    p.heat=.55f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_RIFLE_LOOP&&loop);
    p.heat=.2f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_RIFLE_EXIT&&!loop&&seconds>0);
    // Cooling must run forward within each state, with the final frame at recovery.
    int prev=-1;float last=-1;
    for(int tick=0;tick<128;tick++){
        p.heat=1-tick/150.f;int state=bg_firstperson_service(&p,&seconds,&loop);
        assert(state>=BG_SERVICE_RIFLE_ENTER&&state<=BG_SERVICE_RIFLE_EXIT);
        if(state==prev)assert(seconds>=last);
        else assert(state>prev);
        prev=state;last=seconds;
    }
    p.overheated=false;assert(bg_firstperson_service(&p,&seconds,&loop)==-1);
    puts("PASS: full/empty reload selection, native clocks, normal/charged overheat entry, vent loop, exit and cancellation");
}
