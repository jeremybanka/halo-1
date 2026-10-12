#ifndef BG_ANIMATION_PROFILE_H
#define BG_ANIMATION_PROFILE_H
#include <stdint.h>
/* Diagnostic CPU costs. sample includes DMA; callers include their helpers. */
#if defined(N64) && defined(BG_PROFILE)
typedef struct {
    uint32_t decode, scatter, writeback, sample, interpolate, dma;
    uint32_t meshes, poses;
    uint32_t repeat_last, repeat_frame;
} bg_animation_metrics;
extern bg_animation_metrics bg_animation_profile;
#define BG_ANIM_BEGIN(name) uint32_t name = get_ticks_us()
#define BG_ANIM_END(field, name) (bg_animation_profile.field += (uint32_t)get_ticks_us() - (name))
#define BG_ANIM_COUNT(field) (bg_animation_profile.field++)
#else
#define BG_ANIM_BEGIN(name) ((void)0)
#define BG_ANIM_END(field, name) ((void)0)
#define BG_ANIM_COUNT(field) ((void)0)
#endif
#endif
