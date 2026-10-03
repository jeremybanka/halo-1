#ifndef BG_RENDER_PACING_H
#define BG_RENDER_PACING_H
#include <stdbool.h>
#include <stdint.h>
#include "blam/runtime.h"
#ifndef BG_PACED30_BUFFERS
#define BG_PACED30_BUFFERS 3
#endif
#if BG_PACED30_BUFFERS != 3 && BG_PACED30_BUFFERS != 4 && BG_PACED30_BUFFERS != 5
#error "Paced presentation supports three, four or five display surfaces"
#endif

/* N-1 completed surfaces can wait while one is scanned out; prefill stays two.
 * The caller
 * owns display_show; this state machine never releases or discards a surface.
 * IRQ callbacks serialize complete/VI; main must mask IRQs around mode changes. */
typedef struct {
    uint8_t queue[BG_PACED30_BUFFERS-1],count;
    bool enabled,started,due,missed;
    uint32_t next_vi;
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
    uint8_t peak;
#endif
} bg_present30;

static inline bool bg_present30_complete(bg_present30*p,unsigned id){
    if(id>=BG_PACED30_BUFFERS||p->count>=BG_PACED30_BUFFERS-1)return false;
    for(unsigned i=0;i<p->count;i++)if(p->queue[i]==id)return false;
    p->queue[p->count++]=(uint8_t)id;
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
    if(p->count>p->peak)p->peak=p->count;
#endif
    return true;
}
static inline int bg_present30_pop(bg_present30*p){
    if(!p->count)return -1;
    unsigned id=p->queue[0];p->count--;
#if BG_PACED30_BUFFERS == 3
    if(p->count)p->queue[0]=p->queue[1];
#else
    for(unsigned i=0;i<p->count;i++)p->queue[i]=p->queue[i+1];
#endif
    return (int)id;
}

/* Four or five surfaces permit FRONT + old SDK READY + two new held frames.
 * Therefore prefill alone cannot establish a clean pacing boundary. Track
 * submitted ownership until VI_ORIGIN proves each predecessor was shown.
 * Caller serializes updates with IRQs and gates acquisition while draining. */
typedef struct {
    uint8_t outstanding,ready,draining;
    bool have_flip;
    uint32_t last_flip_vi;
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
    uint8_t peak_outstanding,peak_ready;
#endif
} bg_present30_tracker;
static inline unsigned bg_present30_bitcount(unsigned bits){
    unsigned count=0;while(bits){bits&=bits-1;count++;}return count;
}
static inline bool bg_present30_track_submit(volatile bg_present30_tracker*t,unsigned id){
    if(id>=BG_PACED30_BUFFERS||(t->outstanding&(1u<<id)))return false;
    t->outstanding|=1u<<id;
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
    unsigned count=bg_present30_bitcount(t->outstanding);
    if(count>t->peak_outstanding)t->peak_outstanding=count;
#endif
    return true;
}
static inline bool bg_present30_track_release(volatile bg_present30_tracker*t,unsigned id){
    if(id>=BG_PACED30_BUFFERS||!(t->outstanding&(1u<<id))||(t->ready&(1u<<id)))return false;
    t->ready|=1u<<id;
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
    unsigned count=bg_present30_bitcount(t->ready);
    if(count>t->peak_ready)t->peak_ready=count;
#endif
    return true;
}
static inline void bg_present30_track_observe(volatile bg_present30_tracker*t,unsigned id,uint32_t vi){
    if(id>=BG_PACED30_BUFFERS||!(t->ready&(1u<<id)))return;
    unsigned keep=~(1u<<id);
    t->ready&=keep;t->outstanding&=keep;t->draining&=keep;
    t->last_flip_vi=vi;t->have_flip=true;
}
static inline void bg_present30_track_begin_drain(volatile bg_present30_tracker*t){t->draining=t->outstanding;}
static inline void bg_present30_track_cancel_drain(volatile bg_present30_tracker*t){t->draining=0;}
static inline bool bg_present30_track_start_blocked(const volatile bg_present30_tracker*t,uint32_t vi){
    return t->draining||(t->have_flip&&(int32_t)(vi-t->last_flip_vi)<2);
}
static inline int bg_present30_vi(bg_present30*p,uint32_t vi){
    p->due=p->missed=false;
    if(!p->enabled)return -1;
    if(!p->started){
        if(p->count<2)return -1;
        p->started=true;p->next_vi=vi;
    }
    if((int32_t)(vi-p->next_vi)<0)return -1;
    /* Never release consecutive frames to catch up after a missed deadline. */
    p->next_vi=vi+2;p->due=true;
    int id=bg_present30_pop(p);p->missed=id<0;return id;
}

/* Preserve every elapsed simulation tick while waiting before acquisition.
 * The original local clock intentionally limits one update to seven ticks;
 * short chunks retain its arithmetic without losing a long wait's backlog. */
static inline unsigned bg_paced_clock_update(blam_clock*c,uint64_t elapsed_us){
    unsigned ticks=0;
    while(elapsed_us>100000){ticks+=blam_clock_update(c,.1f);elapsed_us-=100000;}
    return ticks+blam_clock_update(c,(float)elapsed_us*.000001f);
}
/* Apply the original local game's seven-tick per-render catch-up ceiling to
 * the TOTAL wait, not separately to each poll. Return discarded excess ticks.
 * The caller clears leftover_dt at acquisition if any overflow occurred. */
static inline unsigned bg_paced_clock_accumulate(blam_clock*c,uint64_t elapsed_us,unsigned*pending){
    unsigned produced=bg_paced_clock_update(c,elapsed_us);
    unsigned accepted=produced<7-*pending?produced:7-*pending;
    unsigned dropped=produced-accepted;
    *pending+=accepted;c->ticks-=dropped;
    return dropped;
}
#endif
