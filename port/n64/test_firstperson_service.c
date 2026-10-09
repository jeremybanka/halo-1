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
    p.reload=0;p.weapon=BG_W_PLASMA_PISTOL;p.overheated=true;p.heat=1;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_ENTER&&seconds==0&&!loop);
    p.overheat_charged[0]=true;
    assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_CHARGED);
    p.heat=.65f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_LOOP&&loop);
    p.heat=.2f;assert(bg_firstperson_service(&p,&seconds,&loop)==BG_SERVICE_HEAT_EXIT&&!loop&&seconds>0);
    p.overheated=false;assert(bg_firstperson_service(&p,&seconds,&loop)==-1);
    p.overheated=true;p.weapon=BG_W_AR;assert(bg_firstperson_service(&p,&seconds,&loop)==-1);
    puts("PASS: full/empty reload selection, native clocks, normal/charged overheat entry, vent loop, exit and cancellation");
}
