# Hang 'Em High, Chill Out and Battle Creek

Based on merged main `0ac2d7c9`. New maps retain their source architecture,
collision, Slayer eligibility, equipment weights/timers and starting profiles.
Source graphics/audio remain private in `halo64-assets`.

## Acceptance

- [x] Import all three BSPs, original lightmap colors and placed scenery.
- [x] Preserve Blood Gulch/Wizard banks byte-for-byte.
- [x] Retain existing shared model banks, eight-slot pose cache and queue budgets.
- [x] Original loadouts: Hang 'Em High magnum/no grenades; Chill Out AR/no
      grenades; Battle Creek plasma pistol/four frags.
- [x] 28/25/22 Slayer starts and 43/32/30 item placements. Three/two directed
      teleporter links in Chill Out/Battle Creek; Hang 'Em High has none.
- [x] All starts pass capsule clearance; minimal asset-specific offsets for
      one authored start per new map, resolved by the unchanged contact solver.
- [x] Live 75-second four-controller host replays, source pickup rules,
      teleporters and a 117-step/six-match host menu cycle.
- [x] Initial 4 MiB Ares inspections: zero RDP errors/warnings for all three.
- [x] 46 maintained validation groups; 2,000 actual legacy terrain command
      sequences remain byte-identical despite new foliage material states.
- [x] Final scenery silhouettes/colors from multiple angles: whole-card removal,
      original vertices/UVs retained; 24 direction coverage gate plus 8-angle
      textured full-silhouette comparison (worst 96px 97.1%, 32px 96.3%).
- [x] Map-specific asset batching/reduction trials and quiet four-player timings.
- [x] Blood Gulch/Wizard comparison against the merged checkpoint.
- [x] Native normal-budget cycle and assertion-logging validator: 117/117 steps,
      six completed matches, zero validator RDP errors/warnings.
- [x] Final validator cycle without the diagnostic assertion wrapper: 117/117,
      six matches and zero RDP errors/warnings.
- [x] Native gameplay screenshots and silent gameplay videos for all three maps.
- [x] Committed production release boot reaches the original main menu.
- [x] One PR containing all three maps: https://github.com/jeremybanka/halo-1/pull/6.

## Source limits

Opaque materials use original diffuse textures filtered to 32px; Battle Creek's
64px CI4 ground bakes the original grass/sand alpha mask and detail layers.
Lightmap colors are baked into vertices. Water/glass use static pixel coverage;
portal textures and vegetation poses are static. Full Xbox multipass shaders,
water ripples, reflections and wind are not emulated.

New-map material flags extend the existing byte: 1 transparent cutout without
Z writes, 2 alpha-tested geometry with Z writes, 4 two-sided geometry. Legacy
0/1 command streams are independently compared against the merged source.

Evidence and unshipped experiments live in `build/n64-three-map-audit/`.
Generic foliage collapse was rejected after textured silhouette coverage losses;
architecture and collision remain unchanged during asset-only refinement.


## Asset reproduction

The private `generated/maps` directory holds five `HM64` banks and matching
original collision/BVH banks. `map_catalog.def` keeps the Xbox menu IDs stable.
Source cache files come from the owned disc, not the public repository.

```
build/n64-python/bin/python port/n64/pack_maps.py
build/n64-python/bin/python port/n64/test_maps.py --export-spawn-clearance
build/n64-python/bin/python port/n64/pack_maps.py
build/n64-python/bin/python port/n64/test_maps.py --maps-cycle
```

`map-bins.json` configures only the new maps' spatial material bins; settings
for Blood Gulch and Wizard are rejected. `scenery-reduced.json` preserves the
selected original foliage triangles. `select_map_foliage.py` generates complete
card selections from owned source meshes, clipping their sampled coverage by
original trunk geometry. Blender MCP applies the selection; canonical source
positions/UVs are retained in the packed proxy, avoiding vertex drift.

`audit_map_scenery.py` compares both meshes at identical scale/alignment with
the same filtered textures, including their alpha masks. These are offline
geometry previews, not retail Xbox or native RDP screenshots. Direct Ares
captures are separate. Generic collapse and planar cleanup trials were not
included; flag pedestals and teleporter-base geometry remain complete.

The maintained regression additionally compares 15,300 Blood Gulch simulation
ticks (the replay plus six showcases) against merged main `0ac2d7c9`: all
144,170,464 serialized state bytes match. The original 69-step cycle remains
available; `--maps-cycle` adds three matches, for 117 steps/six live matches.


## Four-player timing and remaining performance work

The final banks retain all BSP architecture and source collision. Hang 'Em High
keeps the original 8×8×4 bins (329 chunks): broader 16×16×8 bins reduced chunks
to 191, but gave no useful timing improvement; finer 6×6×3 bins increased
chunks to 374 and also measured 19.5 FPS. Chill Out uses 6×6×3 bins (238 chunks)
and Battle Creek uses 12×12×6 bins (247 chunks). Battle Creek scenery retains
2,069 of 2,394 source triangles; complete overlapping foliage cards account for
the reduction. Pedestals and teleporter structures remain complete.

| Map | Overall FPS | Early / combat | Late / vehicles | P95 / maximum interval | End free heap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hang 'Em High | 19.5 | 18.7 | 20.2 | 66.8 / 66.8 ms | 266 KiB |
| Chill Out | 20.7 | 20.8 | 20.7 | 66.8 / 66.8 ms | 261 KiB |
| Battle Creek | 20.1 | 19.0 | 21.2 | 66.8 / 100.3 ms | 154 KiB |
| Blood Gulch | 24.1 | 26.4 | 22.1 | 66.8 / 167.1 ms | 22 KiB |
| Wizard | 24.9 | 24.4 | 25.3 | 66.8 / 66.8 ms | 329 KiB |

These are distinct simulation poses displayed by the native VI callback over
75 seconds (75.017–75.050) after a one-second warmup, in Ares NTSC with 4 MiB, release LTO,
three display surfaces and 32 KiB queues. New maps have no vehicles; their
benchmark's COMBAT/VEHICLES headings mean early/late on-foot replay segments.
Free heap is a result-page reading, not a minimum watermark. The capture videos
are silent Ares window recordings with actual wall-clock frame timestamps.

Matched merged-main `0ac2d7c9` measurements are Blood Gulch **24.0 / 26.4 / 21.8**
and Wizard **24.9 / 24.4 / 25.3**. There is no measured old-map regression in these
runs. The new maps' **>25 FPS development gate and final 30 FPS target remain
open**; none of these measurements certify physical-console performance.
Accepted shared model, pose-cache, geometry-workspace and queue budgets remain.

`build/n64-three-map-audit/comparison.html` contains native inspection images,
gameplay recordings, the source/reduced scenery comparisons and timing evidence.
`timing.json` binds each result to its ROM and selected-map bank hash. Timed
candidates were built before commit; compiler-input and selected-bank hashes
are compared to the committed release rather than treating their recorded base
commit as the final source identity.

Final reproduction commands:

```sh
build/n64-python/bin/python port/n64/test_map_assets.py
build/n64-python/bin/python port/n64/test_maps.py --maps-cycle
build/n64-python/bin/python port/n64/build.py --preset release --maps-cycle --validate --output-dir build/n64-three-map-audit/frontend-cycle-final-validator
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/n64-three-map-audit/release
build/n64-python/bin/python port/n64/build.py --preset release --initial-map hangemhigh --vi-benchmark --output-dir build/n64-three-map-audit/hangemhigh-final-timing
```

Use `--initial-map chillout` or `beavercreek` for their timing runs. `--map-qa 1`
and `3` inspect routes and one-player architecture without simulation. Battle
Creek uses authored courtyard/river Slayer starts facing the arena for those
pages; the other maps use their authored starts and headings.
