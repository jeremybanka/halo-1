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
one large contiguous heap block. Collision face indices are reclaimed after
fixing immutable shared-corner pointers. Selected-map payload is approximately
229 KiB for Wizard and 268 KiB for Blood Gulch on the 32-bit target, excluding
allocator overhead, GPU command blocks and the lazily loaded world workspace.
The respective original collision/BVH ROM banks are 119,186 and 369,488 bytes.

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
- [ ] Ares inspection of textures, lighting, seams and all inspection views.
- [ ] Ares menu-to-match/results, cross-map switches and quit/resume under 4 MiB.
- [ ] Four-player VI timing, tail latency and minimum free heap; >25 FPS
      development gate and final 30 FPS target.

The Mac was locked during this implementation pass, so Ares captures and FPS
are pending. Builds and host tests do not establish target visual quality or
performance. Do not replace the previous verified release with these ROMs yet.

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
ROMs are under `build/n64-wizard-audit/`; no screenshots have been captured yet.
