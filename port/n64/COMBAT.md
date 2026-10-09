# Combat fidelity — damage, timing and projectiles

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

- [x] Source cone limits and error growth/recovery; demake random distribution.
- [x] Source firing cadence, reload interruption and animation event timing.
- [x] Melee animation-keyframe timing and original 25-ray sweep.
- [x] Needler attachment, fuse, supercombine and tracking adapter.
- [x] Rocket/grenade radial damage, bounce, fuse and obstruction adapter.
- [x] Original vehicle hull rays and blast cover; requested destructible hulls.
- [x] Body stun and original fall-damage thresholds.
- [ ] Animated hit regions and articulated vehicle collision nodes.
- [ ] Mounted-weapon damage profiles and full vehicle material response.
- [ ] Retail Xbox recordings, explosive/Needler breakpoint certification and
      human controller acceptance.

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

## Second pass — timing, projectiles and vehicle cover

The continuation replaces the remaining generic firing/reload/melee clocks and
hand-grenade/Needler rules with adapters driven by the owned Xbox definitions:

- Firing acceleration/deceleration, automatic/semi-automatic flags, error
  growth/recovery, source cone limits and the sniper's zoom-accuracy flag.
  Spread is orientation-independent; the demake RNG is still different.
- Source first-person animation frame counts and melee keyframes. Reload
  cancellation retains ammunition only after the source halfway threshold;
  shotgun shells load individually. The melee hit occurs at keyframe + 1 and
  tests the source 5-by-5 ray fan, applying one damage event.
- Frag/plasma grenade gravity, surface-normal bounces, arming and fuse times.
  Plasma grenades stick to units/vehicles, rather than every terrain surface.
  Source radial damage profiles and four core obstruction rays replace the
  old universal linear blast. Vehicle hulls now obstruct those rays.
- Needler launch-time target retention, bounded turning at constant speed,
  individually attached needles and delayed fuses. Further attachments reset
  the uncombined group; the supercombine replaces one needle's detonation and
  scatters the remaining group timers. It no longer deals an invented instant
  300 damage on the seventh contact.
- Source stun accumulation, duration and movement/turning/jump penalties, plus
  velocity thresholds derived from the original harmful falling distances.
- Original vehicle collision triangles with a compact BVH. The hull follows
  the rigid body; articulated turret/wheel/hatch collision remains at bind pose.
- Sustained overturning ejects occupants, including all three Warthog seats.
  The original flipped predicate is `up.k < 0.2`; six consecutive ticks and
  a 0.3-second same-vehicle splatter grace are explicit adapter choices.
  An airborne Banshee is exempt. Exit placement is clamped above local support.

### Acceptance boundaries

These replace the earlier timing/projectile TODOs above, but are not a claim
of complete Xbox parity. Player collision still uses coarse posture-scaled
regions; an animated-region approximation was not accepted. Exact random cone
sampling, Needler wander, complete projectile travel, moving collision nodes,
blast impulse and unit contact/exit clearance remain approximations. Original
multiplayer hull invulnerability is deliberately overridden by the requested
vehicle destruction feature; mounted-weapon damage still needs a separate audit.

Two source-reconstruction details require retail Xbox comparison:

1. The extracted 120-native-damage frag does not alone kill a fully shielded,
   full-health player. The recorded double kill now uses visible AR preparation
   before throwing, through normal gameplay damage.
2. Exactly seven attached needles, using the recovered profiles and combining
   path, can leave 20 normalized body health. The full-health kill recording
   uses 20 actual shots and two supercombines. This breakpoint is **not certified
   against retail Xbox**; do not reintroduce an arbitrary damage override to
   make the demonstration pass.

The recovered projectile timer switch also falls through from first-bounce to
at-rest. This adapter honors the frag tag's first-bounce setting; the small
rest-speed/contact bias is a demake choice.

### Regression evidence

- Eight ASan/UBSan suites: combat geometry, combat, game, shields, movement,
  interactions, replay and six showcases. The geometry suite compares 12,996
  rotated world-space rays against an independent unaccelerated triangle oracle.
- Weapon workspace test runs 20 resize/reuse/release lifecycles for both fenced
  slots. Frontend QA now cycles all eight weapons in all four views before the
  ordinary 15-kill match and return to the menu.
- `build/n64/combat-timing-audit/` retains Ares recordings, exact ROM copies,
  timing evidence and a comparison page. These are staged N64 captures, not
  Xbox footage. The rollover scene explicitly stages an inverted chassis;
  ejection and recovery use production gameplay.
- Initial accelerated collision run: 27.3 overall / 28.0 combat / 26.7 vehicle
  FPS; P95 66.8 ms, maximum 267.4 ms. The unaccelerated mesh had fallen to 23.1
  FPS in the vehicle section. See the release manifest for the final queue
  configuration and measurements; this initial run is not release certification.

The expanded all-weapons lifecycle exposed memory exhaustion missed by the old
shotgun-only fixture. Score text caches now share four owner workspaces, and
first-person buffers are sized to the current mesh at a completed frame-slot
fence. Queue sizing and the final stress result are recorded in the manifest.

The recommended configuration returns to the existing `--paced30` default of
three display surfaces (still four player views), with explicit
`--rspq-buffer-kib 32`. The final quiet run measures 26.4 overall / 27.7 combat /
25.1 vehicle FPS and 164 KiB free heap. P95 is 66.8 ms and maximum 267.4 ms;
these are section averages, not a sustained floor guarantee. Four surfaces
failed under memory pressure when cycling meshes; reducing only the graphics
queue did not fix it. The final lifecycle passes 37/37, with 127–128 KiB free in observed combat
frames and 424 KiB after returning to the menu; screenshots are retained in the
audit and manifest.
Keep four/five-surface variants experimental until this exact stress passes.
