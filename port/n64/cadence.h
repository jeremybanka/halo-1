#ifndef BG_CADENCE_H
#define BG_CADENCE_H
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>

#define BG_CADENCE_CAPACITY 5120
#define BG_CADENCE_WARMUP_US 1000000ULL
#define BG_CADENCE_DURATION_US 75000000ULL
typedef struct {
    uint64_t elapsed;
    unsigned frames,slow_frames,minimum,maximum,p95;
} bg_cadence_result;
typedef struct {
    uint32_t samples[BG_CADENCE_CAPACITY];
    uint64_t origin,previous;
    unsigned started,count,overflow;
    /* Single interrupt writer publishes once; the main loop then owns sorting. */
    volatile unsigned complete;
    bg_cadence_result result[3];
} bg_cadence;

/* Called only by the RDP completion interrupt. No allocation, sorting, logging,
 * floating-point work or waits. Each interval belongs to the frame completing
 * NOW, so a phase transition is not attributed to the preceding frame. */
static inline void bg_cadence_record(bg_cadence*c,uint64_t now,unsigned vehicle) {
    if(c->complete)return;
    if(!c->started){c->started=1;c->origin=c->previous=now;return;}
    uint64_t previous=c->previous;c->previous=now;
    if(previous<c->origin+BG_CADENCE_WARMUP_US)return;
    uint32_t elapsed=(uint32_t)(now-previous);vehicle=!!vehicle;
    if(c->count<BG_CADENCE_CAPACITY)c->samples[c->count++]=elapsed|(vehicle<<31);
    else c->overflow++;
    for(unsigned i=0;i<2;i++){
        bg_cadence_result*r=&c->result[i?1+vehicle:0];
        if(!r->frames||elapsed<r->minimum)r->minimum=elapsed;
        if(elapsed>r->maximum)r->maximum=elapsed;
        r->frames++;r->elapsed+=elapsed;r->slow_frames+=elapsed>33333;
    }
    if(c->result[0].elapsed>=BG_CADENCE_DURATION_US){
        atomic_signal_fence(memory_order_release);
        c->complete=1;
    }
}
static inline unsigned bg_cadence_complete(const bg_cadence*c){
    unsigned complete=c->complete;
    atomic_signal_fence(memory_order_acquire);
    return complete;
}
static int bg_cadence_compare(const void*a,const void*b){
    uint32_t x=*(const uint32_t*)a&0x7fffffff,y=*(const uint32_t*)b&0x7fffffff;
    return (x>y)-(x<y);
}
/* Main-thread only, after bg_cadence_complete(). */
static inline void bg_cadence_finish(bg_cadence*c){
    qsort(c->samples,c->count,sizeof(c->samples[0]),bg_cadence_compare);
    unsigned seen[3]={0};
    for(unsigned n=0;n<c->count;n++)for(unsigned i=0;i<2;i++){
        unsigned index=i?1+(c->samples[n]>>31):0;
        if(++seen[index]==(c->result[index].frames*95+99)/100)
            c->result[index].p95=c->samples[n]&0x7fffffff;
    }
}
#endif
