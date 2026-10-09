#ifndef BG_FIRSTPERSON_SERVICE_H
#define BG_FIRSTPERSON_SERVICE_H
#include <math.h>
#include "game.h"
#include "interaction_poses.h"
/* Gameplay retains CE's empty-reload timer even for a partial magazine.
 * Visual reload-full finishes at its own rate, holding its terminal pose.
 * Heat cooling is 0.2/sec; the last source exit clip leads into unlock at .15. */
static inline int bg_firstperson_service(const bg_player*p,float*seconds,bool*loop){
    *loop=false;
    if(p->reload>0){
        *seconds=p->anim_time;
        if(p->weapon==BG_W_AR)return BG_SERVICE_AR;
        if(p->weapon==BG_W_PISTOL)return p->ammo?BG_SERVICE_PISTOL_FULL:BG_SERVICE_PISTOL_EMPTY;
        if(p->weapon==BG_W_SNIPER)return p->ammo?BG_SERVICE_SNIPER_FULL:BG_SERVICE_SNIPER_EMPTY;
        if(p->weapon==BG_W_ROCKET)return p->ammo?BG_SERVICE_ROCKET_FULL:BG_SERVICE_ROCKET_EMPTY;
    }
    if((p->weapon==BG_W_PLASMA_PISTOL||p->weapon==BG_W_PLASMA_RIFLE)&&p->overheated){
        float elapsed=fmaxf(0,(1-p->heat)/.2f),remaining=fmaxf(0,(p->heat-.15f)/.2f);
        bool rifle=p->weapon==BG_W_PLASMA_RIFLE;
        int exit=rifle?BG_SERVICE_RIFLE_EXIT:BG_SERVICE_HEAT_EXIT;
        int enter=rifle?BG_SERVICE_RIFLE_ENTER:p->overheat_charged[p->slot]?BG_SERVICE_HEAT_CHARGED:BG_SERVICE_HEAT_ENTER;
        if(remaining<bg_service_poses[exit].duration){
            *seconds=bg_service_poses[exit].duration-remaining;return exit;
        }
        if(elapsed<bg_service_poses[enter].duration){*seconds=elapsed;return enter;}
        *loop=true;*seconds=elapsed-bg_service_poses[enter].duration;return rifle?BG_SERVICE_RIFLE_LOOP:BG_SERVICE_HEAT_LOOP;
    }
    return -1;
}
#endif
