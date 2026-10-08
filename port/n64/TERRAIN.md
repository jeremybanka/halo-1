# On-foot terrain and landing pass

The 4 MiB build now uses the original Blood Gulch collision surfaces, rather
than the reduced render mesh, for floor/ray queries and the on-foot capsule.
`extract_terrain.py` triangulates the original convex surface edge rings without
simplification. It preserves plane orientation, shares vertices, and builds a
small spatial grid for floor and capsule queries. Rays reuse the resident vehicle
collision surfaces with nearest-first ray/AABB BVH traversal and original polygon
containment tests. The full original BSP tree remains an optional 8 MiB path.
This is a compact collision adapter, not the complete Blam object-physics service.

## Source-derived behavior

- Original cyborg multiplayer radius 0.2, standing height 0.7 and crouched height
  0.5 world units. Clearance tests cover the continuous capsule axis, including
  walls, ceilings and the space between the former two sample spheres.
- Ground velocity projects onto the contact plane and accelerates in three
  dimensions. Uphill/downhill falloff begins at 20 degrees; the 45-degree values
  are 0.65 / 1.25 of the directional speed. Surfaces steeper than 45 degrees
  do not support walking; gravity and contact sliding remain active.
- The original inward contact bias is removed by collision, preserving tangent
  velocity. Airborne crouching raises the feet by the height change without
  adding an impulse. Standing waits until the full-height capsule has clearance.
- Soft landing begins at 1.5 units/sec normal impact speed. Hard landing begins
  at 5. Recovery follows `biped_start_landing`, including its hard-branch numerator
  and truncation to 30 Hz ticks. Hard recovery blocks movement intent and jumping.
- Original crouch idle/move and standing/crouched soft/hard landing poses are
  streamed through the existing ROM frame cache. Crouch blends into the standing
  mesh, keeping body width; held-weapon markers follow the same source poses.
  Combat clips without a crouch overlay retain a height-only fallback.
- Hit spheres move with capsule height. They remain simplified hit geometry,
  not the original animated per-node damage regions.

Constants are extracted from the owned USA Rev 2 cyborg multiplayer tags.
Arithmetic references are `source/units/bipeds.c`: `biped_get_physics_pill`,
`biped_update_physics`, `biped_start_landing`, and the stand-clearance path.

## Adapter boundaries

The capsule uses bounded spatial substeps and iterative contact projection,
with a 0.015-unit contact skin. It does not reproduce the original swept-feature
solver's exact corner ordering. Moving support objects, player/player capsule
contacts, step-up orchestration, body-stun damage penalties, original falling
_damage_ effects and first-person landing camera effects remain follow-ups.
The pre-existing fall-damage approximation remains; landing recovery should not
be confused with complete fall-damage parity. Vehicle rigid-body solver arithmetic is
unchanged. Zero-height queries reject polygons beyond their front plane plus
the contact width, and conservatively reject edge cylinders whose
expanded segment bounds cannot contain the mass point; 30,000 contact-result
comparisons against the unpruned adapter agree. A 32-entry cache retains the
original static polygon projections, updating thickness for each query;
contact answers are never cached. Floor/ray queries now see original terrain.

## Cost and verification

The nearby-triangle cache stores candidate IDs, not collision results. Its
expanded bounds contain all postures and queries until the player moves outside
that region. Overflow scans the full bank. Every tick still tests contacts.
The ray BVH retains entry distances on its stack to avoid repeating bound tests.
Floor eligibility is precomputed, and plane-interior capsule contacts exit once
they attain the plane-distance lower bound. Neither optimization drops geometry.

Tests cover walls, ceilings, high-speed travel, posture clearance, 45-degree
speed scaling, 60-degree slipping and landing thresholds. A candidate-cache
oracle checks contact coverage against every original triangle. Existing game,
vehicle, interaction, effects, replay and showcase regressions remain required.
The full original BSP provides an independent oracle for the shared BVH ray service.
All 2,733 sampled rays agree within 0.003 world units.

Video comparisons use the same scripted ramp, crouch and landing inputs on the
pre-change and revised N64 builds. They are Ares captures, not retail Xbox
footage. Low-ceiling clearance is verified by a synthetic host collision fixture;
the ramp recordings do not claim to demonstrate an actual crouch-only passage.
Exact ROM identities, captures and timing results: `build/n64/terrain-audit/`.

The quiet four-player VI replay measured 26.9 FPS overall, 28.8 combat and
25.1 vehicles on the 4 MiB / four-display-surface build. P95 overall pose
interval is 66.8 ms; maximum is 234.0 ms (vehicle maximum 66.9 ms). Live free
heap is 53 KiB. These section averages do not establish a sustained minimum
or physical-console acceptance. The dedicated 30 FPS/latency pass remains open.
