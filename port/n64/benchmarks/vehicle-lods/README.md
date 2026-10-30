# Wraith and Shade distance LOD appraisal

This is an opt-in local candidate against public checkpoint `031e79f5` and
private assets `39a541d`. Read [VEHICLE_DISTANCE_LODS.md](../../VEHICLE_DISTANCE_LODS.md).
The accepted bank and original dirty research checkout are preserved.

## Author and build

Run `author.py` through Blender MCP's Python executor, supplying its absolute
`__file__`. It creates a new scene and saves `build/vehicle-lods/distance-lods.blend`
and `reduced.json`. Existing Blender scenes are retained. It imports the owned
CE Wraith/Shade meshes from `build/pve-vehicles/source/extended-raw.json`, keeps
rigid parts separate, preserves UV/material data and protects the outer extent
of each connected component before symmetric collapse.

The initial unprotected reduction collapsed the Shade's feet/barrels; it was
rejected. Its reduced JSON and silhouette measurements remain in the local
archive as failed authoring evidence, not candidate assets.

From the isolated `build/n64-pve-squad/source` checkout:

```sh
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/pack.py
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/silhouettes.py
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/run.py build
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/run.py capture
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/collect.py
build/n64-python/bin/python port/n64/benchmarks/vehicle-lods/viewer.py
```

Optional case names select subsets. SDK/Tiny3D paths are explicit in `run.py`.
Build outputs are isolated. Captures must run serially; the helper terminates
only its own Ares process. Completed ROMs contain the DFS payload, so the runner
removes that redundant intermediate after verifying the finished ROM hash.
The playable ROM is excluded from automatic capture.

`--vehicle-distance-lods` requires the generated `vehicle_distance_data.c` in
an explicit enemy bank and an isolated output directory. The bank adds four
meshes and rigs; all 33 pre-existing bank files remain byte-identical. New
meshes use the same ordered rigid-part matrices, with conservative local
bounds covering the near and both distance tiers at every pose.

## Measurements and image checks

- Fresh 1–4-player captures for both the four-vehicle overload (QA8) and the
  one-Ghost control (QA9), before and after: sixteen 45-observation captures.
  Five warm-ups are discarded for FPS; engaged and all-player-alive scopes
  are reported separately. Damage, deaths, respawns and tick-600 stress
  restarts remain real. Faster execution can sample a different combat window.
- `PVE_PHASE` is per rendered frame; `COLLISION` partitions completed
  simulation ticks. Do not interpret several accumulated ticks as one decision.
- Thirty-six native inspection pages per version, four angles per page:
  two hulls, three poses, two angle sets and three requested tiers. The
  reference always draws the detailed articulated hull. All twelve near pages
  and all reference tier repeats match across all sixteen framebuffer bits.
- Ordinary automatic-LOD routes at simulation ticks 1/60/180 export nine pages:
  full scene twice, four individual hull omissions, all-hulls omission and
  two full-scene repeats. Full repeats are exact; camera and hull poses match.
  All-hulls-omitted before/after images match, isolating changes to hulls.
- Serialized category timings repeat tick 60. Their image matches the ordinary
  route. These drains destroy pipeline overlap and are not additive production
  frame times or separate pure RSP/RDP measurements.
- Offline silhouettes compare quantized geometry with backface culling at
  eight angles and 192/64/28 pixels. They are explicitly not native screenshots.
  Native differences amplify RGB changes ×4; silhouette differences color
  shared coverage gray, removed coverage red and added coverage cyan.

All target measurements are Ares v148, NTSC 320×240, audio enabled, 8 MiB.
They are not new cartridge measurements. The candidate release ROM retains
the maintained 30 FPS pacing preset; timing ROMs are uncapped.

Public files contain scripts, numbers, stripped logs and hashes. Meshes,
Blender files, packed art, raw framebuffers, native PNGs and full manifests
remain in the private local archive. No ROM or owned map cache is archived.
The disk-full photo attempt is retained separately as a failure; the successful
36-page rerun supplies the appraisal. No push or merge is part of this pass.
