`--paced30` enables four-view presentation on every second retrace. For the
current build, use `--paced30 --paced30-buffers 5`: its production replay
has zero missed deadlines. In the preceding visibility/weapon-display revision,
four surfaces offered lower measured input-to-display latency with one
vehicle-phase deadline miss. That four-surface comparison was not repeated
after the controls/menu update.
The ordinary no-option build remains unpaced. The option adds `-paced30` to the ROM name;
frozen `--snapshot-tick` builds ignore it. This is an emulator-tested profile,
not a physical-console performance guarantee.

The final controls/menu/scoreboard revision was remeasured with five surfaces in Ares v148,
Metal, NTSC and 4 MiB. In 75.017 seconds after one second of warmup, all 2,244
fresh displayed poses arrive two retraces apart: 1,078 combat and 1,166 vehicle
poses. There are zero missed deadlines, duplicate displayed poses or dropped
simulation ticks; six intermediate poses are skipped. P95 and maximum are
33.4 ms, with the NTSC rate displayed as 29.9 FPS. Input sample to VI is
130/135 ms mean/maximum, ready to VI is 98/116 ms, and free heap is 641 KiB.
Held/SDK-ready/submitted peaks remain 4/1/4. The original menu asset bank and
working storage remain resident during this menu-closed gameplay measurement.
The local proof is `build/n64/controls-menu-scores-qa/timing-result.json`, with the
captured result page and exact ROM/source hashes. This is a fresh measurement
of the same scripted replay, not a claim about every possible match.

The final Xbox C-button/scoreboard revision also measures the demanding case
of all four held-R score panels visible during the entire replay. This run has
2,243 fresh poses and **one missed vehicle-phase deadline**: 2,242 intervals
are two retraces and one is four retraces (66.8 ms). Combat has 1,078 poses
with no misses; vehicles have 1,165 poses with the one miss. There are no
repeated displayed poses or dropped simulation ticks, and seven intermediate
poses are skipped. Input sample to VI is 129/135 ms mean/maximum; ready to VI
is 96/115 ms, with 640 KiB free heap and held/ready/submitted peaks of 4/1/4.
This stress case therefore does **not** meet an uninterrupted nominal-30-Hz
floor. The separate evidence is
`build/n64/controls-menu-scores-qa/scores-timing-result.json`.

The score renderer reuses permanent panel command blocks, retains CPU text
until scores change, and caches the exact fixed-point glyph rectangles.
It avoids repeated formatting, layout and scale divisions without changing
the font pixels or submitted rectangle words. The original uncached score
candidate had four vehicle deadline misses in the same replay; the optimized
candidate reduces that to one. Normal gameplay timing is measured separately.

In the three-surface four-view mode, completed frames wait in a two-entry FIFO
while the third surface is scanned out. After two completed frames prefill the queue, one frame
is released every second VI retrace. An empty deadline repeats the displayed
frame and increments the miss counter; it never triggers consecutive-retrace
catch-up. This targets nominal 30 Hz on NTSC/MPAL and rejects PAL. Actual timing
comes from observed retraces, not a hard-coded 33,333-microsecond deadline.

The prefill trades additional input-to-display latency for tolerance of an
isolated slow frame. It cannot guarantee deadlines under sustained or clustered
overload. Switching to one/two views drains held completed surfaces in FIFO and
returns to immediate completion-driven presentation. When re-entering four
views, older ready surfaces may drain before the new two-frame prefill starts.
Three-surface ownership prevents two held surfaces coexisting with an older
ready surface, so the first paced release cannot overtake that transition.

`--paced30 --paced30-buffers 4` selects four display surfaces
with the `-paced30-buffers4` filename suffix. The default remains three surfaces;
an explicit buffer option requires `--paced30`, and snapshots ignore both.
The fourth 320×240 RGBA16 surface costs 153,600 pixel bytes plus surface metadata
and allocator overhead. It permits three submitted frames behind the displayed
surface while retaining the same **two completed frames** for startup prefill
and the same two fenced geometry slots. Extra capacity may reduce acquisition
bubbles, but can also retain a longer queue and increase input-to-display
latency. It does not reduce GPU work or establish a frame-rate guarantee.

`--paced30 --paced30-buffers 5` extends that experiment to five surfaces,
using the `-paced30-buffers5` suffix. It adds another 153,600 pixel bytes while
retaining the two-frame prefill and two geometry slots. Buffer counts above
five are rejected. The same ownership tracker handles four and five surfaces;
three-surface and unpaced target assembly remain unchanged by this extension.

Before adding the tiny-model layer, quiet Ares runs still missed deadlines:

| Run | Missed two-VI deadlines | Skipped poses | Input sample → VI mean/max | Live free heap |
| --- | ---: | ---: | ---: | ---: |
| Three surfaces, exact pose cache | 14 | 20 | 68 / 102 ms | not recorded |
| Four surfaces, deferred animation | 6 | 12 | 100 / 135 ms | 923 KiB |
| Five surfaces, same deferred renderer | 3 | 9 | 129 / 135 ms | 773 KiB |

Each measures 75 seconds after one second of warmup on ares v148, Metal,
NTSC and 4 MiB. All have zero repeated displayed poses and zero dropped
simulation ticks. The remaining four/five-surface misses are in the vehicle
phase and produce four-VI/66.8 ms gaps. Four-view combat holds two-VI cadence.
The three-surface checkpoint predates deferred animation; four/five are a
matched source comparison. Exact ROM/source hashes and phase metrics are in
`runtime-cache-quiet-results.json`, `runtime-lazy-four-results.json` and
`runtime-five-quiet-results.json` under the local performance audit.
These earlier results did not meet the nominal-30-FPS target.
The separately recorded four-surface RDP validation finishes with zero errors
and warnings; its instrumentation is not a performance measurement.

Before the visibility and weapon-display changes, the tiny-model build met
the nominal-30-Hz cadence in the complete
75.017-second quiet ares replay with four surfaces. All **2,244 fresh poses**
arrive exactly two retraces apart: 1,078 combat poses and 1,166 vehicle poses,
with **zero missed deadlines, duplicate displayed poses or dropped simulation
ticks**. The observer reports 33.4 ms p95 and maximum, and truncates the NTSC
rate to 29.9 FPS. Six intermediate simulated poses were skipped; this is
separate from dropped ticks and repeats. Input-sample-to-VI latency is
100 ms mean / 102 ms maximum; ready-to-VI is 69 / 84 ms. Live free heap is
906 KiB, with held/SDK-ready/submitted peaks of 3/1/3.

The same model recipe's private three-surface comparison has one vehicle
deadline miss and 67 / 101 ms input-sample-to-VI latency. Four surfaces were
therefore the recommended profile for that revision. Its original 59-entry bank remained
unchanged; twelve tiny meshes are selected only for already-far pickups and
vehicles below the conservative four-view pixel threshold. Full scene geometry,
audio, simulation and HUD remain enabled. See [MICRO_LODS.md](MICRO_LODS.md).
That revision's result, exact ROM/source/bank hashes and captured page are in
`performance-audit/runtime-micro-production-four-results.json`; private
candidate results remain separately labeled. This measurement covers the
scripted replay, not every possible match.

After the title-safe aiming projection, conservative edge submission,
Scorpion cannon repair and on-weapon ammunition displays, the preceding
four-surface build presents 2,243 fresh poses in 75.017 seconds. There is one
vehicle-phase missed deadline: 2,242 intervals are two VI retraces and one is
four retraces (66.8 ms). The exact-output CPU/command-cache refinements preserve
this cadence result. Its displayed p95 is still 33.4 ms; p95 alone does not
establish an every-two-VI guarantee. See
`visibility-weapon-qa/timing-four-result.json` for the ROM/source hashes.

The **production five-surface profile** using the same renderer and assets has
2,244 fresh poses, all exactly two VI retraces apart: 1,079 combat and 1,165
vehicle poses. It has zero missed deadlines, duplicate displayed poses or
dropped simulation ticks, and six skipped intermediate poses. Displayed p95
and maximum are 33.4 ms. Input-sample-to-VI latency increases from the matched
four-surface run's 100/118 ms mean/maximum to **127/135 ms**; ready-to-VI is
98/115 ms. Live free heap is 718 KiB, with held/SDK-ready/submitted peaks 4/1/4.
The extra surface costs 150 KiB and retains a longer presentation queue; this
does not reduce scene rendering work. Production evidence is
`visibility-weapon-qa/timing-result.json`, its captured `timing-result.png`,
and frozen `timing-builds.json`. The quiet ROM's SHA-256 is
`eee71ec9162d92d6d74295d50534971954379718f90239f09088194c8b74cd23`.
The video lasts 106.017 seconds including lead-in and result display;
the measured replay window is 75.017 seconds after one second of warmup.

The earlier **private five-surface candidate** independently produced the same
displayed counters. Its separate ROM/source/object proof remains at
`visibility-weapon-qa/quiet5/result.json` and `quiet5/provenance.json`; it is not
substituted for the production measurement. Four surfaces remain available
when the measured 27 ms lower mean sample-to-VI latency is preferable to the
five-surface run's uninterrupted two-retrace cadence. RDP validation is a
separate diagnostic and does not establish these timing results.

These are emulator measurements. The official ares v148 RDP bridge submits
commands to paraLLEl-RDP without charging emulated CPU time for physical pixel,
blending, antialiasing, depth or framebuffer-memory work. Waiting for the host
GPU at SyncFull does not add those omitted costs to CPU Count. RSP execution
and DMA do advance emulated clocks. Consequently, the VI measurements can
compare command/CPU/RSP workload in ares, but even a zero-miss run cannot
certify a physical N64 frame budget. The DPC busy flags in a diagnostic trace
also do not isolate a hardware fill-rate bottleneck. See the
[v148 RDP integration](https://github.com/ares-emulator/ares/blob/v148/ares/n64/vulkan/vulkan.cpp)
and local `performance-audit/ares-v148-timing-review/` source audit. The installed
app reports v148; a reproducible binary match to that source tag was not made.

Four- and five-surface modes track submitted and SDK-ready surface ownership separately.
Only an observed VI origin clears ownership. When enabling pacing after an
unpaced interval, it releases held frames in FIFO, snapshots all outstanding
predecessors, and gates new acquisition until those predecessors have appeared.
In-flight callbacks release normally during this drain. Input, audio and the
bounded simulation clock continue running. Fresh pacing cannot start until at
least two retraces after the final observed predecessor flip, including across
VI counter wrap. This handles the state that three surfaces cannot reach:
one front surface, one old SDK-ready surface, and two newly held surfaces.

The quiet VI result includes whole-run held-queue peaks and live free heap,
sampled before teardown closes audio or flushes the held queue. Four/five-surface
results also show SDK-ready peak (`R`) and submitted-but-not-presented peak
(`S`, excluding an acquired surface that has not yet been submitted). These
peaks include warmup; they require only bounded integer updates, with no extra
per-frame timer reads. Compare sample-to-VI and ready-to-VI latency alongside
missed deadlines before accepting any buffering benefit.

The acquisition gate waits for a new 30 Hz simulation pose before locking a
display surface. During waits it pumps audio and polls/latches input edges at
roughly 2 ms intervals. Paused menus retain a wall-time redraw permit. Simulation
catch-up keeps the existing seven-tick per-render limit across the entire wait;
excess elapsed ticks are counted and the clock remainder is discarded on
overflow. This matches the existing local clock's overload policy. `DROP` is
that cumulative overload count, including warmup. `POSE SKIP` separately counts
intermediate simulated poses that were not presented. The initial zero-tick
frame is permitted for startup and precedes the measurement warmup.

All benchmark builds, paced or unpaced, now observe VI origin after libdragon's
display callback. The observer uses each surface's monotonic simulated tick ID:
buffer swaps that repeat the same simulation pose are counted separately. It
records a third independent one-second-warmup/75-second window without changing
the existing CPU-acquisition or RDP-completion calculations. The final VI page
reports fresh-pose cadence, one/two/longer retrace gaps, empty scheduled deadlines
for paced mode, and sample-to-VI/ready-to-VI latency. CPU sample timestamps mark
the input-poll/acquisition boundary; they are not physical button-to-photon
measurements. VI origin selection is also distinct from scanline photon timing.
Each pipeline stage's window begins when that stage starts, so their frame sets
are related but are not identical. RDP's existing `>33.33 ms` statistic is kept
for comparison; the VI page uses retrace counts to avoid nominal-refresh rounding
artifacts.

The VI observer is registered before `display_init`; the paced release handler
is registered afterward. This produces release → SDK swap → observation with
the installed libdragon's prepended callback list. Interrupt callbacks perform
bounded integer bookkeeping only, without allocation, sorting, printing or
waiting. Statistics publish once and stop changing before main-thread sorting.
Result-screen teardown drains RSP callbacks and returns every held surface to
ordinary FIFO presentation before unregistering the pacing handler.

```sh
python3 port/n64/build.py --benchmark
python3 port/n64/build.py --benchmark --paced30
python3 port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 4
python3 port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
cc -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Iport/n64 port/n64/test_render_pacing.c port/n64/blam/runtime.c -lm \
  -o build/n64/test_render_pacing
build/n64/test_render_pacing
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Iport/n64 port/n64/test_pacing_fifo.c port/n64/blam/runtime.c -lm \
  -o build/n64/test_pacing_fifo
build/n64/test_pacing_fifo
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -DBG_PACED30_BUFFERS=4 -Iport/n64 port/n64/test_pacing_fifo.c \
  port/n64/blam/runtime.c -lm -o build/n64/test_pacing_fifo4
build/n64/test_pacing_fifo4
python3 port/n64/test_paced_acquire.py
```

Portable tests cover prefill, FIFO ownership, missed deadlines, VI wrap,
duplicates, mode drain, fresh-pose/latency statistics and publication. A test
with an independent three/four/five-surface SDK model runs 64 schedules per capacity with variable
serial GPU delays, long stalls and mode changes while surfaces are still ready
or in flight. It verifies that every acquired surface is released and presented
exactly once, in order. A test
compiled from the actual acquisition function exercises input edges, a 350 ms
display stall, paused menus, resume and view-count changes. These checks do not
establish target performance. Ares validation and both unpaced/paced VI reports
are required before considering any default change. The immutable pre-experiment
main/build sources are under `build/n64/performance-audit/paced30/`.
