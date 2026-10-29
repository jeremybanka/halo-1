# Crunchy Covenant appraisal

See [the report](../../COVENANT_CRUNCH.md). This follows source commit
`373e6d38970c261342a3386278595ea34d28516b`, using the existing Hunter/Spirit bank
as its near/far baseline. Both measured versions contain the same final
three-tier bank; only the `--pve-crunch-baseline` control differs.

## Scope and evidence

- `results.json`, `provenance.json` and the public `*-native.log` files: paired
  ordinary/crowded 1–4 player captures, source/header/input hashes, ROM hashes,
  bank hashes, settings, toolchain and exact options. Five warmup observations
  are discarded. Ordinary runs contain 75 observations; crowded runs 45.
- `gpu/`: a separate serialized four-player crowded pair. Queue drains describe
  remaining outstanding work, not independent whole-chip utilization. Its FPS
  is excluded from the headline matrix.
- `pixel-checks.json`: native model pose states and full RGBA16 differences.
  The 30 original near/Spirit controls match exactly; 22 coarse-tier frames
  are intentional visual changes. Four matched cameras per frame.
- `census.json`: fixed combat state, camera rectangles/positions, per-actor LOD,
  species, clip/time, health, vertex loads and native omission differences.
  Crowded ticks 1 and 60 have all four humans alive. Tick 180 is a dead-party
  camera control; delivery tick 300 inspects an authored dropship arrival.
- `silhouette-summary.json`, `silhouette-audit.json`, `asset-checks.json` and host
  logs: animation/bounds/pose ownership checks and CPU silhouette comparisons.
- `checks-provenance.json`: exact photo/census/graphics/lifecycle ROM and native
  log provenance. Private images and raw framebuffer logs are kept only in the
  private assets repository.

The live averages report samples with at least one living human and landed
hostiles. `all_humans_and_landed_enemies` separately reports the fully living
party. Timing changes can alter the observation window; a matching input script
is not a claim of identical sampled live combat states. Fixed-tick photos/census
are the controlled state comparison. Simulation remains 30 Hz; per-rendered-frame
simulation counters can include several catch-up ticks. CPU phase counters are
nested/overlapping and must not be summed or inverted into FPS.

## Reproduce

Use the owned private assets and corrected Blood Gulch render bank. Runner SDK
and Tiny3D defaults describe this workstation and can be overridden for the
performance matrix. Run from the repository root with its Python environment:

```sh
build/n64-python/bin/python port/n64/benchmarks/covenant-crunch/run_matrix.py build --output build/covenant-crunch/perf --model-bank halo64-assets/assets/covenant-crunch/bank
build/n64-python/bin/python port/n64/benchmarks/covenant-crunch/run_matrix.py capture --output build/covenant-crunch/perf --model-bank halo64-assets/assets/covenant-crunch/bank --settings ARES_SETTINGS
build/n64-python/bin/python port/n64/benchmarks/covenant-crunch/collect.py build/covenant-crunch/perf --output RESULTS
```

The check/extras builders use `build/covenant-crunch/bank`; copy the archived bank
there first. `build_checks.py` builds the fixed combat route and category-timing
controls. `build_extras.py` builds the 52-frame model pair, validated four-player
menu lifecycle and controller-playable release candidate. `capture_all.py`
serializes live/GPU/census/lifecycle captures, owning each Ares subprocess and
terminating only that instance. Capture the model pair with the existing
`benchmarks/covenant-models/capture.py` script. The raw pixel logs are private.

The GPU matrix uses `run_matrix.py` with `--gpu --kinds perf --players 4`, then
`collect.py CAPTURE --gpu --output RESULTS/gpu`. For census decoding use
`benchmarks/firefight-drawing/collect.py CAPTURE/checks CAPTURE/checks/photos`.
The new collector adjusts reported NPC gun loads to the actually selected mesh;
original-bank diagnostics retain their previous interpretation.

`compare.py CAPTURE LOCAL_VIEWER` creates side-by-side, blink and difference ×4
filters, with native combat images and enlarged model inspections. It checks
pose/camera parity and near/ship pixel equality before publishing the viewer.
Silhouette sheets show old far, new coarse, and lost/added silhouette pixels.
No omission mask is used as a runtime culling rule.

For a controller-playable build add `--firefight --preset release --pve-crunch
--pve-model-bank halo64-assets/assets/covenant-crunch/bank` to the usual isolated
SDK/Tiny3D/map-override command. It has no forced photo poses, baseline switch or
profiling instrumentation. Reanalyze archived public logs without assets using
`collect.py THIS_DIRECTORY --logs-only --output RESULTS` (add `--gpu` for gpu/).
