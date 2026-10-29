# Covenant roster — appraisal candidate, 29 October 2026

This opt-in `--pve-roster` candidate adds fourteen CE loadouts and six formations
to the existing 1–4 player Blood Gulch Firefight game. It requires the Expansion
Pak and the three-tier corrected Covenant model bank. It is ready for appraisal;
this pass does not adopt the candidate or claim that four-player performance is
solved. Code and private assets are published for appraisal with PR #12; the candidate remains opt-in.

## Enemy additions and encounter integration

| Formation | Source-derived loadouts |
| --- | --- |
| Major patrol | Major Elite/plasma rifle, Major Grunt/plasma pistol, Major Grunt/Needler, Major Jackal |
| Fuel-rod team | Major Elite/plasma rifle, Spec Ops Grunt/fuel rod, two Minor Grunts |
| Special operations | Spec Ops Elites/plasma rifle and Needler, Spec Ops Grunts/Needler and fuel rod |
| Zealot guard | Commander (gold Zealot)/plasma rifle, Major Elite/Needler, two Major Grunts |
| Sword assault | Commander/energy sword, Major Elite/plasma rifle, Major Grunt/plasma pistol |
| Stealth team | Cloaked Elite/plasma rifle, cloaked Major Elite/plasma rifle, cloaked Major Elite/energy sword |

These join the eight existing formations. All fourteen loadouts occur in the
finite schedule: Majors and fuel rods enter early; Zealots, swords, Spec Ops and
stealth teams enter the escalating later waves/boss mixes. Both authored concealed
arrivals and Spirit passenger/unload routes accept every new formation. Enemy caps
remain 6/8/10/12; the round structure, shared lives and species-based score values
are unchanged. Rank-specific score bonuses have not been added. Challenge still
needs human appraisal; scripted completion is not a difficulty assessment.

## What comes from CE

The extractor records exact `actor_variant`, `actor`, `biped`, collision, weapon,
animation and dialogue paths from the owned b30/a50/c40/d40 caches, with SHA-256
provenance. `extract_pve_roster.py:VARIANTS` enumerates the paths. Original source
action selectors remain in use; adapter records now belong to individual actors,
so different ranks cannot overwrite one another's rules.

- Per-loadout body/shield vitality, shield recharge, aiming error, engagement
  ranges, firing cadence, first delay, burst/pause, grenade decisions, drops,
  evasion and morale parameters feed the existing runtime. A source rate of zero
  means a held trigger governed by the weapon rate, fixing the prior 0.1 shots/s
  fallback. That correction can also affect existing Needler Elites.
- Fuel-rod Grunts use the source missile stance, 1.25-second charge, projectile
  velocity/gravity, blast damage/material response, and single discharge per
  trigger hold. The remaining held burst and source release pause precede another
  charge. Dropped guns detonate after the source 1.75–3-second delay; no fake
  plasma-pistol pickup is left behind.
- Sword Elites use source sword idle/run/attack poses, attack damage and the
  original strike key (0.5 seconds into the selected attack). The variant's
  12-unit tactical charge range is **not** the hit radius: damage is local to
  animated-hand reach plus source damage radius and the victim capsule, with
  a fresh line-of-sight check. No rifle projectile is fired by a sword actor.
- Cloaked variants honor source zero-shield overrides, normal/super camouflage,
  source recharge rates and damage-dependent camouflage loss.
- 100 complete source dialogue permutations and four source weapon-sound
  permutations are packed at 11,025 Hz, signed 8-bit mono. Contact, idle/combat,
  panic, pain, death, grenade and player-kill events feed two shared ROM streams.
  Source-empty speech fields stay silent. Friend-death samples are archived but
  their dedicated event is not yet emitted. Weapon cues include fuel discharge,
  fuel explosion and the source sword attack sound.

The accepted body triangles, UVs, colors, original animation frames and hand grips
are unchanged in the underlying mesh bank. Alternate source poses are skinned onto
the accepted meshes in Blender. Their animated collision tracks are packed too.
Rank palettes are applied separately; gold/red Elite armor needs a brighter
flattened lighting ramp because a direct source color multiply is almost black
without CE's environment/specular lighting. Black Spec Ops retains that multiply.

## Explicit demake boundaries

This remains the bounded CE-derived AI port, not the complete CE actor engine.
Navigation, perception cadence, steering and animation selection use the existing
platform services. The full original sword charge/leap maneuver and attack root
motion are not ported. Weapon poses and strike timing are source-derived; reach
uses the local proxy described above, not the entire original melee-query system.

Existing corrected Grunt/Elite/Jackal bodies represent the ranks; separate special
campaign helmet/body permutations are not added. Cloaking is single-pass dithered
transparency rather than refraction (settled normal/super opacity 18%/6%). Fuel
projectiles use the demake's ballistic/explosion collision handling rather than
every original material bounce/arming response. Dropped guns settle near the
corpse instead of using full original rigid-body physics. Sword dispersal and
energy appearance are simplified. These are appraisal limits, not exact parity.

Speech uses CE priority ordering with bounded two-channel admission, local event
cooldowns and independent permutation counters. It does not port the full
conversation/chatter queue. Speech never consumes combat RNG; stale recycled
speaker events are rejected. PCM stays in ROM with two small DMA windows.

The pre-existing missing **visual** Jackal shield mesh remains unresolved; its
source hit geometry and shield mechanics still operate. This pass does not claim
to fix that earlier audit finding.

Follow-up: [Jackal shield restoration](JACKAL_SHIELDS.md) adds an opt-in source-mesh
restoration with separate matched photos and performance evidence. The roster
results below remain the original pre-restoration appraisal.

## Native measurements

Fresh Ares v148 runs: NTSC 320×240, 8 MiB, audio enabled, uncapped diagnostic ROMs,
45 observations per case, first five discarded. Numbers below average observations
with at least one human alive, enemies alive and no arrivals underway. The playable
release ROM is capped at 30 FPS. These are native N64 ROM measurements in an emulator,
not fresh cartridge measurements or GPU-serialized timing.

| Players | Original crowded baseline | Same mix + new runtime | New-roster crowded | Ordinary opening |
| --- | ---: | ---: | ---: | ---: |
| 1 | 35.75 | 35.05 | 38.35 | 45.81 |
| 2 | 17.32 | 17.52 | 18.50 | 25.96 |
| 3 | 9.40 | 9.86 | 10.92 | 22.04 |
| 4 | 5.19 | 4.86 | 5.54 | 7.77 |

New-roster crowded observed ranges: 29–53 / 8–37 / 3–22 / 2–14 FPS. Ordinary opening:
40–53 / 20–32 / 13–35 / 3–14 FPS. Requiring **all** humans alive gives new-roster
means of 38.35 / 17.94 / 11.13 / 4.67 FPS. Both scopes and sample counts are retained
in `benchmarks/firefight-roster/results.json`.

The same-mix control is broadly close to baseline; one pass does not establish a
precise small regression. The expanded roster replaces the crowded fixture's
enemy composition, so its FPS is not a matched optimization claim. Ordinary
captures cover the opening, not every later wave. Host tests cover the full set.

Four-player live profile means across all 40 retained observations (a different
scope from the active-combat FPS table):

| CPU measurement | Same mix + runtime | New-roster crowded | Ordinary opening |
| --- | ---: | ---: | ---: |
| Simulation / rendered frame | 81.42 ms | 120.12 ms | 58.71 ms |
| Preparation / rendered frame | 21.13 ms | 18.22 ms | 8.52 ms |
| Drawing / rendered frame | 44.27 ms | 43.06 ms | 33.84 ms |
| Audio / sampled frame | 9.64 ms | 12.88 ms | 7.30 ms |
| Simulation / simulation tick | 13.63 ms | 18.18 ms | 12.46 ms |
| Actor phase / simulation tick | 5.12 ms | 6.56 ms | 3.48 ms |
| Projectile phase / simulation tick | 1.61 ms | 4.62 ms | 0.39 ms |
| Submitted vertex loads / rendered frame, all views | 42,943 | 40,873 | 26,193 |

Rendered-frame simulation includes catch-up ticks; it is not the cost of one
30 Hz tick. Drawing/audio can overlap device work or encounter backpressure.
Subphase counters are nested and must not all be added together. This pass does
not isolate dialogue's cost from changed combat, and does not measure independent
RSP/RDP durations. The harder mix increases projectile and actor work; four-player
is still far from 30 FPS. No performance-driven enemy cuts were introduced.

Minimum reported free memory: 287,496 bytes in the same-mix four-player control,
545,288 in the new-roster stress case and 286,920 in the ordinary four-player
opening. The same-mix baseline had 738,704 bytes: this candidate uses approximately
441 KiB more working memory. This is measured headroom, not proof of every possible
late-wave peak. ROM size is 57,720,832 bytes (about 55 MiB); PCM occupies 1,591,135
ROM bytes. Fuel gun: 443 triangles/658 loaded vertices; sword: 128/228. Guns have
one source representation in this pass; bodies retain their accepted three LODs.

## Validation and artifacts

- ASan/UBSan full finite sets, all 14 formations on both arrival routes at 1–4P,
  wave coverage of all new loadouts, and the original non-roster Firefight tests.
- Source-rule tests cover per-actor vitality/shields/grenades, camouflage loss/
  recovery, sword pursuit/local strike/keyframe/no ranged fire, fuel charge/
  discharge/release and exactly-once death detonation, isolated dialogue RNG.
- Existing two-minute 1–4P PvE lifecycle and return-to-PvP tests pass with the
  roster compiled in. All-map/all-mode recertification passes.
- 37,440 bit-identical movement steps; 1,000,008 exact ray distances/materials/
  normals (325,561 hits) against the pre-bounds exhaustive oracle, including all
  12 fuel/sword collision clips. The oracle only gains new pose selection/cache
  identity; its original interpolation and exhaustive intersection math remain.
- 1,506 accepted base animation frames and their triangle/UV/color/grip data
  remain identical. All 104 complete packed audio payloads verify by hash.
- 46 native photo pages × four fixed cameras, all variants at three LODs plus
  sword attack phases. Saved coordinates, angle, phase, cloak, shield and crouch
  state allow reproduction. LOD diffs are not feature-before/after comparisons;
  cloak pages also deliberately vary opacity. Representative near/coarse, rank,
  fuel, sword and cloaking pages were visually inspected. No native assertion or
  RDPQ error was found in these captures.

Local viewer: `build/n64-firefight-roster/comparison.html` in the original research
checkout. It includes the photos, ×4 diffs, packed-audio previews and playable ROM.
Browser policy prevented automatic `file:` navigation; the saved viewer was not
browser-render verified. Native PNGs were inspected directly.

Public scripts, numerical logs, checks and provenance are in
`benchmarks/firefight-roster/`. Private meshes, sampled animations, audio, bank and
photo evidence are archived in `halo64-assets/assets/firefight-roster/`.
Source-owned maps are never included in that archive. See the benchmark README
for reproduction. Neither repository has been pushed for this appraisal pass.
