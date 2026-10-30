# Firefight NPC preparation reuse

28 October 2026. Prototype for appraisal, following the collision acceleration.

NPC preparation is **45.1% cheaper in the four-player opening** and **42.5%
cheaper in the four-player crowded encounter**. It uses the same animation
samples, interpolation fractions, geometry and hit meshes. The CPU saving is
substantial, but four-player FPS improvement remains limited: the crowded
all-humans-alive subset is unchanged at **3.95 FPS**. This does not deliver
four-player 30 FPS.

## What changed

The renderer already prepared an actor's needed LOD once for all cameras. The
remaining repeated work was motion transfer, interpolation and packed vertex
updates. Three changes address those costs:

- A bounded shared cache retains exact ROM frame-pair bytes across actors and
  frames. It replaces the single transfer window with a 192 KiB arena and
  thirty-two span descriptors; overlap and wraparound invalidate stale entries.
- Actors with exactly matching species, LOD, clip, frame pair, interpolation
  fraction and shield state share prepared body geometry within the same fenced
  frame slot. Each keeps its own world transform and weapon attachment. No
  mutable buffer is borrowed across in-flight frame slots.
- Interpolated tracks use the existing eight-byte aligned packed position
  writer. NPC negative-delta rounding remains `>>8`; using the Spartan decoder's
  division would have changed some coordinates. Normals, colors and UVs remain
  intact. Spirit interpolation also works once per unique track before scatter.

There is no animation throttling, coarser time quantization, model reduction,
camera/LOD change or shared hit-pose approximation. AI, movement, collision,
navigation and arrival logic are unchanged. The Hunter/Spirit model candidate
remains opt-in and is the same on both sides of this comparison.

Additional linked BSS is **115,184 bytes (112.48 KiB)**, primarily the larger
motion cache and aligned track array. The lowest sampled free heap in the
four-player opening is 713,328 bytes; the crowded capture reports 836,896 bytes.
These are sampled values, not a proof of peak allocation headroom in every game.

## Fresh matched performance

These are uncapped native N64 programs in **Ares v148, NTSC 320×240, 8 MiB,
audio enabled**, not fresh physical-cartridge measurements. Both versions
include the previous collision optimization and current reload animation fix.
Only the preparation baseline control differs.

| Players | Opening FPS, before → after | Crowded FPS, before → after |
|---|---:|---:|
| 1 | 42.13 → 44.74 | 27.35 → 31.35 |
| 2 | 24.08 → 24.55 | 14.95 → 16.14 |
| 3 | 26.21 → 27.21 | 8.57 → 8.60 |
| 4 | 6.71 → 6.96 | 4.14 → 4.50 |

Headline means require living humans and landed enemies, after five warm-up
observations. Each opening run has 75 observations; each crowded run has 45.
Real damage/deaths remain enabled. Requiring **all four humans alive** gives
**6.65 → 6.89 FPS** in the opening and **3.95 → 3.95 FPS** in the crowded case.
Consequently, the broader crowded mean's 8.7% gain should not be read as a proven
gain during sustained full-party combat. The one-player crowded mean crosses
30 FPS, but its 22 FPS minimum observation also rules out a locked-30 claim.

Each case has one fresh capture. Identical controls, geometry and rules do not
guarantee identical sampled combat windows once frame timing changes. Small
differences are not statistical proof. Compare the paired columns here rather
than treating earlier turns' differently instrumented runs as this baseline.

## Where preparation time went

These are means of one sampled rendered frame per observation, across the
whole post-warm-up capture. Their windows differ from filtered FPS above.

| Four-player preparation | Opening before → after | Crowded before → after |
|---|---:|---:|
| Total NPC preparation | 13.99 → 7.69 ms | 25.69 → 14.77 ms |
| ROM-span lookup / transfer | 3.57 → 0.51 ms | 7.71 → 2.44 ms |
| Track interpolation | 2.19 → 1.53 ms | 4.99 → 3.62 ms |
| Packed vertex updates | 5.66 → 3.19 ms | 9.37 → 5.48 ms |
| Vertex cache writeback | 0.96 → 0.80 ms | 1.35 → 1.11 ms |
| ROM bytes fetched per sampled frame | 17,850 → 2,196 | 39,022 → 11,803 |
| Motion-pair reuse in candidate samples | 86.64% | 63.69% |
| Pose requests sharing an earlier actor in candidate samples | 15.94% | 23.61% |

Visibility, transforms and grips add roughly 1.69 ms in the crowded candidate.
The lower transfer volume combines sample-cache
hits with fewer requests when an actor borrows an already prepared pose. The
scatter reduction combines sharing and faster exact position writes; this
experiment does not isolate each technique into separate FPS trials.

The entire crowded preparation section falls **29.99 → 19.31 ms** per sampled
frame. About 14.77 ms of the candidate is NPC work. Simulation itself is not
accelerated: the continuous counter reports **13.59 → 13.76 ms per actual tick**
in these crowded windows. The small difference reflects timing/workload variation;
the simulation sources and hit geometry remain byte-identical.

## Why split-screen FPS changes less

Preparation savings do not remove the repeated drawing work. The crowded
captures submit **61,683 → 61,629 vertex loads across four cameras**, effectively
unchanged. Draw/submission, including stalls, samples **50.14 → 55.73 ms**; the
pipeline separately reports queue waits of **31.37 → 27.86 ms**. These overlapping
counters do not establish an independent
graphics regression or speedup: the sampled scenes and pipeline overlap change.

The candidate still spends about **19.31 ms preparing a frame**, while the
target frame allowance is **33.33 ms** for the entire frame. Its sampled
simulation section is about **91.29 ms**, because a rendered frame can include
multiple fixed-step catch-up ticks and ancillary updates. The per-tick mean,
per-frame sections and filtered FPS cannot simply be added or inverted.

The separate serialized diagnostic still waits **88.03 → 86.63 ms** for the
outstanding RSP queue, followed by **0.035 ms** of RDP tail on both sides. It
submits about 62,000 loads across four cameras. These waits include audio pumping
and possible RDP backpressure; the tiny final tail does not measure total RDP
rasterization cost. Diagnostic FPS is excluded from the table. The large remaining
queue drain supports graphics work as a major continuing constraint even after
the CPU preparation saving.

Arrival placement still runs synchronously and retains the previously identified
reinforcement hitch. This prototype leaves it unchanged. The next large FPS
opportunity remains reducing graphics work per camera and its submission cost;
arrival scheduling is a separate hitch-specific follow-up. No such changes are
included in this appraisal.

## Accuracy and lifecycle checks

All **52 matched native frames, each with four cameras**, are pixel-identical:
every one of the **3,993,600 RGBA16 pixels** matches all sixteen bits. RDP
validation reports no errors or warnings. The original pose/camera route covers
both LODs, Hunter movement/melee, Spirit door phases, Jackal shield states and
occlusion, and Grunt/Elite movement. The viewer includes before/after, blink and
an amplified difference filter, which is black throughout. Existing visual
defects such as the absent Jackal shield mesh remain unchanged.

Independent pre-change decode/scatter loops also match **631,808 packed poses
covering 941,677,568 vertices** across the canonical and opt-in banks: every
species, LOD, clip, frame pair and all 256 interpolation fractions. Tests compare
the entire packed buffer and deliberately vary normals to catch accidental
overwrites. Cache eviction/reset tests and 4,000 alternating-slot ownership
simulations per bank pass under ASan/UBSan.

The existing movement/hit oracle still passes **37,440 exact movement steps**
across thirteen maps and **686,256 exact hit rays**, including materials and
reflection normals. Full 1–4P Firefight lifecycle/material/arrival tests, the
deferred-animation fence harness and **42 runtime configurations / 168 target
translation units** pass.

The native four-player restart/quit/return-to-multiplayer fixture passes all 39
steps with live actors and transport. A supplementary 223-step, fourteen-match
residency cycle also passes across all thirteen multiplayer maps with Firefight
compiled in and the canonical model bank. It checks the extra fixed memory cost
outside Firefight; only that lifecycle capture disables audio blocking and is
excluded from FPS measurements. RDP validation is clean in both checks.

These tests cover the authored motion banks and representative native views;
they do not assert pixel equivalence for every possible gameplay scene. Host
ownership checks exercise the production lookup but do not emulate the RSP.

The [benchmark directory](benchmarks/firefight-preparation/README.md) contains
the reproducible procedure, raw timing logs, exact input/ROM hashes, memory
evidence, pixel checks, unchanged-service hashes and counter definitions. Native
photos, difference filters and the playable appraisal remain private/local.
The prototype stops here for appraisal.
