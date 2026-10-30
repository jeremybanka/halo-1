# Vehicle simulation query reuse — local appraisal

This candidate builds on the Wraith/Shade distance LOD appraisal. It changes
when Wraith obstruction checks run and how the five vehicle clearance rays
search the static world. Meshes, actor counts, physical contacts, source steering,
weapon tags, navigation and the 30 Hz simulation rate remain unchanged.

## What changed

The mortar's analytic trajectory still updates its visible barrel aim on every
eligible aiming tick, including cooldown. The twelve-segment obstruction test
runs when the burst pause permits a firing decision. The ordinary eligibility
checks remain in their original order. A future special firing mode also keeps
the obstruction check. The grenade wrapper continues to perform both steps.
No shot uses a cached obstruction answer. Invalid trajectories keep the same
fallback aim, and cooldown expiry/ongoing bursts preserve their existing rules.

Clearance builds the original five origins and keeps every lane's nearest-hit
fraction. One conservative bounding box searches the world BVH for potentially
intersecting polygons; candidates stream directly to the exact ray tests.
Plane/projection setup and projected polygon edges are shared across the lanes.
There is no capped candidate list, new persistent cache or stale collision
answer. Cliff support queries and left/right steering probes are unchanged.
Queries requiring normals/materials and the optional original-BSP path retain
their scalar service.

The first experiment shared BVH nodes but still repeated five floating-point
slab tests at each node. Its clearance cost barely improved (3.315 → 3.269
ms/tick), so it was replaced. The final traversal performs one box test per
node, postponing the individual ray tests until a polygon is a candidate.
That rejected experiment and its logs remain under `build/vehicle-simulation`;
all final matrix cases are isolated under its `final` subdirectory.

## Correctness evidence

The host oracle uses the actual pre-change port at `031e79f5`. It does not
compare two instances of the optimized implementation. Strict and target-style
floating-point builds run with AddressSanitizer and UndefinedBehaviorSanitizer.

- 650,000 packet/scalar distances across all thirteen maps, including zero,
  short, axis-aligned and oblique rays: bit-identical.
- 20,000 original versus split ballistic cases: identical complete-path
  decisions and aim vectors, including aim-only cooldown operation.
- 3,000 Wraith cases at pause expiry, zero/negative pause, active burst, shot
  timers, awareness/range and high/low arcs: identical control inputs, aim,
  actor state, timers and random stream.
- 9,600 full gameplay ticks across both fixtures and 1–4 players: identical
  player/vehicle/actor state, pickups, projectile state, events, Firefight
  state and random streams at every accumulated trace checkpoint.
- Existing vehicle entry, occupied-seat rejection, splatter threshold/grace,
  source weapon speed/cooldown, Banshee secondary rules, death/seat release and
  encounter hull destruction regressions pass.

The native four-player verification executes 1,200 identical fixed ticks with
scalar ray and frozen ballistic oracles enabled. All 40 cumulative state/event
checkpoints match, including 226 firing events. All nine native framebuffer
pages at tick 1,200 are bit-identical. This holds the external render schedule
constant as well as the simulation inputs.

An initial comparison of freely running native builds was not a valid full-state
oracle: rendering calls `bg_pickup_mark_visible`, which refreshes pickup timers
using the current match time. Different render cadence can therefore change
hashed pickup bookkeeping. The fixed-tick comparison avoids that uncontrolled
input; the initial live diagnostic logs are retained separately. No pickup
behavior was changed to make the test pass.

These are matched-fixture and differential checks, not a proof over every
possible floating-point input or a new gameplay-balance assessment.

## Fresh native performance

All final live builds use the same geometry/LOD bank and the same profiling
configuration. Ares v148, NTSC 320×240, 8 MiB, audio enabled, uncapped timing.
Each capture has 45 observations; FPS discards five warm-ups and retains samples
with at least one living player/enemy and no pending arrival. Damage, deaths,
respawns and the four-vehicle fixture's tick-600 restarts remain real.

| Players | Four-vehicle stress FPS, before → after | One-Ghost control FPS, before → after |
| --- | ---: | ---: |
| 1 | 16.08 → 23.81 (26/26 samples) | 44.20 → 44.87 (30/30 samples) |
| 2 | 8.73 → 10.83 (37/36 samples) | 24.23 → 24.51 (35/35 samples) |
| 3 | 7.50 → 9.90 (38/39 samples) | 26.93 → 27.62 (40/40 samples) |
| 4 | 3.55 → 4.40 (40/40 samples) | 16.00 → 16.02 (40/40 samples) |

**The four-player scope matters:** the engaged stress average improves by 23.9%, but restricting the capture to all four humans alive gives **2.96 → 3.19 FPS** (27/26 samples, about 7.8%). Neither is a whole-match average or a fixed-state timing. The one-Ghost four-player result is essentially unchanged at 16.00 → 16.02 FPS; its all-four-alive subset is 14.53 → 14.33 FPS (15 samples each). These small control differences do not establish a performance change.

The final four-player stress CPU partition is:

| Disjoint simulation section | Before, ms/tick | After, ms/tick |
| --- | ---: | ---: |
| Humans | 7.455 | 7.977 |
| Vehicle AI | 5.845 | 2.363 |
| Vehicle physics, contacts and weapons | 8.561 | 8.712 |
| Infantry AI/combat | 4.277 | 4.397 |
| Projectiles | 4.803 | 4.847 |
| Total simulation | 31.034 | 28.391 |

Vehicle AI falls **59.6%**, while total simulation falls **8.5%**. The remaining large simulation buckets are vehicle update (8.71 ms/tick), humans (7.98) and projectiles (4.85). The retained full vehicle solvers account for 6.79 ms/tick within vehicle update; the surrounding splatter loop is 1.43 ms/tick. These are nested costs, not additional disjoint sections.

| Work inside vehicle AI | Before, ms/tick | After, ms/tick |
| --- | ---: | ---: |
| Movement clearance, including support | 3.315 | 1.225 |
| World rays within the audit | 2.579 | 0.569 |
| Wraith complete aim/path call | 1.370 | 0.045 |
| Wraith analytic aim | 0.020 | 0.019 |
| Wraith obstruction segments | 1.337 | 0.018 |

Clearance falls **63.0%** and mortar obstruction work falls **98.7%**. Analytic aim remains about 0.02 ms/tick. Wraith obstruction passes fall from 0.786 to 0.010 per simulation tick, while aim-call frequency remains about 0.79 per tick. These child timings overlap their parents.

The four-player capture integrates 1,230/1,260 ticks. Average simulation per rendered frame falls 208.399 → 185.531 ms; preparation is 14.728 → 14.753 ms and drawing/submission 51.361 → 48.136 ms. Several fixed ticks accumulate during a slow rendered frame. These frame-stage averages come from changing combat states; identical frozen photos establish that no drawing simplification was introduced.

Minimum reported free heap is 393,632 → 391,520 bytes in the stress fixture and 354,784 → 352,672 bytes in the control. No persistent collision cache was added. All 27 before/after framebuffer pairs at ticks 60, 180 and 1,200 are bit-identical; camera/hull state records and repeated frames also match.

The targeted AI savings are substantial, but four-player 30 FPS still requires substantial reductions in the remaining simulation and rendering costs. This pass preserves the existing gameplay and stops here for appraisal.

CPU attribution integrates complete 30-tick windows, including startup/restarts.
It uses actual simulation ticks, not rendered frames. The FPS subset is different;
faster builds can sample different combat windows. The detailed profiler adds
clock/counter work equally to both builds. Small single-pair FPS differences
should not be treated as a statistically established gain or regression.
The dedicated equivalence builds perform extra oracle work and are excluded
from performance conclusions. These are native ROM measurements in Ares, not
new SummerCart64 measurements.

## Reproduction and appraisal artifacts

Read [benchmarks/vehicle-simulation/README.md](benchmarks/vehicle-simulation/README.md)
for the exact commands, fixtures, scope and counter definitions. The numerical
results, stripped logs, input/ROM hashes and scripts accompany this report.
`--vehicle-query-baseline` restores the old query scheduling/search costs;
`--vehicle-query-verify` is restricted to isolated cost-audit builds.

The viewer is `build/n64-vehicle-simulation/comparison.html` in the original
checkout; its playable ROM uses the maintained paced release preset. Private
local evidence contains raw framebuffers, source-derived images and exact
compiler inputs. No new art, model, animation, audio or collision assets are
required for the simulation change.

During the run an iCloud placeholder for the owned b40 source cache timed out.
The cache was reconstructed from the resident original map and matched its
existing SHA-256 exactly; only this isolated build's ignored symlink changed.
Compiler temporary-file failures were retried using a dedicated local directory.
Timing ROMs are losslessly compressed between captures to limit disk usage;
manifest validation checks their original decompressed bytes.

This pass stops for appraisal. Nothing from this pass is committed, pushed or
merged automatically.
