# Blood Gulch surface flicker repair

The base hexagon/light panels and some canyon patches combined three issues:

- The initial BSP exporter only decoded environment shaders. The Xbox red/blue
  pylon lights and moss use transparent-generic shaders, so they had become
  solid fallback-colored triangles with no texture mask.
- Untouched moss sheets intersected the decimated cliff surface. They are now
  clipped and projected onto their reduced backing triangles, with interpolated
  original UVs. A small border of two source triangles has no compatible reduced
  receiver and is trimmed (minimum retained area 82.1%).
- Position packing and world depth precision were too coarse for thin layers.
  Terrain vertices now use 1/256 Halo units instead of 1/32; a shared immutable
  matrix converts them into the existing world scale. Bounds remain in world
  coordinates and round outward. The world near plane is four render units
  (1/8 Halo unit), inside the original 0.2-unit player collision radius.
  Normal/scoped far distances and the separate first-person projection remain.

`extract_environment_overlays.py` reads the owned Xbox shader tags and three
source bitmap maps. Black in their additive artwork contributes nothing, so
the N64 approximation uses filtered RGBA16 artwork with an opaque alpha-test mask. The cutout
pass disables edge antialiasing and framebuffer blending; opaque terrain and
objects retain their existing antialiasing.
These small overlays remain depth-tested, use transparent depth comparison,
and never write depth. They share one pass after the opaque terrain, avoiding
repeated blend/depth state changes. Their outward clearance is 1/32 Halo unit. The solid
base and canyon meshes, collision bank, UVs and gameplay are unchanged.

The result has 3,058 environment triangles (+35), 225 batches (unchanged),
928 additional vertex bytes and 216 additional index bytes. The texture bank
is unchanged at 34,816 bytes; the runtime adds one 64-byte terrain matrix and
17 material flags. Removing 9,888 unused prototype-model bytes from the
resident terrain array offsets this: terrain/index/matrix/flag storage is
8,663 bytes smaller overall (excluding code/alignment). The live Spartan and
weapon banks are untouched. Extracted artwork and generated banks remain private.

## Reproduction and evidence

```sh
build/n64-python/bin/python port/n64/extract_environment_overlays.py
build/n64-python/bin/python port/n64/pack_assets.py build/n64/assets/bloodgulch-reduced.json
build/n64-python/bin/python port/n64/test_environment_geometry.py
build/n64-python/bin/python port/n64/validate_terrain.py
build/n64-python/bin/python port/n64/test_pack_terrain.py
build/n64-python/bin/python port/n64/build.py --environment-qa --validate
```

`--environment-qa` runs four slow camera sweeps through the production renderer:
red/blue base pylons and two canyon regions. These are inspection fixtures,
not a gameplay or performance test. Before/after ROMs, native Ares screenshots
and moving captures are in `build/n64/environment-audit/comparison.html`.
Diagnostic ROMs which intentionally disable depth are not release candidates.

Checks cover all emitted corners/UVs/bounds, nonzero correctly wound packed
triangles, 324 independent overlay/wall samples (minimum clearance 0.028242
Halo units), unchanged source architecture and pinned seams, and the camera
projection/culling invariants. The old aggregate `test_base_geometry.py` floor
test is stale: it extracts a removed `cross` helper and targets the superseded
collision bank. Its two source-geometry checks pass; the production collision
bank is byte-for-byte unchanged by this repair.

Performance and lifecycle results are recorded with exact ROM hashes in the
local evidence manifest and release manifest. Emulator evidence does not
certify console performance.

The quiet four-buffer replay measures 26.6 FPS overall, 28.7 in combat and
24.7 in the vehicle section, versus 26.7 / 28.7 / 24.9 before this repair.
Its free heap is 60 KiB. The >25 FPS development gate remains open.
Do not combine the full four-buffer frontend lifecycle with `--validate`:
the additional RDP instrumentation exceeds the 4 MiB memory budget, as it
did before this repair. Validate surfaces with the separate inspection ROM;
run lifecycle checks with `--frontend-qa 4 --paced30 --paced30-buffers 4`.
