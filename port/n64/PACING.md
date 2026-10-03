`--paced30` is an opt-in presentation experiment, not a validated performance
claim. The normal release remains unpaced. The option adds `-paced30` to the
ROM name; frozen `--snapshot-tick` builds ignore it.

In four-view mode, completed frames wait in a two-entry FIFO while the third
surface is scanned out. After two completed frames prefill the queue, one frame
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

`--paced30 --paced30-buffers 4` is a separate, unproven acquisition experiment
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

The final-bank quiet Ares runs still miss deadlines:

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
These results justify neither a sustained-30-FPS claim nor a default change.
The separately recorded four-surface RDP validation finishes with zero errors
and warnings; its instrumentation is not a performance measurement.

Four-surface mode tracks submitted and SDK-ready surface ownership separately.
Only an observed VI origin clears ownership. When enabling pacing after an
unpaced interval, it releases held frames in FIFO, snapshots all outstanding
predecessors, and gates new acquisition until those predecessors have appeared.
In-flight callbacks release normally during this drain. Input, audio and the
bounded simulation clock continue running. Fresh pacing cannot start until at
least two retraces after the final observed predecessor flip, including across
VI counter wrap. This handles the state that three surfaces cannot reach:
one front surface, one old SDK-ready surface, and two newly held surfaces.

The quiet VI result includes whole-run held-queue peaks and live free heap,
sampled before teardown closes audio or flushes the held queue. Four-surface
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
