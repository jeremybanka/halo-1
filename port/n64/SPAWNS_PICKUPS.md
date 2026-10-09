# Slayer spawns, drops and pickup rules

The owned Xbox Blood Gulch cache now supplies Slayer spawn eligibility, starting
equipment, ammunition quantities and map-item schedules. This is a source-backed
adapter, with bounded N64 item storage; it is not the original item physics system.

## Source rules

- `source/game/players.c`, `find_best_starting_location_index`: maximize the
  eligible point's rating multiplied by `sqrt(random(0,1))`.
- `source/game/game_engine.c`, `game_engine_get_distance_rating_for_spawn`:
  free-for-all enemies within 2 world units reject a point; between 2 and 5 units
  multiply its rating by `(distance-2)/3`. No invented line-of-sight weighting.
- `game_engine_get_starting_location_rating`: game-type eligibility and nearby
  vehicle exclusion. The adapter conservatively expands the original hull's
  local bounds by 0.3 units. If every point is blocked, retry next simulation tick.
- The map has 71 start locations, of which **16** are eligible for Slayer.
  Team labels do not partition free-for-all starts.
- The map's non-CTF starting profile is **plasma pistol, no secondary, no
  grenades**, adopted at the user's request. Ordinary respawn is 3 seconds;
  suicide respawn is 10 seconds (`build_game_variant_slayer` / death handling).
- `source/items/weapons.c` supplies initial rounds and reserve caps. Walking
  across a matching ballistic weapon adds actual rounds to reserve, without
  refilling the carried magazine. Battery weapons require a manual exchange.
- `source/units/units.c` drops both carried weapons and remaining grenades on
  death. Swapping a weapon drops its existing ammunition and battery/heat state.
- `game_engine_update_item_spawn` uses placement override, collection period,
  or a 30-second fallback, on a match-clock schedule independent of pickup time.

`extract_pickups.py` reads the retail tags and emits private `pickup_data.c`
and `pickup-report.json` (including source cache hash and raw selected fields).
Run with `build/n64-python/bin/python port/n64/extract_pickups.py` after restoring
the private source assets.

| Weapon | Loaded | Reserve | Reserve cap |
| --- | ---: | ---: | ---: |
| Assault rifle | 60 | 180 | 600 |
| Magnum | 12 | 48 | 120 |
| Plasma pistol / rifle | 100% | 0 | 0 |
| Needler | 20 | 60 | 80 |
| Shotgun | 12 | 12 | 60 |
| Sniper rifle | 4 | 8 | 24 |
| Rocket launcher | 2 | 2 | 8 |

There are **35 original equipment placements**, including eight individual frag
and eight individual plasma grenades. Rockets return on 90-second boundaries,
snipers on 120, overshield on 60, and plasma grenades on 180. The central
shield/invisibility collection chooses either power-up with equal probability
on its 180-second schedule. Camouflage lasts 45 seconds. Four existing demake
Needler/plasma-pistol placements remain, giving 39 permanent map slots.

## N64 storage and cleanup choices

The fixed **56-slot** pool reserves map objects and leaves up to **17 drop slots**.
No per-drop heap allocation or model duplication occurs. Expiration reclaims
slots and removes drawing work; it does not return separately allocated models
to the heap. Map schedules are unaffected by drop cleanup.

- Ordinary drop lifetime: 30 seconds maximum.
- Shorten to 10 seconds old after at least 2 consecutive seconds unseen.
- With 12 or more live drops, shorten to 3 seconds old and 3 seconds unseen.
- Visibility from **any** player viewport counts. A living player within 2.5
  world units also protects a drop from early cleanup. Visibility is conservative
  frustum visibility, not expensive wall-occlusion testing.
- A full pool preferentially replaces an old unseen, distant drop. If every
  slot is protected, replace the oldest drop; never replace a map object.
- Ignore the former owner for one second, avoiding immediate auto-recovery.

Other deliberate adapters: grenades are stacked per type rather than creating
one physics object per grenade; dropped objects settle directly on the floor
instead of bouncing. One map object per pedestal replaces the source's ability
to stack untouched copies each period. Ballistic recovery transfers loose reserve
first, then remaining loaded rounds into reserve, conserving the complete dropped
ammunition rather than discarding the source magazine with its depleted object.
Spawn and collection randomness use separate deterministic seeds from combat.

## Verification

`test_pickups.c` exercises actual input, collision, death and inventory paths:
eligible/threat-weighted spawns, vehicle exclusion, source starting equipment,
empty second slot, partial and full reserve transfers, battery exchanges, partial
grenade stacks, death drops, any-viewport visibility protection, independent
map schedules, and 40 repeated deaths through full-pool reclamation.

The Ares audit contains scripted staging followed by normal attack/use input:
an AR dropped with **7 loaded / 19 reserve** is recovered with precisely those
amounts. The second recording stages deaths, then lets production respawn
selection choose among the 16 eligible points with three other players present.
These are N64 recordings, not retail Xbox footage. See
`build/n64/pickup-audit/comparison.html` and the release manifest for ROM identity,
performance measurements and lifecycle evidence.

Remaining acceptance: retail/controller comparison, long hardware sessions,
physical item trajectories and multi-player pickup contention on hardware.

Final verification: nine ASan/UBSan suites pass; Ares frontend lifecycle 37/37,
including all eight weapons, 15 kills, results and menu return. Final quiet
75.017-second timing run: 26.8 overall / 27.8 combat / 25.9 vehicle FPS;
153 KiB live free heap, P95 66.8 ms, maximum 234.0 ms. Final menu free heap
415 KiB. An initial timing ROM black-screened reproducibly; the fresh final
build passes. Its earlier root cause is not established, and the failed ROM is
retained in the audit rather than presented as valid evidence.
