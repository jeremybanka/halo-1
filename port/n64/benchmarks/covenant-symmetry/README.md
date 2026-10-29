# Symmetry and anatomy appraisal

See [the report](../../COVENANT_SYMMETRY.md). Work follows public source
`3accaa1e7c5722ec1f879d65e21c1151794d9838` and private assets
`4a8c85263e659751e3365bec84855acd585a3c95`. Both native versions use the same
runtime and crunchy selection rules. Only the body banks and centered Warthog
coordinates change. No `--pve-crunch-baseline` switch is used.

- `results.json` / eight text native logs: 45 observations for each crowded
  1–4 player pair; five warmup samples discarded. Headline scope has a living
  player and landed enemies. All-humans-alive results are separate. Live
  observations can differ with frame timing; they are not frozen-state proofs.
- `provenance.json`: complete measured manifests, ROM/log hashes, toolchain,
  flags and all included source/data. The collector allows only the expected
  two PvE bank paths and Warthog world-bank difference; all other inputs match.
- `photo-provenance.json` / `pixel-checks.json`: 71 frozen four-camera frames,
  exact pose/state parity, nine unchanged pixel controls. Native pixels and
  all derived pictures remain in the private archive.
- `bind-silhouettes.json`, `animated-silhouettes.json`, `silhouette-summary.json`
  and `part-silhouettes.json`: source reference vs previous/corrected geometry.
  Eight poses × six views × three diagnostic resolutions per species, plus
  regional anatomy checks. They supplement the native images.
- `asset-checks.json`, `repro-check.json`, host logs: exact mirrored regions,
  unchanged source animation/hit/grip data, stable unrelated world geometry,
  packed pose/bounds checks and byte-identical Blender recipe reproduction.

The Hunter connected shell uses symmetry-aware reduction with protected source
arms. Only its separate spines use exact half-mirroring; treating the attached
arms as independent retained faces opened cracks and was rejected. The other
three actors use exact mirrored geometry/weights/colors at all three tiers.
The previous crunchy archive remains the baseline.

`author.py` runs inside Blender and accepts `-- --output DIR`. It consumes the
private `source-colors.json` capture. Bake with `bake_pve_blender.bake`, then
`pack.py`. The authoring recipe reproduces `reduced-source.json` byte-for-byte.

`run.py build baseline` runs before installing centered Warthog generated data.
The new `pack_extended.py` centers that feature when packing; regenerate the
micro and interaction provenance afterward. Build/capture the candidate with
`run.py build candidate` and `run.py capture candidate`. Use the same settings
file and do not run multiple owned Ares instances simultaneously. Local runner
SDK/Tiny3D/Python paths reflect this workstation.

`audit.py`, `silhouettes.py`, `parts.py`, `collect.py` and `compare.py` generate
the evidence and interactive side-by-side/blink/difference viewer. Existing
`covenant-models/capture.py --frames 71` captures the extended inspection route.
The original 52 pages retain their ordering; 16 middle-tier pages and three
Warthog representations follow them.

The public checkout contains no new source art or native pixel payloads. The
private archive includes the Blender file, authored source, baked animation,
visual bank, native readback logs (gzip), viewer and manifests. The corrected
coarse bank remains opt-in with `--pve-crunch --pve-model-bank BANK`.
