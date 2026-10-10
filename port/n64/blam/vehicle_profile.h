#ifndef BG_VEHICLE_PROFILE_H
#define BG_VEHICLE_PROFILE_H
/* Diagnostic clocks only. Inclusive timings overlap: ground includes feature
 * construction/testing; force includes ground, integration includes sweeps,
 * and step includes force/integration/control/publication. No release storage. */
enum {
    BG_VP_GROUND,
    BG_VP_FEATURE_BUILD,
    BG_VP_FEATURE_TEST,
    BG_VP_SWEEP,
    BG_VP_PAIRS,
    BG_VP_SUSPENSION,
    BG_VP_WORLD_CAMERA,
    BG_VP_HULL_CAMERA,
    BG_VP_AIM_CAMERA,
    BG_VP_FORCE,
    BG_VP_INTEGRATE,
    BG_VP_CONTROL,
    BG_VP_PUBLISH,
    BG_VP_STEP,
    BG_VP_PLAYER_CONTACTS,
    BG_VP_COUNT
};
#if defined(N64) && defined(BG_PROFILE)
#include <libdragon.h>
typedef struct {
    uint32_t us[BG_VP_COUNT], calls[BG_VP_COUNT];
} bg_vehicle_metrics;
extern bg_vehicle_metrics bg_vehicle_profile;
static inline void bg_vehicle_profile_finish(unsigned phase, uint32_t begin) {
    bg_vehicle_profile.us[phase] += (uint32_t)get_ticks_us() - begin;
    bg_vehicle_profile.calls[phase]++;
}
#define BG_VP_BEGIN uint32_t bg_vp_begin = get_ticks_us()
#define BG_VP_END(phase) bg_vehicle_profile_finish(phase, bg_vp_begin)
#else
#define BG_VP_BEGIN ((void)0)
#define BG_VP_END(phase) ((void)0)
#endif
#endif
