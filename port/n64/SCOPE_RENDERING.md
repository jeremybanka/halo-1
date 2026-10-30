# Scoped terrain and HUD corrections — 2026-10-30

The reported Blood Gulch screenshot is reproduced by scope photo 0: a standing
Magnum camera at `(-2, .098919, 1.5)`, yaw 0, pitch −.6, 2× zoom. The old scoped
near plane discarded the foreground ground, revealing sky beneath it.

## Depth

The scope retains its 32-render-unit precision setting only when a conservative
near-field query establishes that the space immediately in front is empty.
Nearby geometry selects the ordinary 4-unit setting (1/8 Halo world unit).
Far distance, exact focal magnification, fixed W normalization, aim projection,
world meshes, movement and collision are unchanged.

The probe tests the full viewport, including its title-safe aiming offset and
rounding margins. It clips rendered triangles rather than collision triangles
or a sparse set of rays. Conservative existing bounds protect moving actors,
vehicles, pickups, objectives, projectiles and the dropship. Fully invisible
players do not force a different depth range.

Local batches are reused within a half-unit eye neighborhood; identical static
probes reuse their result, and the previous intersecting face is tested first
when moving. Work is capped at 128 candidate batches and 12 triangle tests,
plus the previous face. Overflow or an inconclusive search selects the close
plane. Map release and scene reset invalidate the cache. A host check verifies
that every supported zoom/layout's padded probe fits within the cached region.

This is a deliberate precision tradeoff: when foreground geometry is present,
nearby visibility takes priority and distant coplanar faces may fight again.
The elevated long-range fixture retains the previous projection and its pixels.
The rejected experiment using near=4 for every scope visibly regressed that
fixture, so it is not the final implementation.

The native diagnostic logs show roughly 0.6–1.1 ms per scoped cold probe in this
route, after bounding the initial unbounded near-wall query (about 7.4 ms).
These frozen frames reset scene state and do not measure the warm-cache path,
combat cost or game FPS. No new four-player frame-rate claim is made here.

## Weapon-specific artwork

- Magnum: a native-pixel circular aperture, 150×150 solo or 74×74 split, centered
  on the existing aim point. Its outside opacity is preserved; no black outline
  is added. The previous 64×64 mask was stretched across the whole viewport.
- Sniper: retains the source's wide rounded rectangle (236/256 of view width,
  152/256 of height). Its exterior is rasterized at native resolution without
  adding an outline. It never uses the Magnum circle.
- Sniper markings: preserve the five source stamps and their anchor offsets.
  Packed stamps were already half Xbox resolution, but were enlarged a second
  time at runtime. Their size and offset scaling now agree, they land on integer
  pixels, and their alpha is quantized before point sampling. This removes the
  blurred fringe. The native flat-ground capture contains only the terrain,
  one translucent marking color and the cyan reticle in the checked decal area.
  Bracket symmetry, horizontal aim line and vertical stem agree with the cyan
  aim center to within one native pixel.

Source references: owned `scope_pistol_mask`, `scope_sniper_mask`, and five
`scope_sniper_ticks` bitmap sequences; `hud-tag-1198.txt` multiplayer crosshair
placements; `source/interface/hud_draw.c` bitmap placement/bounds. The crisp
edge rasterization and removal of the rim are requested demake adjustments.
No new downloaded or generated art is used.

## Validation and artifacts

`benchmarks/scope-fix/results.json` records hashes, camera poses, native pixel
checks and the playable ROM. The private asset working tree holds the native
readbacks, source snapshots and comparison images under `assets/scope-fix/`.
Local review: `build/n64-scope-fix/comparison.html` in the original checkout.

Ten before/after frames cover 22 camera poses: standing and crouched ground,
steep 10× ground, a nearby wall, two distant camera angles at unzoomed/2×/10×,
and two-, three- and four-player views. The three-player wide P3 is included.
Pixels in the distant view are compared inside the clear aperture, excluding
both old and new sniper stamp bounds. HUD/shape changes remain visible in the
full difference images. This checks sampled views; it is not an exhaustive
proof across every map/camera.

Host checks: camera projection/magnification, 20,000 HUD forward rays, circular
mask symmetry/no outline, conservative triangle clipping (959 independently
sampled interior witnesses), and all viewport candidate-cache bounds. The new
scope mask/depth tests pass AddressSanitizer and UndefinedBehaviorSanitizer.
All 47 runtime configurations / 188 target translation units compile.

From the active checkout, with the existing private banks and SDK installed:

```
TMPDIR=/private/tmp build/n64-python/bin/python port/n64/benchmarks/scope-fix/build.py after
build/n64-python/bin/python port/n64/benchmarks/scope-fix/capture.py after
TMPDIR=/private/tmp build/n64-python/bin/python port/n64/benchmarks/scope-fix/build.py play
build/n64-python/bin/python port/n64/benchmarks/scope-fix/report.py
```

The baseline requires the saved pre-change `hud.c`, `scene.c`, and
`view_camera.h`; the build helper refuses to relabel current code as baseline.
The QA entry point exports frozen frames and is excluded from the playable ROM.
