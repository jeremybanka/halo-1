# Tiny far models

This recipe is a separate asset layer. It derives twelve additional models from
the regenerated far bank, with no game geometry or textures checked into the
repository. The ordinary near/far bank and its 59-entry audit remain the baseline.
Normal builds now include this separate layer. Selection occurs only in the
four-player tiny-far path; it does not replace nearby or first-person geometry.
Target screenshots and graphics validation remain necessary whenever the
recipe changes; successful offline generation alone is not visual acceptance.

## Regeneration

First complete the normal local-disc extraction, reduction and packing commands
in `ASSET_PIPELINE.md`. Then run the generator with Python, NumPy, Pillow and a
background Blender executable available:

```sh
python3 port/n64/generate_micro_lods.py \
  --assets build/n64/assets \
  --verify-generated build/n64/generated \
  --output build/n64/assets/micro-lods.json
python3 port/n64/pack_micro_lods.py
```

Pass `--blender /absolute/path/to/blender` if it is not on PATH or in the standard
macOS application location. Blender uses a separate factory-startup process and
does not alter an open scene. The reviewed recipe was reproduced with Blender
5.2.2. The output provenance records Blender, Python and NumPy versions plus
source, texture and helper hashes. A different tool version requires renewed
payload/visual comparison rather than an assumption of byte identity.

`micro_lod_recipe.json` contains the selected budgets, methods and explicit alias
decisions. `generate_micro_lods.py` reconstructs the actual far-bank geometry,
shader material boundaries and baked RGB using the current protected color
weld. `--verify-generated` asserts that this reconstruction exactly matches the
existing packed preview before any reduction. The input bank is never modified.

Most entries use Blender collapse with interpolated per-corner RGB. Vertices
outside the source AABB are projected back to the source surface, then final
1024-unit quantization is checked against the original far AABB. Shotgun and
frag use deterministic support hulls formed only from original packed vertices.
Those hulls fill small recesses and average incident source colors; they do not
preserve the original topology. Every Warthog material-3 lamp triangle is copied
back with exact original directed corners and RGB after collapse.

The generator writes expanded static corners in engine Y-up Halo units, RGB
bytes and per-triangle material IDs. `pack_micro_lods.py` quantizes at
1024 and applies the existing per-model protected weld exactly once. Repacking an
already-welded micro preview would permit unintended cumulative color drift.
The packer defaults to `build/n64/assets/micro-lods.json` and writes
`micro_data.c`, `micro-preview.json` and `micro-report.json` under
`build/n64/generated`. `--source`, `--generated` and `--output` allow isolated
verification. The original generated banks are not modified.

## Selected quality decisions

The twelve reviewed tiny entries are AR, pistol, plasma rifle, Needler, shotgun,
frag grenade, plasma grenade, overshield, camouflage, Warthog, Ghost and Banshee.
Plasma pistol, sniper, rocket, health pack and Scorpion intentionally retain
their existing far models. Their smaller candidates lost openings, body mass,
barrel bands, track shape or other identifying cues.

The selected entries contain 412 triangles and 386 loaded vertices in total,
compared with 798 loaded vertices for drawing each corresponding current far
model once. These totals do not describe a frame: actual savings depend on
visible instances and the projected-size gate.

The runtime path applies only to an already-far ground pickup or vehicle in four-player
views, with zoom off, finite conservative bounds and no near-plane intersection.
The reviewed gate requires the projected outward world AABB to fit below
7.5 pixels, reserving 0.5 pixels against eight-pixel quality probes. A conservative
sphere can provide a fast pass; corner projection must use the full original
near/far/posed bounds, not a shrunken micro silhouette. All reviewed micro
vertices fit within the original far AABB, so the bounds need not shrink or
change. First-person guns, held weapons and one/two-player views stay on their
finer paths. The original body/part culling and motion rules remain authoritative.
`asset_micro.h` exposes the additional pointer tables and `render_micro_lod.h`
implements the conservative gate. `build.py` requires and links `micro_data.c`
for normal builds; the measured pacing profile is selected separately with
`--paced30 --paced30-buffers 4`.

## Audit supplement

After the micro pack produces `micro_data.c`, `micro-preview.json` and
`micro-report.json`, append its diagnostics to an existing model audit:

```sh
python3 port/n64/audit_models.py --performance \
  --output build/n64/performance-audit \
  --generated build/n64/generated \
  --micro-dir build/n64/generated \
  --micro-only
```

An isolated packed output directory may also be passed to `--micro-dir`.
The generator itself does not produce C. Add `--micro-proof /path/to/independent-proof.json` to retain
a separate emitted-C review alongside the report. Omit `--micro-only` to rerun
the base audit and supplement together. `--html-only` refreshes existing HTML
without rendering or regenerating assets.

The supplement decodes the actual C arrays and checks every batch index,
directed source triangle, shader-material barrier, original-corner color bound
and preview pixel input. It compares highest-detail source, current far and tiny
models over eight angles including top and bottom, at 4/6/8 pixels and four
quarter-pixel phases. The extra twelve entries and five aliases are separate
from the existing 59 rows and the near-model 0.03 IoU budget.

CPU rendering is two-sided and does not emulate N64 coverage antialiasing or
clipping precision. Hulls therefore also require an explicit winding check:
closed edge incidence, outward normals for the model `CULL_BACK` path, and
one-sided native comparisons. Actual target snapshot pairs, advancing graphics
validation and a quiet full replay are separate acceptance requirements.

```sh
python3 -m unittest discover -s port/n64 -p test_micro_lods.py
python3 -m unittest discover -s port/n64 -p test_audit_micro_lods.py
```

## Integration and delivery checklist

The packer emits only the additional bank and pointer tables, using existing
far assets for aliases. Preserve all original bank bytes and bound initializer
rows when revising this recipe; verify new source hashes and actual C index expansion.
Record the exact ROM, source,
SDK, asset and display-buffer provenance for the final quiet replay; an emulator
result does not establish physical-console performance.

Fresh showcase captures belong in a new `videos/micro-lod` directory. Preserve
the earlier `videos/optimized` gallery and raw footage. Each new gallery item
must identify the exact ROM/bank, reset point, source PTS range, decoded frame
count and audio activity. Keep playback at source cadence; label any optional
quarter-speed excerpt clearly. Update the release manifest only after the final
files and their hashes are stable.
