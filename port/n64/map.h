#ifndef BG_MAP_H
#define BG_MAP_H
#include <stdbool.h>
#include <stdint.h>
/* IDs follow the original Xbox menu catalog. */
enum { BG_MAP_BLOOD_GULCH = 9, BG_MAP_WIZARD = 10 };
typedef struct { float pos[3], yaw; uint32_t kind; } bg_map_vehicle;
#ifdef BG_STREAM_MAPS
typedef struct {
    unsigned id, bytes;
    float origin[3], void_height;
    uint32_t world_bytes, world_layout[7][2];
} bg_map_info;
extern void *bg_map_vertex_data, *bg_map_texture_data;
extern const bg_map_vehicle *bg_map_vehicles;
extern unsigned bg_map_vehicle_count;
bool bg_map_load(unsigned id);
void bg_map_unload(void);
bool bg_map_loaded(void);
const bg_map_info *bg_map_current(void);
const char *bg_map_world_path(void);
unsigned bg_map_resident_bytes(void);
#ifndef __MIPSEB__
void bg_map_host_world_order(unsigned block, void *memory, unsigned bytes);
#endif
#endif
static inline unsigned bg_map_id(void) {
#ifdef BG_STREAM_MAPS
    return bg_map_current()->id;
#else
/* Existing host/source-oracle fixtures retain their immutable Blood Gulch
 * tables. Coordinate conversion must use the same map origin on target. */
    return BG_MAP_BLOOD_GULCH;
#endif
}
static inline const float *bg_map_origin(void) {
#ifdef BG_STREAM_MAPS
    return bg_map_current()->origin;
#else
    static const float origin[3] = {68, -118, 0};
    return origin;
#endif
}
static inline float bg_map_void_height(void) {
#ifdef BG_STREAM_MAPS
    return bg_map_current()->void_height;
#else
    return -8;
#endif
}
#endif
