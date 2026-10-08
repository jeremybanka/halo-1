# Aiming, zoom and vehicle camera audit

## Xbox rocket launcher

The owned USA Rev 2 Blood Gulch cache has zero
`projectile.physics.guided_angular_velocity` and an unset
`weapon.triggers[0].flags.tracks_fired_projectile`. The original
`source/items/projectiles.c` only steers when there is a target and a positive
angular velocity. CE therefore has no vehicle-seeking rocket to port. Rockets
remain unguided. Its weapon tag does have one 2x zoom level, now restored.
Extracted evidence lives in `build/n64/generated/camera-report.json`.

## Vehicle framing

`source/camera/following_camera.c:camera_track_splut` chooses a seat's first
camera track (or the globals default), maps pitch from -pi/2..pi/2 into its
control points, and samples `uniform_cubic_spline` from
`source/math/real_math.h`. `following_camera_deterministic` rotates the resulting
forward/left/up offset by viewing yaw. `source/units/units.c:unit_get_camera_position`
uses a named seat camera marker, or the vehicle origin for an empty marker.
`source/objects/objects.c:object_get_marker_by_name` falls back to node zero
when a nonempty marker name is absent. The Ghost/Banshee use this fallback;
the extractor now retains their actual root positions rather than a head-height
estimate.

`extract_camera.py` extracts all four distinct tracks used by the multiplayer
seats, including the a30 Banshee. Warthog seat ordering remains the port's
driver/gunner/passenger order. `view_camera.h` ports the original interpolation
and converts the offset to the port's Y-up basis. This replaces the single
3.5-unit shallow boom. The reticle stays at the established Xbox safe-window
anchor; it is not independently moved upward.

The complete Xbox observer is not ported here. The N64 implementation retains
its bounded terrain raycast for camera obstruction and converges the camera
onto the mounted shot's terrain intersection to keep camera/muzzle parallax
consistent. It does not add original observer spring smoothing or dynamic
object camera collision. At steep pitches or against an obstruction, the hull
can still overlap the reticle. These are not guarantees of an unobstructed
reticle at every possible pose.

## Raster projection accuracy

Tiny3D's `t3d_viewport_attach` packs X/Y viewport scales as integers after
multiplying by its W normalization. With the old far-dependent normalization,
160×120 scales rounded to 3/−2; doubling far changed them to 2/−1. This distorted
framing, misaligned the rendered aim relative to the HUD and made the CPU
frustum disagree with the rasterized image at the edges. A frozen elevated
scope comparison reproduced missing terrain along those edges.

Both world and foreground views now use W normalization 1/512 independently
of clip depth. All supported viewport dimensions have exact integer X/Y
scales (20/−15 for 160×120), and the packed W and depth factors are exact too.
This removes the edge gaps in the captured scope fixture and preserves aim
when changing depth range. The host test reconstructs the SDK's integer
packing rather than checking only ideal floating-point matrices.

## Scope range and precision

Zoom now uses `2*atan(tan(fov/2)/magnification)` so the projected size ratio is
exactly 2x or 10x. Dividing the FOV angle produced excessive magnification.
The scope-only far parameter doubles from 6200 to 12400 renderer units; near
also doubles from 1.4 to 2.8 to preserve the far/near ratio. Ordinary views and
the separate foreground projection retain their depth limits. Existing scoped
high-detail body/vehicle/held-weapon selection stays enabled.

This is deliberately bounded rather than multiplying the far plane by 10.
Blood Gulch's entire extracted geometry fits within a roughly 194-world-unit
bounding-box diagonal, so extending clipping does not reveal a new section of
this map in the recorded views. Tiny3D's current depth matrix also maps its
nominal far argument differently from a conventional OpenGL projection; do
not present the parameter divided by BG_SCALE as a measured visibility limit.
The improvement here is correct magnification and added clipping headroom,
and corrected raster/frustum agreement, not additional texture resolution. Weapon damage ranges are
unchanged.

## Verification

- `test_view_camera.c`: independent cubic-polynomial interpolation oracle,
  all ten seat tracks across the complete pitch range, yaw-basis conversion,
  both viewport FOVs at magnifications 1..10, scope depth ratio.
- `test_game.c`: rocket 2x zoom input and toggle back out; included in the
  ASan/UBSan vehicle/game/replay/showcase suite.
- `build.py --aim-qa 0..3 --validate`: frozen production cameras, level/down/up
  for Warthog gunner, Ghost, Scorpion and Banshee; Magnum unzoomed/2x and sniper
  2x/10x at an elevated inspection vantage aimed at a Scorpion roughly 83 world
  units away. These are visual fixtures, not a frame-rate benchmark.
- `build/n64/aim-audit/comparison.html`: native Ares captures and source evidence.

Before building after checkout:

```sh
build/n64-python/bin/python port/n64/extract_camera.py
```

The small generated camera bank and owned-cache evidence stay under ignored
`build/n64`; the build checks extraction/input hashes before linking.
