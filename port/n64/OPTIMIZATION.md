# Blood Gulch optimization sprint

Base: merged cleanup `ffc5e53d`, branch `codex/n64-optimize`. Priorities are
algorithm improvements, then useful caching. This pass retains the private
asset bank, models, textures, original vehicle equations, 30 Hz simulation,
animations and HUD. It is the first optimization pass; the >25 FPS vehicle
and nominal 30 FPS four-player acceptance gates remain open.

## Measured results

Ares v148, NTSC, Expansion Pak disabled, three display surfaces, two geometry
slots, 32 KiB RSP queues, quiet 75-second four-player replay. Numbers are actual
VI presentations, not the emulator's status-bar rate or instrumented CPU FPS.

| Configuration | Overall | Combat | Vehicles | Free heap |
| --- | ---: | ---: | ---: | ---: |
| Merged cleanup reference | 24.1 | 26.2 | 22.2 | 42 KiB |
| Exact query word rounding + camera ray filtering | 24.8 | 26.6 | 23.1 | 46 KiB |
| Texture blocks / endpoint reuse / strict O2, guard 4 experiment | 25.0 | 26.8 | 23.4 | 33 KiB |
| Cached culling, guard 4 experiment | 25.0 | 26.7 | 23.3 | 32 KiB |
| LTO, guard 4 / experimental mixer | 25.3 | 26.6 | 24.0 | 48 KiB |
| LTO, original mixer / original guard 2 | 24.9 | 26.4 | 23.4 | 49 KiB |
| Release candidate: also exact render bounds rounding | 24.9 | 26.4 | 23.6 | 49 KiB |
| Final maintained release repeat | 25.0 | 26.4 | 23.7 | 49 KiB |

The final repeat has P95 66.8 ms and maximum 167.1 ms overall, 66.8 ms in
the vehicle section (100.2 ms in the preceding candidate trial). Its sample-to-VI mean is 74 ms / maximum 193 ms; ready-to-VI
mean is 19 ms / maximum 37 ms. There are still missed presentation deadlines.
The final improvement is approximately 4% overall / 7% in vehicles. It does
not establish >25 FPS vehicles, a 30 FPS floor, or real-console performance.
The guard-4 option remains an experiment; the release guard stays unchanged.

The experimental packed mixer was removed: exact PCM output alone did not
justify its extra complexity without a demonstrated independent speed gain.
Strict O3 on the vehicle adapter added 10,944 linked bytes for negligible FPS
improvement and was rejected. Release retains O2 with LTO; `--no-lto` permits a
comparison build. LTO keeps conservative linker math/alias/wrap flags and the
original per-source arithmetic contracts.

## Changes and verification

- Batch five camera probes per articulated hull. Every probe retains vehicle
  order; 4096 clearance answers match the checkpoint. Actual collision-pose
  refits fall from 53,680 to 10,596 in the crowded fixture.
- Filter camera packet lanes with conservative static surface bounds before
  their original plane/edge tests. 250,000 rays match under both strict and
  integration math. Candidate order and final hit arithmetic are retained.
- Use exact VR4300 word floor/ceil conversions for BVH coordinates and outward
  render bounds. The target test passes 617,834 inputs, including subnormals.
  Two million bounds comparisons retain the checkpoint's overflow/fail-open
  behavior and partial outputs.
- Size contact stamps to the map's actual 7650 edges / 2704 vertices. This
  reclaims about 6 KiB; an immutable 64-entry edge-feature cache uses about
  3 KiB of that. Its native replay records 41,830 hits / 6504 misses. It retains
  feature order, width and the original feature factory's output.
- Cache projection setup per fenced slot, layout and zoom. 49,832 complete
  viewport states match; perspective evaluations fall from 99,664 to 4834.
- Select the extremal box corner per frustum plane once per view. The predicate
  retains Tiny3D's strict comparisons and floating-point grouping; two million
  box decisions match. Posed vehicle and effect overflow checks also pass.
  An independent FPS gain from this change was not demonstrated.
- Record immutable world texture binds once. 25,600 mock binds retain palette,
  texture and parameter commands. The real effects ROM cycles all weapons and
  reports zero RDP errors/warnings; frontend lifecycle is checked separately.
- Reuse aligned overlapping pose endpoints in the existing fixed cache slots.
  Advancing/reversing frame-pair tests halve DMA bytes (768,000 → 384,000),
  without additional cache storage or changed interpolation data. Alignment
  prevents PI invalidation from discarding copied neighboring cache lines.

Native gameplay traces compare **all checkpoint simulation adapters and inline
headers**, rather than sharing today's collision code. Both ordinary and LTO
candidates retain all 144,166,856 state bytes over 15,300 ticks, replay plus six
showcases. The native validation suite passes 39 groups; target release, quiet,
telemetry and reload links plus 27 entry-point configurations pass. The added
LTO trace is also a maintained validation group.

The frozen tick-1148 before/after Ares game-image crops match **all 427,500
captured pixels**, covering four cameras and vehicle/weapon/HUD geometry. This
is a direct scene comparison, not proof for every possible scene.

## Next larger opportunities

The instrumented 16 KiB diagnostic build gives these inclusive CPU means:

| Phase | Combat | Vehicles |
| --- | ---: | ---: |
| Vehicle physics | 2.388 ms | 12.849 ms |
| Player/pickup/pair simulation | 4.560 ms | 1.803 ms |
| Camera/view preparation | 2.121 ms | 5.982 ms |
| Animation | 5.915 ms | 3.208 ms |
| World submission | 6.764 ms | 6.457 ms |
| Object submission | 3.606 ms | 2.740 ms |
| Audio | 2.823 ms | 3.092 ms |
| Observed queue waits | 0.564 ms | 0.059 ms |

These are diagnostic costs before the final changes, not release FPS. Focus
next on collision feature evaluation and vehicle camera preparation; profile
within those routines before changing them. The existing world candidate cache
already has a 94.2% hit rate and no overflow in the replay. Increasing every
cache or adding a zero-vector shortcut (zero hits in 114,677 queries) is not
supported by those observations.

- [x] Establish baseline and independent checkpoint comparison.
- [x] Reduce repeated work without asset or timing reductions.
- [x] Reject O3 / packed mixer candidates; measure accepted configuration.
- [x] Validate native state, target configurations and direct scene pixels.
- [ ] Recover >25 FPS vehicle scenes.
- [ ] Reach nominal 30 FPS in complex four-player scenes; check hardware.

## Reproduce

```sh
build/n64-python/bin/python port/n64/validate.py --group host --group contracts \
  --group assets --group equivalence --output-dir build/n64-optimization/validation
build/n64-python/bin/python port/n64/validate.py --group target \
  --output-dir build/n64-optimization/target-validation
build/n64-python/bin/python port/n64/build.py --preset release --vi-benchmark \
  --output-dir build/n64-optimization/quiet
build/n64-python/bin/python port/n64/test_word_round_rom.py \
  --output-dir build/n64-optimization/word-test
```

Run ROMs in Ares to read timing, rounding and RDP results. Build/packing success
alone does not confirm execution. Ares pauses when unfocused: raise its window
while running; no emulator preferences were changed. Black startup captures
were not evidence of allocation failure.

Ignored local evidence, ROMs and exact source/asset/toolchain manifests are in
`build/n64-optimization/`. `comparison.html` contains the final audit.
`--benchmark-page 5` holds the detailed CPU cost page. Paced full diagnostics
retain 2560 exact samples per bank (sufficient for the 75-second paced run),
while quiet VI banks retain their original 5120 entries. Timing counters and
clocks are excluded from release and quiet modes. Game assets remain private.

## Collision and camera follow-up (October 10)

Base for this pass: `892fd19a` (first optimization commit, PR #3). Diagnostic
page 6 now measures original ground/contact calls, feature construction,
contact tests, sweeps, pairs, suspension and world/hull/aim camera rays. The
normal generated solver remains byte-for-byte unchanged; diagnostic wrappers
are separate and clocks/storage are absent in release and quiet modes.

Before this follow-up, the 16 KiB diagnostic fixture gave these vehicle-frame
means, in microseconds (inclusive and overlapping): ground 4033, feature
construction 3299, narrow tests 298, sweeps 1897, pairs 51, suspension 709,
world camera fan 1166, hull fan 1700, aim ray 1275; total physics 12474 and
view preparation 6632. These identify feature construction/sweeps and camera
traversal as useful targets. Narrow tests and pair handling are small **in this
replay**; clustered collision stress remains separate work.

The accepted candidate measures **25.3 overall / 26.6 combat / 24.1 vehicle
FPS**, with 49 KiB free, versus 25.0 / 26.4 / 23.7 at the first checkpoint.
P95 remains 66.8 ms; maximum is 167.1 ms overall / 66.8 ms vehicles. This is a
small improvement; >25 FPS vehicles and the 30 FPS goal remain open.

Accepted changes:

- The hull camera traverses one tree for its five rays. It shares the pose,
  basis, origin, node bounds and triangle edge data, preserving each lane's
  node/triangle order, arithmetic and clipping predicates. The original
  single-ray weapon kernel is unchanged. 160,000 packet lanes match that
  checkpoint kernel; full camera-clearance fixtures also pass.
- The existing 32-entry polygon cache serves contacts, sweeps and world/camera
  rays. Immutable projected endpoints avoid repeated linked-edge traversal
  and vertex projection. The zero-height constructor preserves original
  metadata, point order, helpers and containment expression; nonzero-height
  contacts retain the original factory. All 4916 source factories and 765,000
  near-edge/vertex containment probes match. Cache capacity/RAM is unchanged.
- Native validation generates today's solver into isolated outputs, and the
  checkpoint comparison generates the checkpoint's own solver. Previously,
  sharing the generated implementation could conceal a generator regression.
  Ordinary and LTO traces still match all 144,166,856 bytes over 15,300 ticks.

Rejected or neutral experiments are preserved only in ignored local artifacts:

| Candidate | Overall FPS | Vehicles | Finding |
| --- | ---: | ---: | --- |
| Smaller candidate cells | 24.7 | 23.0 | Faster native run, slower N64; rejected |
| Joint matrices + smaller cells | 24.2 | 22.3 | Rejected |
| Joint matrix reuse with original cells | 25.0 | 23.7 | Neutral; removed |
| Candidate octant masks + joint reuse | 24.8 | 23.2 | Extra mask work/RAM; removed |
| Camera packet with those prototypes | 25.2 | 23.8 | Isolate useful camera change |
| Size-optimized solver with prototypes | 24.1 | 22.0 | Smaller code, slower; rejected |
| Size-optimized solver / camera only | 24.5 | 22.8 | 55 KiB free, lower FPS; rejected |
| Two outlined solver phases / camera only | 25.2 | 23.9 | Neutral; removed |
| Camera only, normal O2 | 25.2 | 23.9 | Retained |
| Shared projected polygons, initial modulo loop | 25.2 | 23.9 | Use branch for closing edge |
| Final candidate | 25.3 | 24.1 | Retained, still below gate |

The smaller-cell experiment reduced native candidate scans from 3,307,490 to
1,198,079 while returning the same 216,665 IDs. Cache hits fell from 94.2% to
75.7%, causing more BVH refills; its native speed gain did not transfer to N64.
Quarter-sized cells had only 38.3% hits and were not promoted to a target build.
An exact vertical-sweep shortcut was also left unimplemented: only 7206 of
114,677 native sweeps were vertical. These measurements discourage adding
branches and cache machinery solely on the strength of work-count reductions.

The follow-up native suite passes 43/43 groups. Four ROM modes link and 27
entry-point configurations compile. All 427,500 captured gameplay pixels in
frozen tick 1148 match the first-pass image. Local ROM manifests, timing and
comparison evidence are in `build/n64-collision-camera/`. The private asset
bank remains pinned to `3dcc8d0b7db38c560cd521a85e3ea6ecf18f85a7`.

After diagnostics, vehicle means were: ground 3912 us, feature construction
3241, narrow tests 242, sweeps 1933, pairs 50, suspension 723, world camera
1269, hull camera 661, aim ray 1396; total physics 12029 and view preparation
5937. The clearest reduction is hull-camera work (1700 → 661 us) and total
view preparation (6632 → 5937 us). Physics costs otherwise changed little;
shared polygon projections do not establish a large independent improvement.
Diagnostic nesting and clock overhead remain included; the quiet VI result is
the acceptance measurement. Frontend lifecycle passes 37/37 with zero RDP
errors/warnings. The full 30 FPS target still needs substantial work.

## Solver attribution and terrain experiments (October 10)

Base: `eba62e5e`. This follow-up retains only diagnostic improvements; none
of its terrain prototypes demonstrated an adequate target FPS gain. Release
keeps the flat integer-bounds predicate and its existing RAM layout. Assets,
original solver bodies, physics frequency and render commands are unchanged.

Diagnostic page 7 separates force calculation, integration, control,
publication, complete vehicle steps, player contacts and sky drawing. The
normal generated solver still has SHA256
`f01429a630e6f8649194069255efc710f7bfbcebade0ca5af44941d8adeb7b37`.
Diagnostic wrappers time the original bodies without editing them. All new
clocks and metric storage are excluded from release/quiet builds.

| Inclusive diagnostic phase | Combat | Vehicles |
| --- | ---: | ---: |
| Force calculation | 0.350 ms | 6.210 ms |
| Integration | 0.096 ms | 1.990 ms |
| Control | 0.244 ms | 0.384 ms |
| Publication | 0.020 ms | 0.188 ms |
| Complete vehicle steps | 0.960 ms | 9.307 ms |
| Vehicle/player contacts | 1.086 ms | 0.837 ms |
| Whole vehicle update | 2.370 ms | 12.194 ms |
| World drawing | 5.768 ms | 5.518 ms |
| View preparation | 2.217 ms | 5.869 ms |
| Sky drawing (part of world) | 1.517 ms | 1.419 ms |

These clocks overlap. Force includes ground/contact work, integration includes
sweeps, and step includes force/integration/control/publication. Player-contact
clocks can include damage callbacks. Whole vehicle update includes additional
seat, weapon, support and lifecycle work. Do not add these rows or interpret
the whole-update/step difference as an unmeasured solver body. Ground feature
construction and sweeps remain useful targets; control/publication are small.
Sky is measurable but does not explain most world time.

The terrain experiments preserve original chunk order, materials, triangles,
textures and the exact culling predicate, including its expression grouping:

| Quiet VI experiment | Overall | Combat | Vehicles | Observed free heap |
| --- | ---: | ---: | ---: | ---: |
| Flat baseline repeat | 25.3 | 26.6 | 24.0 | 47 KiB |
| Hierarchy with plane containment | 25.1 | 26.5 | 23.8 | 43 KiB |
| Hierarchy with rejection only | 25.0 | 26.4 | 23.6 | 43 KiB |
| Immutable float bounds | 25.3 | 26.6 | 24.1 | 42 KiB |

Same Ares/NTSC/4 MiB/three-surface/two-slot/32 KiB-queue fixture. Each row
samples 75 seconds after warmup. End-of-run live free heap also reflects
residency at the endpoint; it is not a fixed-allocation measurement. The
baseline is consistent with the preceding 25.3/26.6/24.1 result.

Both hierarchy variants use 63 nodes and 225 IDs. Their one-time CPU allocation
is 1712 bytes, including four visibility bitsets; linked footprint grows about
2776 bytes. Strict and target-math sanitizer fixtures match 22.5 million actual
map chunk decisions for each variant, including clipping boundaries, scopes,
signed zero, nonfinite fallback and original draw order. In the 50,000-view
fixture the containment variant visits 1.14 million nodes + 1.98 million leaf
chunks, versus 11.25 million flat chunk tests. The simpler variant visits
1.20 million nodes + 2.39 million chunks. These are work counts, not speed.

Containment costs 2.264 ms of vehicle-frame view preparation and lowers world
drawing from 5.449 to 2.822 ms in the matching diagnostic trials. Moving work
between timers explains most of that apparent world improvement. The small
combined CPU reduction does not transfer to better quiet VI results. Extra
bookkeeping, branches and cache/code footprint are plausible explanations,
not independently proven causes.

Float bounds use 5400 immutable bytes and preserve every int16 coordinate
exactly. Two million strict/target-math SDK comparisons pass. Its 0.1 FPS
vehicle difference is within the observed baseline variation; losing about
5 KiB of live headroom is not justified. All three prototypes were removed
from maintained code, with their prototype implementations and ROM manifests retained in
ignored `build/n64-terrain-solver/` for reference.

Native checkpoint traces again preserve all 144,166,856 bytes over 15,300
ticks under ordinary and LTO builds. The initial experiment suite passed
44 groups (including the temporary hierarchy test). The final host/contracts/assets suite passes 41/41 groups; the five target
groups pass, including 28 configurations / 112 translation units. Results
are saved separately in that directory. Page 7 is included
in the maintained target configuration matrix, and the benchmark test checks
all 40 phase accumulators. The >25 vehicle FPS and final 30 FPS gates remain
open; this pass claims no production speed improvement.

```sh
build/n64-python/bin/python port/n64/build.py --benchmark --paced30 --lto \
  --rspq-buffer-kib 16 --benchmark-page 7 \
  --output-dir build/n64-terrain-solver/solver
```

Ares showed a black viewport even for the previously verified release.
Restarting Ares restored rendering; no preferences were changed. A black
capture was not treated as an allocation failure or benchmark result.

## Four-candidate strategy investigation

Checkpoint: `c860aa12`. This investigation separates native work counts,
instrumented target CPU costs, serialized graphics controls, and quiet VI
acceptance. Original assets and 30 Hz simulation remain intact. None of these
measurements establishes a global optimum or a real-console FPS floor.

### Ground and contact processing

**Retained candidate: one conservative world candidate stream per vehicle
step.** The initial mass-point envelope is collected once, with a fixed
64-ID limit. Individual contacts and sweeps keep their exact quantized query
bounds, original BVH order and unchanged feature/plane/edge kernels. Queries
outside the envelope, and envelope overflows, use the existing cell cache.
The entry adds 156 workspace bytes; there is no per-frame allocation or growth.

In the native replay, force-query candidate scans fall from 1,517,415 to
780,135 (48.6% fewer). Integration scans fall from 1,424,040 to 703,194
(50.6% fewer); suspension scans fall from 366,035 to 267,845. The actual
per-query candidate IDs, input bits and hit/count results remain identical
across 303,874 queries. Independent ordinary/LTO traces preserve all
144,166,856 state bytes over 15,300 ticks. The normal generated solver remains
byte-identical; this change is in its world adapter.

First quiet trial: **25.6 overall / 26.6 combat / 24.7 vehicle FPS**, versus
25.3 / 26.6 / 24.0-24.1 previously. A combined trial with the unsuccessful
partial-store animation experiment repeats 25.6 / 26.6 / 24.6. The retained
configuration repeats **25.6 / 26.6 / 24.7**, with 46 KiB live free heap.
P95 remains 66.8 ms. Vehicle maxima vary between 66.8 and 100.2 ms across
these trials; the mean gain is not a floor or tail-latency guarantee.

The candidate fixture also exercises random/nextafter bounds, cold/empty
entries, outside-envelope queries and 64-ID overflow fallback under strict
and integration math. Each body-enabled run matches 150,000 raw streams,
uses 40,524 shared streams and triggers 9,478 overflow fallbacks.

Further strategies:

- **Packet feature construction: conditional follow-up.** Sharing candidate
  selection is safe and now useful. Sharing complete contact lists is harder:
  query width, radius, edge/vertex eligibility, deduplication stamps and bounded
  feature-list saturation are query-dependent. A packet implementation must
  emit each lane's original ordered list, not one union contact list. Profile
  factory work again after this accepted broad-phase reduction before taking
  on that larger rewrite.
- **Immutable topology/layout specialization: still open.** Test compact
  surface/edge views or precomputed edge bounds using a bounded hot working set.
  Keep all original factory arithmetic and ordering. Measure increased RDRAM
  footprint and cache traffic on N64; prior finer-cell experiments show native
  scan-count improvements alone are insufficient.
- **Larger generic caches: low priority.** The existing cell cache already had
  about 94% hits and no replay overflow. The accepted envelope improves the
  amount scanned per query instead of merely increasing cache capacity.

### Integration and sweeps

The native replay issues 88,559 integration sweeps. 72,500 (81.9%) have no
surface candidates. Only 273 sweeps occur in a second correction pass; 88,286
are in the first pass. Only 21 report a hit in this replay. Rare hits remain
essential collision behavior; these counts are not permission to skip tests.
Crowded vehicle impacts and overturned vehicles need separate stress coverage.

**Most specific next candidate: exact per-pass Banshee duplicate reuse.** The
retail definitions contain 22 Banshee mass points but 15 unique local positions;
seven pairs repeat positions. The other three vehicles have no such pairs.
The integration query has no radius parameter, so those repeated positions
can produce identical sweeps within a pass. In the combined native workload,
a 16-entry recent-query cache could catch 25,109 / 168,917 sweeps (14.9%);
1/2/4/8-entry caches catch none. In the Banshee showcase the duplicate share
is 31.8%. Generic search/hash overhead is therefore a poor starting point.

A better prototype would precompute authored position aliases, reset validity
per correction pass, and directly reuse a result only when input point/vector
bits and flags match. Preserve defined output fields on misses, surface-order
and equal-distance tie behavior, every mass-point stuck flag, and the original
worst-collision reduction. Do not remove mass points or their force/mass
contributions. This has a limited ceiling: it affects a fraction of the roughly
2 ms integration path, and the accepted envelope already accelerates those
queries. It is source-supported, not yet a measured target speed win.

**Lower-priority options:** batch the remaining sweep broad phase within each
pass, or share immutable polygon setup. Correction passes change position and
orientation, so their candidate certificates must be renewed or checked for
containment. The current polygon cache already shares projections; another
cache must show useful misses/work before consuming RAM. Reducing correction
passes, sweep frequency or collision precision is outside the lossless scope.

### Animation preparation

Page 8 now separates compressed decode, scatter, writeback, ROM-pose sampling,
pose interpolation and DMA. Costs are inclusive where nested (sample includes
DMA). Mesh/pose counts cover different helper families and are not FPS.

| Diagnostic cost | Combat | Vehicles |
| --- | ---: | ---: |
| Compressed decode | 1.396 ms | 0.293 ms |
| Vertex scatter | 1.450 ms | 0.278 ms |
| Measured mesh/pose writeback | 0.602 ms | 0.293 ms |
| ROM-pose sample | 0.809 ms | 0.843 ms |
| Pose interpolation | 0.712 ms | 1.340 ms |
| DMA (within sample) | 0.589 ms | 0.638 ms |
| Whole deferred body/first-person animation | 5.693 ms | 3.205 ms |

**Rejected target prototypes:** six-byte XYZ stores preserving adjacent normals,
and a checked zero-normal template path with direct decoded-word copies. Both
pass native byte comparisons at all 257 blend fractions, odd/even counts,
normals/colors/UV/padding preservation, and zero-normal classification/fallback.
The actual o64 target assembly was inspected. Partial stores returned
25.2 / 26.6 / 24.0 alone and 25.6 / 26.6 / 24.6 with body candidates.
Direct-word copying with body candidates returned 25.5 / 26.6 / 24.5.
Neither establishes an additional quiet VI gain, so neither remains in release.
Their source and ROMs remain in ignored research output. A separate CPU-cost
trial measures combat scatter at 1.420 ms, versus 1.467 ms with the ordinary
kernel in the matching reuse profiler. This small difference does not establish
a substantial CPU gain. Fewer instructions are not enough evidence; memory
traffic, cache locality and scheduling merit isolated kernel tests before more
arithmetic variants. Their exact contribution was not measured.

**Decode caching is poorly supported by this replay.** Exact asset/frame-pair/
fraction keys repeat consecutively in less than 1% of combat calls and about
6% of vehicle calls. Same-frame repeated keys account for about 3% of combat
calls and less than 1% in vehicles. A multi-mesh decoded cache consumes scarce
RAM for little observed reuse; one-slot reuse has a small potential ceiling.
These are rounded call percentages, not saved-time percentages.

Other strategies and prerequisites:

- **Coalesce redundant writebacks:** small, low-risk opportunity if dirty
  ranges and the first RSP borrower are tracked correctly. Compression followed
  by a locomotion blend can write back the same mesh twice. The measured entire
  mesh/pose writeback bucket is only about 0.6 ms in combat, so the removable
  subset is smaller. Animation is deferred inside drawing, not wholly before
  RSP submission; do not move writes past the first borrower or its slot fence.
- **Exact endpoint copies / full-weight blend specialization:** preserve signed
  truncation and every output byte. Do not assume seated bodies are static:
  exported seat clips contain 4-65 frames, and service clips 10-126. First
  measure endpoint/weight frequencies on the large meshes; tiny hatch/marker
  endpoints alone will not produce a substantial gain.
- **Predecoded endpoints or sparse-delta formats:** can reduce integer work but
  increase resident bank/cache size or indirection. Require operation-weighted
  reuse/sparsity counts and a target trial, not just compression ratios.
- **RSP animation:** architectural experiment, not presumed free offload.
  Preserve CPU signed interpolation/truncation, endpoint DMA alignment,
  immutable queued inputs, cache coherency, and CPU overlays/blends that read
  output vertices. Geometry already has a substantial pending tail. Establish
  RSP capacity first, or fuse animation into vertex loading to avoid an extra
  round trip and fence.

### Frame scheduling, graphics and hardware

Page 9 shows the existing serialized geometry-fence/RDP-drain clocks together
with CPU costs and coarse SP/DP status samples. Audio servicing runs during
these waits and its clock overlaps them. DP-busy percentages count polls;
they are not time-weighted utilization. Serialization changes render cadence,
simulation ticks per frame and overlap, so these are not release FPS costs.

| Serialized control (stock body adapter) | Combat geometry tail | Vehicle geometry tail | Vehicle following RDP drain |
| --- | ---: | ---: | ---: |
| Normal pixel coverage, status sampling | 16.001 ms | 18.469 ms | 0.042 ms |
| Empty 3D scissor, same geometry | 15.894 ms | 18.178 ms | 0.036 ms |
| Empty scissor + minimal triangle attributes | 15.683 ms | 18.306 ms | 0.036 ms |

The empty-scissor control suppresses 3D pixel coverage, retaining geometry
submission, transformation and culling. The minimal control retains culling
but strips shade/texture/depth draw flags through a verified linker wrapper;
the installed Tiny3D library and SDK are untouched. These controls are
restricted to serialized benchmarks by both argument and compile-time guards.
Neither is a proposed visual simplification or a playable release option.
DP is busy in 96% of vehicle-tail polls in the first two controls (95% in the
third); SP is not halted in sampled tail polls. Merely reducing pixel coverage
or packet attributes does not materially shorten this measured tail.

**Important source finding:** Tiny3D's `rspq_triangle.inc` calculates attribute
slopes using combined vector lanes even when some packet attributes are
omitted. Thus the minimal-packet control does not remove all setup arithmetic.
Its vertex loader also transforms normals without directional lights, and
matrix setup normalizes three normal-matrix vectors. The source deliberately
avoids a runtime lighting branch because of scheduling costs. Both gameplay
and frontend currently set zero lights and use no custom vertex FX.

**Highest-priority graphics strategy:** investigate a compile-time unlit RSP
variant or targeted command specialization. Keep MVP/projection, homogeneous
W, clipping/fog, UVs, color arithmetic and output packets unchanged. Eliminate
only normal/light/FX work proven unused under explicit zero-light/FX-none
preconditions. A static specialization avoids the generic runtime branch.
Build it as a local library override, guard unsupported lighting/FX, preserve
clipping-overlay layout/restore metadata and the stock fallback, and verify
RSP vertex/packet goldens plus multi-angle Ares pixels. This is a concrete
source-supported next prototype; its gain has not been measured here.

Other scheduling/visibility strategies:

- **Earlier independent simulation while waiting:** conditional on actual
  waiting slack. Preserve 30 Hz tick order, input edges, pause/menu ownership,
  catch-up ceilings and geometry fences. Current ordinary wait/queue clocks
  are small; the graphics tail is large. Do not add display buffers/latency
  merely to hide a throughput bottleneck.
- **Conservative occlusion / original PVS:** promising for indoor maps, more
  modest here. The retail map has 30 clusters, 70 portals and a 120-byte PVS.
  A sample of its 71 starting locations plus 0.62 Z sees 26 clusters at 62
  locations; the other counts are 21-27. This is not a camera replay. Original
  PVS cannot simply be trusted after occluder simplification: derive conservative
  chunk memberships, account for altered geometry, and fail open outside known
  leaves. Preserve the FOV bleed and verify that no visible pixels disappear.
- **Triangle/vertex batching and command locality:** inspect actual RSP command,
  DMA and clipping work after unlit specialization. Current indexed strips and
  immutable blocks already remove much CPU submission work. Preserve each
  vertex attribute and primitive ordering; avoid precision/LOD reductions.

Hardware acceptance remains open. Use the same pinned asset/toolchain bank,
4 MiB configuration, NTSC, three display surfaces/two geometry slots/32 KiB
queues, warmup and 75-second quiet replay. Run baseline/candidate/baseline
repeats, record exact ROM SHA, actual VI poses, interval tails, fresh-pose
skips, memory minima and audio underruns. Add clustered crashes, all vehicles,
scoped long views, active shields/camo and mixed reloads. A console/capture feed
was not available to this investigation; Ares results are not console evidence.
The >25 vehicle and final 30 FPS gates remain open.

The maintained native work-count tool can reproduce the query audit without
changing source or banks:

```sh
build/n64-python/bin/python port/n64/investigate_vehicle_queries.py \
  --output-dir build/n64-strategy-research/query-flat --no-vehicle-body-candidates
build/n64-python/bin/python port/n64/investigate_vehicle_queries.py \
  --output-dir build/n64-strategy-research/query-body --vehicle-body-candidates
```

Ignored evidence, prototype implementations and exact ROM identities are under
`build/n64-strategy-research/`. The retained production change is the bounded
body candidate stream; diagnostics and investigative tooling carry the findings
forward without retaining the failed animation kernels.

Final verification: host/header/checkpoint groups pass 15/15, including ordinary
and LTO traces against `c860aa12`; contracts/assets pass 28/28. The five target
groups pass, including 33 configurations / 132 translation units. Frozen tick
1148 retains every one of 425,250 gameplay pixels in a four-camera crop; macOS
chrome and its top-three-row content shadow are excluded. The frontend runs
all eight weapons and match/results/menu transitions: 37/37, zero RDP errors
or warnings, using the previously verified 8 KiB validation queues.

The 32 KiB validator lifecycle repeatedly produced a black viewport even after
an emulator restart. The matching 8 KiB fixture completed. The SDK validator
has a bounded 12-buffer journal; its exact failure cause was not captured, so
this is recorded as a validation-configuration constraint, not proof of OOM
or a physics regression. Validation defaults now select 8 KiB unless explicitly
overridden. Normal release/quiet queues remain 32 KiB. Hardware acceptance is
still separate.

## Expansion Pak investigation (October 12)

Base: merged full-roster `d071efc5`. This is a research checkpoint, with an
isolated host/target cache prototypes; no default cache, renderer, asset or timing
budget changes. The investigation also repairs a map-coordinate error in the
native vehicle adapter; correctness results are recorded separately below. The prior conclusions were retrieved from **Halo Combat
Devolved - Memory Layout**, conversation `01a12227-ba61-7421-abb0-40443b0026d4`,
including the first optimization, collision/camera, terrain and four-candidate
investigation turns. The relevant requests/conclusions are saved locally in
`build/n64-expansion-research/conversation-evidence.json`, alongside the original
`n64-optimization`, `n64-collision-camera`, `n64-terrain-solver` and
`n64-strategy-research` evidence.

### What the extra memory can change

Current 8 MiB, four-player quiet replays leave **3083 KiB on Sidewinder through
4429 KiB on Longest** at the result page. Those are endpoint samples, not
minimum-free or largest-contiguous-block guarantees. Reserve optional working
sets before map loading, release map-owned tables on unload, and retain a
fallback until lifecycle/peak-residency measurements pass. The earlier Wizard
allocation failures demonstrated that total free bytes alone are insufficient.

Use RAM to retain computations with immutable inputs, or to store offline
visibility/topology certificates. Preserve simulation order/frequency, source
collision arithmetic, animation poses and the RSP geometry fences. Larger
display or command queues should wait for measured acquisition/backpressure:
they do not by themselves shorten the CPU or geometry workload.

The historical timings are attribution evidence, not current full-roster
costs. Vehicle feature construction was around 3.2 ms; animation decode and
scatter each around 1.4 ms in combat; ROM-pose DMA around 0.6 ms. The serialized
geometry tail remained around 16–18 ms even when pixel coverage was suppressed.
These buckets overlap. Removing DMA cannot remove interpolation/scatter, and
a CPU saving need not improve presentation if geometry remains critical.

### First CPU experiment: collision feature working set

The world candidate cache's old 94% hit rate was a reason to avoid indiscriminate
growth. The separate **32-prism / 64-edge feature caches** have a different
working set. The new probe records their actual requests, then checks its
simulation against the production hit/miss counters.

Blood Gulch's 4500-tick host replay (150 simulation seconds, not the 75-second
native timing interval) gives:

| Entries per feature cache | Prism misses | Edge misses | Incremental RAM |
| --- | ---: | ---: | ---: |
| Accepted 32 prism / 64 edge | 17,351 | 8,102 | 0 |
| 128 / 128 | 6,201 | 2,995 | 13.5 KiB |
| 512 / 512 | 984 | 1,128 | 73.5 KiB |

The 512-entry isolated C prototype realizes the modeled counts: **91.7% fewer
combined factory misses** in that replay. It retains every byte of
**403,679,160** recorded gameplay-state bytes across all 13 maps, Blood Gulch's
replay and six showcases. SHA256:
`60c73faaa2b119e1791c489b521fb5f5a3807a38af08f84dbc6c74dcd129dfe1`.
ASan/UBSan pass, and **132,968** source surface/edge factories match the original
factory outputs across the roster. An independent adapter built with the same
sanitizer/compiler contracts supplies the state reference; its digest is not
interchangeable with the older nonsanitized trace. Actual call counts remain
identical. Rendering/camera-only calls are outside this probe.

Quiet target trials use a matched 75-second four-player Blood Gulch replay:

| Adapter | Extra RAM | FPS | Vehicle segment FPS | P95 / maximum interval |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 0 | 24.1 | 22.0 | 66.8 / 133.7 ms |
| 128 / 128 | 13.5 KiB | 24.2 | 22.1 | 66.8 / 167.1 ms |
| 512 / 512 | 73.5 KiB | 24.0 | 21.9 | 66.8 / 167.1 ms |
| Baseline repeat | 0 | 24.1 | 22.0 | 66.8 / 133.7 ms |

Removing factory misses does **not establish a target speed gain**. Neither
capacity justifies promotion; the default remains 32/64. An explicit
`--feature-cache-slots 128|512` builds a separately named diagnostic adapter,
requires a benchmark/QA mode, asserts 8 MiB on target and records all generator
inputs in its manifest. Rendering/camera-only calls remain outside the host
probe. New-map on-foot routes are not Sidewinder driving stress tests.

Full immutable tables cost much more: dense prism/edge payloads total about
806 KiB on Blood Gulch and 1674 KiB on Sidewinder, before allocator padding.
A compact header/point/edge-index design is about 505/1101 KiB, but requires new
access/copy code. The 74 KiB working-set experiment comes first. Loading a dense
table removes construction after load but does not remove per-query feature
selection, contact tests or query-dependent width/height handling.

### Largest map-specific opportunity: source visibility

The source PVS was inspected across all 13 owned maps, using original render
leaf-to-triangle references. Counts below are the median **unweighted source
cluster row**, before frustum culling; they are not a camera replay, packed-chunk
result, pixel proof or promised FPS gain. Triangles without membership stay
visible, including Chiron's four unassigned triangles.

| Map | Median source triangles permitted / total | Raw PVS | Assessment |
| --- | ---: | ---: | --- |
| Chiron TL34 | 1056 / 10494 (10.1%) | 36 B | Strongest first visibility prototype |
| Rat Race | 1548 / 2692 (57.5%) | 64 B | Useful second indoor control |
| Sidewinder | 6334 / 10036 (63.1%) | 280 B | Useful potential, varies by camera region |
| Battle Creek | 2831 / 3317 (85.3%) | 116 B | Smaller typical opportunity |
| Blood Gulch | 5309 / 5503 (96.5%) | 120 B | Usually little benefit |
| Wizard, Boarding Action | 100% in every row | 72 / 328 B | Raw PVS cannot reject geometry |
| Damnation, Chill Out, Derelict | 100% at median | 48 / 40 / 288 B | Limited raw-PVS opportunity |
| Hang 'Em High, Prisoner, Longest | One cluster each | 4 B each | Raw PVS cannot reject geometry |

This is a different experiment from the rejected terrain hierarchy: source PVS
can remove occluded geometry submissions rather than merely reduce the number
of frustum tests. For Chiron, nine 512-chunk visibility rows plus per-chunk
cluster masks occupy **2624 bytes**; camera BSP/leaf lookup and provenance data
are additional. A source-triangle bitset census occupies about 11.6 KiB. The
first implementation should carry original surface memberships through UV
splits/batching, union every contributing cluster in a chunk, and retain
unclassified scenery. Coarse batches spanning rooms may diminish the benefit;
measure packed-chunk rejection before changing batch sizes. Dynamic actor
bounds, portal crossings, scopes and altered transparent occluders must fail
open until conservativeness is demonstrated.

Boarding Action's 435 ms presentation gap cannot be explained away by PVS:
every source row permits its entire map. Fresh inclusive CPU attribution reports
20.1 ms/frame for players, rising to 38.6 ms in combat. The host terrain probe
finds eight candidate-list overflows but **328 full-map queries**, with **4,957,398**
near-triangle calls versus 201,735 on Damnation. A cached overflow sentinel
continues scanning the full map on cache hits. Only Longest also overflows
(81 queries); the other eleven maps have none in these routes. Retaining complete
ordered candidate lists, or offline conservative membership, is the first RAM
experiment for Boarding Action. Preserve the overflow path as fallback and check
candidate order, all state bytes and quiet interval tails; larger lists alone
can make duplicate detection more expensive.

Damnation's inclusive CPU world submission is 16.4 ms/frame and animation 5.4 ms.
Its serialized RSP drain is **68.853 ms**, with a following RDP drain of 0.031 ms.
An empty-scissor control gives **68.784 / 0.033 ms**. Suppressing pixel coverage
barely changes the tail, supporting geometry/command work as a major constraint.
These drains alter scheduling; audio servicing overlaps them and SP/DP polling
percentages are not utilization measurements. They cannot be added to CPU buckets
or substituted for quiet release FPS.
The earlier unlit Tiny3D RSP specialization remains a source-supported candidate,
with no demonstrated target gain yet. It needs little extra RAM, but may matter
more than a memory-heavy CPU cache if geometry is the limiting stage.

### Animation: residency has a bounded ceiling

The current streamed interaction bank is **9,455,056 bytes**, so it cannot all
fit in the spare RAM. Resident payloads for selected groups are about 1.15 MiB
for locomotion endpoints, 2.43 MiB for seat poses, and 3.26 MiB for service poses.
Four simultaneously used clips or a bounded 0.5–1 MiB endpoint arena are more
plausible trials than preloading every weapon state. Selection must come from
current operation/byte-weighted traffic, including mixed reloads and Needler
ammo variants. A direct resident clip reference can remove pair search/DMA;
the existing signed interpolation and scatter/writeback still execute.

The **compressed motion arrays already reside in RDRAM**. Expanding their
aligned track endpoints grows 251,814 bytes to 671,504, an incremental 410 KiB.
That targets byte decode/origin work, not ROM transfer, and still leaves blend
arithmetic and scattering. Precomputing all 257 exact fractions across the
current clips needs over **137 MiB**, even without vertex scatter, so a complete
blend table is outside this budget. Caching final blended poses remains low
priority because the previous exact-key reuse measurements were poor.

### Ranked next experiments

1. **Boarding Action ordered overflow lists:** measure the complete per-anchor
   candidate count and allocate a bounded 8 MiB list pool. Target repeated
   full-map scans; preserve fallback and source ordering. Do not infer capacity
   from the eight overflow refills alone.
2. **Chiron source PVS:** carry source membership through packed chunks and
   measure rejection in the actual four-camera replay before allocating a large
   table. Raw rows permit a median 10.1% of source triangles; conservative
   chunk mapping and pixel equivalence are still unproven.
3. **Expanded animation endpoints:** incremental 410 KiB targets resident byte
   decoding. Profile operation-weighted clip traffic before a 0.5–1 MiB streaming
   endpoint arena; DMA removal cannot eliminate blending and scatter.
4. **Unlit RSP specialization:** little extra RAM, but refresh geometry costs
   and prove transformed vertices/command behavior before adoption. Damnation's
   empty-scissor result makes geometry reduction more promising than larger
   display or command buffers.

Feature-cache growth is not promoted. Every candidate needs separate quiet VI,
CPU attribution, state/pixel checks, interval tails, audio and unload/reload/menu
lifecycle evidence. Reserve working sets before loading maps and measure memory
minima and allocation fragmentation; result-page free heap is not a peak budget.

### Vehicle origin correctness

The adapter still added Blood Gulch's `(68, -118, 0)` origin when registering
native roots on other maps. Sidewinder uses `(0, 0, 0)`: its eight vehicles were
solving contacts in the wrong world. Prepare/publish, flip approach and damage
impulses now use `bg_map_origin()`. This is a correctness repair, not a RAM
optimization, and changes Sidewinder's simulation workload.

The new regression checks 29 native roots across all 13 maps, then 2400
Sidewinder step poses. All eight vehicles encounter source ground and settle;
strict and target-math ASan/UBSan passes agree. The old adapter fails the same
coordinate check. Corrected Sidewinder quiet timing is 9.5 FPS (718 poses),
P95 167.1 ms and maximum 200.5 ms; the prior 9.6 FPS is not a matched
performance comparison because collision contacts changed. No FPS gain is claimed.
Fresh inclusive physics cost is 6.694 ms/frame versus 20.524 ms before repair;
simulation is 25.967 versus 39.009 ms. This is changed contact behavior and cannot
be credited to extra RAM. Presentation remaining slow despite lower CPU cost
supports investigating geometry/visibility alongside CPU caches.
Blood Gulch's 15,300-tick replay/showcases retain all
**144,170,084** state bytes versus `9f1a1e0c` (SHA256
`822988418e44c34db718be9ad6b801e8d605cf38d696d77cf8d59621094575f2`).

The corrected adapter and 512-entry prototype also agree across all maps:
**403,553,812** state bytes, SHA256
`651a4fe40a87442a703d40beeda1e02f419beed393d4d5086317f7f09b9166cb`.
The instrumented terrain probe omits renderer/camera-only calls and checks the
same instrumented source in both adapters. This digest is distinct from the
historical pre-repair experiment above.

The maintained host/contracts/assets suite passes **47/47 groups**. Native
four-player frontend combat/results/menu return completes with **zero RDP errors
and warnings**, using the maintained 8 KiB validation queues. Corrected
Sidewinder's four-view source-start inspection also reports zero RDP errors and
warnings. Temporary Expansion Pak/defocus preferences were restored.

Local evidence is `build/n64-expansion-research/`: `native-costs.json`,
`quiet-timing.json`, `terrain-pressure/results.json`, origin equivalence and
regression logs, screenshots and per-ROM build manifests. The verified release
artifact remains the full-map baseline; these experiments do not replace it.

```sh
build/n64-python/bin/python port/n64/investigate_expansion_assets.py
build/n64-python/bin/python port/n64/investigate_expansion_ram.py \
  --prototype-cache-slots 512 --output-dir build/n64-expansion-research/cache512
build/n64-python/bin/python port/n64/build.py --preset release \
  --initial-map damnation --benchmark --benchmark-page 5 \
  --output-dir build/n64-expansion-research/damnation-cpu
```

## Matched camera geometry and Chiron prototype (October 12)

Base: research `f7d425ab`, including the native vehicle-origin correction.
`investigate_camera_geometry.py` samples **17 fixed simulation ticks × four
cameras × 13 maps**: 884 matched views, with baseline/prototype submission
counts calculated from the same camera matrices and state. It retains the
renderer camera construction, installed SDK float matrices, four-pixel cull
bleed, scoped projection and production AABB predicate. Source map routes differ
across maps; matching means identical tick/camera within each map, not identical
physical routes between differently shaped maps. Dynamic meshes are outside the
host world census. Homogeneous clipping columns are **float estimates**, not
actual RSP clipping operations, cycle counts or timing.

| Map | Mean world vertices / camera | Mean world triangles / camera | Mean batches / camera |
| --- | ---: | ---: | ---: |
| Blood Gulch | 1184 | 746 | 56 |
| Wizard | 2991 | 1633 | 112 |
| Derelict | 5207 | 2952 | 197 |
| Chiron, baseline | 6760 | 4272 | 134 |
| Chiron, conservative PVS | 4565 | 2878 | 90 |
| Damnation | 9990 | 6513 | 234 |
| Boarding Action | 11088 | 7181 | 236 |
| Sidewinder, corrected origin | 9962 | 6912 | 217 |

Native fixed-tick `--geometry-census --snapshot-tick 180` corroborates each
camera's world vertex, triangle, batch and material-change count on Blood Gulch
Chiron, Damnation and Boarding Action, including the Chiron prototype: **20
exact native/host camera records**. Separate per-camera RSP fences give
serialized diagnostics, not production pacing or isolated world-only GPU cost.
The native total-triangle field also includes dynamic objects and first person.

### Conservative Chiron sidecar

`export_chiron_visibility.py` makes a separate provenance-instrumented copy of
the accepted exporter. The shared exporter/batcher and accepted banks stay
unchanged. Original source surface IDs follow UV subdivisions and ordered
batches. The regenerated Chiron bank must match every accepted byte before
export proceeds. Batch masks union all contributing source clusters; source
surfaces without membership and placed scenery retain all clusters. Twenty
batches fail open.

The sidecar is bound to the accepted map SHA256 and contains source collision
BSP nodes/planes, render-leaf cluster IDs, PVS rows and batch masks. This follows
`structure_visibility_find_camera` and `structure_bsp_get_cluster_pvs` in the
original source. Static arrays occupy **78,244 bytes** (76.4 KiB), plus the small
descriptor and a bounded 512-byte traversal stack. This is larger than the raw
row/membership estimate because it includes camera lookup.

The prototype unions rows of leaves touched by a .25-unit ordinary camera
sphere or 1.25-unit scoped sphere, plus plane/rounding margin. Solid, invalid,
unmapped and exhausted traversals retain all geometry. It affects **static
Chiron world batches only**; actors, pickups, effects and first person keep their
existing culling. Retained commands keep their order and material handling.

Actual sampled reductions are **32.5% of world vertex loads and 32.6% of world
triangles**, substantially below the raw source-row opportunity. Forty of 68
Chiron camera samples fail open. The uncertainty fallback is retained for this
first experiment.

The explicit `--chiron-pvs-data visibility.json` switch requires a diagnostic/QA
mode, asserts 8 MiB and emits a separately named ROM. The default renderer and
verified release artifact remain unchanged. Lookup compilation disables
finite-only assumptions, as with the existing conservative render bounds,
so invalid floating-point input cannot turn into permission to hide geometry.

### Validation and native timing

Both strict and target-math ASan/UBSan trials cover 30,000 source camera spheres,
all nine source clusters and over 23,000 valid nearby points. Every sampled
valid point's original PVS row is contained in the conservative union. Synthetic
plane-boundary, outside/solid, unknown batch, NaN, negative radius and cyclic-tree
cases fail open. The accepted renderer source-order checks inspect the default
path with the two explicit research flags disabled. The CPU preparation check
also follows the prototype lookup and verifies that it queues no graphics work.
All **47 maintained validation groups** pass after the final contract recheck.

Frozen ticks **180 and 1148** retain every RGB byte of the 750×567 scaled
four-camera gameplay crop: **850,500 compared pixels, zero changed pixels**.
Window chrome/status and its top shadow are excluded. These eight ordinary/death
views are sample evidence, not exhaustive scope/portal or physical-console
acceptance. Native four-view source-start inspection also reports **zero RDP
errors/warnings**, using the maintained 8 KiB validation queues.

| Quiet 75-second Chiron replay | FPS | Displayed poses | P95 / maximum | Result-page free heap |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 15.5 | 1165 | 100.2 / 100.3 ms | 3721 KiB |
| Conservative PVS | 21.4 | 1612 | 66.8 / 100.3 ms | 3644 KiB |
| Baseline repeat | 15.5 | 1165 | 100.2 / 100.3 ms | 3721 KiB |
| Conservative PVS repeat | 21.4 | 1612 | 66.8 / 100.3 ms | 3644 KiB |

Repeated ABAB controls: approximately **38% higher FPS** and a lower P95 interval
for 77 KiB less endpoint free heap. Both baseline runs display exactly 1165 poses;
both prototype runs display exactly 1612 poses. Quiet measurement contains no
census/profile/serialized fences;
8 MiB, four players, LTO, three surfaces and 32 KiB queues match the baseline.
No host builds/tests run during those intervals.

Local evidence: `build/n64-chiron-visibility/` includes `camera-census/cameras.csv`,
`camera-census/results.json`, `native-census.json`, `pixel-comparisons.json`,
`quiet-timing.json`, `validation-final.json`, sanitizer logs, screenshots and
per-ROM manifests. All payloads and source-derived sidecars remain private. Temporary Ares
Expansion Pak/defocus preferences were restored.
