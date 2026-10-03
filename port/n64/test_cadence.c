#include "cadence.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static bg_cadence sample,saved;
int main(void){
    bg_cadence_record(&sample,0,0);
    bg_cadence_record(&sample,1000000,0);
    assert(sample.result[0].frames==0);
    /* Current frame determines phase; 33333 is within budget, 33334 is not. */
    bg_cadence_record(&sample,1033333,1);
    bg_cadence_record(&sample,1066667,0);
    assert(sample.result[2].frames==1&&sample.result[2].elapsed==33333);
    assert(sample.result[1].frames==1&&sample.result[1].elapsed==33334);
    assert(sample.result[2].slow_frames==0&&sample.result[1].slow_frames==1);
    uint64_t now=1066667;
    while(!bg_cadence_complete(&sample))bg_cadence_record(&sample,now+=40000,1);
    assert(sample.result[0].elapsed>=BG_CADENCE_DURATION_US);
    assert(sample.result[0].elapsed<BG_CADENCE_DURATION_US+40000);
    assert(!sample.overflow&&sample.count==sample.result[0].frames);
    memcpy(&saved,&sample,sizeof(sample));
    bg_cadence_record(&sample,now+100000000,0);
    assert(!memcmp(&saved,&sample,sizeof(sample)));
    bg_cadence_finish(&sample);
    assert(sample.result[0].p95==40000&&sample.result[2].p95==40000);
    assert(sample.result[1].p95==33334);
    assert(sample.result[0].minimum==33333&&sample.result[0].maximum==40000);
    memset(&sample,0,sizeof(sample));
    bg_cadence_record(&sample,250000000,0);
    bg_cadence_record(&sample,251000000,0);
    /* Samples may span phase boundaries and remain in timestamp order. */
    for(unsigned i=100;i;i--)bg_cadence_record(&sample,sample.previous+i*1000,i>60);
    bg_cadence_finish(&sample);
    assert(sample.result[0].frames==100&&sample.result[0].p95==95000);
    assert(sample.result[1].frames==60&&sample.result[1].p95==57000);
    assert(sample.result[2].frames==40&&sample.result[2].p95==98000);
    puts("RDP cadence warmup, completion publication, current-frame phases and quantiles pass");
}
