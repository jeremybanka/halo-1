#include "render_pacing.h"
#include "vi_meter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void queue_test(void){
    bg_present30 p={.enabled=true};
    assert(!bg_present30_complete(&p,BG_PACED30_BUFFERS));
    assert(bg_present30_vi(&p,10)==-1&&!p.due);
    assert(bg_present30_complete(&p,1));
    assert(!bg_present30_complete(&p,1));
    assert(bg_present30_vi(&p,11)==-1&&!p.due);
    assert(bg_present30_complete(&p,2));
#if BG_PACED30_BUFFERS == 3
    assert(!bg_present30_complete(&p,0));
#endif
    assert(bg_present30_vi(&p,12)==1&&p.due&&!p.missed);
    assert(bg_present30_vi(&p,13)==-1&&!p.due);
    assert(bg_present30_vi(&p,14)==2);
    assert(bg_present30_vi(&p,16)==-1&&p.due&&p.missed);
    assert(bg_present30_complete(&p,0));
    assert(bg_present30_vi(&p,17)==-1&&!p.due);
    assert(bg_present30_vi(&p,18)==0&&!p.missed);
    /* Mode exits must drain every locked surface, never discard it. */
    assert(bg_present30_complete(&p,1));assert(bg_present30_complete(&p,2));
    assert(bg_present30_pop(&p)==1);assert(bg_present30_pop(&p)==2);
    assert(bg_present30_pop(&p)==-1);
    p=(bg_present30){.enabled=true};
    assert(bg_present30_complete(&p,1));assert(bg_present30_complete(&p,2));
    assert(bg_present30_vi(&p,UINT32_MAX-1)==1);
    assert(bg_present30_vi(&p,UINT32_MAX)==-1);
    assert(bg_present30_vi(&p,0)==2);
    assert(bg_present30_complete(&p,0));
    assert(bg_present30_vi(&p,20)==0); /* late callback does not trigger catch-up */
    assert(bg_present30_complete(&p,1));
    assert(bg_present30_vi(&p,21)==-1);
    assert(bg_present30_vi(&p,22)==1);
    p=(bg_present30){.enabled=true};
    for(unsigned id=1;id<BG_PACED30_BUFFERS;id++)assert(bg_present30_complete(&p,id));
    assert(!bg_present30_complete(&p,0));
    for(unsigned id=1;id<BG_PACED30_BUFFERS;id++)assert(bg_present30_pop(&p)==(int)id);
    assert(bg_present30_pop(&p)==-1);
}

static void tracker_test(void){
    bg_present30_tracker t={0};
    assert(!bg_present30_track_submit(&t,BG_PACED30_BUFFERS));
    assert(!bg_present30_track_release(&t,1));
    for(unsigned id=1;id<BG_PACED30_BUFFERS;id++){
        assert(bg_present30_track_submit(&t,id));
        assert(!bg_present30_track_submit(&t,id));
    }
    bg_present30_track_begin_drain(&t);
    assert(bg_present30_track_start_blocked(&t,10));
    for(unsigned id=1;id<BG_PACED30_BUFFERS;id++){
        assert(bg_present30_track_release(&t,id));
        assert(!bg_present30_track_release(&t,id));
        bg_present30_track_observe(&t,id,UINT32_MAX);
    }
    assert(!t.outstanding&&!t.ready&&!t.draining);
    assert(bg_present30_track_start_blocked(&t,0));
    assert(!bg_present30_track_start_blocked(&t,1));
    /* Repeated origin observations must not extend the startup deadline. */
    bg_present30_track_observe(&t,1,1);
    assert(t.last_flip_vi==UINT32_MAX);
    assert(bg_present30_track_submit(&t,1));
    bg_present30_track_begin_drain(&t);bg_present30_track_cancel_drain(&t);
    assert(!t.draining&&t.outstanding==(1u<<1));
}

static void clock_test(void){
    blam_clock c;blam_clock_reset(&c);
    assert(bg_paced_clock_update(&c,2500000)==75);
    assert(c.ticks==75);
    c.paused=true;assert(bg_paced_clock_update(&c,5000000)==0&&c.ticks==75);
    c.paused=false;
    unsigned total=0;
    for(unsigned i=0;i<10000;i++)total+=bg_paced_clock_update(&c,1000);
    assert(total>=299&&total<=300);assert(c.ticks==75+total);
    assert(bg_paced_clock_update(&c,0)==0);
    blam_clock_reset(&c);unsigned pending=0,dropped=0;
    for(unsigned i=0;i<2500;i++)dropped+=bg_paced_clock_accumulate(&c,1000,&pending);
    assert(pending==7&&c.ticks==7&&dropped>=67&&dropped<=68);
    c.leftover_dt=0; /* acquisition after an overflow, exactly as main */
    pending=0;
    assert(bg_paced_clock_accumulate(&c,2500000,&pending)==68);
    assert(pending==7&&c.ticks==14);
}

static bg_vi_meter meter;
static void vi_test(bool duplicate){
    memset(&meter,0,sizeof meter);bg_vi_frame frame={0};
    unsigned origin=1;uint32_t pose=0;uint64_t now=100000;
    unsigned changed=0;
    for(unsigned vi=1;vi<5000&&!bg_vi_complete(&meter);vi++){
        now+=16683;bool due=vi%2==0;
        if(duplicate||due){
            origin=origin%3+1;
            if(due)pose++;
            frame=(bg_vi_frame){.pose_tick=pose,.vehicle=vi>2400,
                .sampled_us=now-50000,.completed_us=now-16000};
            changed++;
        }
        bg_vi_record(&meter,now,vi,origin,&frame,due,false);
    }
    assert(bg_vi_complete(&meter));
    bg_cadence_finish(&meter.fresh);
    const bg_cadence_result*c=&meter.fresh.result[0];const bg_vi_result*r=&meter.result[0];
    assert(c->frames>2200&&c->frames<2300&&c->p95==33366&&c->maximum==33366);
    assert(r->gap_two==c->frames&&r->gap_one==0&&r->gap_long==0);
    assert(r->max_gap==2&&r->missed==0&&r->skipped_poses==0);
    assert(r->max_latency_us==50000&&r->latency_us==(uint64_t)c->frames*50000);
    assert(r->max_ready_wait_us==16000&&r->ready_wait_us==(uint64_t)c->frames*16000);
    assert(r->flips==c->frames+r->duplicates);
    assert(duplicate?r->duplicates>2200:r->duplicates==0);
    assert(meter.result[1].flips+meter.result[2].flips==r->flips);
    /* Publication freezes every statistic and sample for main-thread sorting. */
    bg_vi_meter before=meter;
    bg_vi_record(&meter,now+200000,9999,9,&frame,true,true);
    assert(memcmp(&before,&meter,sizeof meter)==0);
    assert(changed>=c->frames);
}

static void missed_test(void){
    bg_vi_meter m={0};bg_vi_frame f={0};
    bg_vi_record(&m,1,0,1,&f,false,false);
    f.pose_tick=1;f.sampled_us=999999;f.completed_us=1000000;
    bg_vi_record(&m,1000001,60,2,&f,true,false); /* warmup ends */
    bg_vi_record(&m,1033367,62,2,&f,true,true); /* no new buffer */
    f.pose_tick=3;f.sampled_us=1040000;f.completed_us=1060000;
    bg_vi_record(&m,1066733,64,3,&f,true,false);
    assert(m.result[0].missed==1&&m.result[0].due==2);
    assert(m.result[0].gap_long==1&&m.result[0].max_gap==4);
    assert(m.result[0].skipped_poses==1&&m.fresh.result[0].maximum==66732);
}

int main(void){
    queue_test();tracker_test();clock_test();vi_test(false);vi_test(true);missed_test();
    puts("Pacing: prefill/FIFO/misses/wrap/drain; full clock backlog; VI fresh/duplicate/latency/freeze tests pass.");
}
