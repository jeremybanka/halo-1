# Shared, budgeted Firefight navigation — appraisal

**The repeated full-map rebuilds are removed from the combat loop.** The
prototype retains the existing walkable graph, exact shortest-distance rule,
retreat/spacing choices, perception memories and source-derived combat behavior.
It replaces synchronous floods with shared goal caches and scheduled searches.

This report compares fresh baseline and prototype runs of the same ordinary and
crowded 1–4 player fixtures. [Raw evidence and reproduction instructions](benchmarks/firefight-navigation/README.md)
include all sixteen native logs, build/input hashes and host validation. The
earlier [cost diagnosis](FIREFIGHT_PERFORMANCE.md) explains why this service was
the first target. Geometry, collision meshes, enemy caps and difficulty are
unchanged. Stop here for appraisal before pursuing another optimization.

## Performance

The navigation service is much cheaper, but **this is not an across-the-board
Firefight FPS win**. Ordinary two- and three-player play improve substantially;
the four-player opening regresses, and the crowded Hunter fixture does not
improve. That mixed result is the appraisal, not a reason to omit any case.

Mean FPS below uses the living-human/landed-enemy subset. Parentheses are the
range of one-second FPS readings, not instantaneous frame-time percentiles.

| Players | Ordinary baseline → candidate | Crowded baseline → candidate |
| --- | --- | --- |
| 1 | **38.42 → 38.42** (3–49 → 22–45) | **19.79 → 19.58** (5–24 → 5–24) |
| 2 | **19.24 → 24.45** (4–36 → 16–43) | **11.42 → 11.09** (2–20 → 2–20) |
| 3 | **8.89 → 24.59** (3–20 → 10–33) | **6.52 → 5.95** (2–12 → 2–10) |
| 4 | **8.75 → 6.28** (2–22 → 3–12) | **4.24 → 4.12** (1–8 → 1–8) |

The all-humans-alive opening filter confirms the direction of these results:
**18.39 → 24.40** FPS for two players, **8.49 → 24.62** for three, and
**8.75 → 6.26** for four. The solo mean is unchanged, but its low reading rises
from 3 to 22 FPS. The maximum reported rolling frame time falls from
**324 → 79 ms** solo and **282 → 86 ms** with two players. Four players instead
reach **756 ms versus 446 ms** in the baseline, so the worst hitch is not fixed.

Sampled opening CPU time, in milliseconds per rendered frame:

| Players | Simulation before → after | Preparation before → after | Submission before → after |
| --- | ---: | ---: | ---: |
| 1 | 11.82 → 3.17 | 8.25 → 9.18 | 5.47 → 5.13 |
| 2 | 26.57 → 9.22 | 11.00 → 9.97 | 13.30 → 11.94 |
| 3 | 67.58 → 14.82 | 13.77 → 7.49 | 23.95 → 17.04 |
| 4 | 98.00 → 72.48 | 10.67 → 18.39 | 30.31 → 38.56 |

Four-player opening submission rises from **29,920 to 49,081 vertex loads**
per sampled frame, and NPC preparation rises from **7.72 to 14.76 ms**. The
combat subset averages 7.92 versus 8.98 living enemies. The build retains the
same models and cap; the different refresh schedule changes the combat
trajectory and what is visible. These counters support a heavier-scene
explanation, but do not isolate every cause of the regression. In particular,
the single worst hitch still needs attribution. Do not dismiss the regression
as noise or claim that all of the two-/three-player improvement is navigation
alone: those scenes also diverge.

The crowded four-player run still spends about **125 ms in simulation, 37 ms
in preparation and 47 ms in submission** in the sampled frames. Navigation
service averages only **0.072 ms per simulation tick** in its measured continuous
intervals. Enemy collision/hit processing, pose/mesh preparation and rendering
remain expensive; the earlier diagnosis identifies those services, but this
experiment does not newly separate each of their individual costs.

The navigation counters establish the targeted change independently of FPS:

| Players | Opening service mean ms/tick | Largest service call, ms | Longest completed refresh, ticks |
| --- | ---: | ---: | ---: |
| 1 | 0.055 | 4.376 | 1 |
| 2 | 0.235 | 10.685 | 8 |
| 3 | 0.158 | 9.310 | 3 |
| 4 | 0.161 | 10.789 | 7 |

Every native case respects the 256-step limit. Mean completed cold-refresh
latency in the opening is **1.00–1.43 ticks**; the largest observed completion
delay is eight ticks, about **0.27 simulated seconds**. Immediate cache hits
do not wait for the queue. The two-player opening expands **11,642 nodes over
the whole capture**. For scale, the old diagnostic expanded **135,744 in one
bad simulated second**; these are different windows and trajectories, not a
matched per-query speedup ratio.

The smallest sampled free heap is **603,696 bytes** in the four-player opening.
The appropriate conclusion is to keep this as a measured navigation prototype
for appraisal, not to declare four-player Firefight solved. A fixed-state
render/combat replay would help separate navigation scheduling changes from
scene cost before interpreting another FPS comparison.


## What changed, and what comes from CE

The old adapter had one reverse distance field per human. Each actor passed its
own remembered target location, so actors chasing the same human could replace
each other's field. Arrival checks also reused those slots. A changed goal
cleared 33,282 entries and traversed the entire reachable component—6,464 nodes
in the measured main region. Several searches could execute synchronously in
one simulation tick.

The original source provides two useful patterns:

- [`actor_get_timeslice`](../../source/ai/actors.c) accumulates service age and
  selects expensive service work separately from ordinary actor updates.
  [`actor_destination_update`](../../source/ai/actor_moving.c) gates path refresh
  on that timeslice while continuing destination progress checks.
- [`path.c`](../../source/ai/path.c) uses a cost-ordered heap and a remaining-cost
  estimate to direct traversal toward a destination. It does not rebuild a
  whole-map field for every actor's new goal.

The N64 implementation applies those principles to the existing grid:

1. **Separate immutable reachability from pursuit.** Connected-region labels are
   computed once at map load. Arrival validation compares two labels and never
   starts a pursuit search or invalidates an actor cache.
2. **Share results by the actual remembered goal.** Sixteen goal caches retain
   proven exact route distances. Identical goal nodes share work across actors
   and targets. Different memories of one human coexist. Pending requests pin
   their caches; inactive entries are replaced by least recent use.
3. **Search only for missing distances.** A heap-based A* query stops at a proven
   cached route suffix. Eight landmark distance tables, computed once during
   loading, supply lower bounds that guide searches around canyon detours.
   These landmarks are an N64 adaptation, not a claimed copy of CE code.
4. **Service a shared queue within a work budget.** One incremental search state
   is shared by up to twelve pending actors. Round-robin selection occurs between
   point queries. At most **256 search/commit steps per 30 Hz simulation tick**
   are serviced. Existing actor decisions, movement, attacks and perception run
   on their previous schedules. Heap state and landmark data are packed for
   locality on the native CPU.

Only exact distances are committed. To preserve pursuit **and retreat**, a
refresh obtains the actor node's distance and all linked neighbor distances,
then uses the original neighbor order, strict comparison and dynamic friendly
spacing penalty. A closest-looking partial path is not treated as a valid answer.

The eight landmark floods and component labeling occur once at loading, not
once per actor or moving goal. Runtime field allocation still clears a bounded
16 KiB distance array; it does not traverse the map. Search generation stamps
avoid clearing all search state for each point query. Their rare 16-bit wrap
performs a metadata clear. Thus 256 is a bound on traversal/commit steps, not
on every instruction or microsecond in the navigation system.

## Behavior preservation and timing boundary

For a fixed actor position, remembered goal, action and friend positions, the
new completed refresh selects the **same neighbor as the original full flood**.
The graph's two layers, heights, connectivity, capsule clearance and unit edge
costs are unchanged. Cache reuse does not substitute a live human position for
an actor's last sighting or share awareness between enemies.

The intentional difference is asynchronous refresh timing. An actor retains its
previous certified waypoint while waiting; a new actor starts at its own position.
Moving target memory does not continually cancel a useful in-flight refresh.
The next refresh uses the latest memory. Death, slot-generation changes and
target changes invalidate requests; changing actor position updates the requested
origin. This can alter encounter trajectories and kill timing. It is not a claim
of frame-for-frame or pixel-identical gameplay.

The seven extracted original CE selector/panic/grenade bodies still match the
source byte-for-byte. Enemy health, shields, weapon cadence, accuracy, damage,
panic, grenade rules, hit materials, movement collision and formation tuning
are unchanged. This remains a bounded N64 navigation adapter, not the original
CE navigation mesh, cover planner or full AI engine.

## Validation

- Independent breadth-first oracle: **240** pursuit/retreat/cower choices with
  friendly spacing, **17,567** cached exact distances, component reachability,
  reciprocal edges and landmark lower bounds. All passed under ASan/UBSan.
- Twelve actors across four targets sharing one goal: one cache, maximum
  completion **6 ticks**. Twelve distinct remembered goals coexist without
  per-human cache replacement. Twelve simultaneous distinct long routes finish
  within **19 ticks** in the host fixture; random isolated cases peak at 15.
- Moving-memory refresh, slot-generation/target/death cancellation, epoch wrap,
  restart and the 256-step invariant passed.
- Full Firefight sets for 1–4 players, every formation and both arrival routes,
  reserves, scoring, bonus/restart and PvP return passed. Existing squad tests
  passed two minutes per player count, source-selector/leader-loss panic checks,
  timed melee, ordnance and drops.
- All sixteen native captures completed without an assertion. All eight paired
  manifests have identical build options except output directories, identical
  private asset revisions and render-bank hashes, and only the six expected
  navigation/scheduling/telemetry runtime input changes.

The host worst case of 19 ticks is about **0.63 simulated seconds**. It deliberately
queues twelve independent cold routes at once; it is a latency boundary to
appraise, not evidence of broken distance results. Native completed-request
latencies are reported separately. Tests do not replace a human playtest of
responsiveness in every tactical situation.

## Memory and measurement limits

Navigation-related linked BSS grows from **532,528 to 856,616 bytes**, including
new telemetry: **324,088 bytes / 316.5 KiB additional RAM**. The largest additions
are landmark distances, the shared search workspace and dense-node indexing.
This deliberately spends Expansion Pak memory to avoid repeated CPU work.
`memory.json` contains the actual linked symbol sizes, rather than an estimate
from C array declarations.

The measured source is `42f2b8da`; the baseline is `5b652475`. The final
documentation commit also corrects a comment about contiguous landmark storage;
it makes no executable change. Assets remain at `07daf1cf`. A paced release
ROM is built for manual appraisal; headline results use uncapped profiling ROMs.

An intermediate prototype (`8d02cdd8`) used separated search arrays. In its
two-player opening, the largest navigation service call was 26.316 ms and
cumulative service cost was 1,209,168 µs through tick 2289. Packing the search
records and transposing landmark storage reduced these to **10.685 ms** and
**531,139 µs** through tick 2284, respectively. The algorithms and host oracle
results were unchanged. The slightly different ending tick means this is a
closely matched layout experiment, not an identical instruction replay.

FPS comes from one-second native observations in Ares v148, NTSC 320×240, 8 MiB.
It is not a physical SummerCart64 measurement. Each case has one fresh capture;
small mean differences should not be treated as statistically established wins.
Different trajectories can change the number of alive/visible actors and filter
membership, particularly in three- and four-player combat. The wider FPS range,
whole-window results and CPU counters remain available in `results.json`.

Simulation/preparation/submission counters sample rendered frames; simulation
can include several catch-up ticks. Their means are not a frame-by-frame trace
and must not be inverted into FPS or added to nested navigation timings. RSP/RDP
drain counters are disabled in these ROMs, so this experiment does not measure
GPU occupancy. The maximum reported rolling frame time is not a global p95.
