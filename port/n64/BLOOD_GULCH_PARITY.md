# Blood Gulch Slayer completion checklist

Practical parity: Halo players can bring familiar tactics and expectations into
a complete couch match and get predictable results, with deliberately reduced
presentation. This does not require the complete Blam engine or identical shaders.

Priority agreed October 8, 2026: feature parity first. Optimize as needed to keep
**more than 25 displayed FPS** during development; finish with a dedicated
**sustained nominal 30 FPS** four-player optimization pass. Measure the current
ROM, separate simulation/presentation/host speed, and retain exact build hashes.
Old benchmark results do not certify a newer build.

## Essentials

- [ ] On-foot movement and aiming
  - [x] Original walking/backward/strafe/crouch speeds and acceleration.
  - [x] Jump impulse, gravity and airborne steering.
  - [x] Controller response, zoom sensitivity and source-derived aim assistance
        with terrain/vehicle occlusion (approximate target pills).
  - [x] Matched N64 before/after videos and source-backed numerical checks.
  - [x] Slope projection/falloff, steep-surface sliding and terrain capsule contacts.
  - [x] Original collision surfaces in the 4 MiB spatial-grid adapter.
  - [x] Posture-aware clearance, crouch/landing poses and hard-landing recovery.
  - [x] Moving vehicle supports, player/player contacts and adjacent-ground recovery.
        The bounded capsule adapter still differs from the full source contact solver; see [FIDELITY_EDGES.md](FIDELITY_EDGES.md).
  - [x] Source body stun and original falling-damage thresholds.
  - [x] Animated original hit regions and first-person landing-effect source audit.
        The owned tags/source do not define an extra landing camera shake.
  - [ ] Retail Xbox video comparison and human controller acceptance.
  - [ ] Current four-player performance check and necessary optimization:
        the source-fidelity pass measures 24.4 overall / 26.3 combat / 22.7
        vehicle section FPS in Ares. Vehicles are below the development target;
        the overall P95 is 66.8 ms and maximum is 200.5 ms. Sustained floor
        and hardware acceptance remain; changed deaths alter the replay load.
  - [x] Recover release memory headroom: three display buffers retain four-player
        splitscreen; the expanded all-weapons lifecycle passes. Final memory
        measurements and the 32 KiB graphics queue are recorded in the manifest. Four-buffer builds currently fail that stress
        case and are not the recommended release configuration.
- [x] Source Slayer spawn eligibility and distance-weighted selection;
      conservative vehicle-bound exclusion. See [SPAWNS_PICKUPS.md](SPAWNS_PICKUPS.md).
- [x] Dropped weapons/grenades and pickup ammunition conservation; bounded
      pool with faster unseen cleanup. Physical item trajectories remain simplified.
- [x] Original map pickup timing, starting equipment and basic Slayer respawn
      delays. One object per map pedestal is a deliberate memory limit.
- [ ] Combat audit — **active**, see [COMBAT.md](COMBAT.md).
  - [x] Source direct-damage profiles, fractional vitality and material modifiers.
  - [x] Shield/headshot breakpoints, overcharge EMP and damage-range falloff.
  - [x] Forward/airborne melee strength and rear force-kill.
  - [x] Four staged N64 before/after encounter videos and sanitizer checks.
  - [x] Source spread/bloom limits, firing cadence, reload interruption and timed melee sweep.
  - [x] Source grenade/rocket damage, bounce/fuses/cover and Needler tracking/detonation adapters.
  - [ ] Certify explosive/Needler breakpoints against retail Xbox (see COMBAT.md).
  - [x] Animated hit regions, vehicle material modifiers and direct rider transfer.
  - [ ] Xbox/controller acceptance.
- [x] Camouflage visibility transitions and interaction with targeting/radar;
      requested full-invisibility/reveal timing. See [POWERUPS_VEHICLE_EDGES.md](POWERUPS_VEHICLE_EDGES.md).
- [ ] Vehicle edge cases: exposed occupants, damage, blast cover, splatters,
      boarding/dismount clearance and camera obstruction.
  - [x] Exposed-seat/hull-ray and blast-cover regression coverage for all seats.
  - [x] Safe voluntary exits, late obstruction, boarding approach checks.
  - [x] Swept hull/capsule splatters and rotating plasma attachments.
  - [x] Camera shoulder clearance and neighboring-hull obstruction.
  - [ ] Recover >25 FPS in the vehicle-heavy replay after clearance/contact changes.
  - [x] Animated hull parts, original material/mounted-weapon damage profiles,
        source collision shove and original vehicle-pair force/torque transfer.
  - [ ] Retail/controller acceptance of the bounded contact adapter.
- [ ] Four-person hardware acceptance session: repeated full matches, all
      controller subsets, disconnects, pause ownership, audio under load,
      menu transitions, long-session stability and memory margin.
- [ ] Final four-player 30 FPS optimization and latency pass.

## Established foundations (regression coverage must remain)

- [x] One-to-four-player local Slayer, scoring and match completion.
- [x] Main menu, joining, countdown, results and rematch flow.
- [x] Eight Xbox multiplayer weapons, grenades, two-weapon inventory and zoom.
- [x] Original vehicle drive/rigid-body solvers; boarding, exits and flipping.
- [x] Shield/overshield states and audio; health and power-up pickups.
- [x] Recognizable reduced models, animation, weapon effects and spatial audio.
- [x] Compact pixel HUD, all 60 AR rounds, on-weapon AR/Needler ammunition.

These checks mean implemented foundations, not full behavioral equivalence.

## Deliberate demake choices / later improvements

- Keep the compact HUD and selectable N64/Xbox control layouts.
- Keep requested wreck/despawn behavior and Banshees/extra weapon placements;
  consider separate classic and expanded presets later.
- [ ] Halo ring and restrained cloud layers.
- [ ] Persistent controller/profile preferences.
- [ ] Clean stale README claims as individual audits replace them.

## Acceptance evidence

Use source-backed encounters and repeatable inputs: movement start/stop/reversal,
jumping and air steering, aiming near/behind targets, pistol shield/headshot
sequences, shotgun distance, plasma follow-up, grenade cover, melee directions,
and occupied vehicles. Record ordinary gameplay paths after explicitly labeled
staging. Distinguish retail Xbox footage, reconstructed source references, and
N64 before/after footage. Never label an oracle or demake render as Xbox capture.

Movement implementation and remaining boundaries: [MOVEMENT.md](MOVEMENT.md),
[TERRAIN.md](TERRAIN.md).
Matched recordings: `build/n64/movement-audit/comparison.html` and
`build/n64/terrain-audit/comparison.html`.
Current source/ROM identity: `build/n64/release-manifest.json`.
Terrain/landing baseline: 26.9 FPS overall / 25.1 vehicle section / 53 KiB
free heap, using four display surfaces, exact original collision surfaces and
cached static contact projections. Overall P95 pose interval 66.8 ms and maximum
234.0 ms; vehicle maximum 66.9 ms. Section averages clear 25 FPS, but this does
not certify a sustained floor. See the terrain audit timing manifest.

Latest environment-surface repair: 26.6 overall / 28.7 combat / 24.7 vehicle section
FPS and 60 KiB timing-fixture free heap. The vehicle-heavy section needs its
small regression recovered before checking off the development performance
gate. See [ENVIRONMENT_SURFACES.md](ENVIRONMENT_SURFACES.md) and
`build/n64/environment-audit/comparison.html` for the before/after visual evidence.

Combat direct-damage pass: 27.7 overall / 28.8 combat / 26.6 vehicle FPS,
56 KiB timing-fixture free heap; changed damage affects replay composition.
See [COMBAT.md](COMBAT.md) and `build/n64/combat-audit/comparison.html`.

Combat continuation: source timing/projectile adapters and original vehicle hull
ray geometry implemented; sustained rollover ejects occupants. Animated player
regions, moving hull parts, mounted weapon profiles and retail acceptance remain
open. See COMBAT.md and the current release manifest for explicit boundaries.

Earlier timing/projectile run: 26.4 overall / 27.7 combat / 25.1 vehicle FPS,
164 KiB free in the timing fixture, three display surfaces and 32 KiB queue
buffers. P95 66.8 ms, maximum 267.4 ms; this clears section averages, not a
sustained 25 FPS floor. Four-buffer variants fail the expanded all-weapons
lifecycle and are not recommended.

Spawn/pickup pass: 26.8 overall / 27.8 combat / 25.9 vehicle FPS, 153 KiB
live free heap, three display surfaces and 32 KiB queue buffers. P95 66.8 ms,
maximum 234.0 ms; the sustained-floor checkbox remains open. The fixed item
pool restores source map placements and conserves dropped ammunition while
cleaning unseen drops sooner. See [SPAWNS_PICKUPS.md](SPAWNS_PICKUPS.md).

Power-up/vehicle-edge pass: **25.7 overall / 27.6 combat / 23.9 vehicle FPS**,
125 KiB live free heap, three display buffers and 32 KiB queues. The vehicle
section is below the development gate. P95 is 66.8 ms; maximum 267.4 ms overall,
100.2 ms in vehicles. Both release and diagnostic lifecycles pass 37/37; the
validator needs a 16 KiB queue to fit its additional memory overhead in 4 MiB.
See [POWERUPS_VEHICLE_EDGES.md](POWERUPS_VEHICLE_EDGES.md) and
`build/n64/powerup-vehicle-audit/comparison.html` for current evidence and limits.

October 9 source fidelity closure: [FIDELITY_EDGES.md](FIDELITY_EDGES.md).
Retail explosive/Needler comparison is deferred by explicit user instruction.

Source-fidelity quiet replay: **24.4 overall / 26.3 combat / 22.7 vehicle FPS**,
52 KiB live free heap. P95 66.8 ms, maximum 200.5 ms. Source contact and hit-region
work is implemented; the >25 FPS development gate remains open.

October 9 first optimization pass: **25.0 overall / 26.4 combat / 23.7 vehicle
FPS**, 49 KiB free, unchanged assets and 30 Hz simulation. Exact state and
frozen-scene comparisons pass. The >25 vehicle and final 30 FPS gates remain
open; see [OPTIMIZATION.md](OPTIMIZATION.md) for candidates and next bottlenecks.

October 10 collision/camera follow-up: **25.3 overall / 26.6 combat / 24.1
vehicle FPS**, 49 KiB free. Source traces and frozen pixels still match. Both
performance gates remain open; see [OPTIMIZATION.md](OPTIMIZATION.md).
