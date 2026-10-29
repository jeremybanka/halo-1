# Firefight: actor terrain caches and conservative hit bounds

28 October 2026. Prototype for appraisal; no further optimization is included.

Four-player active-combat mean FPS rises from **5.79 to 6.69** in the ordinary
opening (+15.5%) and **3.48 to 4.24** in the crowded encounter (+21.8%). The
crowded simulation saves **5.31 ms per tick**, while movement and hit results
match independent pre-change implementations throughout the regression corpus.
Additional linked BSS is **26,032 bytes (25.42 KiB)**. This is a useful CPU saving;
it does not bring four-player Firefight close to 30 FPS.

## What changed

Each actor now retains its own expanded, ordered terrain candidate list. Temporary
spawn/clearance probes use four separate entries. The original four contact lists
still determine contact order, but their misses can filter the actor's short list
instead of repeatedly scanning and deduplicating map-grid cells. An initial
direct replacement failed exact movement comparisons at seams and was rejected.
The accepted implementation preserves the original contact refresh semantics.

Animated enemy hit meshes gain conservative whole-pose bounds and bounds for
contiguous groups of sixteen triangles. Bounds refit on the existing pose-cache
refresh, reject missed groups, and preserve exact triangle traversal order for
surviving groups. Bounds expand by one packed coordinate unit. Damage materials,
shield gaps, weak points, nearest hits and reflection normals retain the original
tests. Overflow paths keep exact fallback behavior. AI decisions, navigation,
encounters, render geometry, animation, movement shapes and hit meshes are unchanged.

## Fresh native results

These are paired uncapped N64 programs running in **Ares v148, 320×240 NTSC,
8 MiB, audio on**, not new physical-cartridge measurements. Both sides use the
same reload fix and opt-in Hunter/Spirit model candidate from the previous
appraisal. The canonical private model bank remains unchanged.

| Players | Ordinary opening, before → after | Change | Crowded encounter, before → after | Change |
|---|---:|---:|---:|---:|
| 1 | 40.92 → 42.05 FPS | +2.8% | 24.15 → 27.40 FPS | +13.5% |
| 2 | 23.12 → 24.06 FPS | +4.1% | 12.50 → 15.27 FPS | +22.2% |
| 3 | 23.07 → 26.09 FPS | +13.1% | 6.91 → 8.50 FPS | +23.0% |
| 4 | 5.79 → 6.69 FPS | +15.5% | 3.48 → 4.24 FPS | +21.8% |

Headline means include observations with living humans and landed enemies, after
five warm-up observations. Each opening capture contains 75 observations; each
crowded capture contains 45. Combat and deaths are active. Requiring **all four
humans alive** gives 5.70 → 6.57 FPS for the opening and 3.15 → 4.05 FPS for the
crowded encounter, so the gains are also present under that stricter filter.

Each case has one fresh capture. Matching build inputs and deterministic input
scripts do not guarantee identical sampled combat states: timing changes affect
which ticks fall into an observation. Small changes are not statistical proof.
Do not compare this table directly against an earlier turn's build; the paired
baseline here includes the same current animation and model candidate.

## What the CPU savings consist of

Fresh counters accumulate over **30 actual simulation ticks**, independently of
rendered frames. The following are means across complete intervals after warm-up;
their windows differ from the filtered FPS subset above.

| Four-player service | Opening before → after | Crowded before → after |
|---|---:|---:|
| Entire game tick | 15.54 → 13.27 ms | 18.74 → 13.43 ms |
| Capsule terrain movement, nested | 5.65 → 4.54 ms | 5.16 → 3.87 ms |
| Enemy hit queries, nested | 1.78 → 0.73 ms | 6.50 → 2.43 ms |
| Terrain query reuse | 53.41% → 94.25% | 50.07% → 96.97% |

The two nested services explain most of the observed saving. In the crowded
candidate, only **3.6%** of triangles eligible after the old loose actor check
reach exact triangle tests. Pose construction, bound refits, actor checks and
box checks still cost time, so a 96.4% reduction in triangle tests does not mean
a 96.4% reduction in total hit-query time. The latter falls by about **62.7%**.
There are no cache overflows in these native captures; forced overflow cases
pass the independent host oracle.

The remaining crowded **13.43 ms/tick** breaks down into disjoint sections:
human controls/movement/weapons and associated updates **6.83 ms**, actor update
**4.91 ms**, projectiles **1.61 ms**, and director/vehicles/post-update work about
**0.06 ms**. These are service ownership totals, not a claim that AI decision
selection itself takes 4.91 ms. Terrain and hit work is already inside them.

## Remaining frame costs

The ordinary counters sample one rendered frame per observation. They are useful
for attribution but cannot be added or inverted to reconstruct the combat FPS:
simulation can execute several catch-up ticks per rendered frame, and the
averages include different states from the filtered FPS subset.

| Four-player crowded sampled frame | Before | After |
|---|---:|---:|
| Simulation section, including catch-up ticks and ancillary updates | 148.52 ms | 89.31 ms |
| Pose/camera preparation | 29.91 ms | 29.65 ms |
| NPC preparation within that section | 25.34 ms | 25.19 ms |
| Draw/submission section, including stalls | 51.38 ms | 53.13 ms |
| Queue wait reported within the pipeline | 19.86 ms | 29.49 ms |
| Submitted vertex loads across four cameras | 61,911 | 61,520 |

Collision acceleration leaves geometry and preparation effectively unchanged.
The candidate's preparation alone is about **29.65 ms**, almost the entire
**33.33 ms** frame allowance. Draw/submission also remains large. The increased
queue wait is consistent with the CPU reaching existing graphics work sooner;
it does not establish a graphics regression, particularly with different sample
windows. Queue and NPC preparation counters overlap their parent sections.

Separate serialized graphics diagnostics report **84.70 → 86.45 ms** waiting
for the submitted RSP queue to finish, followed by **0.051 → 0.037 ms** for the
remaining RDP drain. Geometry remains about 62,000 loads across the four views.
The long queue drain supports substantial outstanding graphics work after CPU
submission. It includes audio pumping and can include RDP backpressure; the
tiny final RDP tail does **not** mean rasterization costs only 0.037 ms or prove
that all of the 86.45 ms is vertex transformation. These deliberately serialized
runs change pipeline overlap and are excluded from headline FPS. Their draw,
audio and drain timers overlap and must not be added together.

There is also a separate **arrival hitch** in the opening. The candidate's
largest measured simulation tick is **623.83 ms**; its containing 30-tick interval
spends **598.04 ms in the arrival/wave director**. The corresponding baseline
interval spends 591.13 ms there, with a 620.36 ms largest tick. The aggregate
counter does not prove that all 598 ms occurred in that one tick, but it clearly
locates substantial work in the same interval. This is distinct from steady
crowded combat, whose director averages only 0.015 ms per tick.

Source inspection explains the risk: `ff_zone_points` tries up to 81 placements
per authored zone; `ff_arrive` can try six zones and then fall back from concealed
arrival to Spirit delivery. Each attempt can do floor queries, capsule clearance,
reachability and up to five concealment rays per living camera. Those checks run
synchronously. They are unchanged in this prototype.

For the next appraisal, the strongest hitch-specific opportunity is to precompute
static formation clearance/grounding and budget the dynamic visibility search,
retaining final safety checks before committing an arrival. Raising sustained
four-player FPS also requires reducing pose/preparation and repeated per-camera
graphics work. These are separate follow-ups; neither is implemented here.

## Verification and artifacts

- **37,440 movement steps across thirteen maps** match the pre-change solver,
  comparing complete player state and impact with no tolerance: sixteen
  interleaved units, crouch, jump, teleport, support and scratch probes.
- **686,256 exact hit comparisons**, including 234,017 hits, match distance,
  material/region and reflection normal across all four species and twelve
  clips, seventeen animation phases, rotated actors, shield states, recycled
  slots, axis-aligned/short rays and authored vertices.
- Both movement/ray suites pass under strict ASan/UBSan and target-style
  fast-math options with contraction disabled. These are host oracles, not a
  proof for every possible floating-point input on physical hardware.
- Forced 512-ID actor-list and 128-ID contact-list overflow preserve full-scan
  results. Sixteen persistent actor entries survive 128 scratch queries, then
  480 warm actor queries cause zero grid rebuilds.
- Existing general collision/movement/weapon/vehicle/replay tests, full 1–4P
  Firefight lifecycle tests, all 26 modes across thirteen maps and exact source
  spawn weighting/selection tests pass. All **39 runtime configurations / 156
  translation units** pass; the matrix, graphics diagnostics and paced playable
  ROM build successfully.

The only private-bank changes refresh dependency hashes after the diagnostic
edits to `game.c`. The map packer's consumed teleporter declaration is unchanged;
no model, motion, map or audio payload changes are included.

[Reproduction, raw logs, provenance and detailed counter definitions](benchmarks/firefight-collision/README.md)
include the independent pre-change oracle revision, exact source/input hashes,
all sixteen captures, separate graphics captures, host logs, memory evidence and
machine-readable results. The prototype stops here for appraisal.
