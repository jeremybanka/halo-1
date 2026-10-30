# Four-camera Firefight drawing census

28 October 2026. See [the analysis and proposed next step](../../FIREFIGHT_DRAWING.md).
This audit follows `c39213e85a752de967fe1e56ab4fca61f5f9c12b`; it does not replace
the previous live performance matrix or change ordinary rendering.

## Evidence

- `results.json`: camera rectangles/positions, category loads, per-actor species,
  LOD, clip/time, health, body/weapon loads, actual-pose frustum results, native
  omission pixel counts/bounds, and category timing controls.
- `*-census.log`: native output with only the private `FF_PIX` image data removed.
- `provenance.json`: exact ROM, generated diagnostic source, source/header/include,
  native readback, census and settings hashes, build options, parent source and
  private asset commits. The generator evolved to add the optional category timing
  control during the audit; measured generated files have their own exact hashes.
- `model-inventory.log`: body complexity and exact full-animation/attribute
  equivalence classes, using the same opt-in Hunter/Spirit bank as the measurements.
- `configs-test.log`: 42 normal runtime configurations / 168 target translation
  units still compile after the restricted diagnostic build option is added.

All captures run native N64 programs in Ares v148, NTSC 320×240, 8 MiB and audio
on. No FPS from these frozen/serialized runs is a gameplay performance result.
The previous preparation report remains the current live 1–4 player measurement.

The eight route states are crowded QA4 at ticks 1, 60, 180 and 360; ordinary QA3
at 360 and 900; and authored delivery QA5 at 60 and 300. Tick 1 and 60 crowded
have four living humans. The later crowded cameras are after all humans die;
these are explicitly separated from living-party conclusions. Opening 900 shows
retained corpses; opening 360 and delivery 60 have no visible Covenant. Those
controls are not evidence of cheap active combat.

Each capture exports 17 frames: full scene at pages 0/1, omission of actors
0–11 at pages 2–13, omission of the Spirit at page 14, omission of all NPC-held
guns at page 15, full scene again at page 16. `collect.py` requires all normal
baseline images to match all sixteen RGBA16 bits. Differences are final-image
contributions, not visible triangle counts; AA/blending/depth interactions may
contribute. It also computes a union of actor omission masks to avoid adding
overlapping pixels as independent screen area. No zero-difference result is
used as a runtime culling rule.

The `body_in`/`gun_in` fields test outward-rounded bounds of every currently
prepared visual vertex transformed by its actual body/attachment matrix. This
expensive CPU scan is diagnostic only. A practical optimization would use
precomputed conservative visual bounds; collision bounds do not automatically
contain every rendered surface. `gun_far` evaluates the existing 12-pixel
projected-size rule, without changing the chosen weapon mesh.

The ordinary census includes full opaque+alpha body loads once; alpha submission
occurs later. Sky/HUD rectangles are outside the renderer's load counter. Actor
removal omits its body/alpha/held gun, leaving gameplay and unrelated effects
unchanged. Category timings therefore describe dispatch intervals, not perfectly
isolated ownership of every graphics command.

## Graphics control

`timing` repeats crowded tick 60 and drains the RSP queue after each category on
page 1; census printing is confined to page 0. `submit_us` includes CPU queuing
and any lazy animation work in that interval. `remaining_rsp_us` is a queue drain,
including possible RDP backpressure, not independent pure RSP occupancy. It uses
`rspq_wait` without the ordinary audio-pumping loop. Timings are diagnostic, not
live performance or category GPU timers. The whole-scene GPU diagnostic still
runs separately after the per-camera passes.

`timing-empty` adds the existing zero-area scissor control. Its category counts,
actor states and selections match `timing` and the ordinary crowded-60 census.
Native inspection confirms 3D pixels are suppressed. Covenant span is
87.452 → 87.421 ms, including 86.665 → 86.645 ms of remaining queue drain.
This supports geometry/triangle-command work over pixel-fill cost as the major
constraint; it does not distinguish all vertex, triangle-setup and RDP command
costs. Each control has one capture, so tiny differences have no statistical claim.

Empty-scissor surfaces do not have a fully rendered background. Its final page
has 2,770 differing RGBA16 values despite pages 0/1 matching; **its omission pixels
are invalid and excluded from visibility conclusions**. Only its page-1 timing
and matched submission/state records are used. All nine normally rendered
captures pass complete baseline stability.

## Reproduction

Use the existing Python environment, SDK/Tiny3D, corrected Blood Gulch override,
and owned private assets. `build_matrix.py` has the same SDK/Tiny3D defaults as
previous local benchmark runners; edit those paths for another installation.

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-drawing/build_matrix.py
```

Optional positional case names limit the build list. Each command uses
`--pve-squad --pve-players 4 --pve-qa 3/4/5 --pve-photo-tick TICK --profile
--pve-draw-audit`, an isolated output directory, and the archived candidate bank
`halo64-assets/assets/covenant-model-appraisal/bank`. The diagnostic permits up
to 1,800 simulated ticks. Ordinary photo fixtures retain their previous limit.
The build generates isolated copies of main/scene/NPC draw sources; playable
source remains untouched. Do not use the audit ROM as a gameplay build.

Capture one owned emulator at a time:

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-drawing/capture.py ROM ARES_SETTINGS NATIVE_LOG
build/n64-python/bin/python port/n64/benchmarks/firefight-drawing/collect.py build/firefight-draw-audit LOCAL_VIEWER_DIRECTORY
```

For timing, build the crowded-60 arguments into `timing/` with
`--collision-profile --gpu-diagnostic`; build `timing-empty/` with the additional
`--gpu-empty-scissor`. Both use the same renderer/bank/route. The collector expects
matching per-case ROM manifest directories. Raw native logs contain private game
pixels and must not be committed to this public repository.

`model_inventory.c` compiles on the host with the small Tiny3D packed-vertex stub
emitted by `test_pve_preparation.py`, the public `port/n64` headers, private
candidate `pve_data.c` and canonical `generated/models_data.c`. Pass the candidate
`pve-motion.bin` to the executable. It compares every sample of every clip,
normal/color/UV attributes and Jackal shield membership. Its exact equivalence
counts are ideal global lower bounds before finite vertex-cache batching; the
position-only counts omit appearance distinctions and are not achieved loads.

The local/private viewer and raw pixel evidence accompany the public metrics.
No reduction in geometry, animation fidelity, hit meshes, or enemy counts is
included in this audit.
