#ifndef BG_VI_METER_H
#define BG_VI_METER_H
#include <stdbool.h>
#include "cadence.h"

typedef struct {
    uint32_t pose_tick;
    unsigned vehicle;
    uint64_t sampled_us,completed_us;
} bg_vi_frame;
typedef struct {
    uint64_t latency_us,ready_wait_us;
    unsigned max_latency_us,max_ready_wait_us;
    unsigned flips,duplicates,gap_one,gap_two,gap_long,max_gap;
    unsigned due,missed,skipped_poses;
} bg_vi_result;
typedef struct {
    bg_cadence fresh;
    bg_vi_result result[3];
    uintptr_t previous_surface;
    uint32_t previous_pose,previous_vi;
    unsigned seen,measuring;
    volatile unsigned complete;
} bg_vi_meter;

/* Called AFTER libdragon's display callback: origin names the surface selected
 * for this retrace. Timestamps measure that selection, not a photon's emission.
 * A repeated simulation pose is counted but does not become a fresh-pose sample.
 * Every VI can count an empty scheduled deadline, including repeated surfaces. */
static inline void bg_vi_record(bg_vi_meter*m,uint64_t now,uint32_t vi,
        uintptr_t surface,const bg_vi_frame*f,bool due,bool missed){
    if(m->complete)return;
    unsigned phase=!!f->vehicle;
    if(m->measuring)for(unsigned n=0;n<2;n++){
        bg_vi_result*r=&m->result[n?1+phase:0];r->due+=due;r->missed+=missed;
    }
    if(m->seen&&surface==m->previous_surface)return;
    bool fresh=!m->seen||f->pose_tick!=m->previous_pose;
    if(m->measuring)for(unsigned n=0;n<2;n++){
        bg_vi_result*r=&m->result[n?1+phase:0];r->flips++;r->duplicates+=!fresh;
        if(fresh){
            uint32_t gap=vi-m->previous_vi;
            r->gap_one+=gap==1;r->gap_two+=gap==2;r->gap_long+=gap>2;
            if(gap>r->max_gap)r->max_gap=gap;
            uint32_t latency=(uint32_t)(now-f->sampled_us),ready=(uint32_t)(now-f->completed_us);
            r->latency_us+=latency;r->ready_wait_us+=ready;
            if(latency>r->max_latency_us)r->max_latency_us=latency;
            if(ready>r->max_ready_wait_us)r->max_ready_wait_us=ready;
            r->skipped_poses+=(uint32_t)(f->pose_tick-m->previous_pose)-1;
        }
    }
    m->previous_surface=surface;
    if(fresh){
        bg_cadence_record(&m->fresh,now,phase);
        m->previous_vi=vi;m->previous_pose=f->pose_tick;
        if(now>=m->fresh.origin+BG_CADENCE_WARMUP_US)m->measuring=1;
    }
    m->seen=1;
    if(bg_cadence_complete(&m->fresh)){
        atomic_signal_fence(memory_order_release);m->complete=1;
    }
}
static inline bool bg_vi_complete(const bg_vi_meter*m){
    unsigned complete=m->complete;atomic_signal_fence(memory_order_acquire);return complete;
}
#endif
