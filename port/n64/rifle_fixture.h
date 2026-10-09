#ifndef BG_RIFLE_FIXTURE_H
#define BG_RIFLE_FIXTURE_H
/* Explicit historical test loadout, independent of the map's Slayer preset. */
#include "game.h"
static void bg_fixture_rifle_loadout(unsigned i){
    bg_player*p=&bg_players[i];p->slot=0;p->inventory[0]=p->weapon=BG_W_AR;p->inventory[1]=BG_W_PISTOL;
    p->magazines[0]=p->ammo=60;p->reserves[0]=p->reserve=240;
    p->magazines[1]=12;p->reserves[1]=60;p->grenades[0]=p->grenades[1]=2;
    p->weapon_ready=p->cooldown=0;
}
#endif
