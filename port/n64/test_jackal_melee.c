#include <stdio.h>
#include "game.c"
#include "jackal_melee_fixture.h"
#ifdef BG_PVE_ROSTER
#include "test_jackal_shield.inc"
#endif
int main(void){
    assert(bg_map_load(BG_MAP_BLOOD_GULCH));unsigned cases=0;
    for(unsigned rank=0;rank<
#ifdef BG_PVE_ROSTER
    2
#else
    1
#endif
    ;rank++)for(unsigned rotation=0;rotation<4;rotation++)for(unsigned mode=0;mode<8;mode++){
        printf("MELEE rank=%u rotation=%u mode=%u\n",rank,rotation,mode);fflush(stdout);
        jackal_melee_case(rank,mode,rotation);cases++;
    }
    printf("PASS %u actual melee attacks: shield face, depleted shield, exposed body, backstabs and four actor yaws\n",cases);
#ifdef BG_PVE_ROSTER
    jackal_shield_acceptance();
#endif
}
