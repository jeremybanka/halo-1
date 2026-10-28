# Firefight performance appraisal — 28 October 2026

This is the diagnosis of the pre-optimization baseline. The subsequent
[shared navigation appraisal](FIREFIGHT_NAVIGATION.md) documents the replacement
of repeated full-map searches and fresh paired 1–4P results.

**The drops have two major causes: expensive simulation spikes in our custom
navigation services, and enemy representations that are much heavier than the
multiplayer models.** The original CE action-selection functions are a small
part of the measured cost. Simplifying models alone will not remove the worst
hitches; reducing the intelligence of the enemies is not the first remedy either.

This report adds an ordinary two-player native opening capture and a separate,
timing-only diagnostic to the [existing Firefight measurements](benchmarks/firefight-limited/README.md).
Gameplay, enemy counts, source assets and production code are unchanged.
[Raw logs, reproducible analysis, source checks and provenance](benchmarks/firefight-performance/README.md)
accompany the report.

## What the two-player demo costs

The new capture uses the demo's ordinary wave director and automated two-player
inputs, with real damage, deaths and respawns. It starts at the beginning of a
match and records 75 one-second observations, discarding the first five.
It is an **uncapped profiling ROM in Ares v148**, NTSC 320×240 with 8 MiB RAM.
The demo uses the paced release build. These are native N64-program measurements
in an emulator, not a new physical-cartridge test or a human playtest.

| Ordinary two-player opening | Mean FPS | One-second range | Observations |
| --- | ---: | ---: | ---: |
| At least one human alive, enemies alive and landed | **19.37** | **4–38** | 52 |
| Both humans alive, enemies alive and landed | **18.48** | 4–30 | 42 |
| Whole retained window, including quiet/dead/arrival periods | 26.10 | 4–59 | 70 |

These are not the earlier crowded two-player Hunter fixture, which measured
11.92 FPS in its living-human/landed-enemy subset. The ordinary opening has no
Hunters. Its performance problems already exist with Elites and Grunts.
The filters do not require every enemy to be visible or firing, and a departing
Spirit may still be present after all passengers have landed.

The coarse CPU counters in the new ordinary opening are:

| Measured section | Mean sampled ms per rendered frame | Scope |
| --- | ---: | --- |
| Simulation | **28.98** | All accumulated simulation ticks, game updates and associated per-tick services |
| Scene preparation | **10.88** | Includes **8.68 ms** preparing NPC/Spirit geometry and poses |
| Drawing/submission | **13.88** | Includes drawing commands, HUD, interleaved audio pumping and possible queue backpressure |

These are averages of the reported frame in each observation, **not a complete
frame-by-frame trace**. They cannot be inverted or summed to reproduce mean FPS.
The simulation row may contain several 30 Hz ticks. Nested counters must not be
added again: the old `ai_us` averages 11.89 ms *inside simulation*, and
`pve_render_us` is *inside preparation*.

One 4-FPS observation at tick 669 reported **188.27 ms simulation**, 22.03 ms
preparation and 24.75 ms submission. Its rolling 120-frame maximum reached
268.61 ms; a later window reached 272.91 ms. This is a substantial hitch, not just
a slightly expensive steady frame. Those maxima are individual rolling-window
observations, not a global percentile calculation.

## AI: what is expensive, and what is actually CE

The port makes perception/action decisions at **5 Hz per landed, living actor**,
with staggered starting times. Movement, turning, attacks and other combat
updates run at **30 Hz**, independently of the number of viewports. Split-screen
adds targets and views; it does not run a separate enemy brain for each camera.
It also raises the live enemy cap: 6/8/10/12 for 1/2/3/4 humans.

The new diagnostic accumulates timings over exactly 30 simulation ticks at a
time. This avoids confusing a slow rendered frame's catch-up work with the cost
of one simulation tick. After the initial squad landing, ticks 601–2310 comprise
1,710 ticks, or 57 simulated seconds. They include later deaths and reinforcements.

| Disjoint game-tick section | Mean ms per 30 Hz tick |
| --- | ---: |
| Enemy update: perception, decisions, navigation, movement and attack control | **7.30** |
| Human controls, movement, weapons, pickups and player separation | **2.95** |
| Projectile update | **1.53** |
| Arrival/wave director | 0.10 |
| Vehicle update | 0.01 |
| Mode/after-tick bookkeeping | 0.03 |
| **Whole game tick, including small unassigned overhead** | **11.94** |

The following are **nested costs**, not additional rows to add to that total:

| Nested service | Mean ms per tick | Interpretation |
| --- | ---: | --- |
| Navigation distance field lookup/rebuild | **3.27** | Spiky; full reachable-map search on cache miss |
| Enemy capsule/world collision | **3.01** | Every active actor tick, including standing support |
| Animated enemy hit detection | **1.31** | Within human weapon/projectile processing; separate from visual animation |
| Enemy perception tests | 0.31 | Distance/FOV checks and world line-of-sight rays |
| CE selector calls and their adapter handlers | **0.071** | Includes grenade/evasion/panic handler work invoked by those selectors |

This instrumented run achieved 19.39 FPS in its engaged subset versus 19.37 for
the baseline. That is a useful perturbation check, not proof of identical frame
scheduling. Timers add overhead and change which frame is sampled. The diagnostic
is used for attribution; the unmodified profiling build supplies the headline FPS.

### Navigation explains the worst spikes

[`pve_path`](pve_nav.inc) builds a reverse breadth-first distance field. That is
potentially a good squad strategy: many enemies can follow one field. The current
implementation makes its expensive case too easy to trigger:

- It has only **one cached goal per human**, while callers pass each actor's own
  last-seen target position. Different memories can replace each other's fields.
  Arrival reachability checks also use these same slots with current player positions.
- A changed goal clears a **33,282-entry** distance array and traverses the entire
  reachable component. The measured component contains **6,464 nodes**.
- Navigation runs during decisions, but can also run from the 30 Hz attack loop
  when an otherwise eligible shot is blocked by facing or a friendly actor.
  Consequently, the old `move_us` counter contains navigation too.

In ticks **631–660**, the diagnostic recorded **21 rebuilds**, **135,744 visited
nodes**, and **563.97 ms in distance-field work**. All game simulation in those
30 ticks took 858.22 ms. The selector calls and their handlers took just **2.44 ms**.
Path time divided by rebuild count is approximately **26.9 ms per rebuild** in
that window; this includes the much smaller cache-hit lookup overhead.

Across ticks 601–2310 there were **207 rebuilds** and **1,338,048 node visits**.
The counts establish excessive full searches. Conflicting remembered goals are
a source-visible explanation, but this capture did not record individual goal
histories, so it does not quantify how many misses were avoidable cache eviction.

A rebuild already consumes most of a 33.33 ms display-frame budget. Several in
one tick can delay presentation, which causes the clock to request extra simulation
ticks, which then adds more work before the next picture. The clock bounds
catch-up at seven ticks, but that still allows large bursts. This is a cost problem
in the current adapter, not evidence that faithful CE decision-making inherently
requires this much CPU.

### Fidelity assessment

**We have source-derived behavior with selected original routines, not a complete
CE AI-engine port.** The distinction matters for both performance and behavior.

| Layer | What is preserved | Boundary |
| --- | --- | --- |
| Species decisions | Grunt, Elite, Jackal and Hunter action-selector bodies | Their inputs and called services are supplied by compact adapters |
| Panic/grenades | Original panic-transition, grenade-consideration and grenade-handling bodies | Throw validation, trajectories, threat detection and execution use local services |
| Tuning and presentation | Source tags for health/shields, difficulty, vision, weapon cadence, accuracy, movement and animation; source sampled poses and damage materials | Sampling, scheduling and the surrounding simulation differ from CE |
| Perception/navigation | Line of sight, awareness, last-seen pursuit, obstacle-aware movement | Nearest-visible-player selection and a two-layer grid replace CE's richer perception, destination and path systems |
| Cover and cooperation | Shield-based retreat/cowering, leader-loss panic, friendly-fire clearance and local spacing | No complete CE firing-position search, cover selection, squad communication or tactical coordination |
| Other behavior | Survival-specific arrivals and search orders | Campaign commands/conversation and several surprise/berserk handlers are absent or explicit no-ops |

The [source census](benchmarks/firefight-performance/census.json) verifies all
**seven extracted function bodies byte-for-byte** against the repository's CE
source. This proves those bodies' provenance; it does not prove end-to-end
behavioral equivalence with the original game. For example, an aware actor's
perception no longer uses the initial facing restriction, and dead-target
retargeting can give it the position of the nearest living player without a fresh
sighting. Those are local policies.

CE itself has a service-timeslice mechanism in
[`actor_get_timeslice`](../../source/ai/actors.c), and
[`actor_destination_update`](../../source/ai/actor_moving.c) gates path refreshes
on that timeslice. Its [path system](../../source/ai/path.c) traverses authored
walkable structure surfaces. Our uniform 5 Hz decisions plus immediate full-grid
rebuilds do not reproduce that scheduling or path representation.

## Enemy models compared with multiplayer models

These are **body-only submissions per visible camera**, measured from the actual
packed batches. A vertex load includes batch duplication and even-count padding;
it is not a count of unique geometric points. Weapons, riders, first-person
models, projectiles and effects are excluded. The Jackal's authored shield geometry
is included in its body model.

| Model | Near / far triangles | Near / far vertex loads | Near / far batches |
| --- | ---: | ---: | ---: |
| Spartan | 328 / 135 | **562 / 250** | 10 / 5 |
| Grunt | 730 / 342 | **1,516 / 784** | 26 / 14 |
| Elite | 572 / 368 | **1,224 / 776** | 21 / 14 |
| Jackal | 757 / 449 | **1,526 / 946** | 26 / 16 |
| Hunter | 2,006 / 2,006 | **3,378 / 3,378** | 58 / 58 |
| Spirit | 2,956 / 2,956 | **4,228 / 4,228** | 77 / 77 |
| Warthog | 318 / 152 | 298 / 170 | 10 / 4 |
| Ghost | 242 / 134 | 244 / 142 | 7 / 4 |
| Scorpion | 388 / 210 | 450 / 282 | 12 / 6 |
| Banshee | 352 / 198 | 256 / 142 | 10 / 5 |

The Grunt, Elite and Jackal use source low/superlow representations. **Hunter
and Spirit use the source `superhigh` representation at both distances**; their
far entries alias the near mesh. Some vehicles also have micro LODs smaller than
the table, and near articulated parts can be culled separately.

A distant Grunt costs **3.1× a distant Spartan** in vertex loads. A Hunter costs
**6× a near Spartan**, **13.5× a far Spartan**, or **11.3× the entire near Warthog**.
Two Hunters alone submit **6,756 loads per camera**. An all-far Elite patrol of
one Elite and four Grunts costs **3,912 loads per camera**, before its guns or the
map. The old 1,500-load map budget is therefore not a budget for the complete
Firefight frame; the actors can exceed it several times over.

Animation also differs. The multiplayer Spartan uses compact resident 8-bit
motion tracks and specialized decode/scatter routines. NPCs stream **16-bit pose
samples from ROM**, interpolate tracks on the CPU, scatter into packed vertices,
and write those buffers back for the RSP. The motion bank totals approximately
2.02 MB. NPC preparation is already shared across viewports for each required
actor/LOD, so four cameras do **not** mean four identical animation decodes.
Different cameras can, however, require both LODs of an actor, and every visible
camera repeats its geometry submission. The current Hunter alias does not prevent
both logical LODs being prepared when separate cameras request near and far;
that is another opportunity to share identical work.

The Spirit currently transfers and interpolates its full door-pose mesh every
visible frame, even at an unchanged door opening. Its hull is mostly rigid, making
that an especially promising representation/cache improvement. NPC visibility is
frustum-based rather than wall/cluster occlusion. Corpses can remain rendered for
15 seconds; the live enemy cap is not necessarily the number of bodies drawn.

This explains why the crowded Hunter fixture spends **24.90 ms preparing NPCs
in two-player**, versus **8.68 ms** in the ordinary opening. That is a comparison
of different encounters, not an isolated Hunter-on/off experiment, so it does not
assign the full difference to Hunters alone.

## Other costs and the limits of the current profiler

- **Movement collision is substantial.** NPC capsules use the existing world
  collision solver every tick. The 3.01 ms above excludes human movement. Visual
  decimation will not directly make this collision mesh or its queries cheaper.
- **Hit detection has bursts of its own.** Enemy broadphase acceptance is followed
  by a linear scan of the animated hit mesh: 158/228/420/502 triangles for
  Grunt/Elite/Jackal/Hunter. There is a pose cache but no per-enemy triangle
  hierarchy. In ticks 1561–1590, projectile processing took 343.63 ms across the
  30 ticks; enemy hit tests across all callers took 234.70 ms and entered loops
  covering 37,920 triangles. These counters overlap and must not be added.
  Existing Spartan hit tests reject groups by animated bounds, while vehicles
  already use hierarchies with selectively updated bounds.
- **Audio is meaningful.** `PHASE audio` averaged **6.10 ms per reported frame**
  in the ordinary two-player capture. Audio pumping can happen during submission
  and waits, so this is not an extra independent 6.10 ms to add to the frame table.
  It is real work to retain in subsequent profiling, especially when a long tick
  leaves several audio buffers needing service.
- **The director is not the sustained bottleneck in this opening.** It averages
  0.10 ms per tick in the detailed combat window, though placement validation can
  still make individual spikes. This does not bound later-wave worst cases.
- **RSP/RDP utilization is not separated here.** The saved `rsp_wait=0` and
  `rdp_wait=0` mean serialized drain measurement was disabled, not idle graphics
  hardware. Submission can contain backpressure; CPU and graphics execute with
  overlap. We cannot honestly assign a GPU-busy percentage from these logs.
- **Memory has headroom, not unlimited space.** The ordinary two-player capture's
  lowest sampled free heap was **1,186,544 bytes**; the existing crowded four-player
  fixture reached **1,092,128 bytes**. This leaves options for bounded caches, but
  not for putting the entire motion bank into RAM without other tradeoffs.

## Recommended order of work

1. **Make navigation shared and bounded.** Cache by actual goal identity rather
   than letting different remembered positions overwrite a single player slot;
   preserve each actor's perception memory. Compact the baked graph to valid
   nodes, retain reusable fields, and service rebuilds under a fixed budget with
   safe previous routes while work is pending. Record goal histories first to
   quantify eviction. This targets measured hitches without changing decisions,
   encounter strength or the intended behavior.
2. **Accelerate collision without changing shapes.** Reuse valid support/contact
   information for movement and add conservative groups/hierarchies to enemy hit
   meshes. Preserve Jackal shield gaps, Hunter weak points, walking paths and all
   damage materials. Reuse the lessons already present in Spartan/vehicle queries.
3. **Give enemies an N64 representation budget.** Prioritize real Hunter and Spirit
   distance LODs, then smaller distant Grunts/Elites/Jackals, assessed from matched
   combat views. Keep the Spirit hull rigid and animate/cache its doors separately.
   Evaluate bounded pose caching and conservative actor visibility before reducing
   visible animation quality. Multiplayer assets show that source-derived models
   can be much cheaper than these initial PvE exports.
4. **Reprofile the complete pipeline.** Repeat ordinary and crowded 1–4P captures,
   retain per-tick counters and hitch statistics, and add separate graphics-drain
   diagnostics. Include audio and queue stalls. A 30-FPS frame has **33.33 ms for
   the complete game**, not 33.33 ms per viewport or per subsystem.

The first substantial improvement should come from avoiding repeated whole-map
navigation searches. Model/animation work is the next major budget problem,
especially for Hunters and the Spirit. Neither requires abandoning the source
behavior standard; the most expensive measured services are exactly where our
implementation currently differs from CE's richer, scheduled systems.
