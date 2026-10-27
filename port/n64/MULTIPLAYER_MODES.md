# Local multiplayer modes

The N64 shell now launches all 26 original Xbox presets on all 13 maps with
an 8 MiB Expansion Pak. One to four local players use the existing join,
controller, pause, restart and postgame flows. Custom gametype editing,
System Link and saved profiles remain outside this implementation.

| Family | Presets |
| --- | --- |
| Slayer | Slayer, Slayer Pro, Elimination, Phantoms, Endurance, Rockets, Snipers, Team Slayer |
| Oddball | Oddball, Reverse Tag, Accumulate, Juggernaut, Stalker, Team Ball |
| King of the Hill | King, King Pro, Crazy King, Team King |
| Race | Race, Rally, Team Race, Team Rally |
| Capture the Flag | CTF, Invasion, Iron CTF, CTF Pro |

`game_modes.def` is generated from the preset builders in
`source/game/game_engine.c`. `export_game_modes.py --check` compares every
field against those builders: score limits, health, loadouts, radar, vehicles,
respawn delays and growth, lives, handicaps and objective traits. Timed goals
are shown as minutes and seconds; scores for other modes retain their own units.

## Playing

Choose a map and preset in Multiplayer → Split Screen. Team modes default to
alternating red/blue controllers. Each joined controller can press left/right
on the pregame screen to change teams; changing a team extends the countdown.
Teams follow physical controllers into the packed game viewports. Armor,
friendly radar dots, the scoreboard and winning rows reflect those teams.

Touch the enemy flag or active skull to carry it. Carrying retains your weapon
inventory but blocks firing, grenades, zoom and weapon pickups. Melee works;
**R in N64 controls / C-up in Xbox controls** drops the objective. Carriers may
ride passenger seats, but cannot drive or use the gunner seat. Death drops the
objective, and dropped objectives fall to the floor and eventually reset.

HUD markers identify flags (F), the ball (B), the hill (H) and your next race
checkpoint (+). A flag carrier also gets a marker at the capture destination.
Objective notices report pickups, drops, returns, captures and checkpoints.
Original mode-start and flag-event announcer clips stream from ROM.

Notable original rules are preserved:

- **CTF Pro:** your own flag must be home to capture. **Iron CTF:** touching your
  dropped flag does not return it. **Invasion:** carry the flag from your base
  to the opposing base, with five lives.
- **Reverse Tag / Accumulate:** ownership transfers through kills, rather than
  carrying a physical skull. Accumulate can grant several scoring balls.
  **Juggernaut / Stalker:** the holder earns kill points and receives the
  preset's damage, camouflage or speed traits.
- **King:** occupants score even when opposing players contest the hill;
  teammates do not multiply the team's scoring rate. Moving hills change
  every 60 seconds.
- **Race:** visit checkpoints in order, then return to the first for a lap.
  **Rally:** a different shared checkpoint is chosen after a score. Team Race
  advances with the least-completed teammate, so everyone must finish.
- **Elimination / Endurance:** limited lives, with Endurance's newest dead
  player waiting while another can respawn. Phantoms assigns scoring targets.

Vehicles use the preset's source selection. The existing expanded vehicle
roster is retained for ordinary Slayer. Race vehicle starts exist on Blood
Gulch and Sidewinder; indoor races are on foot. The port's existing movement,
collision and combat implementation remains the foundation of these modes.

## Asset and memory design

Map geometry banks are unchanged. Each map gains a small version-2 `.modes64`
sidecar with mode-specific starts, starting equipment, pickup eligibility,
flag/ball/hill/checkpoint locations and race vehicle starts. The sidecar binds
to the map ID and a fingerprint of the original spawn records. Positions are
floor-projected and checked by the existing capsule solver; five newly used
starts require small clearance corrections, recorded in the private bank.
All authored hills have at least one capsule-clear, standable scoring position.

Objective meshes and first-person animations come from the owned source.
Flag banners retain the original red/blue artwork and attachment points on a
two-triangle cloth surface; cloth simulation and Xbox shader effects are not
reproduced. World meshes use the source artist LOD. First-person arms use the
existing Blender reduction and animation pipeline. Frame-slot fences protect
all animated and hill vertex buffers, including switching between guns and
objectives. Mode audio reuses the existing small streamed-announcer window.

New presets require the Expansion Pak. A 4 MiB machine shows them dimmed with
that explanation; the existing five-map Slayer selection remains available.
The optimized Sidewinder hierarchy/PVS candidate itself already requires 8 MiB.

Private art, sound, source-coordinate data and generated banks live in
`halo64-assets`; the public repository contains the exporters, rules, tests
and reports. Builds verify all thirteen metadata sidecars and objective/audio
hashes, rejecting missing or stale data before producing a ROM.

## Reproduction and checks

With the private bank connected, the ordinary release build includes the modes.
Regeneration from the owned Xbox caches uses:

```sh
build/n64-python/bin/python port/n64/export_game_modes.py --check
build/n64-python/bin/python port/n64/extract_mode_maps.py --source-root /path/to/source-checkout
build/n64-python/bin/python port/n64/extract_objectives.py --maps /path/to/xbox/maps --output halo64-assets/assets/objectives
# Blender: port/n64/reduce_objectives.py, then port/n64/pack_objectives.py.
build/n64-python/bin/python port/n64/test_maps.py --modes
build/n64-python/bin/python port/n64/validate.py --group host --group contracts --group assets
```

The map fixture runs all **26 × 13 = 338 combinations** with ASan/UBSan,
checks source start eligibility and clearance, loadouts, vehicles, objectives,
hill reachability and unloads, then exercises actual production scoring,
transfers, lives, team penalties, carrier controls and ordered/team races.
The legacy all-map lifecycle fixture remains separate.

`build.py --modes-cycle` produces a distinctly named native acceptance ROM.
It navigates the production menus using controller edges, joins four players,
selects Wizard, and completes each preset through its normal game-over and
postgame logic. It stages positions and combat and lowers the score limit to
one; this is automated acceptance evidence, not a human playthrough or a
performance benchmark. It never assigns a winner directly. The playable ROM
does not include this fixture.

## Acceptance recorded 2026-10-27

The [checked-in report](validation/multiplayer-modes-20261027.json) records:

- 16/16 maintained host/header groups, 25/25 renderer contracts and 8/8 asset
  groups passing; all 338 map/preset combinations pass with sanitizers.
- Ares completing all 26 presets with four players on Wizard, through the
  real postgame flow. Postgame free heap returns to 4,102,568 bytes each time.
- Four-player Wizard Slayer completing with 4 MiB, with 415,976 bytes free
  at postgame. This checks the ordinary renderer, not the 8 MiB Sidewinder
  candidate configuration.
- Separate flag, skull and hill previews displaying zero RDP errors and
  warnings. Local screenshots and full logs accompany the build artifact.
- The final playable ROM retains the accepted Sidewinder hierarchy, PVS,
  bulk submission, 30 FPS pacing and 32 KiB RSPQ configuration. These checks
  do not establish a new FPS benchmark or physical-cartridge validation.

Use `--modes-preview 17`, `7` or `12` to hold a staged CTF, Oddball or King
match open for visual review; add `--validate` for RDP diagnostics. Preview
fixtures raise the goal and reposition players; they are absent from release.

## Flag-grip correction

The original generic 198-triangle hand reduction moved the upper gripping
hand's fingers and palm inside the flag shaft. The depth buffer then correctly
drew the shaft in front, giving the fingers a broken, transparent appearance.
Opaque-material and back-face-culling diagnostics did not repair the geometry.

The objective reducer now preserves the source left-hand wrist/palm and five
finger surfaces, while reducing the forearms and other hand. Flag hands use
555 triangles (795 with the unchanged pole/banner), versus 1,612 in the source
hands. The packed flag viewmodel rises from 818 to 1,380 vertices; the skull,
world objectives and gameplay geometry are unchanged. Four-MiB Slayer retains
its gun-only workspace capacity. New objective modes already require 8 MiB.

`test_objective_grip.py` independently skins the original hand and compares
nearest-surface occlusion in the four-player grip region. Across four idle
poses, only two of 4,483 source-hand samples differ at packed precision. The
old mesh fails this regression check. The native repaired view has zero RDP
errors/warnings; the fixture freezes idle poses for repeatable visual review.
