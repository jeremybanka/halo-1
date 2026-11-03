# Map-aware Firefight

The Firefight menu supports Blood Gulch, Battle Creek and Rat Race. Each map
shows its own encounters. All require an 8 MiB Expansion Pak. Unsupported
map/fight combinations are rejected again at launch, and restart preserves the
selected map and encounter.

| Map | Encounter | Rules |
| --- | --- | --- |
| Blood Gulch | Onslaught / Gauntlet | Existing finite survival rules, Spirit deliveries, enemy vehicles and shared Warthog. Gauntlet requires the optional roster. |
| Battle Creek | Courtyard Defense | Completely clear six infantry waves around the courtyard. Checkpoint and resupply after every wave. |
| Rat Race | Station Sweep | Two waves in each of three sectors: cargo bay, service hall and upper station. Rally markers guide movement between sectors; completing a sector saves a checkpoint. |

The new encounters use Normal difficulty, five-second respawns and unlimited
reserve lives. Their simultaneous enemy caps are 4 / 5 / 6 / 6 for 1–4 humans.
Waves contain two squads, or three with 3–4 humans, separated by at least eight
seconds. Three- and four-member squads mix Grunts, rifle/Needler Elites and
Jackals. There are no Hunters, cloaked swords, fuel rods, enemy vehicles,
dropships, skull escalation or timed Grunt bonus in these two scenarios.

Between waves, health, armor-specific shields, carried ammunition and map
supplies replenish. A team wipe retries the current checkpoint, preserving
completed encounter scores/statistics and discarding gains from the failed
section. A simultaneous full wave clear and team wipe grants the clear. Explicit
Restart Match starts the selected encounter from its beginning.

Station Sweep waits for a living teammate to reach the next marked rally point
before starting that sector. The HUD shows its distance, turn direction and a
world marker. Other players retain control of their movement. Neither scenario
adds a destructible defense object or changes the original map architecture.

## Map data and arrivals

`firefight_maps.inc` owns each map's entrance patches, intended floor heights,
sector membership, rally points, minimum enemy separation and dropship/vehicle
capabilities. Blood Gulch retains its original authored entrance coordinates.
New player starts use the selected sector's walk graph, actual human capsule
clearance and separation from living enemies and teammates.

Casual ground arrivals search at most 25 candidates per authored entrance.
Every member must have capsule clearance, spacing and a route to a living
player. Fifteen body-envelope samples must be obscured by collision geometry
from every living player's eye position, with a three-unit minimum separation.
Turning away alone does not make a point eligible. Failed arrivals leave the
packet pending; these scenarios never fall back to a Spirit or visible spawn.
Players exposing all eligible approaches can therefore delay reinforcements.

## Navigation and lifetime

`bake_firefight_nav.py` builds FNV1 banks from the selected maps' existing
collision banks during a normal Firefight build. It uses production clearance
with a 0.24-radius, 0.8-height enemy capsule, half-unit sampling, six floor
layers and reciprocal walk links. Battle Creek has 1,999 nodes; Rat Race has
2,038. Their ROM banks are 43,998 and 44,856 bytes. Battle Creek's disconnected
walk regions remain distinct: arrival reachability is checked rather than
assuming every part of the map connects. NPC jumping, ladders and teleporters
are outside this pass.

Only the selected small-map bank is allocated. A column index bounds nearest
node lookup to adjacent cells; existing shared route fields retain their
256-work-unit-per-tick service budget. Graphs, pending routes and actor state
are released at map unload and rebuilt on map changes. Blood Gulch retains its
accepted graph and source schedule.

The build records graph hashes, map/collision hashes and the bake command.
The original GUNGNIR asset certificate remains intact. Its character-specific
code and all asset bytes remain hash-locked; changes to shared build, map, HUD
and frontend presentation code are recorded separately in the build manifest.
Inherited character acceptance does not claim fresh shared-runtime coverage.

## Validation and reproduction

Run `test_firefight_maps.py --output-dir <fresh-output>` through the workspace
storage guard. It covers both base and expanded roster configurations:

- Concealed, reachable entrances and valid human starts at 1–4 players.
- Independent breadth-first connectivity/distance oracles and bounded routing.
- Actual enemy walking through the production AI and collision system.
- Six-wave completion at every party size, both sector transitions, full clears,
  checkpoints, score/statistic rollback, respawns, resupply and map unloading.
- Wrong-map, truncated, oversized and invalid-link navigation rejection.
- Firefight menu selection, armor/countdown, results and map-change behavior.

`test_firefight_player_warthog.py` additionally runs the inherited Blood Gulch,
Gauntlet, Warthog and enemy-vehicle sanitizer suites. Fixture kills establish
lifecycle correctness; human completion time and balance remain playtest work.

Native fixtures use `build.py --firefight-map-qa beavercreek` or `ratrace`,
`--pve-players 1..4` and `--validate`. They drive actual menu controls through
launch, live ground arrivals, restart, quit/cancel and multiplayer return.
Their diagnostic healing isolates allocation/render/menu checks from balance.
Use a fresh output directory and the ordinary workspace guard for each build.

Both four-player GUNGNIR fixtures pass in Ares, including six allocated enemies,
restart, quit/cancel and multiplayer return, with zero RDP validation errors or
warnings. Each native manifest's 288 compiler inputs was verified against the
current source. [The acceptance record](benchmarks/firefight-maps/validation.json)
binds the raw host/native logs and ROMs by hash; those artifacts remain local.

## Cartridge target

The primary cartridge is SummerCart64, with a **78 MiB** ROM budget. Its extended
mapping adds 14 MiB of flash-backed ROM beyond the initial 64 MiB SDRAM region.
The manifest identifies builds requiring extended ROM access; 8 MiB Expansion
Pak RAM is still required independently. This replaces the earlier assumption
that an expanded-roster ROM above 64 MiB necessarily needs a size reduction.

References: [official features](https://github.com/Polprzewodnikowy/SummerCart64#features),
[PI memory map](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/01_memory_map.md#pi-memory-map),
[extended-ROM configuration](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/04_config_options.md#14-rom_extended_enable).
