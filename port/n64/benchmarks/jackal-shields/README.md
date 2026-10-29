# Jackal shield restoration appraisal

Read [the report](../../JACKAL_SHIELDS.md). Work is isolated from the original
research checkout and remains an opt-in `--pve-jackal-shields` candidate. It
builds on the local Firefight roster candidate, not a separate AI revision.

From the checkout root:

```sh
build/n64-python/bin/python port/n64/restore_jackal_shield.py prepare
```

In Blender, import `port/n64/restore_jackal_shield.py` and call `bake()`. This
uses mathutils to convert the source mesh into forearm-local coordinates and
bake its attachment tracks. It does not edit the active scene. Then:

```sh
build/n64-python/bin/python port/n64/restore_jackal_shield.py pack
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/audit.py
build/n64-python/bin/python port/n64/test_maps.py --firefight --roster \
  --output-dir build/jackal-shields/host
```

The source is the private full-detail `base00 superhigh` Jackal model, retained
from the original CE extraction. The source audit also checks it against the
pre-reduction `firefight-combat` extraction. All 76 shield faces are rigidly
weighted to bone 26. One static mesh/texture serves all three body LODs. All
seven existing roster bank files remain byte-identical; `pve_jackal_shield.c`
is the only added runtime asset. Rules and canonical collision are unchanged.

`run.py build VERSION SUITE` builds matched ROMs. VERSION is `before` or
`after`; SUITE is `photos`, `roster-photos`, `control`, `roster`, `ordinary`,
`perf` (all three timing matrices), or `play` (menu-based 30 FPS release).
Before/after use the same code and original assets, with the shield flag/asset
enabled only after. SDK, tiny3d, corrected ground and Ares settings match the
previous roster appraisal. Example:

```sh
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build before perf
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build after perf
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build before photos
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build after photos
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build after roster-photos
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build before roster-photos
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/run.py build after play
```

Run `run.py capture before photos` and `run.py capture after photos` separately,
then `capture_all.py` for serial timing captures and the repeated original roster
photos. Each process owns and terminates only its own Ares instance. Ares requires
native desktop execution; sandbox-only launches can exit without a usable log.
No global emulator preferences are changed. Do not run captures concurrently.

```sh
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/photos.py
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/collect.py
build/n64-python/bin/python port/n64/benchmarks/jackal-shields/viewer.py
```

There are 72 paired shield frames: two ranks × three LODs × twelve states, each
with four fixed cameras. Full/quarter/hit/depleted are explicit fixtures; the
14.9/15.1-second pages run production ticks through the source recharge delay.
The original 46-page roster route is repeated with a fresh shield-off control
and checked against its saved native baseline. Opaque non-Jackal pages require
exact identity; cloak pages use noise dithering, so their exact states and both
pixel-difference counts are retained without claiming pixel identity.
No screenshot is synthesized as native output. Diff filters and pixel masks are
derived from framebuffer readbacks. The actors are suspended for inspection.

`photos.py` verifies inactive-state pixel equality, exact recharge appearance
outside the caption, opaque foreground depth and visible rear-actor detail.
The coarse geometry leaves only three pixels in the deliberately eroded rear
overlap test; the evidence records those counts, not a larger claimed sample.
Host tests exercise actual shield/body ray results, damage, EMP, the source
15-second delay, immediate restoration and dead-actor behavior. They also check
that shield damage starts the visual flash and a subsequent exposed-body hit
does not restart it.

Timing uses QA 4 (old crowded composition), QA 7 (new crowded roster) and QA 3
(ordinary opening), each at 1–4 players before/after. Every case retains 45
observations and discards five warm-ups. Engaged FPS means at least one human and
enemy alive and no arrival underway; all-human-alive scope and raw CPU counters
are also preserved. Final source/header inputs are identical except for the
additional shield asset and compile flag. `collect.py --logs-only` reproduces
summaries from checked-in timing logs and validates their archived hashes.

Run `archive.py` after the viewer and checks succeed to preserve private art and
native framebuffer evidence. Then run `validate.py` to verify all 29 final ROMs,
current source hashes, archived payloads, viewer links and JavaScript syntax.
This checks the saved artifact without claiming a browser render. Do not publish
private art or framebuffer payloads in the public repo.

The private archive `halo64-assets/assets/jackal-shields/` contains source art,
the candidate bank, photos and compressed native readbacks. Public benchmark
files contain numerical evidence, scripts and hashes. ROMs stay local.
