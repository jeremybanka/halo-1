#define bg_tick jackal_original_tick
#include "../../game.c"
#undef bg_tick
#include "../../jackal_melee_fixture.h"
static unsigned jackal_ticks;
void bg_tick(const bg_input inputs[4],float dt){
    (void)inputs;unsigned phase=jackal_ticks%45,number=jackal_ticks/45;
    if(!phase){
        unsigned rank=number/32,rotation=(number/8)%4,mode=number%8;
        debugf("JACKAL_MELEE START case=%u rank=%u rotation=%u mode=%u\n",number,rank,rotation,mode);
        jackal_melee_case(rank,mode,rotation);
        debugf("JACKAL_MELEE PASS case=%u health=%.4f shield=%.4f\n",number,bg_players[4].health,bg_players[4].shield);
    }
    bg_input in[4]={0};jackal_original_tick(in,dt);
    if(number==63&&phase==30)debugf("JACKAL_MELEE_QA PASS cases=64\n");
    jackal_ticks++;
}
