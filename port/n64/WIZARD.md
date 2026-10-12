# Wizard map port

Blood Gulch and Wizard share one ROM, the existing local multiplayer menu,
Slayer simulation, weapons, characters, HUD and audio. Only the selected map's
render, collision, spawn and item tables are resident. Other maps remain greyed
out. The source-only implementation is on `codex/n64-wizard`, based on the
current `codex/n64-optimize` playtest fixes.

## Source fidelity

The locally owned Xbox Wizard cache supplies the complete 2,972-triangle
render geometry and 1,559 collision polygons, triangulated into 2,844 capsule
collision faces. No architectural decimation is applied. The scenario supplies
48 starts (16 eligible for Slayer), 30 equipment placements, four teleporter
links, eight two-sided ladder sheets and the plasma-pistol/no-grenade starting
profile. There are no vehicles in this map.

Base textures are filtered to 32×32 RGBA16. Compressed lightmap UVs select
original lightmap colors, baked into vertex RGB; shared packed corners differ
by at most eight RGB units. Transparent light shaders become alpha-tested,
tinted emissive sheets with the existing small surface clearance. This is a
lighting/material approximation, not the original Xbox shader pipeline.

Ladders preserve the original climbable collision flag and use the original
vertical-support projection and vertical-intent multiplier. They run through
the existing bounded capsule movement adapter; this is not a full port of the
original biped physics solver.

## Map lifetime

`pack_maps.py` writes private, big-endian `HM64` banks into
`halo64-assets/generated/maps/`. The public repository contains the packer and
loader, not game-derived geometry or pixels. Blood Gulch's existing emitted C
values are serialized without changing its geometry, texture coordinates,
palette or collision floats.

`map.c` validates section lengths, capacities, texture formats, grid ranges,
world layout and local render indices. Individual allocations avoid requiring
one large contiguous heap block. Collision face indices stream through a
768-byte fixup buffer instead of a temporary 32 KiB heap allocation.
Selected-map payload is approximately
214 KiB for Wizard and 268 KiB for Blood Gulch on the 32-bit target, excluding
allocator overhead, GPU command blocks and the lazily loaded world workspace.
The respective original collision/BVH ROM banks are 119,186 and 369,488 bytes.
Large collision blocks are allocated first and read by their original file
offsets. First-person vertices and the accepted animation cache are reserved before
match map allocations. Map blocks and collision fixup pointers are allocated
from largest to smallest; world commands are recorded before the existing body
allocation path. All production workspace sizes and the eight-slot, 70,912-byte
animation cache are unchanged. A temporary four-slot experiment was rejected
and reverted; it is not part of the map addition.

Menu transitions fence and free world command blocks before their backing map
data. Starting another match loads fresh indices before their in-place Tiny3D
conversion. Floor-query caches are invalidated when the map changes. Quit
confirmation retains the current map for resume. Shared models and audio stay
in the existing residency system. The optional Blood Gulch source-BSP diagnostic
uses Wizard's selected collision adapter when playing Wizard.

## Validation and remaining acceptance

- [x] Full existing host, renderer-contract and asset validation: 43/43 groups.
- [x] Address/undefined sanitizer tests for alternating map load/unload,
      all 16 eligible starts, four live teleports and all 16 ladder triangles
      in both climbing directions.
- [x] A staged match produces 15 kills through actual damage, respawn and
      scoring, completing in 55.83 seconds.
- [x] A 2,250-tick four-player replay produces 714 shots and six kills without
      invalid coordinates, vehicles or premature match completion.
- [x] The same map tests pass with the optional Blood Gulch source BSP enabled.
- [x] Release, Wizard inspection and menu-to-results ROMs compile.
- [x] Ares inspection of source starts, upper routes, teleporter approaches
      and one-player architecture; all four pages show zero RDP errors/warnings.
- [ ] Reverify Ares 69-step Wizard → Blood Gulch → Wizard with the restored
      accepted eight-slot cache. Earlier reduced-cache results are superseded.
- [ ] Four-player VI timing, tail latency and minimum free heap; >25 FPS
      development gate and final 30 FPS target.

Initial Ares inspection and the 37-step Wizard menu-to-results flow passed
with zero RDP errors or warnings. Extended cross-map testing found and is
checking allocation-order fixes. Earlier reduced-cache production and RDP-validator builds completed all 69
steps. Those runs are superseded by verification with the unchanged accepted
cache and allocator. The first
quiet replay measured 24.1 FPS, with 253 KiB free heap. Balanced 8×8×4 material
bins measured 24.8 FPS and 337 KiB free, retaining all 2,972 source triangles,
materials, interpolated texture wrap, collision and scenario tables. Existing
color merging still permits an eight-unit RGB difference. Overly broad
16×16×8 bins regressed to 24.2 FPS; 8×8×2 bins measured 24.7 FPS.
The final allocation layout measured 24.9 FPS, early 24.4 / late 25.3,
with 335 KiB free heap and 66.8 ms P95/maximum presentation intervals.
The accepted Blood Gulch checkpoint measured 23.5 FPS in the current session.
A restored-cache run overlapped host tests and is not a clean performance
comparison; an idle-host comparison is pending. Blood Gulch is a regression
check for this PR, not an optimization target.
These are emulator measurements, not real-console acceptance. The >25 FPS
development gate and final 30 FPS target remain open. Do not replace the
previous verified release until the full native lifecycle checks pass.

Reproduction commands:

```sh
build/n64-python/bin/python port/n64/pack_maps.py
build/n64-python/bin/python port/n64/validate.py
build/n64-python/bin/python port/n64/test_maps.py --blam-bsp
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/n64-wizard-audit/release
build/n64-python/bin/python port/n64/build.py --preset release --initial-map wizard --vi-benchmark --output-dir build/n64-wizard-audit/quiet
build/n64-python/bin/python port/n64/build.py --preset release --initial-map wizard --frontend-qa 4 --validate --output-dir build/n64-wizard-audit/frontend-wizard
```

`--wizard-qa 0..3 --validate` selects frozen source-start, upper-route,
teleporter and one-player architecture views. Local logs, build identities and
ROMs and native screenshots are under `build/n64-wizard-audit/`.
`comparison.html` includes the original menu reference, all native inspection
pages, countdown evidence, gameplay video, lifecycle results and VI timing.
The pregame thumbnail follows the selected map, matching the existing dynamic
map name. Wizard and Blood Gulch retain their original source thumbnail frames.

## Scope and Blood Gulch regression contract

This PR adds Wizard to the accepted `d51bde69` Blood Gulch systems. Shared
combat, physics, rendering, HUD, audio and production cache budgets remain the
baseline. Changes in those files are limited to selected-map data binding,
map coordinates/limits, Wizard ladders, map lifetime and diagnostic fixtures.
Blood Gulch geometry, textures, vehicles and weapons are not simplified.
Wizard-only material batching reduces its draw chunks without architectural
decimation; further compromises belong in Wizard's assets rather than shared
systems or Blood Gulch.

The selected Blood Gulch banks produce byte-identical complete gameplay state
against the accepted checkpoint for 15,300 ticks: the four-player replay and
all six showcase scenarios (144,170,464 bytes, SHA256
`5a814a80ae9d49ef69cc96c2826fa21b30cccf8589b57c12349ef40d0e211781`).
The cache implementation and first-person allocator are restored verbatim,
and 36 renderer-helper equivalence checks pass.

```sh
build/n64-python/bin/python port/n64/test_runtime_equivalence.py --reference d51bde69 --streamed-maps --output-dir build/n64-wizard-audit/accepted-blood-equivalence
```
