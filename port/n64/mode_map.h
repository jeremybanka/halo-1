#ifndef BG_MODE_MAP_H
#define BG_MODE_MAP_H
#include <stdint.h>
#include "pickup_rules.h"
enum { BG_MARK_FLAG, BG_MARK_BALL, BG_MARK_HILL, BG_MARK_RACE, BG_MARK_VEHICLE };
typedef struct { float pos[3],yaw; uint16_t kind,id; } bg_mode_marker;
typedef struct { bg_map_item item; uint32_t modes; } bg_mode_item;
typedef struct {
    const int (*starts)[4];
    const uint32_t *spawn_modes;
    const float (*spawn_positions)[3];
    const bg_mode_marker *markers;
    const bg_mode_item *items;
    unsigned spawn_count,marker_count,item_count;
} bg_mode_map;
#ifdef BG_STREAM_MAPS
const bg_mode_map *bg_current_mode_map(void);
#else
static inline const bg_mode_map *bg_current_mode_map(void) { return 0; }
#endif
#endif
