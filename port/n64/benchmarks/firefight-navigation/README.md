# Shared, budgeted Firefight navigation — 28 October 2026

Read [FIREFIGHT_NAVIGATION.md](../../FIREFIGHT_NAVIGATION.md) for the appraisal.
This experiment changes route services, not enemy models or combat tuning.

## Evidence and matching

- Baseline: `5b652475c798c4e7b0f36e4be000a4cd1f35d38f`.
- Measured candidate: `42f2b8da2afd45ee3f79f61e31b0380d0aa08117`.
- Private assets: `07daf1cf1821701955c3eba20d1acccf784598d8`, unchanged.
- Sixteen raw `*-native.log` captures: baseline/candidate × ordinary/crowded ×
  1–4 players. Ares v148, NTSC 320×240, Expansion Pak, audio enabled; uncapped
  native N64 profiling programs. These are not physical-cartridge measurements.
- `opening`: QA3 ordinary match director and deterministic player inputs, 75
  one-second observations. `perf`: QA4 cap-sized mixed fight including Hunters,
  45 observations, reset every twenty simulated seconds. Both use real damage,
  deaths and respawns. The healing/forced-kill lifecycle fixture is excluded.
- Discard the first five observations. The headline subset requires at least
  one living human, a living enemy and no enemies still arriving. Also report
  whole-window and all-humans-alive results. These conditions do not guarantee
  every enemy is visible, and a departing Spirit may remain on screen.
- `results.json`: all derived summaries. `provenance.json`: ROM, raw-log and
  build-manifest hashes, toolchain, source revisions and input comparisons.
  Build options match except output directories. The private source assets and
  corrected-ground Blood Gulch render bank match exactly. Runtime input changes
  are limited to six navigation/scheduling/telemetry files.
- `memory.json`: navigation BSS symbol sizes from the linked MIPS executables.
- `host-navigation.log`, `host-firefight.log`, `host-pve.log`: ASan/UBSan results.
  `census.json`: unchanged models and seven exact CE source-body comparisons.

Only one emulator capture runs at a time. The four baseline openings were
captured first. The final candidate two-player opening was checked before the
remaining candidate openings and interleaved baseline/candidate stress captures.
The first cache-layout prototype was superseded, and is not mixed into these
headline results. `layout-before-opening-2-native.log` and
`layout-provenance.json` archive its two-player comparison; its remaining local
artifacts stay under `build/firefight-navigation/first-prototype`.

Scheduling changes can alter encounter trajectories, deaths and visible models.
These are matched scenarios and inputs, not identical frame replays or pixel
equivalence tests. Native path service counters show the direct work reduction;
FPS also reflects whatever combat the resulting actors produce.

## Reproduce

Use a separate baseline worktree at the revision above, with private assets,
the existing Python environment, and the same build input directories available.
The original research checkout must not be reset or cleaned. The corrected-ground
render bank is generated as described in [PVE_SQUAD.md](../../PVE_SQUAD.md).

```sh
build/n64-python/bin/python port/n64/test_maps.py --navigation --output-dir build/firefight-navigation/host-navigation
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/firefight-navigation/host-firefight
build/n64-python/bin/python port/n64/test_maps.py --pve --output-dir build/firefight-navigation/host-pve
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/census.py

build/n64-python/bin/python port/n64/benchmarks/firefight-navigation/run_matrix.py build --baseline-root build/firefight-navigation/baseline-source --output build/firefight-navigation/matrix
build/n64-python/bin/python port/n64/benchmarks/firefight-navigation/run_matrix.py capture --baseline-root build/firefight-navigation/baseline-source --output build/firefight-navigation/matrix --settings build/firefight-limited/ares.bml
build/n64-python/bin/python port/n64/benchmarks/firefight-navigation/collect.py build/firefight-navigation/matrix
```

The matrix runner accepts SDK/Tiny3D paths, version, fixture and player filters.
`--resume` keeps complete existing captures; use it only while those ROMs are
unchanged. It must not reuse a log after rebuilding a different candidate.
Each capture is bounded to 240 wall-clock seconds and terminates only the Ares
process it owns. Build manifests/ROMs stay local because they contain private
assets or local paths. Their hashes and input differences are checked in.

Reanalyze checked-in logs without rebuilding ROMs:

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-navigation/collect.py port/n64/benchmarks/firefight-navigation --logs-only --output build/firefight-navigation/reanalysis
```

The default collector additionally validates matching ROM manifests; that mode
requires the original local matrix directory (or equivalent rebuilt inputs).

## Counter interpretation

`NAV` records cumulative counters since encounter initialization. `us` is service
time in the sampled rendered frame, which can contain several simulation ticks.
`max_us` is the largest service invocation seen since reset. `max_work` must be
at most **256**; a work step is a node expansion, a path-distance commitment or
the transition into commitment. This is an algorithmic work budget, not a hard
microsecond deadline. Heap work and cache misses have variable cost.
These service timers exclude request admission, goal-cache allocation and the
immediate cached-waypoint application inside `pve_destination`; those remain in
the overall simulation counters. Up to seven catch-up simulation ticks can run
before one rendered frame, so the step budget is not a per-rendered-frame limit.

`requests` counts deferred actor refreshes; `ready` counts immediately cached
refreshes. `shared` counts reuse of a goal cache, including repeated use by the
same actor. It is not a count of cross-actor cache hits. `searches` counts point
queries used to fill missing exact distances; an actor refresh may need its own
node and eight neighbors. `expanded` and `committed` record actual graph work.
`max_wait` is completed-request latency in 30 Hz simulation ticks.

The collector computes service cost and request latency from adjacent monotonic
counter intervals, excluding intervals crossing stress resets. It reports the
number of measured ticks, so this is not confused with a full-encounter trace.
Maxima in the stress logs can miss activity after the last observation before a
reset. Pending/cancelled requests are not in completed-request latency means.

CPU simulation/preparation/submission are sampled rendered-frame counters.
Do not add nested AI or navigation timings again, invert their means into FPS,
or treat disabled RSP/RDP drain counters as zero GPU work. Reported rolling
120-frame maxima are neither global percentiles nor instantaneous FPS minima.
