#include <libdragon.h>
#include "runtime_config.h"
#include "presentation.h"
#ifdef BG_BENCHMARK
static bg_cadence completed_cadence;
static bg_cadence_tail completed_tail;
#endif
#ifdef BG_VI_MEASURE
static bg_vi_meter visible_meter;
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
typedef struct {
    surface_t *screen;
    unsigned vehicle;
    uint32_t pose_tick;
    uint64_t sampled_us, completed_us;
#ifdef BG_BENCHMARK
    bg_cadence_frame sample;
#endif
} bg_completion_frame;
/* Metadata follows DISPLAY buffers, not the two geometry slots. A
 * display buffer cannot be acquired again before completion AND presentation. */
static bg_completion_frame completion_frames[BG_PACED30_BUFFERS];
static uint32_t video_retraces;
#ifdef BG_PACED30
static bg_present30 presenter;
#ifdef BG_PRESENT_TRACK
static volatile bg_present30_tracker present_tracker;
static void present_surface(unsigned id) {
    bool released = bg_present30_track_release(&present_tracker, id);
    assertf(released, "Invalid display surface release");
    (void)released;
    display_show(completion_frames[id].screen);
}
#endif
static void paced_vi(void) {
#ifdef BG_PRESENT_TRACK
    ++video_retraces;
    if (present_tracker.draining || (!presenter.started && bg_present30_track_start_blocked(
                                                               &present_tracker, video_retraces))) {
        presenter.due = presenter.missed = false;
        return;
    }
    int id = bg_present30_vi(&presenter, video_retraces);
    if (id >= 0)
        present_surface((unsigned)id);
#else
    int id = bg_present30_vi(&presenter, ++video_retraces);
    if (id >= 0)
        display_show(completion_frames[id].screen);
#endif
}
void bg_presentation_mode(bool enabled) {
    disable_interrupts();
    if (presenter.enabled != enabled) {
        /* Release every held surface in FIFO. In-flight full-sync callbacks
         * use the new mode; libdragon retains acquisition order across both. */
        int id;
#ifdef BG_PRESENT_TRACK
        while ((id = bg_present30_pop(&presenter)) >= 0) {
            present_surface((unsigned)id);
        }
#else
        while ((id = bg_present30_pop(&presenter)) >= 0)
            display_show(completion_frames[id].screen);
#endif
        presenter.enabled = enabled;
        presenter.started = false;
        presenter.due = presenter.missed = false;
#ifdef BG_PRESENT_TRACK
        if (enabled)
            bg_present30_track_begin_drain(&present_tracker);
        else
            bg_present30_track_cancel_drain(&present_tracker);
#endif
    }
    enable_interrupts();
}
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PRESENT_TRACK)
static void observe_vi(void) {
#ifndef BG_PACED30
    ++video_retraces;
#endif
    /* VI_ORIGIN is the physical scanout address. This callback is registered
     * before display_init, so libdragon's prepended swap handler runs first. */
    uint32_t origin = *(volatile uint32_t *)0xA4400004u & 0x00ffffffu;
    for (unsigned i = 0; i < BG_PACED30_BUFFERS; i++) {
        const bg_completion_frame *f = &completion_frames[i];
        if (!f->screen || PhysicalAddr(f->screen->buffer) != origin)
            continue;
#ifdef BG_PRESENT_TRACK
        bg_present30_track_observe(&present_tracker, i, video_retraces);
#endif
#ifdef BG_VI_MEASURE
        bg_vi_frame sample = {.pose_tick = f->pose_tick,
                              .vehicle = f->vehicle,
                              .sampled_us = f->sampled_us,
                              .completed_us = f->completed_us};
        bool due = false, missed = false;
#ifdef BG_PACED30
        due = presenter.due;
        missed = presenter.missed;
#endif
        bg_vi_record(&visible_meter, get_ticks_us(), video_retraces, origin, &sample, due, missed);
#endif
        break;
    }
}
#endif
static void frame_complete(void *argument) {
    bg_completion_frame *frame = argument;
    uint64_t now = get_ticks_us();
    frame->completed_us = now;
#ifdef BG_PACED30
    if (presenter.enabled
#ifdef BG_PRESENT_TRACK
        && !present_tracker.draining
#endif
    ) {
        bool queued = bg_present30_complete(&presenter, (unsigned)(frame - completion_frames));
        assertf(queued, "Paced presentation queue overflow/duplicate surface");
    } else
#endif
#ifdef BG_PRESENT_TRACK
        present_surface((unsigned)(frame - completion_frames));
#else
    display_show(frame->screen);
#endif
#ifdef BG_BENCHMARK
    bg_cadence_record_with_tail(&completed_cadence, &completed_tail, now, frame->vehicle,
                                &frame->sample);
#endif
}
void bg_presentation_submit(surface_t *screen, unsigned vehicle, uint32_t pose_tick,
                            uint64_t sampled_us
#ifdef BG_BENCHMARK
                            ,
                            const bg_cadence_frame *sample
#endif
) {
    unsigned i = 0;
    while (i < BG_PACED30_BUFFERS && completion_frames[i].screen &&
           completion_frames[i].screen != screen)
        i++;
    assertf(i < BG_PACED30_BUFFERS, "Display buffer metadata exhausted");
    completion_frames[i] = (bg_completion_frame){
        .screen = screen, .vehicle = vehicle, .pose_tick = pose_tick, .sampled_us = sampled_us};
#ifdef BG_PRESENT_TRACK
    disable_interrupts();
    bool submitted = bg_present30_track_submit(&present_tracker, i);
    assertf(submitted, "Display surface reused before VI presentation");
    (void)submitted;
    enable_interrupts();
#endif
#ifdef BG_BENCHMARK
    completion_frames[i].sample = *sample;
#endif
    /* libdragon's detach_show uses this same full-sync callback, with
     * display_show directly. No extra fence or wait is introduced. */
    rdpq_detach_cb(frame_complete, &completion_frames[i]);
}
#endif

void bg_presentation_observer_init(void) {
#if defined(BG_VI_MEASURE) || defined(BG_PRESENT_TRACK)
    register_VI_handler(observe_vi);
#endif
}
void bg_presentation_paced_init(void) {
#ifdef BG_PACED30
    assertf(get_tv_type() != TV_PAL, "Experimental paced30 requires NTSC/MPAL (60 Hz)");
    register_VI_handler(paced_vi);
#endif
}
#ifdef BG_PACED30
bool bg_presentation_draining(void) {
#ifdef BG_PRESENT_TRACK
    return present_tracker.draining;
#else
    return false;
#endif
}
void bg_presentation_stop(void) {
    rspq_wait();
    bg_presentation_mode(false);
    disable_interrupts();
    unregister_VI_handler(paced_vi);
    enable_interrupts();
}
bg_presentation_pressure bg_presentation_peaks(void) {
    bg_presentation_pressure result = {0};
    disable_interrupts();
#ifdef BG_VI_MEASURE
    result.held = presenter.peak;
#endif
#ifdef BG_PRESENT_TRACK
    result.ready = present_tracker.peak_ready;
    result.outstanding = present_tracker.peak_outstanding;
#endif
    enable_interrupts();
    return result;
}
#endif
#ifdef BG_VI_MEASURE
const bg_vi_meter *bg_presentation_meter(void) {
    return &visible_meter;
}
void bg_presentation_finish_metrics(void) {
#ifdef BG_BENCHMARK
    bg_cadence_finish(&completed_cadence);
#endif
    bg_cadence_finish(&visible_meter.fresh);
}
#endif
#ifdef BG_BENCHMARK
const bg_cadence *bg_presentation_cadence(void) {
    return &completed_cadence;
}
const bg_cadence_tail *bg_presentation_tail(void) {
    return &completed_tail;
}
#endif
