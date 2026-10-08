# Combat fidelity — direct damage pass

October 8, 2026. The first combat pass replaces generic player damage for the
AR, pistol, plasma pistol/rifle, shotgun, sniper, overcharge and melee with
profiles extracted from the owned Xbox Blood Gulch tags. `extract_combat.py`
preserves the values and provenance in the private asset bank. `combat.h`
adapts the original `object_cause_damage`, `object_damage_shield` and
`object_damage_body` rules to the demake's 100-scale vitality.

## Implemented

- Fractional body vitality; small hits no longer round upward individually.
- Original shield/body material modifiers, leg reduction and shield overflow.
- Pistol/sniper lethal head hits only when positive damage reaches the body.
  Plasma rifle multiplayer head damage doubles after the shield calculation.
- Overcharge EMP removes normal shields or charged overshields. Acquisition
  invulnerability remains; the source rear-melee force-kill bypass remains.
- Shotgun/plasma damage energy follows source initial/final velocity and damage
  range, with source minimum and random damage bounds.
- Source melee strength scales with forward velocity and extended airborne
  time. A hit from behind uses the original facing test and force-kill rule.
- Projectile damage profiles are stored at firing, independent of later weapon
  switching. Existing shield effects, audio, assists and deaths remain connected.

Controlled full-vitality results: pistol 5 body / 3 head shots; sniper 2 body /
1 head shot. A shield-only hit cannot trigger a head kill. A stationary frontal
melee deals 56 native shield damage; a rear melee kills through full overshield.
An overcharge against a fully charged overshield clears the shield and leaves
the body intact. The close-range shotgun showcase now kills in one shot.

## Deliberate boundaries and next work

This is not complete combat parity. Target regions remain three coarse spheres,
not animated collision geometry. Hitscan travel remains instantaneous; damage
falloff uses continuous constant-deceleration energy rather than the complete
original per-tick projectile solver. Floating-point boundary behavior is not
certified bit-identical to Xbox. Random damage uses the demake RNG.

- [ ] Source cone distribution, error growth/recovery, movement/zoom spread.
- [ ] Source firing cadence, reload interruption and animation event timing.
- [ ] Melee animation-keyframe timing and original 25-ray sweep; the present
      adapter still uses one immediate aim ray and blocks melee during reload.
- [ ] Needler attachment, fuse, supercombine and tracking audit.
- [ ] Rocket/grenade radial damage, bounce, fuse and obstruction audit.
- [ ] Vehicle materials, exposed occupants and blast cover.
- [ ] Animated hit regions, body stun and original fall damage.
- [ ] Retail Xbox recordings and human controller acceptance.

## Evidence

`build/n64/combat-audit/comparison.html` contains four before/after Ares videos:
pistol body/head duels, overcharge/plasma rifle, near/far shotgun, front/rear
melee. These are staged N64 encounters using production input and damage paths,
not retail Xbox captures. The scenarios repeat every 12 seconds; recording
start phases differ. The right panes show the targets' shield/health HUDs.

`test_combat.c` covers damage breakpoints, material/leg modifiers, shield-only
head hits, EMP, range endpoints, melee scaling/rear hits, fractional vitality
and production projectile dispatch. Combat, game, shields, movement,
interactions, replay and six showcase suites run with ASan/UBSan.

Current ROM hashes, timing and lifecycle results are recorded in
`build/n64/release-manifest.json`. Emulator averages do not establish a hardware
frame-rate floor. The >25 FPS development gate and final sustained 30 FPS gate
remain open until their measured criteria are satisfied. The current quiet run
measures 27.7 / 28.8 / 26.6 FPS overall/combat/vehicles; the full frontend
lifecycle shows 17 KiB free during four-player combat. Recover memory headroom
before expanding resident systems.
