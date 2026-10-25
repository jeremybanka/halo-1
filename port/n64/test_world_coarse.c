#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include "render_cull.h"
static uint32_t seed=0x34575432;
static uint32_t next(void){seed^=seed<<13;seed^=seed>>17;return seed^=seed<<5;}
int main(void) {
    for(unsigned trial=0;trial<200000;trial++) {
        int16_t box[6],child[6];float p[6][4];uint8_t selected[6][3];
        for(unsigned a=0;a<3;a++) {
            int lo=(int)(next()%60001)-30000,width=next()%2768;
            box[a]=lo;box[a+3]=lo+width;
            child[a]=lo+next()%(width+1);child[a+3]=child[a]+next()%(box[a+3]-child[a]+1);
        }
        for(unsigned i=0;i<6;i++)for(unsigned a=0;a<4;a++)p[i][a]=((int)(next()%20001)-10000)/(a==3?1.f:4096.f);
        bg_frustum_prepare(selected,(const float(*)[4])p);
        int group=bg_frustum_classify((const float(*)[4])p,selected,box);
        bool visible=bg_frustum_box_cached((const float(*)[4])p,selected,child);
        if(group<0)assert(!visible);
        if(group>0)assert(visible);
    }
    /* Strict contact on a plane is rejected; grouping must not turn >= into >. */
    float p[6][4]={{1,0,0,0},{-1,0,0,10},{0,1,0,10},{0,-1,0,10},{0,0,1,10},{0,0,-1,10}};
    uint8_t sel[6][3];bg_frustum_prepare(sel,(const float(*)[4])p);
    int16_t box[6]={-2,-1,-1,0,1,1};assert(bg_frustum_classify((const float(*)[4])p,sel,box)==-1);
    puts("200000 union/child frustum certificates and strict plane contact passed");
}
