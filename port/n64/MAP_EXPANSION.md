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
- [ ] Map-specific asset batching/reduction and quiet four-player timings.
- [ ] Blood Gulch/Wizard comparison against the merged checkpoint.
- [ ] Native menu/countdown/quit-resume/results cycle, normal and validator ROMs.
- [ ] Final screenshots/gameplay videos and committed release boot.
- [ ] One PR containing all three maps.

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
