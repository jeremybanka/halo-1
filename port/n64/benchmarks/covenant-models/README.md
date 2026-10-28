# Covenant model appraisal — 28 October 2026

This is an **opt-in visual prototype**, not an adopted replacement bank.
`--pve-model-bank PATH` replaces only `pve_data.c` and the streamed
`pve-motion.bin`. Definitions, collision, navigation, source AI selectors,
encounters, scoring and player behavior still use the approved bank. The normal
build does not define `BG_PVE_MODEL_CANDIDATE`.

The isolated bank and photos are archived at private asset commit `eb0c53e` under
`halo64-assets/assets/covenant-model-appraisal/`. Its `bank/` directory can be
passed directly to the override without rebuilding Blender assets. This archive
does not replace any canonical generated payload.

Read [COVENANT_MODELS.md](../../COVENANT_MODELS.md) for the appraisal and timing
tables. The comparison page and derived art belong in the private asset archive,
not this public benchmark directory. Local native ROMs and raw pixel readbacks
remain under `build/covenant-models`.

## Geometry and renderer changes

| Model | Before triangles near / far | Candidate triangles near / far | Before loads near / far | Candidate loads near / far |
| --- | ---: | ---: | ---: | ---: |
| Hunter | 2,006 / 2,006 | 1,306 / 1,138 | 3,378 / 3,378 | 1,606 / 1,464 |
| Spirit | 2,956 / 2,956 | 944 / 860 | 4,228 / 4,228 | 1,232 / 1,084 |

Loads sum `(batch.count + 1) & ~1`, exactly as the runtime does. They are
per-instance, per-camera body submissions, excluding attached guns, riders and
other actors. The source Hunter and Spirit originally alias their near mesh in
the far entry; the original Spirit renderer always uses near. Other actor
triangles and clips remain identical. Their load counts change slightly because
the candidate batches separate source render modes.

`reduce_pve_blender.py` uses Blender collapse reduction with zero-weight protected
vertices. Open/nonmanifold edges, articulated seams, material seams, and each
material/bone region's supports in 26 directions restrict collapse. Hunter near
also protects its whole face and back spines. This prevents a broad shield or a
Spirit boom from disappearing even when it is not a whole-model extremum.
Requested collapse ratios are 0.40/0.20 for Hunter and 0.32/0.16 for Spirit;
protected geometry prevents those ratios from being reached literally.

Original skeleton motion, hit meshes and attachment poses are retained. Blender
transfers the source corner colors and tint masks, rather than interpolating UVs
into unrelated atlas regions. Full motion trajectories, material IDs and tint
still constrain vertex sharing; color tolerance rises from 8 to 24 only for the
reduced Hunter/Spirit. Initial versions that flattened the Hunter shield or
introduced orange atlas streaks were rejected and are not in the evidence.

The measured candidate includes source two-sided surface flags, separate energy
blending, Spirit distance selection (20 world units in 1P; 15 in split-screen;
zoom forces near), and unchanged-door pose reuse per fenced frame slot.
Therefore these timings **do not isolate mesh reduction from packing or pose
caching**. Energy surfaces draw after opaque world objects, including Spartans,
pickups and grenades; they depth-test without writing depth. Armor stays opaque.
Standard alpha is a bounded approximation of CE's layered additive shaders, not
a port of the animated shield/tractor-beam shader.

The included alpha surfaces are the Spirit beam and near Grunt inset lights.
The Jackal shield audit found **zero shield faces in either selected render LOD**;
only the source superhigh mesh contains its 76 shield triangles. The native
up/down pairs are consequently identical, despite working shield collision.
This pre-existing visual omission is documented for a focused repair, not fixed
or hidden by the Hunter/Spirit reduction. Jackal photo pairs are defect evidence,
not a successful test of shield blending.

## Matching and limitations

- Baseline source: `d7c4e2d0e04feda2bb8a4f5585ff307cad015852`; canonical private
  bank: `b673db776fbcfac5a477bd1098561d3490503771`. Candidate manifests identify
  the parent commit plus exact measured working-tree source hashes.
- Sixteen captures: baseline/candidate × ordinary/crowded × 1–4 players.
  Ares v148, NTSC 320×240, 8 MiB, audio enabled, uncapped native N64 code.
  These are emulator results, not fresh physical-cartridge measurements.
- Ordinary QA3 uses the real director and 75 one-second observations. Crowded
  QA4 uses cap-sized mixed squads, including Hunters, and 45 observations;
  it resets every twenty simulated seconds. Both retain real damage and deaths.
- Drop the first five samples. Headline results require a living human, a living
  enemy, and no enemies still arriving. This does not guarantee that every enemy
  is visible or that a departing Spirit is offscreen. Whole-window and
  all-humans-alive subsets are also saved. Identical controls and scenarios do
  not guarantee identical combat trajectories or visible work.
- CPU counters are sampled rendered-frame costs. AI and NPC animation are
  nested within simulation and preparation; do not add them again. Disabled
  RSP/RDP drain counters are not measurements of zero graphics work. Integer
  FPS minima are not frame-time percentiles.
- Native inspection has 52 paired frames, each with four matched cameras:
  both LODs; Hunter idle/run/melee; Spirit doors closed/open/intermediate;
  Jackal shield up/down, idle/fire and Spartan overlap; Grunt/Elite idle/run.
  Models are suspended above sloping terrain and far meshes are shown close
  enough to inspect. Photo fixtures are excluded from performance results.
- The native difference filter amplifies RGB differences fourfold. Geometry
  changes are expected, so this is not a pixel-equivalence claim. `photos.json`
  records fixed actor/camera positions and source phases. The CPU audit supplies
  72 additional orthographic views at packed position precision, with silhouette
  overlap and backface-only pixel counts. It is not a proof for every viewpoint.
- Soundness checks cover finite skin weights and poses, surviving material
  regions, packed opacity classes, 1,004 animation frames, aligned motion-bank
  bounds, unchanged hit/weak-point/attachment data and source rules. Thin Hunter
  triangles can still collapse at 1/128-unit precision; see the quantization
  audit. Animated shader parity and sorting of intersecting energy effects
  remain outside this prototype.

## Reproduce

Use the existing owned Firefight source cache, Python dependencies, Blender and
SDK. The reduction script is batch Blender; the live Blender connector was
unavailable during this authoring pass. The preparation command requires an
empty output directory and never overwrites the canonical bank.

```sh
build/n64-python/bin/python port/n64/benchmarks/covenant-models/prepare.py --output build/covenant-models-repro
build/n64-python/bin/python port/n64/test_pve_model_candidate.py build/covenant-models-repro

build/n64-python/bin/python port/n64/benchmarks/covenant-models/run_matrix.py build --baseline-root BASELINE_CHECKOUT --output build/covenant-models-repro/matrix --candidate-bank build/covenant-models-repro/bank
build/n64-python/bin/python port/n64/benchmarks/covenant-models/run_matrix.py capture --baseline-root BASELINE_CHECKOUT --output build/covenant-models-repro/matrix --settings ARES_SETTINGS
build/n64-python/bin/python port/n64/benchmarks/covenant-models/collect.py build/covenant-models-repro/matrix --output build/covenant-models-repro
```

The baseline checkout must be at the revision above. The original captures used
its clean source before adding the prototype; its isolated ROMs were retained.
The matrix runner uses the same corrected-ground Blood Gulch bank as earlier
Firefight measurements and accepts `--sdk` and `--tiny3d` paths. Run one emulator
at a time. `--resume` may only reuse logs whose ROMs are unchanged.

Build each native photo ROM with `--pve-squad --pve-model-qa --validate`, its own
`--output-dir`, the same SDK/Tiny3D and corrected-ground map override. Add
`--pve-model-bank` only for the candidate. `capture.py ROM SETTINGS LOG` stops at
52 readback frames and terminates only its owned Ares process. Name the logs
`photo-before-native.log` and `photo-after-native.log` in the capture directory.
After the collector writes `results.json`, `compare.py CAPTURE OUTPUT` assembles
the photo viewer, difference filter and timing table. Use `--firefight --preset
release --pve-model-bank PATH` with a separate output directory for normal play.

Archived public timing logs can be reanalyzed without the private art or emulator:

```sh
build/n64-python/bin/python port/n64/benchmarks/covenant-models/collect.py port/n64/benchmarks/covenant-models --logs-only --output build/covenant-models-reanalysis
```

Host validation commands:

```sh
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/covenant-models/host-firefight
build/n64-python/bin/python port/n64/test_maps.py --pve --output-dir build/covenant-models/host-pve
build/n64-python/bin/python port/n64/test_deferred_animation.py
```

The runtime configuration test covers 36 configurations / 144 target translation
units, including both model QA modes. The native four-player frontend fixture
also exercises actor buffers through restart, quit and return to multiplayer.
