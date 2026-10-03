#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "firstperson_ammo_logic.h"

int main(void) {
    unsigned rounds_fired=0,regrowth_frames=0;
    for(unsigned weapon=BG_W_AR;weapon<=BG_W_NEEDLER;weapon+=BG_W_NEEDLER) {
        bg_reset();bg_set_players(4);
        assert(bg_give_weapon(0,(bg_weapon)weapon));
        bg_player*p=&bg_players[0];p->yaw=0;p->pitch=.5f;
        int initial=p->ammo,target=weapon==BG_W_AR?37:7;
        int other[3];for(unsigned j=1;j<4;j++)other[j-1]=bg_players[j].ammo;
        for(unsigned tick=0;p->ammo>target&&tick<300;tick++) {
            bg_input in[4]={0};in[0].fire=true;
            int before=p->ammo;bg_tick(in,1.f/30);
            if(p->ammo<before) {assert(p->ammo==before-1);assert(p->recoil>0);rounds_fired++;}
            unsigned digits[2];bg_ar_ammo_digits(p->ammo,digits);
            if(weapon==BG_W_AR)assert((int)(digits[0]*10+digits[1])==p->ammo);
            else assert(bg_needler_ammo_state(p->ammo,p->reserve,-1)==(unsigned)p->ammo);
            for(unsigned j=1;j<4;j++)assert(bg_players[j].ammo==other[j-1]);
        }
        assert(p->ammo==target);
        int reserve=p->reserve;bg_input in[4]={0};in[0].reload=true;bg_tick(in,1.f/30);
        assert(p->reload>0);unsigned last=(unsigned)p->ammo;
        for(unsigned tick=0;p->reload>0&&tick<150;tick++) {
            memset(in,0,sizeof(in));bg_tick(in,1.f/30);
            if(weapon==BG_W_NEEDLER&&p->reload>0) {
                /* Source reloadclip is71/30s; parent normalizes the actual
                 * 1s demake reload to that same mesh/overlay time. */
                float source_elapsed=p->anim_time*(71.f/30)/bg_weapon_defs[weapon].reload;
                unsigned state=bg_needler_ammo_state(p->ammo,p->reserve,source_elapsed);
                assert(state>=last&&state<=20);if(state>(unsigned)p->ammo)regrowth_frames++;
                last=state;
            }
        }
        assert(p->reload==0&&p->ammo==initial&&p->reserve==reserve-(initial-target));
    }
    assert(rounds_fired==36&&regrowth_frames>0);
    printf("PASS: live30Hz AR/Needler fire/recoil/reload; %u shots, %u predicted regrowth frames before real refill; other players' ammo isolated.\n",rounds_fired,regrowth_frames);
}
