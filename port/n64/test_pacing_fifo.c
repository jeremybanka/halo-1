/* Independent model of libdragon's three/four/five-surface acquisition/VI contract.
 * Production headers under test; this SDK model is deliberately separate from
 * the presenter's queue implementation. No N64 source/bank is changed. */
#include "render_pacing.h"
#include "vi_meter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum state { FREE, FRONT, RENDERING, COMPLETE, READY };
typedef struct {
    enum state state;
    unsigned generation;
    uint64_t done_us;
    bg_vi_frame frame;
} surface;
typedef struct {
    bg_present30 pacing;
#if BG_PACED30_BUFFERS >= 4
    bg_present30_tracker tracker;
#endif
    bg_vi_meter meter;
    surface surface[BG_PACED30_BUFFERS];
    unsigned front, acquired, completed, released, presented;
    unsigned release_count[2048], present_count[2048];
    unsigned transitions, misses, phase_flips, last_flip_vi, draws;
    unsigned fixed_delay_us,peak_held;
    uint32_t rng, last_pose;
    uint64_t rdp_end;
    bool rendering_enabled, request_enable, have_pose;
} simulation;

static unsigned old_ready_prefill_flips,old_inflight_mode_changes,draining_gate_checks;

static uint32_t random_u32(simulation*s){
    s->rng=s->rng*1664525u+1013904223u;return s->rng;
}
static bool all_drained(const simulation*s){
    for(unsigned i=0;i<BG_PACED30_BUFFERS;i++)if(i!=s->front&&s->surface[i].state!=FREE)return false;
    return s->pacing.count==0;
}
static void invariants(const simulation*s){
    unsigned front=0,locked=0;
    for(unsigned i=0;i<BG_PACED30_BUFFERS;i++){
        front+=s->surface[i].state==FRONT;
        locked+=s->surface[i].state>=RENDERING;
    }
    assert(front==1&&locked<BG_PACED30_BUFFERS&&s->surface[s->front].state==FRONT);
    assert(s->pacing.count<BG_PACED30_BUFFERS);
    for(unsigned i=0;i<s->pacing.count;i++)assert(s->surface[s->pacing.queue[i]].state==COMPLETE);
    assert(s->presented<=s->released&&s->released<=s->completed&&s->completed<=s->acquired);
#if BG_PACED30_BUFFERS >= 4
    unsigned outstanding=0,ready=0;
    for(unsigned i=0;i<BG_PACED30_BUFFERS;i++){
        if(s->surface[i].state>=RENDERING)outstanding|=1u<<i;
        if(s->surface[i].state==READY)ready|=1u<<i;
    }
    assert(s->tracker.outstanding==outstanding&&s->tracker.ready==ready);
    assert(!(s->tracker.draining&~outstanding));
#endif
}
static void show(simulation*s,unsigned id){
    surface*f=&s->surface[id];
    assert(id<BG_PACED30_BUFFERS&&f->state==COMPLETE);
    assert(f->generation==s->released+1); /* acquisition FIFO, even after stall */
    assert(++s->release_count[f->generation]==1);
#if BG_PACED30_BUFFERS >= 4
    assert(bg_present30_track_release(&s->tracker,id));
    assert(!bg_present30_track_release(&s->tracker,id));
#endif
    f->state=READY;s->released++;
}
static void disable_pacing(simulation*s){
    s->pacing.enabled=false;
    int id;while((id=bg_present30_pop(&s->pacing))>=0)show(s,(unsigned)id);
    s->pacing.started=s->pacing.due=s->pacing.missed=false;
    s->phase_flips=0;
#if BG_PACED30_BUFFERS >= 4
    bg_present30_track_cancel_drain(&s->tracker);
#endif
}
static void enable_pacing(simulation*s){
    s->pacing.enabled=true;s->pacing.started=false;
    s->pacing.due=s->pacing.missed=false;
#if BG_PACED30_BUFFERS >= 4
    bg_present30_track_begin_drain(&s->tracker);
#endif
}
static void complete_due(simulation*s,uint64_t now){
    for(;;){
        int id=-1;
        for(unsigned i=0;i<BG_PACED30_BUFFERS;i++)if(s->surface[i].state==RENDERING&&
            s->surface[i].done_us<=now&&(id<0||s->surface[i].done_us<s->surface[id].done_us))id=(int)i;
        if(id<0)break;
        surface*f=&s->surface[id];f->state=COMPLETE;f->frame.completed_us=now;
        assert(f->generation==++s->completed);
        bool hold=s->pacing.enabled;
#if BG_PACED30_BUFFERS >= 4
        hold=hold&&!s->tracker.draining;
#endif
        if(hold){
            assert(bg_present30_complete(&s->pacing,(unsigned)id));
            if(s->pacing.count>s->peak_held)s->peak_held=s->pacing.count;
            /* A duplicate completion must not enqueue or free a surface twice. */
            unsigned before=s->pacing.count;
            assert(!bg_present30_complete(&s->pacing,(unsigned)id));
            assert(s->pacing.count==before);
        }else show(s,(unsigned)id);
    }
}
static void retrace(simulation*s,uint64_t now,uint32_t vi){
    /* Actual SDK registration order: presenter, display callback, observer. */
    unsigned queued=s->pacing.count;bool was_started=s->pacing.started;
    int id;
#if BG_PACED30_BUFFERS >= 4
    if(s->tracker.draining||(!s->pacing.started&&bg_present30_track_start_blocked(&s->tracker,vi))){
        id=-1;s->pacing.due=s->pacing.missed=false;
    }else
#endif
    id=bg_present30_vi(&s->pacing,vi);
    if(id>=0){
        if(!was_started)assert(queued>=2); /* same two-completion prefill */
        if(s->phase_flips)assert((uint32_t)(vi-s->last_flip_vi)>=2);
        s->last_flip_vi=vi;s->phase_flips++;show(s,(unsigned)id);
    }
    s->misses+=s->pacing.missed;
    unsigned next=(s->front+1)%BG_PACED30_BUFFERS;
    if(s->surface[next].state==READY){
        if(s->pacing.enabled&&!s->pacing.started)old_ready_prefill_flips++;
        s->surface[s->front].state=FREE;s->front=next;
        surface*f=&s->surface[next];f->state=FRONT;
        assert(f->generation==s->presented+1);
        assert(++s->present_count[f->generation]==1);s->presented++;
        if(s->pacing.enabled&&s->pacing.started)assert(id==(int)next);
    }else assert(id<0);
#if BG_PACED30_BUFFERS >= 4
    bg_present30_track_observe(&s->tracker,s->front,vi);
#endif
    if(s->surface[s->front].generation){
        surface*f=&s->surface[s->front];assert(f->frame.completed_us<=now);
        bg_vi_record(&s->meter,now,vi,(uintptr_t)s->front+1,&f->frame,s->pacing.due,s->pacing.missed);
    }
}
static void acquire(simulation*s,uint64_t now){
    uint32_t pose=(uint32_t)(now/33333);
    if(!s->rendering_enabled||(s->have_pose&&pose==s->last_pose))return;
#if BG_PACED30_BUFFERS >= 4
    if(s->tracker.draining){draining_gate_checks++;return;}
#endif
    /* Exact display_try_get traversal; never return the front surface. */
    unsigned next=(s->front+1)%BG_PACED30_BUFFERS;
    while(next!=s->front&&s->surface[next].state!=FREE)next=(next+1)%BG_PACED30_BUFFERS;
    if(next==s->front)return;
    surface*f=&s->surface[next];assert(f->state==FREE);
    f->state=RENDERING;f->generation=++s->acquired;assert(s->acquired<2048);
    f->frame=(bg_vi_frame){.pose_tick=pose,.vehicle=(now/5000000)%2,.sampled_us=now};
#if BG_PACED30_BUFFERS >= 4
    assert(bg_present30_track_submit(&s->tracker,next));
    assert(!bg_present30_track_submit(&s->tracker,next));
#endif
    uint64_t delay=s->fixed_delay_us?s->fixed_delay_us:4000+random_u32(s)%44000;
    if(!s->fixed_delay_us&&s->acquired%47==0)delay+=120000; /* stalls longer than prefill */
    if(s->rdp_end<now)s->rdp_end=now;
    f->done_us=(s->rdp_end+=delay);
    s->last_pose=pose;s->have_pose=true;s->draws++;
}
static void run(uint32_t seed,uint32_t start_vi,bool direct_transition){
    simulation s={.pacing={.enabled=true},.rng=seed,.rendering_enabled=true};
    s.surface[0].state=FRONT;
    uint64_t next_vi=16667;uint32_t vi=start_vi;
    unsigned next_transition=0;
    static const uint64_t transitions[]={5000000,8000000,15000000,18000000};
    for(uint64_t now=0;now<40000000;now+=1000){
        /* VI precedes DP in a shared MI interrupt, including exact ties. */
        if(now>=next_vi){retrace(&s,now,vi++);next_vi+=16667;}
        complete_due(&s,now);
        if(next_transition<4&&now>=transitions[next_transition]){
            bool enable=(next_transition&1)!=0;
            disable_pacing(&s);s.rendering_enabled=!enable;
            s.request_enable=enable;
            if(enable&&direct_transition){
                /* Production false->true: old SDK READY surfaces still flip
                 * while new completions fill the two-frame held queue. */
                enable_pacing(&s);s.request_enable=false;s.rendering_enabled=true;
                for(unsigned j=0;j<BG_PACED30_BUFFERS;j++)old_inflight_mode_changes+=s.surface[j].state==RENDERING;
            }
            next_transition++;s.transitions++;
        }
        if(s.request_enable&&all_drained(&s)){
            s.pacing=(bg_present30){0};enable_pacing(&s);
            s.request_enable=false;s.rendering_enabled=true;
        }
        if(now>=30000000){
            s.rendering_enabled=false;s.request_enable=false;
            disable_pacing(&s);
        }
        acquire(&s,now);invariants(&s);
        if(now>30000000&&all_drained(&s))break;
    }
    assert(s.transitions==4&&s.draws>500&&s.misses>0);
    assert(all_drained(&s)&&s.acquired==s.presented);
    assert(s.acquired==s.completed&&s.completed==s.released);
    for(unsigned i=1;i<=s.acquired;i++)assert(s.release_count[i]==1&&s.present_count[i]==1);
    assert(s.meter.result[0].duplicates==0);
    assert(s.meter.result[0].missed>0&&s.meter.result[0].gap_long>0);
}
static void steady_timing_test(void){
    simulation s={.pacing={.enabled=true},.rendering_enabled=true,.fixed_delay_us=8000};
    s.surface[0].state=FRONT;uint64_t next_vi=16667;uint32_t vi=0;
    for(uint64_t now=0;now<10000000;now+=1000){
        if(now>=next_vi){retrace(&s,now,vi++);next_vi+=16667;}
        complete_due(&s,now);
        if(now>=8000000){s.rendering_enabled=false;disable_pacing(&s);}
        acquire(&s,now);invariants(&s);
        if(now>8000000&&all_drained(&s))break;
    }
    assert(all_drained(&s)&&s.acquired==s.presented&&s.acquired==s.released);
    assert(s.misses==0&&s.peak_held==2);
    const bg_vi_result*r=&s.meter.result[0];unsigned frames=s.meter.fresh.result[0].frames;
    assert(frames>200&&r->duplicates==0&&r->missed==0);
    unsigned latency=(unsigned)(r->latency_us/frames);
    assert(latency>=48000&&latency<=51000);
    printf("Ideal8ms serial-render fixture: %u surfaces, held peak%u, sample-to-VI mean%uus, max%uus; no extra prefill frame or steady third held frame. This is a model, not N64 timing.\n",
        BG_PACED30_BUFFERS,s.peak_held,latency,r->max_latency_us);
}
#if BG_PACED30_BUFFERS >= 4
static void predecessor_drain_test(bool inflight_last){
    /* The counterexample to the old three-surface capacity proof: a front
     * buffer, an old SDK-ready predecessor, and all remaining held frames.
     * The second variant leaves the final predecessor in flight. */
    simulation s={.pacing={.enabled=true},.rendering_enabled=true,.rng=1};
    s.surface[0].state=FRONT;s.acquired=BG_PACED30_BUFFERS-1;
    s.completed=BG_PACED30_BUFFERS-1-(unsigned)inflight_last;s.released=1;s.release_count[1]=1;
    for(unsigned id=1;id<BG_PACED30_BUFFERS;id++){
        surface*f=&s.surface[id];f->generation=id;
        f->frame=(bg_vi_frame){.pose_tick=id,.sampled_us=0,.completed_us=0};
        assert(bg_present30_track_submit(&s.tracker,id));
        if(id==1){f->state=READY;assert(bg_present30_track_release(&s.tracker,id));}
        else if(id==BG_PACED30_BUFFERS-1&&inflight_last){f->state=RENDERING;f->done_us=40000;}
        else{f->state=COMPLETE;assert(bg_present30_complete(&s.pacing,id));}
    }
    invariants(&s);
    /* Disable flushes held frames to the SDK in acquisition order. Re-enable
     * must drain every predecessor, not start on the old two-held criterion. */
    disable_pacing(&s);enable_pacing(&s);
    assert(s.tracker.draining==(1u<<BG_PACED30_BUFFERS)-2&&!s.pacing.started);
    unsigned vi=0;
    while(s.tracker.draining){
        assert(++vi<=BG_PACED30_BUFFERS+1);
        uint64_t now=(uint64_t)vi*16667;
        unsigned before=s.acquired;acquire(&s,now);assert(s.acquired==before);
        retrace(&s,now,vi);complete_due(&s,now);invariants(&s);
        assert(!s.pacing.started&&s.phase_flips==0);
    }
    assert(s.front==BG_PACED30_BUFFERS-1&&s.presented==BG_PACED30_BUFFERS-1&&all_drained(&s));
    assert(!s.tracker.outstanding&&!s.tracker.ready);

    /* After the drain, exactly the usual two fresh completions start pacing.
     * No extra prefill frame is introduced for the additional surfaces. */
    acquire(&s,200000);assert(s.acquired==BG_PACED30_BUFFERS);
    s.surface[0].done_us=200001;complete_due(&s,200001);
    retrace(&s,216670,13);assert(!s.pacing.started&&s.presented==BG_PACED30_BUFFERS-1);
    acquire(&s,233333);assert(s.acquired==BG_PACED30_BUFFERS+1);
    s.surface[1].done_us=233334;complete_due(&s,233334);
    assert(s.pacing.count==2);
    retrace(&s,250005,15);assert(s.pacing.started&&s.presented==BG_PACED30_BUFFERS);
    retrace(&s,266672,16);assert(s.presented==BG_PACED30_BUFFERS);
    retrace(&s,283339,17);assert(s.presented==BG_PACED30_BUFFERS+1);
    invariants(&s);assert(all_drained(&s));
    for(unsigned i=1;i<=BG_PACED30_BUFFERS+1;i++)assert(s.release_count[i]==1&&s.present_count[i]==1);
}
#endif
int main(void){
    steady_timing_test();
    for(unsigned seed=1;seed<=16;seed++){
        run(seed,0,false);run(seed,UINT32_MAX-500,false);
        run(seed,0,true);run(seed,UINT32_MAX-500,true);
    }
    assert(old_ready_prefill_flips>0&&old_inflight_mode_changes>0);
    printf("Covered %u old SDK-ready flips during prefill and %u in-flight mode transitions.\n",old_ready_prefill_flips,old_inflight_mode_changes);
    printf("PASS:64 serial-RDP/%u-surface event simulations; FIFO/prefill/stalls/duplicate rejection/drained+direct mode changes/VI wrap; every acquired frame released and presented exactly once.\n",BG_PACED30_BUFFERS);
#if BG_PACED30_BUFFERS >= 4
    predecessor_drain_test(false);predecessor_drain_test(true);
    assert(draining_gate_checks>0);
    printf("Acquisition gated during %u old-surface drain polls.\n",draining_gate_checks);
    puts("Explicit front+old-SDK-ready+remaining-held and in-flight predecessor cases drain before unchanged two-completion prefill.");
#else
    assert(draining_gate_checks==0);
#endif
}
