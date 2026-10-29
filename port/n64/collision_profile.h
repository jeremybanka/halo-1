#ifndef BG_COLLISION_PROFILE_H
#define BG_COLLISION_PROFILE_H
#include <stdint.h>
/* Diagnostic counters only. Section times are disjoint; terrain/hit times
 * are nested. Emit each 30 actual ticks, independently of rendered frames. */
#ifdef BG_COLLISION_PROFILE
typedef struct {
    unsigned ticks,tick_us,max_tick_us,director_us,humans_us,vehicle_ai_us,vehicles_us,actors_us,projectiles_us,after_us;
    unsigned terrain_us,terrain_queries,terrain_hits,terrain_misses,terrain_overflows,terrain_actor_overflows,terrain_candidates;
    unsigned hit_us,hit_queries,hit_pose_builds,hit_available,hit_triangles,hit_groups,hit_rejected,hit_root_rejected;
} bg_collision_profile_data;
extern bg_collision_profile_data bg_collision_profile;
#ifdef N64
#include <libdragon.h>
#define BG_COLLISION_NOW() get_ticks_us()
#else
#define BG_COLLISION_NOW() 0u
#endif
#define BG_COLLISION_COUNT(field,n) (bg_collision_profile.field+=(uint32_t)(n))
#else
#define BG_COLLISION_NOW() 0u
#define BG_COLLISION_COUNT(field,n) ((void)0)
#endif
#endif
