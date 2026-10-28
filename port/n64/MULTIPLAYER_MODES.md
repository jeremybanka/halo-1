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
field represented in the N64 rule table against those builders: score limits, health, loadouts, radar, vehicles,
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

## Source consistency audit (2026-10-27)

The preset settings and scenario data are source-derived; the runtime is still
an N64 adaptation. Passing the tests below is not proof of complete source
behavior equivalence. This audit makes the current boundaries explicit:

| Area | Source consistency and limits |
| --- | --- |
| Starting locations | Source mode eligibility and CTF team partitions are retained. Threat weights, accumulated teammate bonuses and Invasion's base-distance preference now match the recovered rating routines on identical inputs (see Spawn weighting below). Starts remain floor-projected; five need capsule-clearance corrections. Living N64 players stand in for source unit presence, and nearby-vehicle rejection uses the existing collision-bounds adapter. |
| Starting weapons and grenades | Map/mode starting equipment is extracted from scenario tags. Generic-loadout and Rockets/Snipers overrides follow the source presets. Inventory/ammunition behavior uses the existing N64 weapon implementation. |
| Map pickups | Source locations, mode eligibility, weighted item choices and respawn periods are exported. The N64 pickup manager retains one active object per pedestal rather than stacking untouched copies. |
| Death and manual drops | Weapons retain ammunition, heat and grenade quantities; objectives drop on death or weapon-switch input. Placement/physics are simplified: inventory drops are placed near the floor, and objectives fall vertically. Loose inventory has an N64 lifetime/pool policy (30 seconds maximum, with earlier unseen/pressure cleanup), not full source item-object behavior. |
| Objective mechanics | Capture/return rules, carrier restrictions, ball transfers and traits, hill scoring and race progression have production-transition tests. The flag's 17-second and ball's 40-second return periods come from source. Pickup/capture tests use the port's proximity/raycast adapter; reset edge timing and object physics are not tick-for-tick source comparisons. Oddball's missing-marker fallback selects marker zero/first rather than the source random fallback. |
| Win conditions | The named presets' goals, score units, team rules and lives are represented and tested. Native acceptance completed every preset, but stages players and lowers goals to one; it is not an exhaustive comparison of tie/endgame edge cases against the original engine. |
| Existing engine | Movement, combat, collision and ordinary Slayer's expanded vehicle roster retain the accepted N64 behavior. Custom gametype editing and the full Xbox engine are outside this implementation. |

The publication audit reran `export_game_modes.py --check` (all 26 represented
preset rows match) and `test_maps.py --modes` with ASan/UBSan (all 338 map/preset
combinations and the production rule-transition tests pass). Earlier native
acceptance and the latest flag checks remain in the linked validation reports.
The [audit record](validation/multiplayer-source-audit-20261027.json) binds the
original review to its inspected code and test log. The subsequent spawn fix
below resolves the two weighting gaps identified by that audit.

## Spawn weighting

Spawn selection now uses the source distance rules. Enemies inside two units
exclude a start; the weight ramps up between two and five units. Teammates
closer than 0.25 units exclude it; exactly 0.25 applies the source 0.1 penalty.
In team games, each living teammate one to six units away contributes a curved
bonus. Those contributions add, saturate at three, and become a multiplier
of `1 + 3 × bonus` (maximum 10), instead of the old flat 1.5 multiplier.
All distances are three-dimensional.

Invasion additionally uses the reciprocal of squared distance to the team's
authored base marker, clamped to 0.5–10 before taking the reciprocal. After
game tick 30, the source's 0.33-power curve and 0.5–2 bounds soften this
preference. Source Invasion swaps flag slots, so its opposite-slot lookup
refers to the player's own authored base, not the opposing base. Drawable
flag floor adjustment, carrying and dropping do not move this spawn anchor.
An integer warmup counter advances after simulation, matching source tick
order and avoiding a floating-point transition one tick early.

The existing seeded random selection remains unchanged. `test_maps.py --modes`
compiles the original rating function bodies with a small storage adapter,
then compares weights and selected starts against production gameplay. It
covers all 26 presets and 13 maps, both team layouts, one to four players,
live/dead/self units, exact distance boundaries and Invasion ticks 30/31.
`--target-math` also checks the port with target-style math flags while keeping
the reference compiled strictly. This is a host differential test on the
same adapted coordinates and presence state, not a complete Xbox replay or
a bit-exact claim across host and N64 math libraries.

The [spawn validation report](validation/multiplayer-spawns-20261027.json)
records fresh mode/gameplay checks, the target build and input hashes.

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
30-vertex cloth simulation (see Animated flag cloth below). Full Xbox shader
effects are not reproduced. World meshes use the source artist LOD. First-person arms use the
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

## Flag surface precision and material correction

The geometry correction above was incomplete. Its hand-versus-pole regression
did not detect collapsed finger faces or the native surface speckles. Rounding
the preserved hand to 1/256 units collapses 26–55 hand triangles and reverses
up to six per baked pose. The flag viewmodel now uses 1/4096-unit coordinates
with shared 16-bit motion tracks. All 22 baked poses retain their face area
and orientation; sampled interpolations also retain them. Existing gun/skull
byte packing is unchanged (44 default clip outputs compared exactly).

Higher coordinate precision alone did not remove all native speckles. The
first-person hand/pole now draws as an opaque, back-face-culled surface, followed
by the two-sided, alpha-tested cloth in its own batch. The hand no longer samples
the cloth atlas. A separate near-plane experiment did not remove the artifacts
and was discarded. The world flag retains its existing rendering path.

The flag still uses **795 triangles and 1,380 vertex loads**. It uses 25 batches
instead of 24, and the objective animation bank grows from 68,150 to 103,106
bytes (+34,956 bytes). This change does not establish a new FPS result.

The [surface validation report](validation/flag-surface-20261027.json) records
the native idle/melee captures, 47 passing header/renderer/asset checks, and
the playable ROM hash. The independent source-grip test now agrees on all
4,411 sampled idle hand pixels. `test_objective_materials.py` executes the
production drawing helpers to check opaque hand/pole state, two-sided cloth,
both team textures, and state restoration before subsequent objectives.

For repeatable native photos, use `--modes-preview 17 --objective-photo N
--validate`, where N=0–3 selects an idle keyframe and N=4–9 a melee keyframe.
The preview also freezes gait bob. These controls are absent from playable
builds. Native screenshots show the reduced viewmodel; they are not a claim
that all reduced arm/other-hand silhouettes match the full source mesh.

## Animated flag cloth

The flag banner now uses a 6×5 particle grid (30 vertices, 40 triangles), replacing
its rigid two-triangle rectangle. The original uses a 16×13 grid. The port keeps
the original pole markers, fabric dimensions, gravity, air drag, and weighted
neighbor constraints from `source/objects/widgets/flags.c` and
`source/physics/point_physics.c`. It retains the authored difference between the
0.35-unit pole attachment spacing and the fabric's 0.30-unit rest height.

`extract_flag_cloth.py` exports the source map wind settings, including Derelict's
sheltered clusters, into the private bank. Its compact weather selector matches
164,144 valid point queries through the original BSPs, with zero differences.
The wind follows the original bounded random walk and spatial gust lookup, using
a private deterministic random stream so visual motion cannot change gameplay.
Wind definitions are indexed by the stable Xbox map ID, not catalog row order.

Each flag updates once at 30 Hz, shared by all cameras. Grounded and carried flags
use the same state; the first-person view maps that deformation onto its animated
pole markers. Transfers, large attachment jumps and long hitches reset the cloth.
Vertices remain local to each fenced frame slot. The repaired hand and pole keep
their opaque pass; only the cloth uses the two-sided, alpha-tested team texture.

This is a reduced air-only simulation, not full Xbox cloth/shader fidelity. In
particular, it has fewer folds and does not simulate a separate first-person
cloth state. The hand/pole geometry is unchanged. The first-person flag now uses
**833 triangles and 1,406 vertex loads**, up 38 triangles and 26 loads, with the
same 25 batches. The world flag uses 485 triangles, 430 loads and 13 batches.

The [cloth validation report](validation/flag-cloth-20261027.json) records 48
passing header/renderer/asset checks, a final focused recheck after replacing
libm gust-index rounding with the source bit-based lookup, and native four-player
CTF captures with zero RDP errors/warnings. The sanitizer fixture covers ten
simulated minutes of moving/turning anchors, exact pinned endpoints, sag,
independent flags, teleport resets and 4,096 gust-index comparisons.

In the native diagnostic route, wind plus simulation for both flags averaged
**0.978 ms per 30 Hz update**. Total preparation averaged 4.377 ms per rendered
frame in this heavy, close-up four-view fixture, which performed about three
simulation steps per rendered frame. That wider timer includes deferred carrier
animation and world vertex emission. Neither timer includes first-person emission
or GPU drawing; these are not matched FPS measurements or cartridge results.
Four-MiB Wizard Slayer still completes, with 321,616 bytes free at postgame.

Reproduce the native wind/turning/grounded-flag route with
`build.py --modes-preview 17 --flag-cloth-qa --validate`. It is excluded from
playable builds. The local `build/n64-multiplayer-modes/flag-cloth.html` review
contains unmodified native capture sequences and the updated playable ROM.
