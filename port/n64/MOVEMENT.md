# On-foot movement and aiming

This pass translates the player-control arithmetic from reconstructed Xbox
source and reads constants from the owned USA Rev 2 Blood Gulch cache. It does
not claim to run the complete original biped collision/animation system.

## Implemented

- Directional run speeds: forward 2.25, backward/sideways 2 world units/sec.
  Crouch speeds: 0.9 forward, 0.65 backward, 0.6 sideways.
- Vector-limited acceleration/deceleration, including reversal; 9.6 units/sec²
  standing, 4.8 crouching, 1.05 airborne. Velocity survives release and jumping.
  Constants in the retail globals are velocity changes per 30 Hz tick; the
  demake adapter converts them to seconds rather than treating them as SI values.
- Retail jump impulse 0.07 units/tick (2.1 units/sec); original global gravity
  0.0035651792 units/tick² (3.20866128 units/sec²). The discrete flat-ground
  trajectory peaks at 0.652616 units and returns in 39 ticks.
- Six-tick crouch transition, including camera height from 0.62 to 0.35 units.
- Original six-point stick response, diagonal look expansion, 120°/sec base yaw,
  60°/sec pitch, and full-yaw deflection acceleration to 3x over one second.
  Below the retail 0.85 peg threshold the acceleration timer resets.
- Sensitivity divided by the actual 2x/10x magnification; original ±85.5° pitch.
- Per-weapon retail autoaim/magnetism angles and ranges, zoom scaling and
  zoom-only eligibility. Original half-range/full-range attenuation and target
  priority (autoaim, magnetism, distance). Camo/dead targets are excluded.
- Target friction and relative-velocity adhesion only while moving/looking;
  original per-tick angular caps translated to seconds. Aim does not move on
  completely idle input. Fire uses bounded target blending/deviation before
  weapon spread; grenades and melee do not acquire weapon autoaim.
- Terrain and vehicle-cover checks before selecting assist targets.
- Wall depenetration cannot manufacture horizontal momentum. Velocity into
  a collision correction is removed while tangent velocity remains.

Sources: `source/units/bipeds.c` (`biped_update_physics`, `biped_jump`, player
movement setup), `source/game/player_control.c` (piecewise response and look),
`source/game/aim_assist.c` (target pill, attenuation, selection, relative angular
velocity and shot cone), `source/physics/physics.c` (gravity). The source is the
repository's reconstruction, not a fresh retail executable disassembly.

## Boundaries still requiring parity work

Ground movement currently applies the original acceleration in the horizontal
plane, using existing floor snapping and wall pushing. Original ground-normal
projection, slope speed/falloff, slipping, support objects, capsule collision,
stand-up clearance, body-stun penalties and hard-landing orchestration are not
ported here. Target pills use a posture-scaled collision-height approximation
instead of animated pelvis/head node positions. Vehicle cover uses the existing
conservative spheres, and the original full object collision service is absent.
Crouched hit geometry/animation need a coordinated follow-up. Aim target queries
use current player records; there is no new object partition or native observer.

N64 button layouts and their established /80 stick scale and .12 axis deadzone
are retained. Vehicle turn-rate tuning remains unchanged. Auto-leveling and
saved sensitivity preferences are not added in this pass.

## Evidence and reproduction

`extract_movement.py` creates the small private `movement_data.c` bank and
input/hash provenance. The build rejects a stale bank. `test_movement.c` checks
source speed/acceleration breakpoints, air reversal, jump trajectory, both
control layouts, zoom, target exclusion, terrain/vehicle cover and adhesion
sign/no-input behavior. It runs in the existing sanitizer suite:

```sh
build/n64-python/bin/python port/n64/extract_movement.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py
build/n64-python/bin/python port/n64/build.py --movement-qa 0 --validate
build/n64-python/bin/python port/n64/build.py --movement-qa 1 --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 4
```

The two QA modes reset staged encounters every twelve simulation seconds and
feed normal gameplay inputs. Mode 0 covers start/release/reverse, jumping with
air reversal and crouching. Mode 1 covers fine sweeps, moving-target adhesion
and scoped sweeps. Video comparisons are N64 before/after, not Xbox footage.
The baseline uses pre-change gameplay with the same recording fixture.
Local recordings, source reports and exact ROM hashes live under
`build/n64/movement-audit/`. The measurement manifest records current performance;
video capture frame rate and emulator VPS are not displayed-pose performance.

## Working performance profile

The quiet four-player Ares run on October 8 measures 27.1 displayed FPS overall,
28.8 in combat and 25.5 in the vehicle section. Free heap is 108 KiB. These
section averages clear the development floor; sustained minimum performance
does not. Overall P95 pose interval is 66.8 ms; the maximum is 334.2 ms.
Average input-sample-to-display latency is 92 ms, with a 345 ms maximum.
Real-console acceptance and the final 30 FPS/latency pass remain open.

Four display surfaces replace the previous five-surface recommendation and
recover 150 KiB for the working set. The 16 KiB command queue remains; doubling
it did not improve the vehicle section. Without the pose cache the four-surface
run measured 26.8 overall / 28.7 combat / 24.9 vehicles, with 161 KiB free heap.

`interaction_cache.h` retains eight large immutable ROM frame pairs and eight
128-byte marker pairs. This adds 52.4 KiB over the old single scratch buffer.
Adjacent frames are fetched in one transfer and reused while their endpoints
remain the same; interpolation, mesh detail and animation timing are unchanged.
The cache is consumed synchronously into the existing fenced geometry slots.
It is released while full-screen menus are active and reloaded lazily in play.
Host sanitizer tests compare every fetched byte with uncached data through
reuse, length changes and 10,000 evictions. Four-player lifecycle validation
checks the actual renderer and menu memory transitions separately.
