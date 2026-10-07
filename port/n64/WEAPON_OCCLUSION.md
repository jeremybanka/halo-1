# Remaining Xbox weapon occlusion audit

This follows the outward-winding and first-person depth repair in
[OCCLUSION.md](OCCLUSION.md). The assault rifle, plasma rifle, Needler, shotgun
and sniper rifle were inspected in eight offline views and four runtime views.
The runtime gallery also covers idle, firing, reload and melee poses, the AR
counter, Needler ammo states (0/5/10/20), and both grenade pickups.

## Repair

The first-person hands were split into independent material and anatomy
partitions before reduction. Collapse moved adjacent boundary vertices apart,
leaving holes in the gloves and sleeves. This affected every weapon.

The Blender performance profile now reduces each hand as connected geometry.
It retains per-face material indices, per-loop UVs and interpolated skin weights.
It does not project material islands separately onto nearby source surfaces.
There are 198 hand triangles instead of 191; boundary edges decrease from 197
to 14, comprising only the two intentional open sleeve ends. No winding-conflict
edges remain. Shared corners follow exactly identical trajectories in all 22
baked frames per weapon (idle, firing, reload and melee).

All gun triangles and gun animation trajectories are unchanged. Packed color
welding can shift a few vertex colors because the shared vertex order changed.
Near and distant world meshes are unchanged. Muzzles, the sniper's scope and
brackets, decorative light/decal sheets and the Needler's original double-sided
needle cards must not be closed indiscriminately. A welded topology audit counts
the Needler cards as inconsistent edges; inspection shows they deliberately
contain reverse triangle pairs for both sides.

| First-person silhouette overlap with source, eight-view mean | Before | After |
| --- | ---: | ---: |
| Assault rifle and hands | .804 | .913 |
| Plasma rifle and hands | .768 | .887 |
| Needler and hands | .788 | .886 |
| Shotgun and hands | .796 | .905 |
| Sniper and hands | .820 | .896 |
| Hands alone | .733 | .895 |

These are backface-culled, depth-tested offline measurements, not gameplay
performance scores. The larger improvement comes from restoring solid arms,
not changing gun silhouettes. First-person packed assets shrink from 340,382
to 295,012 bytes, mostly from more compact animation trajectories.

## Reproduce

Run `reduce_firstperson.py` in Blender with `--performance-profile`, then
`pack_firstperson.py` and `pack_fp_ammo.py`. See [ASSET_PIPELINE.md](ASSET_PIPELINE.md)
for extraction prerequisites. Ammo data must be repacked after the vertex order
changes; the build checks both banks' hashes.

```sh
build/n64-python/bin/python port/n64/build.py --weapon-qa
build/n64-python/bin/python port/n64/build.py --weapon-qa --validate
build/n64-python/bin/python port/n64/test_fp_hand_seams.py
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The gallery has 13 six-second pages, alternating first-person poses and world
views for each weapon, then Needler ammo and grenade pickups. On pose pages,
P1 is idle, P2 fires, P3 reloads and P4 performs melee. It uses the production
renderer and animation paths with frozen fixtures; it is not human gameplay.
Keep Ares focused during recordings if its defocus-pause option is enabled.

`test_connected_reduction.py` runs through Blender Python/MCP. It checks that
a two-material closed skinned surface remains closed, outward-facing and joined
after collapse. `test_fp_hand_seams.py` checks the two sleeve openings and all
owned-asset animation trajectories. Ammo, packing, directional/depth and actual
segmented DMA-address regressions also run against the rebuilt assets.

Local evidence is in `build/n64/weapon-occlusion-audit/`: `comparison.html`,
matched Ares images/videos, `index.html` with 24 eight-angle comparisons,
`firstperson-candidate.blend`, topology and animation seam reports, and build logs.
Extracted game assets and recordings remain local and ignored by Git.

## Validation result

Ares 148 in 4 MiB mode completed all 13 gallery pages with **zero RDP errors
and zero warnings**. Matched captures confirm the arm repair across the five
remaining weapons. The AR physical panel displays 60; the Needler shows
retracted, partial and full crystal states. A separate uninstrumented gallery
provides the clean before/after images. The earlier two interrupted validation
recordings are superseded by `validation-final.mp4`.

The checks passed: one Blender connected-material integration test, two
owned-hand topology/trajectory tests, four owned-ammo tests, 28 packing tests,
two culling/depth tests, 1,024 direct/replayed AR counter command traces and
10,710 segmented first-person address checks.

The separate 75.084-second quiet four-player VI run measured **29.1 displayed
FPS overall / 28.9 during vehicles**, compared with 28.9 / 28.6 immediately
before this repair. Free heap increased from 100 to **144 KiB**. Vehicle P95
remains 33.4 ms, maximum 66.8 ms, with 36 intervals exceeding two VIs (previously
48). The existing 300.8 ms maximum combat interval remains. Sustained 30 FPS is
still unmet. These are Ares measurements; this pass did not test console hardware.
