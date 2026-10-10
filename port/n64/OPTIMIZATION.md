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
