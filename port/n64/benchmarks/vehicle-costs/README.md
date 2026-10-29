# Vehicle CPU and drawing attribution

Read [PVE_VEHICLE_COSTS.md](../../PVE_VEHICLE_COSTS.md). This is an isolated
diagnostic against the published vehicle checkpoint, not an adopted optimization.
The normal playable sources are not rewritten by the generator.

`vehicle_cost_audit_source.py` copies the gameplay/rendering/physics translation
units and local include chain into each output directory. It wraps original
operations with clocks and counters; every generated file is hash-bound in
`manifest.vehicle_cost_audit`. The build option requires enemy-vehicle QA8/9,
profiling, collision counters and an isolated output directory. Empty-scissor
controls additionally require frozen photos and serialized graphics diagnostics.
The runtime configuration header rejects invalid macro combinations too.

## Reproduction

Run from the isolated `build/n64-pve-squad/source` checkout with the existing
private vehicle bank and accepted corrected-ground map override restored.
SDK/Tiny3D paths are explicit in `run.py`.

```sh
build/n64-python/bin/python port/n64/benchmarks/vehicle-costs/run.py build
build/n64-python/bin/python port/n64/benchmarks/vehicle-costs/run.py capture
build/n64-python/bin/python port/n64/benchmarks/vehicle-costs/collect.py
```

`archive.py` packages the verified evidence into the private assets working
tree; it does not commit or push. The archive keeps exact compiler inputs in
deduplicated gzip blobs and retains historical generator/header versions.
`validation.json` records which inputs match current files and which were
verified against the checkpoint commit. Reproducing the historical cases
requires restoring those versions, as identified by their manifest hashes.

Optional case names select subsets. The capture helper starts and terminates
only its own Ares process. Run captures serially. The four main live cases have
45 observations each; `live-shot-8-4` repeats the overload with an extra read-only
cooldown counter. This fifth case followed the initial diagnosis; its extra
fields are absent in the original four logs. The archive retains the earlier
generator versions as well as the final generator. Reproducing all cases with
the final generator records the added counter in every case.

Frozen captures export nine pages: full scene twice, four individual hull
omissions, all-hull omission, and two full-scene repeats. The pilot remains.
`photo-1`, `photo-60` and `photo-180` are ordinary routes; `timing-60` adds category
queue drains on page 1; `empty-60` adds zero-area 3D scissoring. Images and their
full RGBA5551 values come from native framebuffer readback. The collector verifies
all offsets/coverage, repeat identity and matched state/counts for the controls.
Only ordinary rendered images support omission-pixel conclusions.

## Reading the counters

- `COLLISION` partitions completed groups of 30 simulation ticks. The new
  `VA_AI`/`VA_PHYS` records use the same interval, grouped by vehicle kind.
- `VA_AI.total` includes goals, width/support clearance, the retained CE
  controller, friendly-line checks and mortar arcs. `rays`/`floors` are nested
  inside goal/clearance work. `arc_pause_us`/`arc_pause_calls` identify arc tests
  performed with a positive burst pause; analytic aim still needs to be kept.
- `VA_PHYS.step` wraps the retained complete solver step. `force` includes
  `ground` and feature construction/testing. `sweep` spans force and integration;
  it must not be added to them. `splatter` wraps the surrounding biped loop,
  separate from step. Contact/resolve child timings can occur inside that loop
  or other movement/clearance services. Do not add all fields as independent time.
- `VA_DRAW` measures one category per camera, on frozen page 1. `submit` is CPU
  dispatch; `remaining` drains the RSP queue and may include RDP backpressure.
  `span` sums those two times. The synchronization destroys normal overlap;
  these are diagnostic spans, not production frame-time or pure chip occupancies.
- `VA_HULL` records actual selected LOD, submitted loads/triangles and pose.
  Omission pixels record the final image contribution, not visible source
  triangles and not a certified visibility decision.

Public logs strip framebuffer payloads. Private assets hold raw captures,
generated diagnostic sources/manifests, settings, PNGs and the local comparison
viewer. The normal playable ROM is unchanged. `results.json` and `provenance.json`
bind the public report to actual native builds. No ROM or owned map is archived.
The configuration check passed 45 configurations / 180 target translation units;
its log is retained alongside the numerical evidence. Viewer JavaScript and
all static/dynamic file links were checked; native PNGs were visually inspected.
