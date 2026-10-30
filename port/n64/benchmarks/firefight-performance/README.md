# Ordinary two-player Firefight performance diagnosis

Read the [performance report](../../FIREFIGHT_PERFORMANCE.md) for findings and
limitations. This evidence supplements, rather than replaces, the
[full 1–4P appraisal](../firefight-limited/README.md).

- Source: `be9924a7ee7b4f6a148050179e9bebec58303309`.
- Private assets: `07daf1cf1821701955c3eba20d1acccf784598d8`.
- Ares v148, NTSC 320×240, 8 MiB, audio enabled, uncapped diagnostic ROM.
- `opening-2-native.log`: ordinary director, QA3 two-player inputs, unmodified
  gameplay source, 75 one-second observations. Drop the first five for FPS.
- `detail-2-native.log`: same scenario, isolated timing-only `game.c` and includes.
  Every `DETAIL` line accumulates exactly 30 simulation ticks. Counters are nested;
  see `results.json` for their interpretation. No healing, forced kills or
  reduced enemy counts are introduced.
- `results.json`: derived summaries; every raw sample remains in the logs. Post-landing tick
  attribution uses ticks 601–2310, including later reinforcements/deaths. This
  window is different from the FPS living-human filter.
- `census.json`: actual model batch loads, collision mesh sizes and seven exact
  CE function-body comparisons. No original meshes or source bodies are embedded.
- `provenance.json`: ROM/log/build-manifest hashes, toolchain/options and original
  versus instrumented source hashes. Full build manifests remain at the recorded
  local artifact paths; inputs are reproducible from the revisions and generator.

The report changes no production code. The diagnostic adds clock reads, wrapper
calls, counters and one log line per 30 ticks. It is not a shipping optimization.
Its 19.39 engaged FPS versus the baseline's 19.37 is a gross perturbation check;
individual sampled frames and event timing are not assumed identical.

## Reproduce

From the source checkout, with the existing private assets and corrected Blood
Gulch render bank available:

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/census.py
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/instrument.py build/firefight-analysis/runtime

build/n64-python/bin/python port/n64/build.py --pve-squad --pve-players 2 --pve-qa 3 --profile --output-dir build/firefight-limited/opening-2 --sdk /Users/jem/dojo/n64-2048/.build/libdragon --tiny3d /Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit --map-bank-override build/pve/ground/bloodgulch.map64
build/n64-python/bin/python port/n64/build.py --pve-squad --pve-players 2 --pve-qa 3 --profile --game-source build/firefight-analysis/runtime/game.c --output-dir build/firefight-limited/detail-2 --sdk /Users/jem/dojo/n64-2048/.build/libdragon --tiny3d /Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit --map-bank-override build/pve/ground/bloodgulch.map64

build/n64-python/bin/python port/n64/benchmarks/firefight-performance/capture.py build/firefight-limited/opening-2/halo-64-render-candidate-profile.z64 build/firefight-limited/ares.bml build/firefight-limited/opening-2-native.log
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/capture.py build/firefight-limited/detail-2/halo-64-render-candidate-profile.z64 build/firefight-limited/ares.bml build/firefight-limited/detail-2-native.log
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/summarize.py build/firefight-limited
```

Run captures sequentially with other emulator workloads stopped. The capture
runner terminates only the emulator subprocess it starts. Existing logs can be
reanalyzed without an emulator:

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-performance/summarize.py port/n64/benchmarks/firefight-performance
```

Do not interpret integer FPS minima as frame-time percentiles, invert sampled
CPU means into FPS, add nested counters, or interpret disabled drain counters as
zero RSP/RDP work. The diagnostic has not isolated later-wave performance or
physical-cartridge timing.
