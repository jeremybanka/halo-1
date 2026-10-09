#include "effects_qa.h"
#include "weapon_effects.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void){
    bg_reset();bg_fx_reset();
    for(unsigned p=1;p<4;p+=2){
        float old=bg_floor(p*1.8f,4,100)+.015f,actual=bg_floor(p*1.1f,4+p*.8f,100);
        printf("Former P%u staging: feet %.4f, moved-position floor %.4f (%.4f below floor)\n",p+1,old,actual,actual-old);
    }
    for(unsigned tick=0;tick<3000;tick++){
        bg_input in[4];bg_effects_qa_input(in,tick/30.f);bg_clear_events();bg_tick(in,1.f/30);bg_fx_update(1.f/30);
        for(unsigned p=0;p<4;p++){
            const bg_player*q=&bg_players[p];float floor=bg_floor(q->pos[0],q->pos[2],100);
            if(!(q->health>0&&q->respawn==0&&floor>-999&&q->pos[1]>=floor-.025f))fprintf(stderr,"tick %u player %u health %f respawn %f feet %f floor %f\n",tick,p,q->health,q->respawn,q->pos[1],floor);
            assert(q->health>0&&q->respawn==0&&floor>-999&&q->pos[1]>=floor-.025f);
        }
    }
    puts("PASS: two complete effects cycles, all four players stay above terrain with no deaths or stuck respawns");
}
