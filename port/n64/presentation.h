#ifndef BG_PRESENTATION_H
#define BG_PRESENTATION_H
#include <libdragon.h>
#include "runtime_config.h"
/* Register the observer BEFORE display_init and pacing AFTER display_init.
 * Completion metadata follows display surfaces, independent of geometry slots.
 * Full-sync/VI callbacks alone release surfaces. The application never owns
 * this queue; mode changes drain it under the original interrupt discipline. */
void bg_presentation_observer_init(void);
void bg_presentation_paced_init(void);
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
void bg_presentation_submit(surface_t *screen, unsigned vehicle, uint32_t pose_tick,
                            uint64_t sampled_us
#ifdef BG_BENCHMARK
                            ,
                            const bg_cadence_frame *sample
#endif
);
#endif
#ifdef BG_PACED30
void bg_presentation_mode(bool enabled);
bool bg_presentation_draining(void);
void bg_presentation_stop(void);
typedef struct {
    unsigned held, ready, outstanding;
} bg_presentation_pressure;
bg_presentation_pressure bg_presentation_peaks(void);
#endif
#ifdef BG_VI_MEASURE
const bg_vi_meter *bg_presentation_meter(void);
void bg_presentation_finish_metrics(void); /* only after the ISR publishes complete */
#endif
#ifdef BG_BENCHMARK
const bg_cadence *bg_presentation_cadence(void);
const bg_cadence_tail *bg_presentation_tail(void);
#endif
#endif
