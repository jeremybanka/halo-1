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
  - [ ] Moving supports, player/player contacts and source step-up orchestration.
  - [x] Source body stun and original falling-damage thresholds.
  - [ ] Animated hit regions and first-person landing effects.
  - [ ] Retail Xbox video comparison and human controller acceptance.
  - [ ] Current four-player performance check and necessary optimization:
        the timing/projectile pass measures 26.4 overall / 27.7 combat / 25.1
        vehicle section FPS in Ares. Both section averages clear 25, but
        the overall P95 is 66.8 ms and maximum is 267.4 ms. Sustained floor
        and hardware acceptance remain; changed deaths alter the replay load.
  - [x] Recover release memory headroom: three display buffers retain four-player
        splitscreen; the expanded all-weapons lifecycle passes. Final memory
        measurements and the 32 KiB graphics queue are recorded in the manifest. Four-buffer builds currently fail that stress
        case and are not the recommended release configuration.
- [ ] Spawn selection: replace player-index/team cycling with appropriate Slayer
      spawn eligibility and threat-aware selection.
- [ ] Dropped weapons/grenades and pickup ammunition conservation.
- [ ] Original map pickup timing, starting equipment and respawn rules.
- [ ] Combat audit — **active**, see [COMBAT.md](COMBAT.md).
  - [x] Source direct-damage profiles, fractional vitality and material modifiers.
  - [x] Shield/headshot breakpoints, overcharge EMP and damage-range falloff.
  - [x] Forward/airborne melee strength and rear force-kill.
  - [x] Four staged N64 before/after encounter videos and sanitizer checks.
  - [x] Source spread/bloom limits, firing cadence, reload interruption and timed melee sweep.
  - [x] Source grenade/rocket damage, bounce/fuses/cover and Needler tracking/detonation adapters.
  - [ ] Certify explosive/Needler breakpoints against retail Xbox (see COMBAT.md).
  - [ ] Animated hit regions, vehicle materials and Xbox/controller acceptance.
- [ ] Camouflage visibility transitions and interaction with targeting/radar.
- [ ] Vehicle edge cases: exposed occupants, damage, blast cover, splatters,
      boarding/dismount clearance and camera obstruction.
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

Latest timing/projectile run: 26.4 overall / 27.7 combat / 25.1 vehicle FPS,
164 KiB free in the timing fixture, three display surfaces and 32 KiB queue
buffers. P95 66.8 ms, maximum 267.4 ms; this clears section averages, not a
sustained 25 FPS floor. Four-buffer variants fail the expanded all-weapons
lifecycle and are not recommended.
