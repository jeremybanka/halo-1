# Firefight vehicle cost audit — 29 October 2026

The strongest opportunities are **real distant Wraith/Shade meshes** and
**less repeated clearance work**, especially the Wraith's firing-path tests.
The retained CE steering functions are a small part of vehicle AI time. Larger
generic collision caches are not supported by the earlier target experiments.

This audit follows the published Firefight checkpoint `66644065` and private
assets `15c2d3c`. It adds isolated diagnostic source generation and evidence;
it does not adopt a geometry, behavior, enemy-count or simulation-rate change.
The existing playable ROM remains the available-seat candidate.

## What was measured

Four live captures repeat QA8 (Ghost, Banshee, Wraith, Shade plus infantry) and
QA9 (one Ghost plus infantry), at one and four players. Enemy caps remain 6/12.
Each has 45 observations; FPS discards five warm-ups and includes at least one
living human and enemy with no arrival underway. A fifth four-player QA8 capture
adds only a Wraith cooldown counter to investigate a specific opportunity.

CPU attribution integrates every completed 30-tick window, including startup
and QA8's tick-600 restarts. Its denominator is **actual simulation ticks**,
not rendered frames. These windows differ from the FPS subset. Added diagnostic
work can slow execution and change the sampled combat window; this is not an
optimization benchmark or a statistical estimate of small regressions.

Three frozen four-camera routes at ticks 1, 60 and 180 retain ordinary rendering.
Tick 60 is repeated with serialized category drains and with zero-area 3D
scissoring. Each exports nine native framebuffer pages, including individual
hull omissions, all-hull omission and full-scene repeats. Pilots remain present.
All four normally rendered routes have bit-identical full-scene repeats across
all sixteen framebuffer bits. The ordinary/timing tick-60 frame also matches.
Timing/empty-scissor cameras, hull states and submission counts match exactly.
Empty-scissor pixels are excluded from visibility conclusions.

All measurements use native N64 ROMs in Ares v148, NTSC 320×240, 8 MiB and audio
enabled. They are not new cartridge measurements. Raw data, counters and build
hashes are in [benchmarks/vehicle-costs](benchmarks/vehicle-costs/README.md).

## CPU simulation: the four-vehicle overload

The primary four-player audit records 1,230 simulation ticks. Average total
simulation is **30.87 ms/tick**, almost the entire 33.33 ms interval available
at 30 Hz before rendering, animation preparation and audio.

| Disjoint simulation section | ms/tick |
| --- | ---: |
| Humans | 7.56 |
| Vehicle AI | 5.75 |
| Vehicle update, including physics, contacts and weapons | 8.64 |
| Infantry AI/combat | 4.29 |
| Projectiles | 4.54 |
| Director and remaining work | 0.05 |

The sampled rendered-frame simulation average is 212.38 ms because long frames
accumulate several fixed simulation ticks. It is not one 212 ms AI decision.
Reducing graphics work and reducing per-tick work both matter; neither the
vehicle-only budget nor the total simulation budget leaves four-player 30 FPS
close to solved.

### Steering versus clearance

| Vehicle | AI total | Movement clearance | Mortar arc validation | Retained movement controller |
| --- | ---: | ---: | ---: | ---: |
| Ghost | 0.818 ms | 0.606 ms | — | 0.057 ms |
| Banshee | 1.092 ms | 0.642 ms | — | 0.082 ms |
| Wraith | 3.608 ms | 1.998 ms | 1.349 ms | 0.043 ms |
| Shade | 0.188 ms | — | — | 0.037 ms |

All values are per simulation tick in the same four-vehicle capture. Child
columns belong inside AI total; they must not be added to it. The movement
controller is the retained CE movement/facing/throttle path, not the complete
physics solver.

The five-ray width check is often repeated in left/right directions after an
obstruction. The Wraith averages **1.94 clearance calls, 9.72 movement rays and
3.89 support-floor queries per tick**. Its movement rays cost 1.53 ms/tick;
support-floor calls cost 0.40 ms/tick. The rays/floors are already inside the
1.998 ms clearance number. Banshee floor support for flight goals is also
measured, but is outside its five-ray clearance child.

The Wraith also averages 0.786 ballistic-arc calls per tick, roughly 24 per
simulated second. Each successful full traversal tests twelve world segments.
The source tag specifies a 0.1-second burst and a 4–6-second pause. The current
adapter validates the arc before checking whether that pause permits firing.
The analytic trajectory also sets the visible barrel aim, so skipping the
entire function during cooldown would change presentation. The useful split
is cheap trajectory/aim calculation every tick, with obstruction tests only
when their result can affect the firing state.

The separate cooldown follow-up covers 1,200 ticks: **926 of 938 arc calls
(98.7%) occur with a positive burst pause**, accounting for **1.328 ms/tick**
of the 1.346 ms arc bucket. This is an opportunity bound, not a measured saving:
some arithmetic must remain for aim, and any pause-expiry or ongoing-burst edge
case must still receive a fresh obstruction result before it can affect a shot.

### Retained physics and biped contacts

| Vehicle | Full solver step | Force calculation | Ground queries within force | Integration | Sweeps across solver phases |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ghost | 1.599 ms | 0.850 ms | 0.186 ms | 0.242 ms | 0.376 ms |
| Banshee | 2.445 ms | 1.464 ms | 0.338 ms | 0.393 ms | 0.288 ms |
| Wraith | 2.532 ms | 1.508 ms | 0.426 ms | 0.394 ms | 0.519 ms |
| Shade | 0.158 ms | 0.026 ms | 0.016 ms | 0.011 ms | 0.003 ms |

These are inclusive timings: force includes ground/feature work; sweep time
occurs inside force and integration. Do not sum all columns. The full solver
steps sum to **6.73 ms/tick**, within the vehicle-update section above.
Shade's low mean reflects its existing rest/sleep path after settling.

The source mass-point counts are Ghost 5, Banshee 22, Wraith 15 and Shade 4.
The shared 64-surface body candidate envelope is already enabled. Building
collision features costs only about **0.63 ms/tick across all four vehicles**;
feature tests add about 0.04 ms. Eliminating every factory miss would not
eliminate the full solver cost.

The surrounding swept splatter loops cost **1.39 ms/tick**. Their hull/capsule
calls plus ordinary player resolution are nested measurements. This particular
overload is predominantly a rejection workload: the vehicle capsule narrow
phase tests zero triangles in its completed windows, while the live one-Ghost
control does exercise some triangle tests. Broad rejection is already working.
These fixtures do not justify reducing contact precision or omitting rare
impacts; production threshold/impact tests remain the correctness reference.

## Drawing: excessive distant hull detail

At frozen tick 60, every camera submits:

| Hull | Selected tier | Vertex loads | Pixels changed by hull omission, cameras 1 / 2 / 3 / 4 |
| --- | --- | ---: | --- |
| Ghost | Far | 142 | 15 / 0 / 23 / 17 |
| Banshee | Far | 142 | 26 / 23 / 20 / 20 |
| Wraith | Far | 1,320 | 109 / 83 / 102 / 86 |
| Shade | Far | 1,348 | 0 / 3 / 11 / 6 |

Wraith plus Shade account for **90.4% of the 2,952 hull loads per camera**.
The Wraith's visible difference fits roughly 17–21 × 8–10 pixels; the Shade
is at most 5 × 4 pixels here. The same mismatch appears at ticks 1 and 180.
These are final-image contributions, including occlusion/AA interactions, not
counts of visible source triangles. A zero contribution in one image is not
a conservative runtime visibility rule.

The new hulls retain their source mesh in the far bank. Ghost/Banshee already
have much cheaper far representations. The existing tiny-screen fallback does
not activate for these views. The first far transition is distance-based; a
proper middle/coarse representation selected by full projected bounds is the
clear opportunity. Use the full object bounds, not the few pixels left visible
after occlusion, to choose an LOD.

Serialized four-camera category spans at that identical frozen state:

| Drawing interval | Ordinary | Zero 3D pixel area |
| --- | ---: | ---: |
| World and setup | 24.085 ms | 24.051 ms |
| Vehicle hulls | **24.465 ms** | **24.453 ms** |
| Covenant bodies, pilots and held weapons | 30.760 ms | 30.749 ms |
| Other players | 4.042 ms | 4.044 ms |
| Pickups/objectives | 7.128 ms | 7.214 ms |
| Effects/alpha | 6.082 ms | 6.125 ms |
| First-person interval | 19.527 ms | 19.675 ms |

Only **0.128 ms** of the vehicle interval is CPU submission; the remaining
24.337 ms is the queue drain, including possible RDP backpressure. Removing
pixel coverage changes hull time by only 0.012 ms in this single control.
This supports vertex/triangle/command processing over pixel fill as the main
hull graphics cost. It does not independently measure pure RSP versus RDP
occupancy, and the small difference is not statistically meaningful.

These serialized spans must not be added to production per-frame CPU timing.
The diagnostic deliberately destroys pipeline overlap. They also show that
perfectly free vehicles would still leave significant world/Covenant/first-person
work; vehicle LODs alone cannot establish four-player 30 FPS.

## Ranked next steps

1. **Author Wraith and Shade middle/coarse hulls.** Preserve Wraith silhouette,
   mortar opening/hatch and Shade tripod/gun outline; retain detailed near,
   zoom and interaction views. Suggested starting budgets for the roughly
   20-pixel and 5-pixel views are 250–350 and 100–150 loads respectively, then
   tune with the same multi-angle silhouette and native difference checks.
   These are authoring targets, not measured savings. At 300/120 loads, this
   scene's hull submissions would fall from 11,808 to 2,816 across four cameras
   (76.2%); graphics time will not necessarily scale linearly. Collision, weapon
   aim, animation phase and physical contacts should remain unchanged.
2. **Split Wraith aiming from firing-path validation.** Retain the analytic aim
   each tick. Avoid the twelve segment tests during a pause that prevents the
   result from affecting firing; retain an immediate fresh test at eligibility.
   Prove identical firing decisions, random draws, aim directions and shot times.
   The current entire arc path costs 1.35 ms/tick; that is an upper bound, not
   a promised saving. The cooldown follow-up places 1.328 ms/tick in positive
   pause calls; the actual removable portion needs an equivalence experiment.
3. **Batch coherent clearance queries.** Share one conservative candidate
   traversal for the five parallel rays (and related directional probes), then
   keep each lane's original nearest-hit arithmetic, ordering and support result.
   Target the 3.25 ms/tick movement-clearance total. Static-world candidate reuse
   is preferable to simply reducing the decision frequency; moving a vehicle
   must not invalidate an unverified stale clearance answer.
4. **Pursue specific solver reuse after the above.** The Banshee has 22 mass
   points but 15 unique authored positions. The previous research identified
   exact repeated integration inputs, with about 31.8% duplicates in its own
   Banshee showcase. Preserve all mass/force contributions and correction-pass
   ordering; reuse only bit-identical query inputs. The current Banshee sweep
   bucket is only 0.288 ms/tick, so this is a smaller opportunity than new LODs
   or Wraith queries. Neither removing mass points nor slowing physics is proposed.

The earlier [collision-cache investigation](OPTIMIZATION.md) reduced factory
misses by 91.7% with 512-entry caches but measured 24.0 FPS versus a 24.1 FPS
baseline. It was not promoted. The current small feature-build bucket gives no
reason to repeat that as the first optimization.

## Live context and limits

| Workload | 1-player diagnostic FPS | 4-player diagnostic FPS |
| --- | ---: | ---: |
| One Ghost plus infantry | 44.40 | 15.97 |
| Four vehicle types plus infantry | 18.04 | 3.40 |

These instrumented captures supplement the preceding 44.47/16.10 and
18.73/3.60 checkpoint figures; they do not replace those lighter-build results.
Different fixtures have different infantry mixes, targets, deaths and views.
Subtracting the two rows does not isolate the cost of three extra hulls.

The diagnosis supports a combined CPU and graphics pass, beginning with the
Wraith/Shade LODs and Wraith firing-query split. A stable 30 FPS result still
requires whole-match profiling and human playtesting after those changes.
