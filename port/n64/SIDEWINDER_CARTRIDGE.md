# Sidewinder cartridge candidate

The 2026-10-24 cartridge candidate carries the reviewed Sidewinder terrain,
tree and distance LODs, conservative visibility, intact room/wall batching,
bulk submission, private unlit Tiny3D, and shared spatial hierarchy into the
normal controller-driven multiplayer frontend. It requires an Expansion Pak.
All thirteen maps remain selectable. Only Sidewinder uses its baked hierarchy;
other maps retain the original per-batch frustum predicate and draw order.
World unload invalidates/frees hierarchy state before another map is loaded.

This is an opt-in cartridge branch based on `origin/main` at `d071efc5`, with
the existing expansion-research commits and subsequent local research work.
The original research checkout, canonical asset banks and normal build defaults
are preserved. Rejected structure reductions and visibility-audit data are not
selected by this build.

Private inputs used by this candidate:

- Asset submodule: `6349c1d2e30f80d0c91f42b29a50a9212efcf964`.
- `build/n64-sidewinder-sections/candidate-maps/sidewinder.map64`, SHA256
  `9b02bf420e1168f33e16eae0d3280ef9fbdbb854921b98a94d08f0256f8b0bac`.
- Its `visibility.json`, SHA256
  `e425b771c6f0f7c1e6fd15da9f4c063af0d5fff5d25abe3f531dfa4736496259`.
- `build/n64-sidewinder-throughput/tiny3d-unlit`, including its recorded
  `unlit-manifest.json`. The shared installed Tiny3D is not modified.

The full bank/sidecar and all 17,222 candidate triangles are unchanged from the
hierarchy appraisal. That appraisal's before/after photos, native pixel checks
and measurements remain under `build/n64-sidewinder-hierarchy` in the research
checkout. These are Ares measurements, not physical-console FPS claims.

Build from this checkout with the private input paths resolved to the retained
research checkout. Keep the output directory inside this checkout:

```sh
build/n64-python/bin/python port/n64/build.py \
  --preset release --initial-map sidewinder --playable-candidate \
  --world-hierarchy --world-bulk-submit --rspq-buffer-kib 32 \
  --sdk /Users/jem/dojo/n64-2048/.build/libdragon \
  --tiny3d /Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit \
  --map-bank-override /Users/jem/dojo/halo-1/build/n64-sidewinder-sections/candidate-maps/sidewinder.map64 \
  --world-pvs-data /Users/jem/dojo/halo-1/build/n64-sidewinder-sections/visibility.json \
  --output-dir build/cartridge-release
```

This uses release LTO, paced presentation, three surfaces and 32 KiB queues.
It does not enable a replay, scripted input, frozen camera, performance overlay
or RDP diagnostic. Sidewinder is the default map selection in the menus.
The ROM manifest records every compiled source, header and bank hash.

A separate `--maps-cycle` build (without `--playable-candidate`) exercises all
thirteen maps through fourteen live matches and quit/resume. It logs frontend
steps only in that QA build. Host ASan/UBSan gameplay checks can use the exact
packaged banks with `test_maps.py --maps-cycle --world-cells --map-directory
build/cartridge-qa/frontend-files/maps`. The ordinary renderer contract and
randomized hierarchy certificate checks remain separate checks.
