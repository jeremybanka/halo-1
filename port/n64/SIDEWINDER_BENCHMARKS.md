# Sidewinder optimization benchmarks and cartridge checkpoint

Documented October 27, 2026. The latest measured hierarchy candidate reaches
**17.556 FPS in the four-player Ares replay** and **29.986 FPS on the single-player
walking route**. World CPU time falls **17.393 → 15.036 ms** across four views.
The corresponding interactive cartridge build is source commit `9b86a886`.

The owner reports good performance in actual console play on most maps on
October 27. This is qualitative play feedback: physical-console FPS, player
counts, routes and per-map timings were not instrumented. The numerical results
below are N64 ROMs running in Ares. No new performance run was made when writing
this report, and the earlier all-map survey is not a timing claim for this ROM.

[Checked-in evidence and verifier](benchmarks/README.md) cover 25 studies and
187 source artifacts. Each record has numeric results and private-original
SHA256 provenance. Available recent raw counters and ROM/run hashes are included.
Full images, pose data, source snapshots and game payloads remain in the local
`build/n64-*` appraisal directories. Original experiment status fields describe
their appraisal dates; the cartridge checkpoint below records subsequent use.

## Measurement contract

Quiet throughput counts **distinct simulation poses displayed at VI**, excluding
duplicate presentations. Use NTSC, 8 MiB, release LTO, three display surfaces,
32 KiB private queues, one-second warmup and a 75-second sample. The four-player
replay and single-player walking route are separate workloads. Compare paired
builds within a study: adjacent studies can have small fresh-baseline drift from
code layout, changed sample distribution and independently built fixtures.

CPU attribution, serialized graphics controls, native census, RDP validation
and frozen photo ROMs are separate from quiet timing. Inclusive CPU intervals
overlap. RSP fence wait measures **remaining** work after CPU submission;
residual RDP drain does not measure all RDP work. Neither should be added to
normal-pipeline CPU intervals as a frame-time accounting identity. RDP validation
uses 8 KiB queues. Fixed-camera geometry counts are static world vertex loads,
including repeated batch vertices and padding; dynamic objects add work.

The matched analysis uses 17 ticks × four cameras (68 samples, 63 live) and
24 complete photo states. Offline float/nearest-texture renders omit native fog,
HUD, dynamic geometry and RDP rounding; their pixels are a different check from
native captures. Scope, transitions and arbitrary camera paths are not exhausted
by a finite photo route.

## Sidewinder development ledger

Values are FPS before → after within each row. Earlier screenshot-derived runs
retain their original rounded fields; this table calculates FPS from saved pose
count/sample milliseconds where available. Modern logs use microseconds.
“Repeated” means both four-player controls were repeated; single-player repeat
coverage is stated separately in the record. Small gains without repeated
controls should be read at that precision.

| Experiment | Four players | One player | Evidence and decision |
| --- | ---: | ---: | --- |
| Initial protected terrain reduction | 9.57 → 9.70 | 27.71 → 27.83 | Repeated both routes; modest reduction. [record](benchmarks/results/2026-10/n64-sidewinder-photography.json) |
| More aggressive protected terrain | 9.57 → 9.86 | 27.71 → 27.91 | Repeated both routes; walking surfaces/collision preserved. [record](benchmarks/results/2026-10/n64-sidewinder-aggressive.json) |
| Terrain plus conservative PVS | 9.86 → 10.36 | 27.91 → 28.15 | Repeated both routes; visibility-only pixel controls identical. [record](benchmarks/results/2026-10/n64-sidewinder-combined.json) |
| Cluster-aware terrain batching | 10.36 → 10.30 | 28.15 → 28.13 | Repeated both routes; slight regression despite useful source membership. [record](benchmarks/results/2026-10/n64-sidewinder-cluster-terrain.json) |
| Simplified fir trees | 10.30 → 11.22 | 28.13 → 28.89 | Four-player repeats; one single-player pair. Continued with lean trees. [record](benchmarks/results/2026-10/n64-sidewinder-trees.json) |
| Screen-size LOD for trees, structures and terrain | 11.22 → 11.64 | 28.89 → 29.07 | One pair per route; exact near representations, distant proxies. [record](benchmarks/results/2026-10/n64-sidewinder-world-lod.json) |
| Playable-surface/skyline canyon rebuild | 11.64 → 11.67 | 29.07 → 29.08 | One pair per route; small gain under strict surface constraints. [record](benchmarks/results/2026-10/n64-sidewinder-canyon-rebuild.json) |
| One worst-case view to budget | 11.67 → 12.58 | 29.08 → 29.08 | One pair per route; target reaches 1,444 native loads, other views remain costly. [record](benchmarks/results/2026-10/n64-sidewinder-budget.json) |
| Broader budgets and conservative cells | 12.58 → 14.03 | 29.08 → 29.93 | One pair per route; more views reduced, batch overhead rises. [record](benchmarks/results/2026-10/n64-sidewinder-budget-cells.json) |
| Regional representations, unlit RSP and submission work | 14.03 → 17.13 | 29.93 → 29.99 | Repeated four-player controls; largest later throughput gain. [record](benchmarks/results/2026-10/n64-sidewinder-throughput.json) |
| Fine-grid visibility audit | 17.09 → 17.22 | 29.96 → 29.97 | Repeated four-player controls; rejected for little gain and ~985 KiB of additional tables. [record](benchmarks/results/2026-10/n64-sidewinder-visibility-audit.json) |
| Intact room/wall section regrouping | 17.14 → 17.27 | 29.99 → 29.96 | Repeated four-player controls; fewer loads, more batches and CPU work. [record](benchmarks/results/2026-10/n64-sidewinder-sections.json) |
| Shared hierarchy with LOD after rejection | 17.22 → 17.56 | 29.99 → 29.99 | Repeated four-player controls; kept for cartridge play. [record](benchmarks/results/2026-10/n64-sidewinder-hierarchy.json) |

The starting protected-terrain control was about 9.57 FPS; the latest hierarchy
control is about 17.56. That is useful historical context, **not one controlled
AB test of the entire stack**. The final within-study hierarchy gain is 1.98%.
The current four-player route still falls short of 30 FPS.

## Geometry changes and rejected approaches

- The early cost audit found live-camera means of **2,211 terrain**, **4,241
  structures**, and **3,112 scenery** loads (9,565 total). Structure costs were
  substantial even when the objects looked simple. [Cost audit](benchmarks/results/2026-10/n64-sidewinder-cost-breakdown.json).
- Conservative architectural simplification barely changed the full replay
  mean: **9,142 → 9,131** loads. An isolated west-base panel treatment reached
  **9,082**. Those investigations did not establish new native FPS gains.
  [Structures](benchmarks/results/2026-10/n64-sidewinder-structures.json),
  [west-base panels](benchmarks/results/2026-10/n64-sidewinder-west-base.json).
- Aggressive and extreme whole-structure collapse were rejected for visual
  damage. Large count reductions and silhouette overlap alone did not protect
  recognizable architecture, UVs or baked lighting. Wall-insert reconstruction
  also failed to save geometry. These are archived alternatives, not cartridge
  assets. [Aggressive](benchmarks/results/2026-10/n64-sidewinder-structures-aggressive.json),
  [extreme](benchmarks/results/2026-10/n64-sidewinder-structures-extreme.json),
  [reconstruction](benchmarks/results/2026-10/n64-sidewinder-base-remodel.json).
- Distance-dependent representations, simpler trees and regional packing gave
  better gains while retaining detailed near geometry and original collision.
  The broad budget pass reduced mean fixed-camera loads **6,983 → 5,279**, but
  mean visible batches rose **177.19 → 260.93**. The following throughput pass
  reached **4,053** loads and **138.90** batches. This motivated reducing CPU
  selection and submission work as well as geometry.
- The throughput ablations measured **14.15 FPS** for eligibility caching,
  **14.38** for the unlit control, **14.05** for full-view command caching,
  **16.06** for regional v2, **17.10** for v3 and **17.13** for v4. These are
  distinct configurations, not independent additive gains. Whole-view command
  caching was unhelpful. [Ablation ledger](benchmarks/results/2026-10/n64-sidewinder-throughput.json).

The one-view 1,500-load result did not generalize map-wide. The current hierarchy
has **3,805.82 mean / 6,514 maximum** loads over the same 68 replay cameras.
Only **9 of 63 live views** are below 1,500; counting dead views gives 12 of 68.
It preserves the finer section candidate's visible geometry exactly.

## Why the shared hierarchy helps

The section regrouping reduced replay means **4,052.59 → 3,805.82** loads and
worst views **6,786 → 6,514**, but increased visible batches **138.90 → 148.01**.
The ordinary CPU profile's world interval rose **16.693 → 17.393 ms**.

A separate detailed profile of that finer-section renderer found the following
approximate costs per four-view frame. Its additional timers change code/cache
behavior: its world total is **17.895 ms including warmup**, and the normal
profile channel in that same run is **17.926 ms excluding warmup**. This is not
an exact decomposition of the earlier 17.393 ms sample.

| Detailed finer-section work | ms / four-view frame |
| --- | ---: |
| Fine/coarse frustum tests combined | 6.960 |
| LOD plus room/cell selection | 5.221 |
| Eligibility rebuilds | 0.870 |
| Material state calls | 0.485 |
| Bulk geometry calls | 0.367 |
| Other setup and loop work, excluding sky | 2.657 |
| Sky, nested within setup in the raw record | 1.334 |

This located the main cost in visibility/LOD decisions, not simply writing the
extra geometry calls. Coarse groups were wholly inside the frustum only **0.16%**
of the time. The eligibility cache hit rate was about **89.7%**.
[Detailed attribution and raw counters](benchmarks/results/2026-10/n64-sidewinder-submission-profile.json).

The shared hierarchy encloses intact batches and both LOD representations.
It rejects parent groups first, passes proven inside-plane information to
children, and evaluates LOD only for surviving groups. Cell/PVS/room eligibility
is cached independently of camera direction and LOD. Selected batches are
submitted in their original ascending order through the existing bulk writer.
It stores 2,742 nodes / 1,368 leaves, uses 62 of 91 declared LOD groups, and has
maximum depth 18. Node storage is 49,356 bytes; replacing older candidate caches
makes the **net startup RAM cost 15,008 bytes** in the quiet four-player build.

| Final paired measurement | Before | Hierarchy |
| --- | ---: | ---: |
| Quiet four-player FPS | 17.2150 | 17.5560 |
| Four-player P95 interval | 66.883 ms | 66.880 ms |
| Quiet single-player FPS | 29.9864 | 29.9864 |
| Normal profile world CPU, all four views | 17.393 ms | 15.036 ms |
| Profiled LOD interval, including warmup | 5.344 ms | 2.560 ms |
| Profiled eligibility interval, including warmup | 0.853 ms | 0.278 ms |
| Eligibility cache hit fraction | 89.60% | 98.50% |
| LOD evaluations / fixed replay camera | 62 | 22.94 |
| Serialized remaining RSP fence wait | 25.679 ms | 27.025 ms |
| Serialized residual RDP drain | 0.034 ms | 0.034 ms |

Both four-player repeats reproduce the complete initial timing records exactly.
World CPU saves **2.357 ms / 13.55%**, while quiet FPS gains **1.98%**. The same
geometry still reaches the RSP. The longer remaining fence wait is consistent
with the CPU finishing earlier; it is not evidence of increased total RSP work.
The hierarchy traversal still costs about **7.510 ms** excluding nested LOD,
and ordered dispatch about **2.278 ms**, in the instrumented four-view totals.
The older zero frustum/dispatch counters mean *uninstrumented*, not free work.
Fixed replay cameras and native frame sampling also differ: native measured
LOD evaluations average 21.53 per view, versus 22.94 for the fixed camera set.
[Final paired results, profiles and counters](benchmarks/results/2026-10/n64-sidewinder-hierarchy.json).

## Pixel, geometry and gameplay evidence

The hierarchy retains every byte of the section candidate's bank and sidecar:
all **17,222 triangles**, collision, movement data, UVs, materials, LOD thresholds
and submission order remain unchanged **relative to that candidate**. Earlier
terrain/tree/far-LOD stages deliberately changed rendered representations.

The hierarchy comparison has zero changed pixels in **196 offline pairs** and
**14 native camera images** (three four-player snapshots plus two route photos).
The native baseline repeat also matches. Eight native census camera sets match
host loads/triangles/chunks/material counts. ASan/UBSan checks cover 200,000
parent/child plane certificates, exact plane contact, 10,000 randomized full-map
views, and the matched replay/photo selectors. The four-view RDP inspection
reports zero errors and warnings.

The preceding **regrouping** comparison is different: its 196 offline pairs
match, but native frames at ticks 180 and 1500 change **3 and 21 pixels**.
Other primary captures match. Its twelve native rejection-control camera images
match exactly, as does repeat capture. Those native rebatching edge differences
remain an exposed caveat; the later hierarchy's zero-pixel result is against
this already-regrouped baseline. [Regrouping evidence](benchmarks/results/2026-10/n64-sidewinder-sections.json).

## Other maps and Expansion Pak experiments

The original thirteen-map benchmark remains in [ALL_MAPS.md](ALL_MAPS.md), now
backed by [checked-in counters and ROM identities](benchmarks/results/2026-10/n64-all-map-audit.json).
It predates the current cartridge's shared submission/unlit changes. The older
[optimization journal](OPTIMIZATION.md) describes Expansion Pak and source-PVS
work; the numerical evidence is also archived here:

| Experiment | Four-player Ares result | Decision / scope |
| --- | --- | --- |
| Blood Gulch feature caches | 24.1 baseline; 24.2 at 128 slots; 24.0 at 512 | No convincing cache win; memory costs retained in evidence. |
| Chiron conservative PVS | 15.5 → 21.4 FPS | Repeated controls; ~38% gain, guarded pixels match. |
| Original Sidewinder conservative PVS | 9.5 → 10.0 FPS | Repeated controls; nonopaque and ten opaque batch exceptions needed. |
| Rat Race conservative PVS | 21.0 → 22.3 FPS | Repeated controls; nonopaque fail-open guard. |

[Expansion Pak trials](benchmarks/results/2026-10/n64-expansion-research.json),
[Chiron](benchmarks/results/2026-10/n64-chiron-visibility.json),
[Sidewinder/Rat Race rollout](benchmarks/results/2026-10/n64-visibility-rollout.json).
The current cartridge selects **Sidewinder's** baked visibility/hierarchy data;
it does not silently enable the Chiron or Rat Race experimental PVS sidecars.

## Cartridge checkpoint and review status

Source **`9b86a8866fb4f5bd0f696b87fe42bea598799524`**, based on main
**`d071efc5db4a5ccc7582dc4769a6ee22bff5f6cd`**, produced a **40,976,384-byte**
interactive ROM with SHA256
`54b80aa457b6afa7706818a60b85ffba1521a60410874dc66f31c580d87a5c13`.
It was copied to `DISK_IMG/homebrew/halo-sidewinder.z64`, fsynced and read back
with the same checksum. It opens normal multiplayer menus, selects Sidewinder
by default, allows all thirteen maps and requires the Expansion Pak. There is
no replay, frozen camera or profiling overlay in this ROM.

Host ASan/UBSan gameplay checks against the exact packaged banks passed all
thirteen maps and a fourteen-match, 224-step frontend/quit/resume cycle. The
separate native QA ROM reached `step=224/224 map=12 done=1`; the exact interactive
ROM also passed its 8 MiB boot check. Map 12 is **Longest** in the Xbox roster.
These lifecycle checks are functional evidence, not performance samples.

The native QA wrapper exited **1 after successful gameplay**, because its final
global Ares-settings hash check detected a change while another Ares instance
was running. Its own children used private settings and were closed before that
assertion. The completion log was preserved; no global-settings restoration was
attempted. This is recorded as successful gameplay with a failed settings-
integrity check, not an unqualified successful wrapper run.
[Cartridge build, logs and deployment receipt](benchmarks/results/2026-10/n64-summercart64-20261024.json).

The runtime remains opt-in (`--playable-candidate --world-hierarchy`); canonical
assets and ordinary build defaults are unchanged. [Build instructions](SIDEWINDER_CARTRIDGE.md)
identify the required private candidate bank, visibility sidecar and unlit
Tiny3D. The documented private hierarchy comparison is
`build/n64-sidewinder-hierarchy/comparison.html`, with before/after, difference,
blend and wipe filters. The rejected fine-grid audit is a different artifact.

The remaining measured limits are four-player throughput below 30 FPS and most
live views above 1,500 static loads. The archive supports further targeted work
without discarding negative results or treating qualitative hardware feedback
as a measured new FPS baseline.
