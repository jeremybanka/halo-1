# Firefight Limited appraisal captures

The implementation and rules are in [FIREFIGHT_LIMITED.md](../../FIREFIGHT_LIMITED.md).
These are native N64 ROM observations in Ares v148, NTSC 320×240, 8 MiB Expansion Pak,
uncapped diagnostic presentation. They are not real-cartridge measurements or
proof of human balance. The playable ROM uses the normal paced release profile.

`results.json` retains every sampled counter and the aggregation. Stress cases
use the same deliberately close formation: two Hunters plus Jackals, Elites and
Grunts, filling the 6/8/10/12 cap for 1/2/3/4 players. Ordinary cases start the real
wave director with aiming/movement inputs. Combat uses production health, damage,
weapon cadence and respawn rules. Bots are a repeatable load fixture, not expert
players or a substitute for playtesting.

Each stress run records 45 one-second observations; each ordinary opening records
75. Discard the first five observations. The whole-window mean includes deaths,
respawn waits and arrivals. `living_players_and_landed_enemies` separately filters
for at least one living human and enemy with no unloading units. It does not
assert that every enemy is visible or shooting. Compare the raw counts and ranges
alongside the FPS, rather than treating a quiet/dead-camera average as combat FPS.

`PHASE` frame statistics are rolling 120-frame windows, not independent repeated
benchmarks. CPU `sim`, `prep`, `draw`, AI, movement/combat and NPC preparation
samples describe the reported frame. Under overload a rendered frame may contain
multiple 30 Hz simulation steps. NPC preparation includes animation DMA/decode,
attachments and visibility. GPU drain counters are zero in these nonserialized
runs: **zero is not a measurement of no RSP/RDP work**.

The lifecycle run uses fixture healing and direct kills to traverse the full
15-wave set, all recovery transitions, repeated slot/buffer reuse and the bonus.
It is excluded from performance results. It passed at tick 16,142 with 105 ground
packets and seven Spirit deliveries; lowest sampled free heap was 1,065,672 bytes.
The final renderer adds an inactive-session guard after this run; the game code,
asset payload and active-session rendering are identical. The menu/PvP native
checks use the guard. The live-arrival menu check passed all 39 controller steps
after waiting for actor/Spirit allocation before restart and quit, then launched
a normal four-player multiplayer match with the NPC pool cleared. Build manifests preserve the exact source hashes.

Frozen photo ROMs export completed RDP RGBA5551 pixels. `decode_photo.py` requires
every pixel chunk exactly once, then converts to an unscaled PNG. They do not
include desktop scaling or VI filtering. Photo logs containing image bytes and
PNGs stay in the private/local appraisal, not this public evidence directory.
The readback code is entirely excluded from live and profiling ROMs. Performance
captures precede a cosmetic correction removing one duplicate respawn prompt;
combat, arrivals, source assets and live render paths are otherwise unchanged.

Run `collect.py /path/to/capture-directory --output results.json` to reproduce
these statistics. `provenance.json` records ROM and log hashes, source revision,
private-asset revision, build-manifest hashes and the original camera/actor poses.

## Measured frame rates

| Fixture | Living humans + landed enemies: mean FPS (range) | Observations | Whole-window mean FPS |
| --- | --- | ---: | ---: |
| Ordinary opening, 1P | 38.4 (3–49) | 39 | 45.7 |
| Ordinary opening, 4P | 8.7 (2–22) | 53 | 13.8 |
| Crowded mixed fight, 1P | 19.2 (4–25) | 20 | 21.8 |
| Crowded mixed fight, 2P | 11.9 (2–26) | 24 | 16.9 |
| Crowded mixed fight, 3P | 6.4 (2–11) | 22 | 8.9 |
| Crowded mixed fight, 4P | 4.3 (1–8) | 26 | 5.3 |

The four-player ordinary opening averages 95.8 ms simulation, 10.7 ms scene
preparation and 30.2 ms drawing/submission in the sampled frames. AI/perception/
path work accounts for 30.5 ms within simulation; NPC preparation is 7.7 ms within
scene preparation. In the crowded four-player Hunter fixture, these rise to
123.1 / 34.5 / 47.3 ms, with NPC preparation alone at 30.3 ms. Counts vary as units
die, players respawn and views change. These averages cover the whole retained
window, not just the living-player subset in the second column.

The next optimization appraisal should examine perception/navigation and
simulation catch-up, then Hunter/Spirit representation and animation transfer/
decode. Geometry submission remains significant, but the new ordinary fight
shows substantial simulation cost too. This implementation intentionally retains
the chosen encounter strength and original source representations; it does not
claim four-player 30 FPS.

Repeated build-manifest sections are shared under `build-manifests/shared/`.
`resolve_manifest.py` expands a case to the byte-identical original JSON; its
SHA-256 must equal the recorded `build_manifest_sha256`. This keeps the review
diff readable without discarding source or toolchain provenance.

The native multiplayer residency cycle also passed all 223 controller steps:
fourteen completed matches across all thirteen maps, including the eight
first-person weapon workspaces and quit/resume. `maps-cycle-native.log` records
that integration trace from source `2e6f1b02` with Firefight compiled in. Its
launch ROM checksum was not retained; this is a source-bound functional test,
not another performance measurement.
