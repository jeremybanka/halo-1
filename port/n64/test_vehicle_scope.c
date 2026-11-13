#include <stdio.h>
#include "game.c"
#include "hud_scope_under_test.inc"

int main(void){
    assert(bg_map_load(BG_MAP_BLOOD_GULCH));bg_ff_start(3);
    assert(bg_vehicles[0].kind==BG_V_WARTHOG);
    bg_player*p=&bg_players[0];p->vehicle=0;p->seat=2;p->seat_state=BG_SEAT_STABLE;
    p->health=100;p->weapon=BG_W_PISTOL;p->zoom=1;
    assert(bg_player_personal_weapon(p)&&!bg_player_third_person(p));
    assert(scoped(p)); /* Reproduces the missing shotgun overlay. */
    unsigned checked=0;
    for(int seat=-1;seat<3;seat++)for(unsigned state=0;state<3;state++)
    for(unsigned dead=0;dead<2;dead++)for(unsigned w=0;w<BG_WEAPON_COUNT;w++)for(unsigned z=0;z<3;z++){
        p->vehicle=seat<0?-1:0;p->seat=seat;p->seat_state=state;
        p->health=dead?0:100;p->weapon=w;p->zoom=z;
        bool personal=seat<0||seat==2;
        bool expected=!dead&&state==BG_SEAT_STABLE&&personal&&z&&(w==BG_W_PISTOL||w==BG_W_SNIPER);
        assert(scoped(p)==expected);checked++;
    }
    printf("PASS %u scope states: foot/driver/gunner/passenger, pistol/sniper levels, other weapons, death and seat transitions\n",checked);
}
