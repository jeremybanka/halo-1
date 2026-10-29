# Firefight Limited — first complete CE demake ruleset

This implements the finite, one-to-four-player survival game proposed in
[the Reach research](FIREFIGHT_DESIGN.md). It is an opt-in `--firefight` build,
requires an 8 MiB Expansion Pak, and enables Blood Gulch. The original
[single-squad checkpoint](PVE_SQUAD.md) remains documented separately.

The rules below are **demake rules version 1**, inspired by Reach Firefight
Limited. They are not a claim of an exact retail Reach variant or of a complete
port of CE's AI engine. Native performance and human balance remain appraisal
items; no dynamic frame-rate-based enemy reduction changes a scored encounter.

## Match and resources

- Three rounds of five waves, with a full-clear boss wave at each round's end.
- Ordinary waves advance with at most one enemy remaining, after all packets
  have arrived and the Spirit has departed. That survivor counts against the
  next wave's cap. Bosses require zero remaining enemies.
- Six seconds to prepare initially, five between ordinary waves, and fifteen
  seconds to recover between rounds. A sixty-second replenishing Grunt bonus
  follows the third boss. No bonus respawns; time expiry or team elimination
  ends the completed set. The survival portion has a thirty-minute limit.
- Ten shared reserve lives and ten-second respawns. A reserve is claimed once
  at death; simultaneous deaths cannot spend it twice. A round clear revives
  dead teammates, restores health/shields, replenishes map supplies and grants
  one reserve per human. Recovery takes priority over a same-tick team wipe.
- CE Heroic enemy difficulty multipliers. Human friendly fire is disabled;
  self damage and Covenant friendly fire remain. A fresh life starts with an
  AR (60/180), pistol (12/60) and two of each grenade. Ordinary map supplies
  are finite within each round; enemy weapon/grenade drops use source tags.
- Round two doubles grenade consideration and halves encounter grenade delay;
  round three also disables motion trackers. Evasion uses the source danger
  handler with a 20% shorter cooldown. These are explicit Catch/Tough Luck/
  Cloud-inspired adaptations, not undocumented Reach implementation claims.
- HUD shows round/wave, reserves, enemies, team score, remaining time, recovery
  messages and last-survivor markers. Results retain individual scores and
  team success/defeat. Restart, quit/cancel and return to multiplayer are supported.

| Humans | Simultaneous enemy cap | Packets per ordinary wave, rounds 1 / 2 / 3 |
| --- | ---: | --- |
| 1 | 6 | 3 / 4 / 5 |
| 2 | 8 | 4 / 5 / 6 |
| 3 | 10 | 5 / 6 / 7 |
| 4 | 12 | 6 / 7 / 8 |

Wave four and the boss each add one packet. Packets contain two to five actors,
with at most two live Hunters across all packets. This separates total wave
strength from simultaneous population: more players get additional opposition
and four-second packet gaps, versus six seconds solo. The first round emphasizes
patrols, Grunts, Needlers and Jackal shield lines. Later rounds add mixed and Elite
strike teams; Hunters enter boss rounds two/three and late-round mixed encounters.
The fifteen-wave totals are 285 / 353 / 419 / 488 enemies for one through
four humans, before bonus reinforcements. These counts are initial challenge tuning. Automated completion tests use fixture
kills and **do not establish fair difficulty or human completion time**.

## Authored arrivals

Every supported formation has both concealed ground placement and a Spirit
passenger/unloading sequence. There is no unsupported randomized composition:

| Formation | Composition |
| --- | --- |
| Elite patrol | Plasma-rifle Elite; four Grunts, including one Needler |
| Grunt infantry | Five Grunts, including one Needler |
| Needler patrol | Needler Elite; three Grunts, two with Needlers |
| Shield line | Two plasma-pistol Jackals; two Grunts |
| Mixed patrol | Elite, Jackal and three Grunts |
| Elite strike team | Plasma-rifle and Needler Elites; two Grunts |
| Hunter pair | Two Hunters |
| Hunter escort | Hunter, Elite, Jackal and Needler Grunt |

Six authored anchors surround the encounter: west rocks (-16, -8), east rocks
(16, 9), north (-5, -23), south (6, 24), blue-base flank (-27, -32) and red-base
flank (27, 32). Coordinates are N64 world X/Z. The four delivery stages are:

1. **Choose and reserve.** Rotate among authored entrances, validate the entire
   formation's capacity and Hunter allowance, and search only inside that
   entrance's nine-by-nine authoring patch. Validate each species' capsule,
   ground height, inter-actor spacing and a navigation route to a living player.
2. **Conceal or announce.** Ground arrivals must be at least ten units from
   every living human and pass five occlusion rays per actor from every living
   camera. Otherwise try a Spirit landing; if no valid route exists, retry later
   without advancing the queue or allocating actors. Initial and boss arrivals
   use Spirits deliberately. The ship approaches above the cliffs then descends
   vertically into its validated landing footprint over eight seconds.
3. **Deliver.** Animate the original Spirit bays open over 1.5 seconds. Original
   CD passenger markers carry the source ride poses. Release passengers at
   0.55-second intervals, playing their source exit poses while moving them to
   individually validated ground positions. Units become damageable on exit;
   a passenger killed while unloading remains dead. Close the bays, climb and
   depart over eight seconds.
4. **Join the fight and recover.** Give each landed squad an initial search order;
   it still needs perception/line of sight to shoot. The director counts arriving
   actors against the cap and waits for departure at wave boundaries. A stranded
   actor can be relocated only when both positions are concealed; this grants no
   kill or score. Corpse slots cannot be reused while their own ordnance is live.

The Spirit is currently a transport: no turret, destructibility, player boarding
or vehicle AI. The world-space flight and dismount paths are authored adapters;
passenger/door meshes, markers and sampled poses come from CE. There are no
Covenant dialogue barks yet. These boundaries are intentional and visible, rather
than placeholder enemy behavior masquerading as original engine behavior.

## Source behavior and hit fidelity

The private b30 extraction supplies minor Grunt/Elite/Jackal variants, Hunters,
Needler-specific Grunt/Elite variants, original low/superlow meshes where present,
animations, weapon attachment markers, collision models, material responses and
difficulty tables. Hunters and Spirits only have the high source representation;
their heavy geometry is retained for this appraisal.

Generated code contains the verbatim CE action selectors for all four species,
the panic transition and grenade-consideration/throwing handlers. Their bounded
platform adapters implement 5 Hz perception/action decisions, 30 Hz movement and
combat, last-seen pursuit, retreat, leader-loss panic, shield recovery, source
bursts/aim error/damage scales, turn rates, timed melee, grenade release and danger
evasion. Friendly-line checks reduce shooting through squadmates. Weapon and
grenade drops use source variant quantities and ammunition fractions.

Jackal shields and Hunter weak points use animated source collision polygons,
not a whole-body shield approximation. Materials survive ray intersection into
damage handling. Needles reflect off the Jackal shield using source reflection
noise/friction and attach through openings. Hunter armor/shield and exposed skin
retain their distinct damage rules, including the CE pistol weak-point kill.
The Hunter projectile uses its actual fuel-rod speed, gravity, charge, damage,
falloff and material modifiers; it is not a rocket with a green color.

Navigation is a two-layer, one-unit grid over the Blood Gulch encounter,
including reachable base interiors and roofs. Edges are baked with the production
capsule solver and the largest supported enemy capsule. This is not CE's original
navigation/cover planner. The [shared navigation prototype](FIREFIGHT_NAVIGATION.md)
retains that graph and exact route costs while replacing per-human full-map
floods with goal-keyed caches and a shared search-work budget. Campaign scripting,
conversation, boarding, coordinated squad maneuvers and all actor variants/ranks
are not ported. The original source
selectors alone do not imply full CE behavioral parity.

Animation tracks stream from a private ROM bank through a bounded 98 KiB transfer
window. This removes roughly 1.9 MiB of resident pose data so the full roster fits
with four cameras. Rendering retains original geometry and interpolates sampled
poses; animation preparation is shared across views. Pools for actors, pickups,
projectiles and render buffers are bounded and exercised through a complete set.

## Scoring

The authoritative death event awards one score entry. Base values are Grunt 10,
Elite 50, Jackal 20 and Hunter 150, multiplied by 1.25 for Heroic with integer
truncation. Headshots or grenade sticks add a further 1.25 multiplier. Kills within
45 ticks extend a multi-kill chain, adding 25 points per step, capped at 100;
every ten kills without dying adds 100. An assisting player contributing more
than 40% of the killer's recorded damage receives one quarter of the base value.
Team score is exactly the sum of individual ledgers. These arithmetic choices
are versioned demake tuning, not verified Reach stacking rules. There is no local
best-score persistence or career-credit system in this implementation.

## Reproduce and verify

Private input extraction (owned maps) uses `extract_pve.py --full --maps …
--output halo64-assets/assets/firefight-combat`. Run `bake_pve_blender.bake(input,
output)` in Blender, using `squad-source.json` and `squad-baked.json.gz`, then run
`pack_pve.py halo64-assets/assets/firefight-combat --output
halo64-assets/generated/pve`. The losslessly compressed Blender payload is tracked;
the equivalent 207 MiB uncompressed JSON and cache files are ignored. The report
hash-binds inputs and the streamed motion bank.

Build the playable ROM with `port/n64/build.py --firefight --preset release
--output-dir build/firefight-limited/play --sdk … --tiny3d …`. The appraisal also
passes the corrected-ground `--map-bank-override build/pve/ground/bloodgulch.map64`;
regenerate that candidate using `conform_bloodgulch_ground.py` as described in
[PVE_SQUAD.md](PVE_SQUAD.md). The canonical multiplayer payload is unchanged.

Validation commands:

- `test_maps.py --firefight`: ASan/UBSan, complete sets 1–4P, all formations and
  both delivery methods, unloading deaths, capacity rejection, reserve races,
  bonus/restart/PvP return, exactly-once scoring, source hit materials, real
  collision rays, Needler reflection, grenade decision/keyframe and safe recycling.
- `test_maps.py --pve`: original squad source selectors, leader-loss panic,
  movement, two minutes per player count, highest NPC-slot ordnance and drops.
- `test_maps.py --modes --target-math --with-pve`: all 26 presets on all 13 maps,
  647,729 exact source spawn ratings and 10,140 identical seeded selections.
- `test_firefight_frontend.c`: 32 roster/host combinations, P3/P4, availability,
  cancellation, memory guards and map restrictions.
- Native `--pve-qa 3`: ordinary opening match with deterministic aiming inputs.
  `--pve-qa 4`: deliberately crowded cap-sized mixed fight, reset every twenty
  simulated seconds; real damage/deaths/respawns. `--pve-qa 5`: Spirit photo route.
  `--pve-qa 6`: full-set allocator/lifecycle soak with fixture healing/kills;
  **not a combat, performance or balance measurement**.
- Native `--firefight-qa 4`: controller edges through entry, restart, quit/cancel
  and return to multiplayer. `--firefight --maps-cycle`: PvP map residency with
  the expanded Firefight executable loaded.

Frozen `--pve-photo-tick` builds also export the completed RDP framebuffer as
RGBA5551 chunks through the diagnostic log. `benchmarks/firefight-limited/
decode_photo.py` reconstructs exact 320×240 PNGs; they have no desktop scaling
or VI filtering. Export is compiled out of performance and playable builds.
Raw image logs and PNGs remain private/local.

The native measurements, build hashes, raw logs and results are recorded in
[benchmarks/firefight-limited](benchmarks/firefight-limited/README.md). Screenshots
and the playable cartridge remain in the local appraisal; original art stays in
the private asset repository. Hardware performance is not inferred from Ares.

A subsequent [performance diagnosis](FIREFIGHT_PERFORMANCE.md) adds ordinary
two-player measurements, per-tick CPU attribution, model comparisons and the
CE behavior fidelity audit.

The [navigation appraisal](FIREFIGHT_NAVIGATION.md) records the subsequent shared,
budgeted route implementation and fresh paired ordinary/crowded 1–4P captures.

The subsequent [collision appraisal](FIREFIGHT_COLLISION.md) adds per-actor
terrain caches and conservative animated hit bounds, exact movement/hit oracles,
and fresh paired 1–4P CPU profiles plus separate graphics-drain diagnostics.
