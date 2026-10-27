# N64 benchmark evidence

The [Sidewinder report](../SIDEWINDER_BENCHMARKS.md) explains the current result,
its development history and the cartridge checkpoint. The October archive
contains 25 studies, including the original thirteen-map survey, Expansion Pak
experiments, visibility controls, geometry/LOD trials, CPU/RSP/RDP attribution,
and the playable cartridge validation/deployment receipt.

`results/2026-10/index.json` lists every checked-in record and its SHA256.
Each study contains selected numeric results, private-source artifact hashes,
and (where available) exact native counter lines plus ROM/run identities.
Private ROMs, map banks, visibility sidecars, textures, images, Blender files,
camera transforms and chat transcripts are not included. Filename references
in historical results identify local evidence, not checked-in image links.

The archive preserves observations as recorded. An old `status: not adopted`
field describes that experiment's appraisal date; the cartridge report states
which candidate was subsequently used. Rounded screenshot transcriptions,
quiet fresh-pose runs, instrumented CPU timings and serialized graphics waits
have different precision and scope. Do not turn an instrumented run into a
quiet FPS claim or interpret a remaining fence wait as total RSP execution.

## Verify the checked-in results

No private assets or emulator are required:

```sh
python3 port/n64/benchmarks/verify.py
```

This verifies the archive hashes, quiet counter arithmetic and repeats, final
CPU/geometry assertions, counter-to-ROM identity references, and cartridge
completion/readback evidence. It explicitly retains the cartridge wrapper's
settings-integrity failure alongside the successful native gameplay result.

## Refresh from the retained local research checkout

```sh
python3 port/n64/benchmarks/collect_research.py --source-root /path/to/halo-1
python3 port/n64/benchmarks/verify.py --source-root /path/to/halo-1
```

The collector reads an explicit artifact allowlist, checks available frozen
ROMs against their run hashes, strips local home paths and camera transforms,
and writes deterministic JSON. `--source-root` on the verifier also checks all
187 original artifact hashes. Existing observations are archived; this command
does not rerun a benchmark or regenerate assets. To inspect a proposed refresh,
pass `--output-dir` to both commands and compare with the tracked directory.

## Reproduce the final paired hierarchy measurement

Use the hash-bound section bank and private unlit Tiny3D described in
[SIDEWINDER_CARTRIDGE.md](../SIDEWINDER_CARTRIDGE.md). Build into separate output
directories under the checkout with common flags:

```text
--preset release --initial-map sidewinder --world-bulk-submit
--rspq-buffer-kib 32 --tiny3d <private-unlit-tiny3d>
--map-bank-override <sections>/candidate-maps/sidewinder.map64
--world-pvs-data <sections>/visibility.json
```

Use `--world-coarse-cull` for before and `--world-hierarchy` for after. For each
side, build separate `--demo --vi-benchmark`, `--photo-walk-benchmark
--vi-benchmark`, `--demo --benchmark --benchmark-page 5`, and `--demo --benchmark
--benchmark-page 9 --gpu-diagnostic` ROMs. Run quiet four-player before/after
controls twice, single-player once per side, and CPU/pipeline profiles
separately. The ROMs implement one-second warmup and 75-second measurement.
Use Ares NTSC/8 MiB, private settings, one emulator, and no concurrent builds or
renders. Preserve the raw `BENCH`, `SUBMIT` and `HIERARCHY` lines and per-ROM
`.build.json` hashes. Emulator wall-clock status-bar FPS is not the metric.

Rebuild `--snapshot-tick 180`, `1500`, `1950` and the `--photo-tour` selections
0/20 independently from performance ROMs. Take raw Ares captures, compare RGB,
and preserve pose/counter records. `--validate --map-qa 0 --rspq-buffer-kib 8`
is a separate RDP check. The retained private appraisal additionally has the
196 offline pairs, full camera poses, scripts and source snapshots under
`build/n64-sidewinder-hierarchy/REPRODUCE.txt`; this numeric archive does not
replace those private visual assets or claim exhaustive view coverage.
