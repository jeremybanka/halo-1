#ifndef BG_RUNTIME_CONFIG_H
#define BG_RUNTIME_CONFIG_H
#if !defined(BG_RELOAD_QA) && !defined(BG_COMBAT_QA) && !defined(BG_MOVEMENT_QA) &&                \
    !defined(BG_DESTRUCTION_QA) && !defined(BG_EFFECTS_QA) && !defined(BG_DEMO) &&                 \
    !defined(BG_SHOWCASE) && !defined(BG_SNAPSHOT_TICK) && !defined(BG_MENU_QA)
#define BG_FRONTEND
#endif
#ifndef BG_PACED30_BUFFERS
#define BG_PACED30_BUFFERS 3
#endif
#if defined(BG_PACED30) && defined(BG_SNAPSHOT_TICK)
#undef BG_PACED30 /* Frozen pixel fixtures always use the ordinary presenter. */
#undef BG_PACED30_BUFFERS
#define BG_PACED30_BUFFERS 3
#endif
#if !defined(BG_PACED30) && BG_PACED30_BUFFERS != 3
#error "Extra display surfaces require the explicit paced30 experiment"
#endif
#if defined(BG_PACED30) && BG_PACED30_BUFFERS >= 4
#define BG_PRESENT_TRACK
#endif
#ifdef BG_PACED30
#include "render_pacing.h"
#endif
#ifdef BG_SNAPSHOT_TICK
#include "replay_snapshot.h"
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK) || defined(BG_SHOWCASE) ||                   \
    defined(BG_PROFILE) ||                                                                         \
    (defined(RDPQ_VALIDATE) && !defined(BG_MODEL_QA) && !defined(BG_INTERACTION_QA) &&             \
     !defined(BG_SHIELD_QA))
#error "Snapshot QA requires an overlay-free build without benchmark/showcase/profile/validation"
#endif
#endif
#if defined(BG_VI_BENCHMARK) &&                                                                    \
    (defined(BG_BENCHMARK) || defined(BG_TELEMETRY) || defined(BG_PROFILE) ||                      \
     defined(BG_GPU_DIAGNOSTIC) || defined(RDPQ_VALIDATE) || defined(BG_SHOWCASE))
#error "Quiet VI measurement cannot include full profiling or a different scene"
#endif
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
#define BG_VI_MEASURE
#endif
#ifdef BG_BENCHMARK
#include "benchmark.h"
#include "cadence.h"
#include "cadence_tail.h"
#include "vi_meter.h"
#ifndef BG_PROFILE
#define BG_PROFILE
#endif
#endif
#ifdef BG_VI_BENCHMARK
#include "vi_meter.h"
#endif
#if defined(BG_GPU_DIAGNOSTIC) && !defined(BG_PROFILE)
#define BG_PROFILE
#endif
#ifdef BG_SHOWCASE
#include "showcase.h"
#endif

#define BG_FRAME_SLOTS 2

#endif
