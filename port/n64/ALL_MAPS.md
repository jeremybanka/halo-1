# Complete Xbox multiplayer roster

The eight remaining Xbox maps join Blood Gulch, Wizard, Hang 'Em High, Chill Out
and Battle Creek in local one-to-four-player Slayer. This is the original
13-map Xbox roster from the locally owned disc; later PC maps are outside this
asset set. The source/runtime base is merged `d240145d`, including the grenade
launch and material-bounce repair.

## Memory profiles

The full roster uses an **8 MiB Expansion Pak**. The accepted five-map profile
remains available on 4 MiB. The original map selector reports **Expansion Pak
required** for the eight new maps on 4 MiB and refuses to launch them. This is
the supported profile boundary; it does not claim that every small new map
individually needs eight MiB.

Sidewinder's initial complete bank stopped during selected-map allocation on
4 MiB after loading its original vehicle world. The same bank boots with the
Expansion Pak. The extra RAM is used for complete map residency in this pass;
the eight-slot pose cache, first-person geometry workspaces, three display
surfaces and 32 KiB production command queues retain their accepted budgets.
Cache, residency and visibility optimization experiments are separate work.

## Original scenario rules

| Map | Slayer starts | Map items | Directed teleport links | Placed vehicles | Starting equipment |
| --- | ---: | ---: | ---: | ---: | --- |
| Sidewinder | 16 | 47 | 4 | 8 | Magnum, four frags |
| Damnation | 30 | 40 | 2 | 0 | Plasma pistol, no grenades |
| Rat Race | 48 | 26 | 4 | 0 | Assault rifle and magnum, four frags |
| Prisoner | 24 | 29 | 0 | 0 | Plasma pistol, no grenades |
| Derelict | 27 | 30 | 4 | 0 | Plasma pistol, four frags |
| Boarding Action | 16 | 50 | 8 | 0 | Magnum, four frags |
| Chiron TL34 | 27 | 40 | 30 | 0 | Magnum, four frags |
| Longest | 28 | 26 | 0 | 0 | Plasma pistol, no grenades |

Sidewinder retains two authored Warthogs, four Ghosts and two Scorpions. Rat
Race has no custom starting-equipment row: `unit_add_initial_weapons` supplies
the multiplayer Spartan's AR and magnum, and the source game engine supplies
four fragmentation grenades. The other maps retain their authored Slayer
starting profiles, item collection weights and timers.

Chiron's group-all-powerups collection selects camouflage, overshield and
health with original weights **70:90:15**. Its third outcome uses the two
reserved tail bytes in the existing 24-byte HM64 item record. Map version,
record stride and the fixed pickup pool remain unchanged; the five accepted
banks remain byte-identical. Legacy two-choice pickups retain their random
sequence and complete gameplay state.

## Geometry and material limits

All eight retain their source BSP architecture and collision, original placed
scenery and authored light-fixture meshes where present. Sidewinder reuses the
previously audited complete foliage-card selections with original retained
positions/UVs. No new architectural decimation is applied. Static fixture
models do not implement dynamic light power, blinking or the Xbox lighting
pipeline.

Map-specific material bins fit the existing 512-chunk, 32-texture,
60-vertex/120-index draw limits. Sidewinder uses 64×64×32 bins; Boarding Action
also uses 64×64×32, Damnation 16×16×8 and Chiron 32×32×16. Remaining maps use the
established 8×8×4 bins. Original lightmap samples are baked into vertex colors;
diffuse maps are filtered to 32px. Sidewinder's source snow/rock blend is baked
with its alpha mask and detail layers, treating its absent micro-detail as a
neutral multiplier. Ground uses the one 64px CI4 palette, while cliff textures
use 32px RGBA16.

New backgrounds use the source outdoor fog color, black when the map has no
sky, or the established source clear-afternoon elevation ramp. Cloud, star,
ring and planet layers are omitted. Water/glass and portal textures retain the
existing static coverage approximations; reflections and animated multipass
shaders are not emulated.

Source starts are archived in provenance before small clearance corrections.
The accepted maps retain their previous offsets and 0.075-world-unit bound.
New-map corrections are bounded to 0.2 units and use the unchanged capsule
solver, including repeated production floor projection at slanted corners.
The largest current correction is approximately 0.159 units. Teleport events
use exact authored exit X/Z; ordinary subsequent contact resolution can move
a player within one capsule radius while retaining full health and clearance.

## Validation and performance evidence

The expanded menu fixture navigates **224 steps and 14 live 15-kill matches**,
covering all 13 maps with a repeated Wizard/Blood Gulch regression boundary.
Each match exercises all eight weapons, quit/cancel/resume, countdown, results
and map unloading. Host checks additionally verify every Slayer start and
teleporter, original loadouts/items and 2,250 simulation ticks per nonlegacy
map, including all three Chiron power-up outcomes through actual refill ticks.

Blood Gulch's replay plus six showcases match merged `d240145d` over 15,300
ticks: all **144,170,084** serialized state bytes are identical, SHA256
`822988418e44c34db718be9ad6b801e8d605cf38d696d77cf8d59621094575f2`.
The five accepted map and collision banks remain byte-identical.

Native acceptance and the final performance table are recorded with exact
ROM and selected-bank hashes in ignored `build/n64-all-map-audit/`. Quiet VI
measurements use the same release/LTO preset, NTSC, eight MiB, four players,
three display surfaces and 32 KiB queues. The observer counts distinct
simulation poses actually displayed over approximately 75 seconds after a
one-second warmup. Blood Gulch includes its combat/driving fixture; other maps
use on-foot route/combat fixtures and report early/late segments. Sidewinder's
parked vehicles retain their normal physics/rendering work. This is a
representative replay comparison, not an identical camera workload or a
physical-console FPS certification. Result-page free heap is not a tracked
minimum watermark.

```sh
build/n64-python/bin/python port/n64/pack_maps.py
build/n64-python/bin/python port/n64/test_map_assets.py
build/n64-python/bin/python port/n64/test_maps.py --maps-cycle
build/n64-python/bin/python port/n64/validate.py
build/n64-python/bin/python port/n64/build.py --preset release --maps-cycle --validate --output-dir build/n64-all-map-audit/frontend-cycle-validator
build/n64-python/bin/python port/n64/build.py --preset release --initial-map sidewinder --vi-benchmark --output-dir build/n64-all-map-audit/sidewinder-timing
```

Enable the Expansion Pak in Ares for the full roster. Change `--initial-map`
to another cache basename from `map_catalog.def` for its replay. Normal builds
consume the baked private banks without reopening the source disc.


## Four-player performance comparison

| Map | Displayed FPS | Early / combat | Late / vehicles | P95 / max interval | End free heap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Wizard | 24.9 | 24.4 | 25.3 | 66.8 / 66.8 ms | 4420 KiB |
| Blood Gulch | 24.1 | 26.4 | 22.1 | 66.8 / 133.7 ms | 4113 KiB |
| Longest | 22.8 | 23.0 | 22.6 | 66.8 / 133.7 ms | 4429 KiB |
| Battle Creek | 21.5 | 22.4 | 20.6 | 66.8 / 66.8 ms | 4245 KiB |
| Rat Race | 21.1 | 21.8 | 20.3 | 66.8 / 100.2 ms | 4328 KiB |
| Chill Out | 20.9 | 20.8 | 20.9 | 66.8 / 66.8 ms | 4353 KiB |
| Hang ’Em High | 19.3 | 18.7 | 20.0 | 66.8 / 66.8 ms | 4357 KiB |
| Derelict | 16.2 | 15.5 | 16.8 | 66.8 / 100.3 ms | 4202 KiB |
| Prisoner | 15.6 | 15.7 | 15.6 | 100.2 / 100.3 ms | 4143 KiB |
| Chiron TL34 | 15.5 | 15.2 | 15.7 | 100.2 / 100.3 ms | 3721 KiB |
| Damnation | 10.8 | 11.8 | 9.8 | 133.7 / 133.7 ms | 3623 KiB |
| Boarding Action | 10.4 | 7.7 | 13.3 | 133.7 / 434.6 ms | 3430 KiB |
| Sidewinder | 9.6 | 9.5 | 9.6 | 133.7 / 200.5 ms | 3083 KiB |

Wizard, Blood Gulch and Longest perform best in these replays. Battle Creek,
Rat Race and Chill Out sit around 21 FPS. Hang ’Em High, Derelict, Prisoner and
Chiron are slower. Sidewinder, Boarding Action and Damnation are the weakest
overall at approximately 10 FPS. Boarding Action also has the worst recorded
presentation gap, about 435 ms, versus about 200 ms for Sidewinder.

**None meets the >25 FPS development gate or final 30 FPS goal.** This pass
adds the full roster while retaining source architecture and accepted shared
workspaces. More RAM resolves residency limits, and leaves roughly 3–4.4 MiB
free on the timing result pages. That room is available for a subsequent
controlled cache/residency/visibility optimization pass; these measurements
are its starting baseline, not a claim that extra RAM alone makes rendering
faster. Individual camera paths, weapons and vehicles differ by map.

The local `build/n64-all-map-audit/comparison.html` contains the sorted table,
native timing screenshots, all eight new-map gameplay recordings and the
source/ROM identity records. Recordings are silent and use real capture
timestamps; their capture rate is not the gameplay FPS measurement.
