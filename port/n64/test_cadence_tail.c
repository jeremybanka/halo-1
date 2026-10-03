#include "cadence_tail.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static bg_cadence cadence;
static bg_cadence_tail tail,saved;
int main(void){
    bg_cadence_frame frame={.sim_ms=11,.triangles=222,.vertices=444,
        .category_triangles={10,20,30,40,50,72},.vehicle_mask=3,.zoom_mask=4,.dead_mask=8};
    bg_cadence_record_with_tail(&cadence,&tail,0,0,&frame);
    bg_cadence_record_with_tail(&cadence,&tail,1000000,0,&frame);
    assert(tail.count==0);
    uint64_t now=1000000;
    for(unsigned i=0;i<20;i++){
        frame.sim_ms=i;
        bg_cadence_record_with_tail(&cadence,&tail,now+=(i*7%20+1)*1000,i&1,&frame);
    }
    assert(tail.count==8);
    for(unsigned i=0;i<8;i++){
        assert(tail.entry[i].elapsed==(20-i)*1000);
        assert(tail.entry[i].frame.sim_ms*7%20+1==20-i);
        assert(tail.entry[i].frame.vertices==444&&tail.entry[i].frame.category_triangles[5]==72);
        assert(tail.entry[i].frame.vehicle_mask==3&&tail.entry[i].frame.zoom_mask==4&&tail.entry[i].frame.dead_mask==8);
    }
    frame.vertices=999;assert(tail.entry[0].frame.vertices==444); /* value copy */
    frame.sim_ms=12345;
    while(!bg_cadence_complete(&cadence))
        bg_cadence_record_with_tail(&cadence,&tail,now+=40000,1,&frame);
    assert(tail.entry[0].elapsed==40000&&tail.entry[0].frame.sim_ms==12345);
    memcpy(&saved,&tail,sizeof(tail));
    bg_cadence_record_with_tail(&cadence,&tail,now+90000000,0,&frame);
    assert(!memcmp(&tail,&saved,sizeof(tail)));
    bg_cadence_finish(&cadence);
    puts("Top-eight RDP tail ranking, copied frame metadata, warmup and publication pass");
}
