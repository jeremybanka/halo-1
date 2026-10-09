# Xbox weapon and vehicle interactions

Weapon replacements use the retail seven-tick hold (233 ms at 30 Hz), followed
by the weapon's original first-person ready animation. Switching inventory
slots uses that same ready clip. Shooting, melee, grenades and another switch
wait for the clip to finish. Ammunition and consumables remain walk-over pickups.

The HUD and simulation now share one target resolver. It names driver, gunner
or passenger, uses the vehicle's original entry/seat markers, rejects occupied
seats, and requires a driver before boarding a Scorpion bench. All ten seat
positions are represented: three Warthog, one Ghost, five Scorpion and one
Banshee. The match still has at most four players.

Use **B** in N64 controls or **C-left** in Xbox controls. Vehicle entry, exit and
flipping start immediately; weapon replacements require the seven-tick hold.
Releasing use, losing the target or changing targets resets the weapon hold. A completed use stays latched
until release, preventing an uninterrupted hold from entering and then exiting.
Seat reservations last through the entire boarding/dismount clip. Vehicle
control and weapons become available after boarding finishes.

## Pixel button prompts and flipping

Pickup, seat and flip prompts use native-size cyan button icons with
integer coordinates and point sampling. There is no separator dash. A circular
B represents N64 use; the Xbox layout shows the four-button C cluster with its
left button filled. Weapon pickups retain the word HOLD. Vehicle prompts name
the vehicle or seat, including FLIP WARTHOG, FLIP GHOST and FLIP BANSHEE.
There is no persistent exit hint while seated. Use still exits immediately
with B (N64 controls) or C-left (Xbox controls), including the exit animation.

`hud_buttons.h` supplies the complete reusable set: A/B circles, mirrored L/R
shoulders, a symmetric Z shoulder, four C-direction clusters, Start and D-pad.
Its immutable IA4 atlas occupies 1,536 bytes and uploads only when an interaction
prompt is present. The gallery shows the complete icon set separately from
gameplay captures. The icon combiner preserves intensity as well as alpha,
so inactive C buttons and letter/arrow cutouts remain distinct.

The original flip torque was already present. Its use gate now matches the
45-degree prompt threshold, instead of incorrectly using the stricter `.2` up
component from `vehicle_is_flipped`, which is a driving-state predicate.
Occupied-driver, destroyed and currently flipping vehicles do not offer flip.
One held press cannot restart the roll or board the recovered vehicle.

Warthog and Ghost retain original recovery behavior. Banshee recovery has a
bounded N64 adaptation: continue the original roll for up to 90 ticks, with a
minimum upward velocity of .025 units/tick while the wing has not cleared the
upright threshold. The original `.9` up threshold ends the assist; position and
orientation are never snapped. This lets a wing clear the terrain instead of
stopping the roll with the craft braced on its side. Physics still determines
the final resting angle on sloped ground.

`test_hud_buttons.py` validates the exact runtime atlas, C-direction rotations,
L/R and Z outlines, cell bounds and four-player prompt widths. Interaction
tests verify one-press recovery to a boardable vehicle for Warthog, Ghost and
Banshee, plus release latching and unavailable targets. Native solver tests
cover the formerly rejected 60-degree lean. The new visual gallery is
`build/n64/button-audit/comparison.html`.
The icon catalogue is shown separately in that gallery, never overlaid on the
interaction fixtures. Those scenes display only each interaction's selected
button, just as the release HUD does; flip fixtures retain an orientation
counter for physics inspection.

## Source and deliberate adaptations

The supplied USA Rev 2 `bloodgulch.map` supplies the Spartan graph, weapon
first-person graphs, globals, seat tags and Scorpion hatch graph. `a30.map`
supplies the Banshee and canopy graph. Generated asset reports record hashes
of the inputs and outputs; copyrighted extracted data stays in ignored build
directories.

- `source/game/player_control.c`, action/reload input processing: held use and
  `minimum_weapon_swap_ticks`; the extracted globals value is seven.
- `source/game/players.c`, action handling: vehicle action dispatch and weapon
  swap latch. Vehicle actions start directly from use, matching Xbox. Streaming
  animation frames from ROM requires no artificial input delay.
- `source/items/weapons.c`, `weapon_ready`: original ready-animation duration.
- `source/units/units.c`, `unit_enter_seat`, `unit_try_and_exit_seat`, seat target
  search and animation completion: enter/exit graph indices 7/8, six-tick
  attachment blending, seat marker selection, driver preference and terminal
  dismount root position. Original seat camera markers are also used.

| Clip | Entry ticks | Exit ticks |
| --- | ---: | ---: |
| Warthog driver | 50 | 26 |
| Warthog gunner | 46 | 24 |
| Warthog passenger | 28 | 30 |
| Ghost | 35 | 24 |
| Scorpion driver | 65 | 55 |
| Scorpion benches | 30 | 22 |
| Banshee | 30 | 30 |

Weapon ready clips last 29 ticks for AR/plasma rifle/sniper, 35 for magnum,
14 for plasma pistol, 23 for Needler/shotgun and 22 for rocket launcher.
Scorpion hatch motion lasts 16 ticks; the Banshee canopy uses 22 ticks.

Every source frame of each one-shot clip is retained, skinned onto the approved
reduced meshes. AR digits, the sniper display and all Needler ammunition poses
follow their original ready motion. Stable seated idle loops use four source
samples. Third-person ready uses the Spartan rifle-ready graph rescaled to the
equipped weapon's ready duration. The existing reduced on-foot movement solver
remains; this change does not port the complete biped physics or camera system.
In particular, horizontal dismount momentum is not retained by that solver.
All seat transitions use the existing third-person inspection-friendly boom;
personal-weapon passengers return to their seat's first-person camera afterward.
Distant empty vehicle LODs retain the closed hatch approximation. Occupied
opening/closing transitions retain the articulated model.

## N64 implementation

`pack_interactions.py` emits source timing/seat definitions and a ROM-only pose
bank. The bank occupies **3,659,856 bytes** of ROM, with a single **7,520-byte**
shared DMA scratch buffer. Only the requested adjacent frames are read.
Animation writes use the existing fenced vertex buffers; conservative bounds
cover both Spartan LODs. Original closed hatch transforms return to the approved
model, and existing muzzle effects remain suppressed during ready/seat changes.

After the ordinary world, first-person/ammo and micro-LOD packers, run:

```sh
build/n64-python/bin/python port/n64/pack_interactions.py
build/n64-python/bin/python port/n64/test_interaction_assets.py
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

If regenerating world models, run `pack_extended.py` and `pack_micro_lods.py`
first. `pack_extended.py` writes the exact indexed-vertex source mapping used by
the interaction packer. The build rejects stale animation provenance.

## Verification

`blam/test_vehicle.py` includes sanitizer coverage for held/released/lost-target
use, contested pickups and seats, every seat's exact entry/exit duration,
reservations, boarding death, passenger weapons, ready locks, ordinary combat,
native vehicle physics, replay and all six gameplay showcases. The passenger
showcase aims forward/right through ordinary controller input so its firing
sweep does not cross the driver from the corrected seat camera.

The input adapter and paced acquisition checks cover held use across render
polls/catch-up ticks. The vehicle pose-cache check compares 114,045 cached and
uncached matrices/bounds, including actual hatch matrices. Asset checks cover
1,969 frames, DMA alignment/ranges, bounds, exact source clip durations and
closed-hatch endpoints.

The local Ares gallery is `build/n64/interaction-audit/comparison.html`. Its
screenshots advance actual use input through the normal simulation and then
freeze it; vehicle views use inspection cameras. These are visual validation
fixtures, not performance measurements. The RDP validator reports zero errors
and warnings in the captured scenes. Reproduce them with:

```sh
build/n64-python/bin/python port/n64/build.py --interaction-qa 0 --interaction-tick 16 --validate
build/n64-python/bin/python port/n64/build.py --interaction-qa 1 --interaction-tick 16 --validate
build/n64-python/bin/python port/n64/build.py --interaction-qa 2 --interaction-tick 30 --validate
build/n64-python/bin/python port/n64/build.py --interaction-qa 2 --interaction-tick 112 --validate
build/n64-python/bin/python port/n64/build.py --interaction-qa 3 --interaction-tick 0 --validate
```

The separate quiet `--vi-benchmark --paced30 --paced30-buffers 5` replay measures
displayed poses in four-player combat and vehicle scenes on a 4 MiB emulated N64.
Exact ROM hashes and results accompany the gallery in its manifest.
