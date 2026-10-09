# Menu, first-person geometry and Blood Gulch bases

Later BSP overlay/depth repairs and the current 1/256 render grid are documented
in [ENVIRONMENT_SURFACES.md](ENVIRONMENT_SURFACES.md). The measurements below
are historical results for the original base-restoration pass.

This pass repairs four problems reported during console playtesting. Local
comparison images and native Ares screenshots are in
`build/n64/geometry-audit/comparison.html`; extracted assets remain untracked.

## Menu backdrop

The source ring and sky already retained their original geometry. The renderer
was drawing both sides, treating the planet/galaxy panels as opaque, and using
ordinary alpha blending for the ring's grayscale multiply decal. The exporter
now preserves blend/depth metadata, converts the grayscale multiplier to an
equivalent black/inverse-alpha decal, and wraps UVs per triangle rather than
independently per corner. The renderer culls backfaces and prevents the decal
from writing depth. The ring's projection uses a four-unit near plane for
better depth precision.

The galaxy's additive shader uses a bounded alpha approximation because the
N64 blender's additive mode can overflow. The original 32×32 texture budget,
camera path and complete source geometry remain. This is not a complete Xbox
shader implementation.

## First-person arms and sniper display

First-person geometry now has a separate `.125 .. 128` depth range. The world
keeps its `1.4 .. 6200` range. FOV, viewport, camera, reticle offset and depth
testing remain consistent; the closer near plane avoids cutting camera-space
arms at the world near plane. Each in-flight slot owns its projection storage.

In Blender, the sniper's four display triangles are lifted 1.5/256 Halo units
away from the housing, before skinning every original animation pose. The
display also has a dedicated 1/4096-unit pose bank; the rest of the weapon
retains the compact 1/256-unit bank. This adds no triangles. At the coarser
precision, 544 of 18,432 interpolated triangle samples collapsed. At the new
precision none collapse. The four faces use the original colors, clip clocks
and normal depth testing, including occlusion by the gun and hands.

## Original base architecture

Both bases, their ramps, interior floors, roof openings, trim and lights retain
all **1,688 original architecture triangles**. Landscape reduction runs
separately at 35%, with all 143 open boundary vertices pinned. The exporter
fails if a boundary moves. Total environment geometry is **3,023 triangles**,
up from 1,870. The render bank still quantizes positions to 1/32 Halo units.

Collision uses those same source architecture faces. Identical emitted float
corners share storage through 32-bit pointers, retaining every coordinate and
the existing collision algorithms. This saves **52,368 bytes** compared with
repeating nine floats per triangle. The resulting collision bank occupies
72,238 bytes, including its grid. Gameplay body buffers and recorded commands
are released together behind an RSP fence for full-screen menus and recreated
on match entry/resume; gameplay state and profiles are preserved.

## Verification

`--geometry-qa` produces a separately named ROM with seven six-second pages:
pistol/Plasma Pistol sleeves, sniper firing poses, sniper reload/melee poses,
four views of each base, and close ramp/roof views of each base. These are
frozen fixtures through the production renderer, not gameplay or FPS evidence.

```sh
build/n64-python/bin/python port/n64/test_base_geometry.py
build/n64-python/bin/python port/n64/test_scope_geometry.py
build/n64-python/bin/python port/n64/test_fp_hand_seams.py
build/n64-python/bin/python port/n64/test_render_matrix.py
build/n64-python/bin/python port/n64/test_render_segments.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py
build/n64-python/bin/python port/n64/build.py --geometry-qa --validate
build/n64-python/bin/python port/n64/build.py --frontend-qa 4 --validate --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The source checks cover exact architecture/UV preservation, all pinned joins,
710 original floor/ramp probes through the compiled runtime collision lookup,
and all 18,432 integer scope interpolation samples. Native ASAN/UBSAN game,
vehicle solver, two replay loops and six gameplay showcase suites pass.
The seven geometry pages and complete four-controller menu/match/results/return
flow pass in Ares 148 with zero RDP errors or warnings and the Expansion Pak
disabled. Use native Ares screenshots when the macOS Metal window capture is
stale; RAM inspection and Tools → Capture Screenshot confirmed the actual
emulated video output continued while desktop captures froze.

The quiet NTSC VI benchmark with five color buffers measures 28.8 FPS overall,
29.0 in combat and 28.5 around vehicles, versus 29.1 / 29.2 / 28.9 before these
repairs. All phases have 33.4 ms p95 intervals; worst intervals are 300.8 ms in
combat and 66.8 ms around vehicles. The free heap is 101 KiB, versus 144 KiB
before. The restored bases therefore have a small measured rendering/memory
cost; the sustained 30 FPS target remains unmet. Emulator timing is not console
hardware verification. Native results and matching camera comparisons are
included in the local report.
