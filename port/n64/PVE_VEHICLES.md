# Enemy vehicles — appraisal candidate

Elite pilots now operate Ghosts, Banshees, Wraiths and Shade turrets in Firefight.
Players can enter available seats. Live humans and Covenant use the source splatter
velocity gate and own-vehicle exit protection. This is an opt-in
`--enemy-vehicle-bank build/pve-vehicles/bank` candidate layered on the local
roster and Jackal-shield work, published for appraisal with PR #12. It remains opt-in.

The viewer is `build/n64-enemy-vehicles/comparison.html` in the original research
checkout. It links the playable menu ROM, 42 native inspection pages, LOD and
memory-fix pixel differences, and timing samples. Reproduction and evidence are
in [benchmarks/enemy-vehicles](benchmarks/enemy-vehicles/README.md).

## Playable behavior

Each round keeps its infantry opening. The first packet of waves 2, 3, 4 and 5
adds a Ghost, Banshee, Shade and Wraith respectively, with an Elite pilot and
infantry escorts. Bonus waves remain infantry. Vehicle arrivals validate the
whole rotated hull, terrain clearance and escort positions before allocation;
they must be concealed from every player camera. These use ground arrival zones,
not a new vehicle-carrying Spirit sequence. Empty retired encounter hulls are
reclaimed only while concealed; player-occupied hulls remain available.

Eligible Elites also approach vacant compatible seats. Enter/exit ownership is
shared with the existing vehicle system. A killed pilot releases its seat; a
destroyed hull kills and scores its occupant exactly once. Encounter vehicles
do not automatically respawn. The source Shade hull has no destructible body
vitality: kill its exposed gunner instead.

Press **Use** near an available seat to start its entry animation immediately.
An occupied seat offers no entry prompt and cannot be stolen. A killed pilot
releases its seat; entry rechecks occupancy before transferring ownership, so
a stale prompt cannot displace another human or Elite. The existing proximity,
obstruction, carrying-objective and seat-role checks still apply. Exits require
safe clearance outside the hull. The earlier 0.6-second hijacking prototype has
been removed following the user's clarification; boarding means vacant-seat
entry, not ejecting a living enemy.

## What comes from CE

`prepare_enemy_vehicle_ai.py` retains 21 source function bodies with source hashes,
including `actor_move_calculate_movement`, its free/aim-controlled branches,
`biped_build_flying_axes` and math helpers. The adapter supplies actor state,
destination/stopping distances, source tag sideslip/oversteer/steering/throttle
parameters and native-cache derived movement values. The existing retained CE
vehicle solver now distinguishes NPC drivers via `unit_driven_by_ai`, including
the original Banshee input behavior. Ghost/Wraith use alien-scout physics,
Banshee alien-fighter physics, and Shade turret physics.

Mounted firing uses the dedicated vehicle actor variants, not the Elite's
handheld-weapon profile: source ranges, bursts, pauses, aim error, lead and
new-target modifiers. Wraiths use high ballistic arcs beyond the source 30-unit
threshold with segmented clearance checks. Banshee secondary attacks use the
source delay/strafe exclusion and reject players on foot, as the original rule
requires. Occupied player vehicles are eligible targets.

The decision/service boundary is still a demake adapter. Ground goals use shared
budgeted navigation plus vehicle-width clearance and cliff probes; Banshees use
strafing/breakaway goals with source avoidance smoothing. We have not transplanted
the full Xbox actor/action, BSP-path, perception or multi-body collision
environment. Difficulty-wide firing adjustments and the complete original combat
state machine are not claimed to be identical.

Source render/collision assets, seat markers, cameras and muzzle markers come
from the owned CE cache. Wraith: 1,086 render triangles / 1,320 vertex loads;
Shade: 924 / 1,348. These hulls retain their source mesh at near/far tiers, with
the existing tiny-screen impostor mechanism available. Existing Covenant geometry
and animation bytes are unchanged.

Elite G-driver, B-driver and GT-gunner clips are baked onto all three accepted
body LODs. Enter/exit retains source keyframes; idle uses four samples. Canonical
pilot hit poses stream from ROM and match their host arrays exactly. The Wraith
source seat hides the pilot. It supplies an enter clip but no matching visible
idle/exit: hidden idle holds its endpoint and exit uses its reverse. Human Shade
clips are appended to the interaction and hit banks. Wraith hatch animation uses
identical fixed-point transforms for drawing and collision. Wraith barrel
pitch/counter-articulation remains the rigid-part approximation, rather than the
complete source aiming graph.

Wraith and Shade use source fire audio and one source engine loop each. The four
existing engine channels select the closest occupied vehicles, including NPCs.
This does not reproduce the full layered start/end/gain sound graph. Wraith
mortar color/explosion presentation is added. The audit also fixed an existing
fuel-rod particle-table index overrun.

The native seat photos caught missing human reticle entries. Wraith now uses
the source HUD sequence 9 (shared with the rocket launcher); Shade uses its
own sequence 12, packed into spare quadrants of the existing 4 KiB HUD atlas.

## Splatter boundary

The gate comes from `source/physics/physics.c:physics_compute_biped_collision`,
after applying the source impulse to the biped. At 30 Hz it is strictly:

- vehicle speed greater than **0.06666667 units/tick**, or
- squared vehicle/biped relative speed greater than **0.0011111111**.

These are approximately 2 units/second vehicle speed or 1 unit/second relative
speed, but the implementation retains the original float constants and XYZ
summation order. Do not round the gate to whole numbers. The source excludes the
victim's previous vehicle through exit tick +90; contact is eligible at +91.
The old port's 0.3-second exclusion and human-only contact path were corrected.

The swept hull/capsule adapter checks up to eight motion substeps and applies
source living-biped impulse halving and reciprocal damage categories (medium
for human/Grunt/Elite/Jackal, large for Hunter). It does not simulate corpses as
physical bipeds. Failure to find capsule clearance is not itself a lethal crush;
the velocity gate must still pass. Full Xbox rigid-body contacts remain outside
this adapter.

## Validation and memory finding

ASan/UBSan checks cover 84 threshold/sign/axis/nextafter cases, 90/91-tick grace
boundaries, actual slow/fast Ghost contacts for humans and all four enemy species,
all four available-seat paths, occupied human/NPC rejection, stale-target rejection,
pilot-death entry, immediate Use activation and safe exit,
autonomous entry, mounted firing and Banshee secondary restrictions. Finite
Firefight tests complete all 15 waves at 1–4 players with zero authored arrival
failures in their scripted camera/kill fixture. Existing roster/shield tests and
all 26 multiplayer presets across 13 maps pass. Spawn checks retain 647,729 exact
source ratings and 10,140 identical seeded selections.

The long four-player stress capture exposed an allocation failure missed by the
short smoke run: unused actor detail-level buffers accumulated. The failed
12-observation capture is preserved privately, excluded from passing benchmarks.
The fix releases unused representations in the current fenced frame slot. A
pressure fallback waits for the RSP and reclaims old frame caches while preserving
the current frame's prepared owners/shared aliases. Removed actors, hidden pilots
and expired corpses also release unused buffers. It changes no mesh, LOD choice,
animation sample or hit pose.

An all-map residency check also found insufficient RAM for Battle Creek while
the larger vehicle bank was resident. The unchanged 192 KiB animation ROM cache
and 64 KiB decode workspace are now allocated only for active PvE and released
at the existing fenced body-release boundary. Multiplayer maps regain that
scratch memory. A second matched 42-frame route isolates this lifetime change
after correcting the reticles; the first route isolates vertex-cache trimming.

That alone was insufficient for Battle Creek. The immutable baked navigation
grid is now read directly instead of copied to a second 199,692-byte array set.
The 262,336-byte goal/route field cache is acquired on PvE start and released on
stop. Its capacity, initialization, exact distances, work budget and cancellation
rules are unchanged. Together with animation scratch lifetime this returns about
708 KiB to PvP maps; active PvE also saves the duplicate grid. ASan/UBSan navigation
checks pass 240 pursuit/retreat/cower choices and 17,567 exact cached distances,
including shared goals, 12 simultaneous routes, generation wrap and restart.
Both failed map-load captures remain archived separately from final passing runs.

All 42 native four-camera frames match pixel for pixel before/after that fix.
Checks also verify additive old asset-table rows, unchanged existing Covenant
mesh/motion, 12 canonical pilot hit streams and all retained function hashes.
The full-roster four-player native run checks the larger resident bank with
expensive infantry poses. Native captures and raw counters are preserved; these
are emulator measurements, not new SummerCart64 timings.

## Available-seat revision

The available-seat correction has fresh ASan/UBSan vehicle and full 1–4-player
Firefight checks, a rebuilt release ROM, 42 matched native photo pages, and a
targeted four-player overload capture. See
[ce-entry.json](benchmarks/enemy-vehicles/ce-entry.json) for its exact results and
ROM/log hashes. Thirty-nine pages remain pixel-identical. The other three only
remove the occupied-Ghost "Hold to board" hints (1,399 pixels per page); every
pixel outside those four documented HUD rectangles remains unchanged.
The fresh four-player overload averages **3.60 FPS** across 40 engaged samples
(45 observations total), versus the preceding capture's 3.70 FPS. Minimum free
memory is 438,336 bytes. This is a regression check, not an optimization result.
This does not turn the historical timing matrix below into a fresh full sweep:
the nine original timing captures, navigation/PvP checks and all-map residency
cycle predate the interaction-only correction and retain their original inputs.

<!-- MEASUREMENTS -->

## Native measurements — preceding vehicle candidate

Ares v148, NTSC 320x240, 8 MiB, audio on; uncapped diagnostic. Nine complete 45-observation captures, first five FPS samples discarded. Real damage/deaths; engaged means at least one human and enemy alive and no pending arrival. Fixtures 7/8 restart at simulation tick 600; restarted intervals remain in the sample. No cartridge timing claim.

| Players | One Ghost + infantry | Four vehicles + infantry | Stress minimum free RAM |
|---|---:|---:|---:|
| 1 | 44.47 FPS (30 samples) | 18.73 FPS (26 samples) | 628.8 KiB |
| 2 | 24.34 FPS (35 samples) | 9.73 FPS (37 samples) | 578.4 KiB |
| 3 | 27.00 FPS (40 samples) | 8.45 FPS (40 samples) | 456.1 KiB |
| 4 | 16.10 FPS (40 samples) | 3.70 FPS (40 samples) | 430.3 KiB |

These are deliberately crowded encounters at the actor cap, not a promise
of a particular frame rate throughout a full match. Three-player results need
not sit between two/four-player results: enemies, targets, deaths, viewports
and visible LODs differ. The playable release ROM is capped at 30 FPS; the
diagnostic ROMs are uncapped. The table uses engaged samples, not post-death
idle frames. All-human-alive scope and ranges are in results.json.

| Four-player fixture | All humans alive FPS / samples | CPU simulation / prep / drawing per rendered frame | Submitted vertex loads, all views |
|---|---:|---:|---:|
| One Ghost, infantry to the 6/8/10/12 actor cap | 14.4 / 15 | 25.54 / 9.68 / 28.36 ms | 24,195 |
| Ghost, Banshee, Wraith and Shade together, infantry to the 6/8/10/12 actor cap | 3.11 / 27 | 202.14 / 14.76 / 53.28 ms | 41,616 |
| Full Covenant roster memory regression, no piloted enemy vehicles | 4.46 / 13 | 119.63 / 18.53 / 48.35 ms | 41,503 |

Drawing is measured elapsed CPU time around submission; it can include queue
stalls and is not an independent RSP/RDP occupancy measurement. Frame counters
may contain several simulation ticks. The following disjoint simulation
partition is normalized per tick; do not add nested terrain/hit counters.

| Four-player fixture | Human simulation | Vehicle AI | Vehicle physics/contact | Infantry AI/combat | Projectiles | Total tick |
|---|---:|---:|---:|---:|---:|---:|
| 9 | 4.55 ms | 0.47 ms | 1.70 ms | 3.08 ms | 2.14 ms | 12.04 ms |
| 8 | 7.29 ms | 5.65 ms | 7.97 ms | 4.25 ms | 4.59 ms | 29.86 ms |
| 7 | 7.23 ms | 0.02 ms | 0.02 ms | 6.80 ms | 6.21 ms | 20.35 ms |

The four-vehicle overload adds substantial vehicle physics and clearance/AI
work while still submitting large actor/hull meshes to four cameras. Long
frames then accumulate multiple fixed simulation ticks. This candidate
delivers the mechanics; it does not meet four-player 30 FPS. The next
performance pass should separate per-vehicle clearance/solver costs and
bound the simultaneous expensive vehicles, alongside vehicle screen-size
LOD work. Do not interpret lower polygon count as sufficient on its own.

The follow-up [vehicle cost audit](PVE_VEHICLE_COSTS.md) now separates those
costs with ten native diagnostic captures. It identifies oversized distant
Wraith/Shade hulls and repeated clearance/firing queries as the strongest next
targets. Its instrumentation and frozen omission views do not change the
playable candidate or replace the timing matrix above.
