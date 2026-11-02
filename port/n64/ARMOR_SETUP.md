# Profiles, armor and match setup

Setup is **Profile → Map → Mode → Armor → Countdown**. Four profiles retain
their red, blue, yellow and green palettes and individual controls. Armor is
an independent choice; any number of players can choose the same suit.
SWAT and Team SWAT preselect and require ODST; the armor page explains this
restriction, and both countdown and gameplay enforce it.
Firefight uses **Profile → Map → Fight → Armor → Countdown**, with the same
per-controller confirmation and a back path to fight selection.

The armor page reuses the profile page's four-card layout. Each joined
controller uses left/right to change suit and A/Start to select it. B unreadies;
the unready host's B returns to mode selection. Once everyone is ready, the
host presses A/Start again to continue. Canceling the countdown returns to
armor. Selections survive rematches, but everyone confirms armor again after
mode selection. Unjoined controllers cannot alter the page.

| Armor | Designation | Health | Base shields | Abilities |
|---|---|---:|---:|---|
| Spartan | MJOLNIR Mk V | 100 | 100 | Standard ammunition and damage |
| Jorge | MJOLNIR Mk IV [G-052] | 100 | 200 | Unlimited rocket reserve; explosion damage cannot remove health |
| ODST | ODST BDU | 100 | 0 | Flashlight toggles VISR |

Jorge still needs to find a rocket launcher. Its two-round magazine, firing
cadence, reload duration, weapon-ready time and reload cancellation are
unchanged. `INF` replaces its reserve number in the HUD. The ability belongs
to the wearer, not the weapon: dropped launchers retain finite physical ammo,
and Jorge does not consume loose rocket pickups merely to replenish reserve.
Other weapons use their normal ammunition rules.

Blast damage follows the normal shield calculations, including material
responses and shield depletion. Health is then protected. This covers frags,
rockets, plasma grenades, supercombines, explosive vehicle weapons and the
legacy explosion path. Destroyed vehicles eject a surviving Jorge, consuming
up to 400 shield points; standard riders retain the existing fatal behavior.
Knockback remains. Bullets, melee, backstabs, falls, vehicle impacts and the
map's lethal boundaries retain normal consequences.

Recharge keeps the existing six-second delay and 25 points/second rate, now
stopping at the suit's base capacity. Jorge's base 200 does not decay as an
overshield. Overshields still add 200 points: 300 for Spartan, 400 for Jorge;
only that bonus decays. The HUD's ordinary shield bar represents the selected
suit's full base capacity. Firefight resupply also restores the suit's base
vitals, and enemy damage retains its difficulty and hit-region rules.

## Ownership and extension points

- `character.h` defines armor identity, labels, base vitals, ability flags and
  memory requirements. `BG_PROFILE_COUNT` stays four as armor choices grow.
- `frontend.h` stores profile and armor separately per physical port. Launch
  packs both through the same host-first port mapping. Capability checks run
  on selection and again at launch; Jorge and ODST require 8 MiB.
- `bg_set_player_armor()` records the match choice before `bg_reset()`.
  Spawn copies it into `bg_player.armor`, so death and restart preserve it.
- Damage, regeneration, reloads, pickups and HUD read the armor definition,
  never the profile color. Rendering selects body and first-person assets
  from armor, then applies the profile palette (red/blue team palettes in team
  modes). Changing suits recreates both
  near/far buffers and first-person buffers; recoloring starts from originals.

The current suits still share the existing CE collision and hit-region model.
No new Jorge hitbox dimensions were specified. A future suit-specific hitbox
should dispatch on armor in both broad-phase bounds and animated narrow-phase
regions, with matching movement/vehicle clearance tests. Adding only a larger
visual model or damage multiplier would not implement a different hitbox.

## Palettes and assets

The backpack stays matte neutral gray in all four variants. Armor retains
existing baked light/dark gradients and neighboring base, secondary and accent
hues, with distinct chest and shoulder colors:

| Profile | Chest | Shoulders |
|---|---|---|
| Red | Orange | Green |
| Blue | Purple | Orange |
| Yellow | Green | Purple |
| Green | Original | Original |

Calves, knee plates, feet and the rear codpiece are 20% darker in every profile.
The codpiece shade uses the rear half in the rest pose, leaving the front
plate unchanged. Both LODs retain the closed codpiece and its rear shading.
The tall left guard beside the helmet shares the shoulder accent; concealed
chest backing shares the chest accent. Other green armor retains the accepted colors. Gold visor, black
undersuit and dark headband are protected by component-aware vertex masks. Both
LODs and custom first-person plates use the same tint function. Weapon pixels
and weapon vertex colors are unchanged. First-person legs remain hidden.

`pack_jorge_lods.py` emits the masks without altering the geometry or pose
bank. `review_armor_palettes.py` renders the production packed poses/colors
and AR, then generates all four menu portraits. Files live in the private
asset library at `assets/jorge/armor-palettes/`.

```sh
build/n64-python/bin/python port/n64/pack_jorge_lods.py --publish
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P port/n64/review_armor_palettes.py
build/n64-python/bin/python port/n64/review_armor_palettes.py --portraits
build/n64-python/bin/python port/n64/test_armor_palettes.py
build/n64-python/bin/python port/n64/test_jorge_firstperson.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py --output-dir build/n64-armor/host
build/n64-python/bin/python port/n64/test_maps.py --frontend-cycle --output-dir build/n64-armor/maps
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/n64-armor/release
```

`test_frontend.c` covers every nonempty controller subset and host, independent
profiles/controls, repeated suits, readiness/back navigation and memory guards.
`test_armor.c` runs the actual damage, reload, pickup, vehicle and simulation
paths under ASan/UBSan. Palette tests compare all 4,240 body vertex/color pairs
with compiled C, and first-person tests cover 1,409 production poses in all
four colors. Emulator presentation remains a separate visual check.

Ares v148 with the Expansion Pak enabled passed the scripted four-player
setup/match/results/settings cycle (36/36). Visual checks cover the armor
cards, all four first-person palettes, rocket `INF` readouts, mixed Spartan/
Jorge views and single-player arms. The release ROM is
`build/n64-jorge-region-repair/release/halo-64-paced30-rspq32k.z64`; hashes and the validation
ledger are in `halo64-assets/assets/jorge/armor-palettes/validation.json`.

## Main integration — 2026-11-01

Rebased onto `f40fefee` with the current multiplayer modes and Firefight. Armor
selection follows fight selection as well as multiplayer mode selection. The
native QA routes use the additional confirmation page; their back/cancel
paths retain the selected mode or fight. Jorge uses team colors during team
matches and keeps his base shield capacity through Firefight resupply.

Both release ROMs compile. Host sanitizer checks cover all roster/host menu
combinations, thirteen maps, all 26 mode presets, Firefight for 1–4 players,
Jorge's abilities, 4,680 LOD decoder cases and 1,409 first-person poses.
The production near/far bank is unchanged. See
[`benchmarks/jorge-main-rebase/validation.json`](benchmarks/jorge-main-rebase/validation.json).

The older replay fixture still fails its `gunner>0` assertion. An isolated
build of untouched `f40fefee` reproduces the failure with identical telemetry
(595 shots, 30 deaths, nine boardings, zero gunner frames); the six showcase
fixtures pass on both. This is an inherited test failure, not a passing full
regression suite. Native emulator validation has not been repeated for the
rebased revision.

## ODST armor

ODST has no shields, cannot consume overshields, and keeps zero shields through
respawn and Firefight resupply. Its normal flashlight button toggles a deep green
VISR viewport with a subtly curved grid, densest at the center. Living enemies,
including cloaked enemies, are bright green silhouettes. Allies and the wearer's
arms/weapon use a cyan halfway between active and inactive HUD colors; the HUD
remains visible. World depth
partially or completely occludes both friendly and hostile units. Normal weapon
zoom and neighboring viewports retain their usual behavior.
The visor, fabric, backpack and forearm plates stay independent of palette changes;
the crown stripe remains neutral grey. Muted profile/team tint appears on the
chest and shoulder plates. The near and far helmets are independently reduced;
both preserve symmetry and the centered stripe.

The fresh Halo 3: ODST extraction, component demake, independent checkpoints,
near/far costs, custom forearms and scoped validation are recorded in
[ODST.md](ODST.md). The discarded earlier ODST mesh is not an input.
