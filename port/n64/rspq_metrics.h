#ifndef BG_RSPQ_METRICS_H
#define BG_RSPQ_METRICS_H
#include <stdint.h>
/* CPU command-queue stalls only. RSP/RDP execution and frame-slot fences are
 * measured separately. Provided by the generated local rspq.c override. */
typedef struct { uint64_t stall_us,words; unsigned switches,waits; } bg_rspq_metrics;
void bg_rspq_get_metrics(bg_rspq_metrics *result);
#endif
