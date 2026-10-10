#include "telemetry.h"
#ifdef BG_TELEMETRY
#include <libdragon.h>
#include <limits.h>
uint32_t bg_counters[BG_COUNTER_COUNT];
void bg_telemetry_report(void) {
    static unsigned minimum_free = UINT_MAX;
    heap_stats_t heap;
    sys_get_heap_stats(&heap);
    unsigned free_bytes = heap.total - heap.used;
    if (free_bytes < minimum_free)
        minimum_free = free_bytes;
    debugf("PRESSURE heap_free=%u sampled_min_free=%u pose_hit=%u pose_miss=%u dma_reads=%u "
           "dma_bytes=%u terrain_hit=%u terrain_miss=%u terrain_overflow=%u floor_hit=%u "
           "floor_miss=%u projectile_full=%u events_full=%u drop_reclaim=%u drop_full=%u "
           "pose_alloc=%u pose_free=%u world_hit=%u world_miss=%u world_overflow=%u "
           "world_bypass=%u world_negative_hit=%u prism_hit=%u prism_miss=%u edge_hit=%u "
           "edge_miss=%u vector_queries=%u vector_zero=%u pose_partial=%u pose_reused_bytes=%u\n",
           free_bytes, minimum_free, (unsigned)bg_counters[0], (unsigned)bg_counters[1],
           (unsigned)bg_counters[2], (unsigned)bg_counters[3], (unsigned)bg_counters[4],
           (unsigned)bg_counters[5], (unsigned)bg_counters[6], (unsigned)bg_counters[7],
           (unsigned)bg_counters[8], (unsigned)bg_counters[9], (unsigned)bg_counters[10],
           (unsigned)bg_counters[11], (unsigned)bg_counters[12], (unsigned)bg_counters[13],
           (unsigned)bg_counters[14], (unsigned)bg_counters[15], (unsigned)bg_counters[16],
           (unsigned)bg_counters[17], (unsigned)bg_counters[18], (unsigned)bg_counters[19],
           (unsigned)bg_counters[20], (unsigned)bg_counters[21], (unsigned)bg_counters[22],
           (unsigned)bg_counters[23], (unsigned)bg_counters[24], (unsigned)bg_counters[25],
           (unsigned)bg_counters[26], (unsigned)bg_counters[27]);
}
#endif
