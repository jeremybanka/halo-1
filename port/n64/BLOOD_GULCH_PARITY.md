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

- [ ] On-foot movement and aiming — **active**
  - [x] Original walking/backward/strafe/crouch speeds and acceleration.
  - [x] Jump impulse, gravity and airborne steering.
  - [x] Controller response, zoom sensitivity and source-derived aim assistance
        with terrain/vehicle occlusion (approximate target pills).
  - [x] Matched N64 before/after videos and source-backed numerical checks.
  - [ ] Slope projection/slipping, support objects and capsule collision.
  - [ ] Crouched body/hit geometry, stand-up clearance and hard landings/stun.
  - [ ] Retail Xbox video comparison and human controller acceptance.
  - [x] Current four-player performance check and necessary optimization:
        27.1 overall / 28.8 combat / 25.5 vehicle section FPS in Ares.
        These are averages; frame-time spikes and hardware acceptance remain.
- [ ] Spawn selection: replace player-index/team cycling with appropriate Slayer
      spawn eligibility and threat-aware selection.
- [ ] Dropped weapons/grenades and pickup ammunition conservation.
- [ ] Original map pickup timing, starting equipment and respawn rules.
- [ ] Combat audit: shield/headshot breakpoints, spread/range, reload interruption,
      melee direction/damage, grenade bounce/fuses/cover, projectile tracking.
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

Movement implementation and remaining boundaries: [MOVEMENT.md](MOVEMENT.md).
Matched recordings: `build/n64/movement-audit/comparison.html`.
Current source/ROM identity: `build/n64/release-manifest.json`.
Current movement pass: 27.1 FPS overall / 25.5 vehicle section / 108 KiB free
heap, using four display surfaces and exact ROM pose caching. Overall P95 pose
interval 66.8 ms and maximum 334.2 ms: section averages clear 25 FPS, but this
does not certify a sustained floor. See the movement audit timing manifest.
