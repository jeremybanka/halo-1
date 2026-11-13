# Three-player Firefight zoom crash

The reported setup was an M64 at Insane with three standard Spartans, in Blood
Gulch Onslaught or Gauntlet. The exact hardware ROM was not identified. The
current source reproduces a matching black-screen failure in an 8 MiB Ares v148
cartridge, without an overclock. M64 Insane confirmation remains a hardware check.

## Cause and observed failures

Mixed zoom requires the union of multiple enemy mesh LODs. The old renderer
allocated and recorded separate command blocks for every actor, LOD and fenced
frame slot. Its vertex allocator could reclaim old caches, but the SDK allocations
inside command recording had no corresponding recovery.

The ordinary director allocation fixture failed just after its 06:33 log sample:
`pve_prepare -> pve_record_surface -> rspq_next_buffer -> memset(NULL, ..., 512)`.
The SDK had failed to allocate its next command-buffer chunk. The crash inspector
then failed `display_init`'s `__safe_buffer[i] != NULL` assertion while trying to
allocate its own display, explaining the black screen.

A second fixture clusters the production pool of ten living enemies and two
recent corpses so their mixed-view representations are visible simultaneously.
It failed on the first preparation with `PvE vertex buffers`, followed by the
same crash-display allocation failure. This is an allocation stress fixture,
not a claim that the director naturally clusters every actor at these positions.

Zoom exposes a RAM peak; the match timer is not a crash trigger. The older
two-player GUNGNIR cache-retirement fix did not cover unchecked command-block
allocations or this larger current-frame working set.

## Repair

- Record the immutable enemy/Spirit commands once per species, LOD and surface
  pass. Segment 2 selects each actor's fenced vertex buffer before playback.
  The expanded bank has 19 shared blocks. Normal, translucent and VISR passes
  use the same binding; first-person meshes retain segment 1.
- Allocate decode scratch from the maximum track count in every resident body,
  Spirit and pilot animation. The expanded bank needs 680 tracks / 5,440 bytes,
  rather than 8,192 tracks / 65,536 bytes.
- Bound the animation ROM cache at 128 KiB rather than 192 KiB. It still holds
  the largest supported 98,336-byte DMA span. Smaller cache capacity can increase
  ROM transfers; this investigation makes no FPS improvement claim.
- If retiring previous-frame caches still cannot fit a complete preparation,
  fence both slots and retry once. Each visible actor and Spirit then uses its
  most detailed requested mesh across all views. Hidden actors stay hidden;
  distant views can submit more triangles under pressure. This mode lasts until
  PvE residency teardown to avoid repeatedly changing allocation policy.
- In the expanded build, that retry also releases the animation cache and uses
  one transfer window sized from the same maximum track count: 8,192 bytes for
  the expanded bank. Animation values stay exact; fewer cached spans can mean
  more cartridge reads. The normal path retains its cache and per-camera LODs.
- Pre-record the Jackal shield commands before actor buffers reach their peak.
  Release shared command blocks, attachments and scratch at the existing PvE
  residency teardown boundary. Keep converted static indices ready for reuse.

Scratch and ROM-cache capacities shrink by 125,632 bytes in the expanded build;
command sharing additionally removes repeated allocations and variable per-actor
command storage. No difficulty, spawn count, damage, zoom magnification or authored
mesh changes are part of the playable repair.

## Evidence and limits

`results.json` records hashes and completed checks, including which revision of
the repair each test exercised. Raw logs, diagnostic cartridges, original fixture
sources and playable builds are locally retained under
`build/firefight-zoom-20261113/` and the
`build/firefight-zoom-followup-20261113-*` directories. These outputs are not
committed. The selected final build and evidence are pinned locally.

The fixtures heal humans, disable their firing, cycle pistol/sniper zoom every
second, and directly clear landed enemies every ten seconds. They test allocations
and resource reuse, not human balance or frame rate. The crowded fixture instead
retains its clustered actors and recent corpses. The additional `jackals` fixture
uses twelve Jackals (ten alive, two corpses) with distinct animation phases to
stress the largest body LOD pair without shared-pose savings. This fills the
renderer pool; it is stronger than the authored formation ratios.

The full expanded cartridge exceeds Ares's 64 MiB ISViewer limit. For logging,
other maps' filesystem payloads are omitted from a separate diagnostic image;
its executable and Blood Gulch resources stay identical to that fixture's full
image. The playable candidate retains all maps and normal gameplay. These tests
are emulator evidence, not a physical-console acceptance result.

Host checks use ASan/UBSan. They compare 1,211,760 direct/segmented commands and
1,587,039,232 animated vertices, including all interpolation bins and exact-sized
scratch. Target checks cover default, expanded, baseline-preparation, VISR,
scope, frontend and audit configurations. Native menu QA checks restart, quit,
return to multiplayer and RDP validation.

The first command-sharing candidate passed the crowded fixture for 1,800 ticks /
60 simulated seconds and both director fixtures for 20,010 ticks / 667 seconds.
Gauntlet won; Onslaught was still in its bonus at that horizon. Its native
three-player frontend validator passed 43 steps without RDP errors or warnings.
Those historical logs remain in `earlier_command_sharing_candidate` in the report.

Follow-up testing found a remaining first-frame failure with twelve Jackals.
The shared-LOD retry passed that direct fixture for 600 ticks / 20 simulated
seconds, but a menu-launched version still exhausted RAM around its first zoom
transition, including without the rendering validator. This exposed the need to
release the large CPU animation cache when entering pressure recovery.

With the transfer-window fallback, the saved `pressure-frontend` fixture recovers
once, cycles pistol/sniper zoom with the twelve-actor pool, restarts, cancels quit,
quits and launches normal three-player PvP. All 43 steps pass without an assertion
or CPU exception. Lowest sampled free heap in its dense first match is 223,136
bytes. This fixture uses telemetry without the rendering validator; samples are
not a per-allocation minimum or a guarantee of every possible scene's budget.

The full follow-up director runs exercise the shared-command/shared-LOD renderer.
Onslaught completes all 15 waves and the bonus with victory at the 11:40 director
timer; Gauntlet completes its set and bonus at approximately 10:50. Neither run
enters the whole-preparation pressure retry. These builds precede the final
transfer-window addition; that final pressure path and teardown are covered by
the saved frontend fixture. Target compilation covers the final source in ten
configurations plus both generated audit translation units. Sanitizers also
check 120 two-LOD and 340 three-LOD view plans, exact transfer-window sizing,
the one-retry limit and idempotent residency teardown.

The final playable ROM is
`build/firefight-zoom-followup-20261113-pressure-window-playable/halo-64-pve-model-candidate-paced30-rspq32k.z64`,
SHA-256 `50c12bd75fd9e6e8254ba8d7aa198a7b25e7b864063cb5703f1e1b2724e5debb`.
It supersedes the earlier `629f0b...` and `bda7b8...` candidates. Physical M64
Insane acceptance remains pending.

## Active combat coverage

The allocation fixtures above suppress human fire and do not establish stability
during active combat. `combat-onslaught` and `combat-gauntlet` add that workload:
three standard Spartans use the real driver, turret and passenger seats, drive a
Warthog circuit, fire automatic weapons and scoped weapons, throw frag/plasma
grenades, dismount and cycle zoom. Enemy AI, movement, shooting, grenade decisions,
damage, deaths, weapon drops, vehicle physics and effects stay active. The
renewable encounter uses the fight's production cap (10/8 living enemies),
including Ghost/Wraith pilots, Hunters, Jackals and roster variants. Corpses
remain for three seconds before their slots are reused.

Test support replenishes ammunition, assists approaches to boarding positions,
and restores living humans and the player transport during the first 40 seconds
of each minute. The other 20 seconds permit ordinary deaths and destruction.
An overturned Warthog uses the normal flip interaction before reboarding. This
keeps the rendering load sustained; it is not a balance or unassisted playthrough.
Enemies are killed by actual gameplay rather than direct test damage calls, and
explosion events are generated by actual weapons and collisions.

The native runner requires 18,000 ticks / ten simulated minutes. It checks
cumulative activity, combat in every minute, recovered driving in every two-minute
window, moving time with all three aboard,
projectile/grenade overlap while driving, scoped combat with ordnance present,
and zoom changes within half a second of explosions. A quiet run fails coverage
even if it never crashes. Event counters are lower bounds if the presentation
queue saturates. Host ASan/UBSan runs qualify the controller before native runs;
the native results are recorded separately.

Both native combat captures complete 18,000 ticks / ten simulated minutes without
an assertion or CPU exception. The renderer sources match the selected playable
ROM. Native event counts and overlap measurements are:

| Fight | Peak projectiles while moving with all three aboard | Explosions | Enemy deaths | Zoom entries within 0.5 s of an explosion |
| --- | ---: | ---: | ---: | ---: |
| Onslaught | 48 / 48 | 475 | 133 | 38 |
| Gauntlet | 48 / 48 | 429 | 144 | 67 |

Onslaught records 89 frag and 66 plasma throws; Gauntlet records 92 and 81.
Joint moving-Warthog/enemy-ordnance/grenade overlap lasts 96.4 and 78.7 simulated
seconds, respectively. The three-view driver/turret/passenger rendering was also
inspected during live combat. These are renewable-encounter stress captures,
complementing the director and frontend tests rather than claiming an unassisted
physical-console playthrough.

Coverage revision 2 allows the ordinary wreck/flip/respawn interval to cross a
one-minute boundary. Gauntlet's 180–240-second interval had no recovered drive,
but still recorded 549 human shots, 199 enemy shots and 42 explosions. The combat
checks remain per minute; the transport check uses two-minute windows. Aggregate
aboard/moving minimums were doubled and the joint aboard/hazard minimum increased
from three to fifteen simulated seconds. Original capture results are preserved;
rechecks of the same raw samples are labeled with their coverage revision.

## Reproduce

With the versioned private asset bank and installed SDK connected, choose a fresh
output and build one of `onslaught`, `gauntlet`, `crowded`, `jackals` or
`pressure-frontend`:

```sh
python3 tools/workspace.py run --output build/zoom-repro-NEW --peak-gib 1.5 -- \
  build/n64-python/bin/python port/n64/benchmarks/firefight-zoom/build_fixture.py \
  --fixture onslaught --logging --output build/zoom-repro-NEW
```

The helper assembles its own checksum-verified enemy-bank overlay from the private
input manifest. `rom/` contains the full fixture and build manifest; `logging/`
contains the separate ISViewer image. Run the logging image with 8 MiB and Ares
Homebrew Mode. Track `ZOOM_SOAK`, `PVE_CACHE_PRESSURE`,
`PVE_SHARED_LOD_PRESSURE`, CPU exceptions and assertions.
The checked fixture sources are production `game.c` wrappers, separate from the
playable ROM. Use the baseline source revision to compare the previous allocator.
The `pressure-frontend` choice enters through the menu QA script and stops at
`FIREFIGHT_QA PASS players=3`; the dense pool is forced only in the first match.

For active combat, select `--fixture combat-onslaught` or `combat-gauntlet` in the
same builder. Run its logging cartridge using known NTSC/8 MiB/Homebrew Ares
settings in a fresh guarded output:

```sh
python3 tools/workspace.py run --output build/zoom-combat-run-NEW --peak-gib 0.1 -- \
  python3 port/n64/benchmarks/firefight-zoom/capture_combat.py \
  --rom build/zoom-repro-NEW/logging/halo-64-pve-model-candidate-profile-paced30-rspq32k.z64 \
  --settings path/to/ares.bml --output build/zoom-combat-run-NEW
```

`combat-results.json` records activity gates, raw samples and the cartridge hash.
The runner owns and terminates only its own Ares process. To qualify the combat
controller against the real game/map with host sanitizers:

```sh
python3 tools/workspace.py run --output build/zoom-combat-host-NEW --peak-gib 0.4 -- \
  build/n64-python/bin/python port/n64/test_firefight_combat_soak.py \
  --output build/zoom-combat-host-NEW
```

Run the focused host checks in guarded fresh output directories:

```sh
python3 tools/workspace.py run --output build/zoom-commands-NEW --peak-gib 0.2 -- \
  python3 port/n64/test_pve_commands.py --output build/zoom-commands-NEW
python3 tools/workspace.py run --output build/zoom-buffers-NEW --peak-gib 0.1 -- \
  python3 port/n64/test_pve_buffers.py --output build/zoom-buffers-NEW
python3 tools/workspace.py run --output build/zoom-pressure-NEW --peak-gib 0.1 -- \
  python3 port/n64/test_pve_pressure.py --output build/zoom-pressure-NEW
python3 tools/workspace.py run --output build/zoom-animation-NEW --peak-gib 0.3 -- \
  python3 port/n64/test_pve_preparation.py --output build/zoom-animation-NEW \
  --bank halo64-assets/generated/pve --bank halo64-assets/assets/enemy-vehicles/bank
```

Buffer, command and pressure checks also run in `validate.py --group contracts`.
