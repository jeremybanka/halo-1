#ifndef BG_PVE_PREPARE_PROFILE_H
#define BG_PVE_PREPARE_PROFILE_H
#ifdef BG_PVE_PREP_PROFILE
typedef struct {
    unsigned visibility_us,buffers_us,matrices_us,motion_us,decode_us,scatter_us,writeback_us,grip_us,ship_us;
    unsigned pose_requests,pose_hits,shared_poses,pair_requests,pair_hits,dma_bytes;
} bg_pve_prepare_profile_data;
extern bg_pve_prepare_profile_data bg_pve_prepare_profile;
#define PVE_PREP_NOW() get_ticks_us()
#define PVE_PREP_COUNT(field,n) (bg_pve_prepare_profile.field+=(unsigned)(n))
#else
#define PVE_PREP_NOW() 0u
#define PVE_PREP_COUNT(field,n) ((void)0)
#endif
#endif
