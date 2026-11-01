# Jorge: CE-scale vertex budgets and a separate far model

The current third-person body comes from
`halo64-assets/assets/jorge/playable-lods/`. The accepted `playable-personal`
source remains unchanged. First person still uses the personal arms and hides
the local body, including the legs.
Armor now selects the model independently of profile; see
[ARMOR_SETUP.md](ARMOR_SETUP.md) for the four palettes and suit abilities.

| Body | Native / GLB vertices | Packed N64 vertices | Triangles | Batches |
|---|---:|---:|---:|---:|
| Previous Jorge, near and far | 1,334 / 1,387 | 2,264 | 2,108 | — |
| Jorge near | 548 / 548 | **598** | 879 | 41 |
| Standard Spartan near | — | 562 | 328 | 10 |
| Jorge far | 276 / 276 | **302** | 444 | 24 |
| Standard Spartan far | — | 250 | 135 | 5 |

These are body-only counts, including Jorge's backpack. The AR is the production
140-triangle weapon and is counted separately. Compared with the old bank, Jorge
loses 73.6% of close vertices and 86.7% of distant vertices. The close count is
6.4% above CE; the distant count is 20.8% above CE. This deliberately allows
geometry for Jorge's helmet, collar and pack. It is a comparable vertex tier,
not triangle-count or rendering-cost parity. The roughly 700-triangle close
target remains future work.

## What changed

`jorge_lods.py` names every retained, merged and omitted source component. Both
folders contain `component-budgets.csv` and `reduction-report.json`; the latter
records requested budgets, actual counts, source components and construction
method. Budgets are soft when protected contours prevent further collapse.

The near model retains the original helmet, visor, chest, collar, shoulder and
thigh surfaces. Overlapping forearm, boot and calf layers become source-fitted
volumes. Separate moving undersuit regions remain under the plates. Small
fittings and the obsolete first-person thigh caps are omitted. Concealed chest
and pack backing fill overlap losses without replacing the visible plates.

The distant model uses fewer layers and simpler limbs. Its chest and collar
remain separate original surfaces; combining them into one hull erased the
collar outline. A small dark internal torso volume is bound to `b_torso`, avoiding
arm-weight stretch during vehicle entry. Reduced hulls are reconstructed from
their retained points to remove zero-thickness fins left by collapse.

The helmet shell and visor surface are the same in both LODs: **50 vertices /
89 triangles** for the shell and **21 vertices / 23 triangles** for the visor.
A cheaper visor sank behind the shell and broke the gold opening into patches;
that candidate was rejected. The black band is retained with one deliberate
dark/olive value per vertex instead of many corner-color splits. The distant
pack uses two inspected source contour rings, preserving its paired crown,
central saddle, shoulders, depth and tapered base. The later palette pass gives
all profiles the same matte gray pack while retaining its original shading.

Packing starts new cache batches at component boundaries and welds only identical
quantized animation trajectories with bounded color differences. Rigid components
can use the existing order-preserving static optimizer. Deforming faces keep their
order. This avoids spending vertices on repeated cache loads, at the cost of more
batches than CE. Reducing submission overhead is a useful later optimization.

## Runtime behavior and cost

The body bank now has two independent meshes and two sets of all **39 clips /
1,530 frames**, with identical clocks and weapon-socket trajectories. Selection
uses the existing Spartan thresholds: squared distance above 16 in one/two
views, above 4 in three/four views; zoom selects near. Mixed split-screen views
can request both LODs of the same player in one frame.

Both meshes remain resident. One shared pair of endpoint buffers streams only
the needed clip/LOD. Weapon sockets come from a requested LOD, avoiding an extra
near-frame DMA when only the far body is visible. Model reloads reconvert both
fresh index buffers, even when the allocator reuses their old addresses.

The combined body bank is **8,370,656 bytes**, down from 20,881,840 bytes. Resident
geometry plus the shared pose cache uses **30,208 bytes** instead of 76,592.
Each Jorge needs **14,400 bytes per buffered frame** for both animated bodies,
versus 36,224 for the old shared near/far mesh. The game still requires the
8 MiB Expansion Pak. These are storage/allocation measurements, not an FPS claim.

## Evidence and limits

- `test_jorge_bank.py --candidate` verifies every serialized position, socket,
  batch/index range and bound in both banks. The source BLEND hashes must match.
- `test_jorge_lod_runtime.py` exercises the actual C loader and decoder under
  ASan/UBSan: 4,680 mixed-player/LOD decode cases, endpoints, loops, blends,
  socket-only reads and three release/reload cycles.
- Both GLBs preserve 85 bones and 39 actions. Reimported geometry matches the
  editable scenes at 195 frame-aligned samples per LOD, within 0.017 mm near
  and 0.005 mm far. Blender and glTF interpolate rotations differently between
  sampled keys (a 27.9 mm hand difference was observed at a half-frame during
  Banshee entry). The game uses its independently verified vertex-frame bank.
- Coverage audits sample all 39 clips at three phases, ten directions and two
  sizes per LOD: 2,340 views each. Additional idle/run/fire/reload pilot samples
  cover other phases. The reports retain silhouette overlap and enclosed-gap
  measurements. They expose small remaining seam differences; they are not a
  claim of pixel-perfect coverage or a watertight assembled mesh. The largest
  newly enclosed regions were five pixels near and four far; worst-view
  silhouette overlap was 89.0% near and 80.9% far. Keep the worst-pose images
  as references for future seam cleanup, rather than treating these as zero-gap passes.
- Matched packed-color views, game-size views, head crops and worst-coverage
  pose comparisons are in `review/`. The AR previews use the actual port asset.
  The close model was not accepted solely on a rest pose or polygon count.

The `--jorge-qa` ROM shows Jorge/CE in the left/right columns and near/far in
the top/bottom rows, then crosses the production LOD threshold. QA asserts the
expected LOD choice on its fixed-distance pages. Each subject is placed on its
own sampled floor. The field QA continues to exercise single/four-player custom
arms, weapons and vehicles through the production state machines.

The final release, comparison and four-player field ROMs build successfully.
Ares at 8 MiB displays the near/far comparison and both mixed Jorge/CE and
all-Jorge four-player weapon views. One emulator session stopped advancing;
after restarting Ares, the unchanged ROM advanced through the weapon pages,
including the all-Jorge shotgun page. ROM and bank hashes are recorded in
`validation-summary.json`.
The release ROM is `build/n64-jorge-lods-release/halo-64-paced30-rspq32k.z64`.

## Reproduce

Use background Blender; preserve the source library. From the repository root:

```sh
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
PYTHON=build/n64-python/bin/python
SOURCE=halo64-assets/assets/jorge/playable-personal/jorge-playable-personal.blend
"$BLENDER" -b "$SOURCE" -P port/n64/jorge_lods.py -- --lod near
"$BLENDER" -b "$SOURCE" -P port/n64/jorge_lods.py -- --lod far
"$BLENDER" -b --factory-startup -P port/n64/bake_jorge_lods.py
"$PYTHON" port/n64/pack_jorge_lods.py
"$BLENDER" -b --factory-startup -P port/n64/export_jorge_lods.py
"$BLENDER" -b --factory-startup -P port/n64/validate_jorge_lods.py
"$BLENDER" -b --factory-startup -P port/n64/validate_jorge_lods.py -- --full
"$BLENDER" -b --factory-startup -P port/n64/review_jorge_lods.py -- --packed
"$BLENDER" -b --factory-startup -P port/n64/review_jorge_lods.py -- --coverage
"$PYTHON" port/n64/report_jorge_lods.py
"$PYTHON" port/n64/test_jorge_bank.py --candidate
"$PYTHON" port/n64/test_jorge_lod_runtime.py
"$PYTHON" port/n64/test_jorge_firstperson.py
"$PYTHON" port/n64/pack_jorge_lods.py --publish
"$PYTHON" port/n64/build.py --jorge-qa --output-dir build/n64-jorge-lods-qa
"$PYTHON" port/n64/build.py --preset release --output-dir build/n64-jorge-lods-release
```

Review the images before publishing. Publishing rejects stale export, bank or
coverage reports. `pack_jorge.py` and the older checkpoint scripts document the
single-mesh pipeline; use `pack_jorge_lods.py` for the current runtime format.
