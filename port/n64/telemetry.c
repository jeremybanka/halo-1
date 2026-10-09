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
           "pose_alloc=%u pose_free=%u\n",
           free_bytes, minimum_free, (unsigned)bg_counters[0], (unsigned)bg_counters[1],
           (unsigned)bg_counters[2], (unsigned)bg_counters[3], (unsigned)bg_counters[4],
           (unsigned)bg_counters[5], (unsigned)bg_counters[6], (unsigned)bg_counters[7],
           (unsigned)bg_counters[8], (unsigned)bg_counters[9], (unsigned)bg_counters[10],
           (unsigned)bg_counters[11], (unsigned)bg_counters[12], (unsigned)bg_counters[13],
           (unsigned)bg_counters[14]);
}
#endif
