# Firefight collision acceleration — 28 October 2026

This prototype adds persistent terrain candidate caches for every actor and
conservative animated bounds for enemy hit meshes. It keeps the existing
collision shapes, triangle ordering, movement solver, damage materials, source
AI selectors and encounter rules. See [the appraisal](../../FIREFIGHT_COLLISION.md)
for the complete paired performance results and remaining costs.

## Implementation and equivalence

Each of the sixteen possible humans/enemies has a dedicated terrain entry;
four more entries serve temporary probes. An entry stores up to 512 ordered,
deduplicated triangle IDs from an expanded grid query. Reuse checks the actor
address, radius, grid rectangle and anchor displacement. Map unload/reset clears
all entries. Recycled actor slots may safely retain IDs when their spatial
envelope still matches: contact answers and actor state are never cached.

The original four small contact lists remain as the final stage. Their refresh
and ordering semantics are preserved, but misses can now filter the actor's
short cached list instead of rescanning/deduplicating grid cells. An initial
direct replacement changed contact order and failed the movement oracle; that
version is excluded. Both the new 512-ID overflow and existing 128-contact-ID
overflow retain exact fallback paths.

Enemy collision meshes are divided into contiguous groups of sixteen triangles,
with a whole-pose bound above them. Bounds refit when the existing animated-pose
cache changes. Rays reject the whole pose or groups conservatively before the
unchanged triangle test. Bounds expand by one packed position unit, handle zero
ray components explicitly, and preserve source triangle traversal order. Equal
distance material/normal decisions, Jackal shield gaps and Hunter weak points
therefore retain their original semantics. Render geometry is untouched.

The linked four-player diagnostic BSS grows by **26,032 bytes (25.42 KiB)**.
`memory.json` records linker section sizes and symbols: 21,280 bytes of actor
cache entries and 4,752 bytes of hit bounds. The 96-byte diagnostic counter block
is present on both sides of the profiling comparison and absent from release.

## Verification

`collision_reference.py` extracts independent pre-change implementations from
`f303c4c9ee0648522a6e8b65147d5ed88c06a301`; the tests do not compare two calls to
the new implementation. Keep that revision available when reproducing in a
shallow checkout.

- **37,440 bit-identical movement steps** across thirteen maps, interleaving
  sixteen units and scratch probes. Full player state and returned impact match,
  covering positions, velocities, grounding/support, crouching, jumps and
  teleports. No floating-point tolerance is used in the accepted test.
- **686,256 exact ray comparisons**, with 234,017 hits, covering all four species
  and twelve clips, seventeen phases, rotated actors, shield up/down, recycled
  slots, short segments, axis-parallel rays and rays through authored vertices.
  Hit distance, damage region/material and reflection normal match exactly.
- The same movement/ray oracle passes with target-style fast-math options and
  floating-point contraction disabled. Native programs use the installed
  VR4300 compiler; host math-option tests are supporting evidence, not a claim
  that Clang is the N64 compiler.
- Synthetic overflow tests cover both cache capacities and exact full scans.
  All sixteen actor entries survive 128 scratch-probe queries, followed by
  480 warm actor queries with zero grid rebuilds.
- Full 1–4P Firefight lifecycle/material/arrival tests; all 26 multiplayer
  presets across thirteen maps; original source spawn rating/selection tests;
  the general movement, terrain, collision, weapons, vehicle and replay
  sanitizer suites pass.
- 39 runtime configurations / 156 target translation units pass. Separate
  native matrix, serialized graphics diagnostics and paced playable ROMs build.

The raw host logs are archived here. `map-dependency-check.json` proves the map
packer's consumed teleporter declaration and packer code are unchanged. Only
the report's whole-`game.c` input hash was refreshed for diagnostic additions;
no map bank bytes changed.

## Native measurement contract

- Ares v148, NTSC 320×240, 8 MiB, audio enabled. These are native N64 programs
  measured in an emulator, not fresh physical-cartridge measurements.
- Both versions include the same reload fix and the same opt-in Hunter/Spirit
  bank from the previous model appraisal. The canonical private model bank is
  not replaced. This isolates collision changes on top of that candidate.
- Baseline/candidate × ordinary/crowded × 1–4 players. Baseline enables only
  `--collision-baseline`; code, geometry, rules and asset input hashes otherwise
  match exactly. Both have the same additional collision instrumentation.
- Ordinary QA3 records 75 observations; crowded QA4 records 45 and restages its
  mixed squad every twenty simulated seconds. Real damage/deaths remain active.
  Discard the first five observations. Headline FPS requires a living human,
  living enemies and no enemies still arriving. Whole-window and
  all-humans-alive summaries remain available.
- `COLLISION` records disjoint game-tick sections over **30 actual ticks**.
  `terrain_us` (capsule movement) and `hit_us` (enemy hit queries) are nested
  services, not extra totals to add. Terrain query counts also include clearance
  and stand checks, so their scope is broader than the capsule timer.
  An unterminated final diagnostic line is excluded when the bounded capture
  stops its emulator during output; the summary records that exclusion.
- Terrain reuse counts either a small contact-list hit or an actor-list hit;
  misses count grid-list rebuilds. `hit_available` counts triangles in meshes
  surviving the original loose actor check; `hit_triangles` counts actual
  narrow-phase calls after shield filtering and optional bounds.
- `PVE_PHASE` still samples one rendered frame per observation. Its simulation
  duration can include several catch-up ticks. Do not invert these averages or
  add nested counters to reconstruct the filtered mean FPS. Queue/audio/HUD
  counters overlap the pipeline sections.
- The extra four-player crowded runs under `gpu/` deliberately serialize RSP
  and RDP drains. Their timings represent outstanding work after submission,
  not complete GPU occupancy. Their FPS is excluded from the headline matrix.
  Zero drain counters in ordinary runs mean this diagnostic is disabled.
- Timing changes can change the observed combat window and render workload;
  match inputs are not a guarantee of identical sampled scenes. Each case has
  one fresh capture, so small FPS differences are not statistical proof.

## Reproduce

From a checkout wired to the private bank and owned source caches:

```sh
build/n64-python/bin/python port/n64/test_maps.py --collision --output-dir build/firefight-collision/host-oracle
build/n64-python/bin/python port/n64/test_maps.py --collision --target-math --output-dir build/firefight-collision/host-oracle-target-math
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/firefight-collision/host-firefight
build/n64-python/bin/python port/n64/test_maps.py --modes --with-pve --output-dir build/firefight-collision/host-modes
build/n64-python/bin/python port/n64/blam/test_vehicle.py --output-dir build/firefight-collision/host-general

build/n64-python/bin/python port/n64/benchmarks/firefight-collision/run_matrix.py build --output build/firefight-collision/matrix --model-bank MODEL_BANK
build/n64-python/bin/python port/n64/benchmarks/firefight-collision/run_matrix.py capture --output build/firefight-collision/matrix --model-bank MODEL_BANK --settings ARES_SETTINGS
build/n64-python/bin/python port/n64/benchmarks/firefight-collision/collect.py build/firefight-collision/matrix
```

`MODEL_BANK` can be the archived
`halo64-assets/assets/covenant-model-appraisal/bank`. The runner also accepts
explicit `--sdk` and `--tiny3d` paths. It uses the same corrected-ground Blood
Gulch override as the earlier benchmarks. `--resume` is only valid for unchanged
ROMs and complete logs. Run one emulator at a time.

For the separate graphics diagnosis, use an independent output directory and
`--gpu --kinds perf --players 4` on the build/capture commands; collect it with
`collect.py CAPTURE --gpu --output OUTPUT/gpu`. A normal appraisal ROM uses
`build.py --firefight --preset release --pve-model-bank MODEL_BANK` with the
same map override, SDK/Tiny3D and an isolated output directory. It has no
collision instrumentation or baseline control enabled.

`provenance.json` records source/header/data hashes, build options, toolchain,
ROM/log hashes and matching checks. Parent commits identify the checkout before
the prototype commit; exact hashes identify the tested working tree.
The checked-in logs can also be reanalyzed without private assets or ROMs using
`collect.py port/n64/benchmarks/firefight-collision --logs-only --output OUTPUT`.
For the archived graphics pair, add `--gpu` and use the `gpu/` input directory.
This validates saved log hashes before reproducing the summaries.
