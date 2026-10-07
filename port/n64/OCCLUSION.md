# Model occlusion repair

The original game-derived meshes have outward triangle winding. The native
renderer had applied the terrain's `CULL_FRONT` convention to those models,
discarding their outside surfaces. First-person weapons also had both depth
reads and writes disabled, allowing later triangles to cover nearer surfaces.
The previous offline audit rendered both sides and could conceal these defects.

The object and first-person passes now use `CULL_BACK`. Terrain keeps its own
winding. Before each first-person pass, `rdpq_clear_z` clears the existing depth
surface inside the active viewport scissor; the weapon and hands then use depth
reads and writes against one another. No additional framebuffer is allocated.
The AR's coplanar numeric overlay explicitly bypasses depth, then restores the
surrounding state. Procedural particles and the two support-hull micro models
now use outward winding too.

## Blender repair

`geometry_closures.py` uses Blender BMesh on selected simple boundary loops. It
adds only existing boundary vertices, copying their source UVs, materials, skin
weights and every baked animation trajectory. It does not fill every opening:
vehicle cockpits, weapon muzzles and decorative sheets remain separate.

| Mesh | Added triangles | Reviewed closures |
| --- | ---: | --- |
| Spartan near | 18 | Neck, waist, wrists, ankles |
| Spartan far | 8 | Waist, wrists, ankles |
| Scorpion near | 8 | Outer track sides and rear deck |
| Magnum world | 4 | Grip base |
| Plasma pistol world | 4 | Upper and lower attachment cuts |

Rocket and first-person weapon geometry needed the shared renderer correction;
they were not inflated or made indiscriminately double-sided. The corrected
CPU audit uses backface culling and a z-buffer. Its before/revised geometry
columns both use the corrected convention; **only the Ares captures compare
the broken and fixed runtime rendering**.

The maintained `--performance-profile` world reduction invokes these closures
after skinning, before saving. All extracted/reduced meshes and Blender review
libraries stay under ignored `build/`.

## Reproduction

Run the normal asset pipeline from `ASSET_PIPELINE.md`, including world
reduction/packing and micro generation/packing. This initial repair left the
first-person banks unchanged; the subsequent shared-hand reduction repair and
remaining-weapon audit are documented in [WEAPON_OCCLUSION.md](WEAPON_OCCLUSION.md).
The closure integration tests need Blender Python; they can run through Blender
MCP with `unittest.defaultTestLoader.loadTestsFromModule(test_geometry_closures)`.

```sh
build/n64-python/bin/python port/n64/build.py --model-qa
build/n64-python/bin/python port/n64/build.py --model-qa --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The model gallery cycles eight six-second, deterministic render-only pages:
Spartan near, Spartan far, Scorpion with seated driver, first-person pistols /
rocket / AR, reload, melee, world weapons, and other vehicles. Four views share
the production culling, animation and drawing paths. The cameras and poses are
fixtures, not human gameplay or a performance benchmark. Validation must remain
at zero errors and warnings through the entire cycle. Timing uses the separate
75-second four-player combat/vehicle replay with the actual VI observer.

Local evidence is in `build/n64/occlusion-audit/`: baseline and repaired Ares
videos, matched screenshots, eight-angle source/packed comparisons, geometry
metrics with hashes, closure counts, a separate repaired Blender library and
build/test logs. `comparison.html` summarizes the runtime comparison.

## 2026-10-07 result

Ares 148 with the expansion pak disabled completed the repaired gallery cycle
with zero RDP errors/warnings. The AR counter, first-person reload/melee poses,
near/far Spartan, seated Scorpion driver and all four vehicle types were checked.
The separate 75.017-second VI run measured 28.9 displayed FPS overall and 28.6
in the vehicle segment (previous native-physics baseline: 28.9 / 28.7). Vehicle
P95 remained 33.4 ms and maximum 66.8 ms, with 48 intervals exceeding two VIs.
The 30 FPS target remains unmet. Live free heap was 100 KiB in the 4 MiB run.
The asset repair adds 1,088 static vertex bytes and 1,232 compressed animation
bytes, plus affected runtime pose buffers and command/index overhead.

Validation included 2 Blender closure/trajectory tests, 2 directional/depth
raster tests, 5 micro-geometry tests, 11 audit tests, 4 owned-ammo tests, 28 packing
tests, 1,024 direct/replayed AR command traces, 10,608 segmented FP address checks
and the existing visibility/articulated-bound regressions. A repeated Blender
export matched all repaired meshes and all 11 near/far Spartan animation clips.
