# Spartan locomotion during reload — 28 October 2026

Spartans keep walking while reloading, including crouched movement. The previous
renderer selected a whole-body reload pose baked over idle, replacing the legs
even though the source action does not animate those channels. Unlike the
earlier firing bug, the independent gait clock already continued correctly;
reload simply did not use it.

## Source behavior and implementation

CE's `replacement_animation_apply` replaces only the channels selected by the
source animation masks (`source/models/model_animations.c:876`).
`unit_preprocess_node_orientations` applies that replacement to the current base
pose before the recoil overlay (`source/units/units.c:10479`). The source
`stand rifle ar reload-1` is a replacement with rotation mask 521288 and zero
translation/scale masks. Pelvis, thigh, calf and foot channels remain those of
the base animation; chest, arm and head rotations carry the reload.

The exporter precomposes those masked channels over standing idle/run and
crouched idle/run, retaining the existing twelve third-person reload samples.
Both approved Spartan render LODs, the right-hand attachment and original
animated hit surfaces use the same composition. Runtime interpolation combines
the independent gait clock, normalized weapon reload timer and crouch amount.
Shotgun shell reloads restart their action phase without restarting the stride.
Already-crouched poses are not scaled down a second time.

This does not add the full CE animation graph. The existing shared AR
third-person action and common forward movement cycle remain; weapon-specific
body reloads, directional strafing and airborne layering are outside this fix.
Ready, melee, grenade, landing, seat and death priorities retain their existing
paths. First-person animation payloads, weapon timers, ammo rules, meshes,
weights and colors are unchanged.

## Native evidence

- Ares v148, NTSC 320×240, 8 MiB, audio enabled. RDP validation reports no errors
  or warnings in either four-camera capture.
- Each version contains 72 native frames: 36 standing and 36 crouched. One frame
  is sampled every three simulation ticks, covering a complete AR reload and
  continued walking afterward. The actor stays at a fixed world position to
  make stride differences visible. Actual movement is tested with game input
  separately. Native photos exercise the near LOD; bank checks cover both LODs.
- The baseline renderer is `scene.c` from
  `9491bad485830367601310a033db199b7d21c57c`. Both ROMs use the final asset bank
  and identical fixture state. Build-input comparisons verify that only
  `scene.c` differs. This isolates rendering, rather than comparing divergent
  live combat trajectories.
- All 58 frames during reload change; all 14 frames after completion are
  pixel-identical. `pixel-checks.json` records per-frame changed-pixel counts.
  The comparison has exact PNGs, difference ×4, four-angle contact sheets and
  paired GIF previews. GIFs are palette previews; PNGs retain native pixels.
- Photos and their comparison page are archived privately at
  `assets/spartan-reload-appraisal/`. Raw pixel-readback logs and ROMs stay
  local. `provenance.json` records native log/ROM hashes and build-input hashes;
  its parent revisions plus content hashes identify the measured working tree.

An ordinary two-player Firefight smoke run completed **75 observations** on
retry. The earlier interrupted run is excluded. After five warm-up observations,
the living-human/landed-enemy subset averaged **23.06 FPS** (51 observations,
range 15–38). Whole-window mean was 29.20 FPS; minimum sampled free heap was
842,800 bytes. This is an uncapped emulator smoke run, not physical cartridge
timing or a new paired performance matrix. Changed animated hit surfaces can
change deaths and combat trajectories. The image-dumping fixture is never used
for performance claims. See `opening-2-native.log` and `opening-2-results.json`.

## Storage and validation

| Resource | Before | After |
| --- | ---: | ---: |
| `interactions.bin` | 12,107,536 B | 18,473,488 B |
| `player-hits.bin` | 1,285,008 B | 2,466,960 B |
| Largest streamed pose pair | 8,736 B | 8,736 B |
| Pose cache allocation | 70,912 B | 70,912 B |

The banks add **7,547,904 ROM bytes**. The atlas is streamed, not resident in
RDRAM; the existing eight large and eight small cache slots remain. Small pose
descriptors and state add metadata, so this is not a zero-total-RAM-growth claim.
The complete playable release ROM is **54,493,184 bytes**, within the 64 MiB
cartridge budget. The approved Covenant model bank remains selected.

Validation completed:

- Actual-input moving reloads for AR, pistol, sniper, rocket launcher, Needler
  and shotgun, standing and crouched. Gait advances without reset, ammo loads
  correctly and shotgun shell loops continue walking. Existing sustained-fire
  tests still pass (23 shots in two seconds in both stances).
- At fixed reload phase, changing gait alters 56 standing and 46 crouched
  collision silhouette rays. Source action priorities are checked.
- Independent source-mask oracle; 417,312 packed lower-body vertex samples
  unchanged across reload phases; direct crouch-base agreement. All 223
  preexisting pose clips are byte-identical, including first-person and firing.
- 11,460 exported ROM frames checked for aligned DMA ranges, source timings,
  conservative bounds and in-place crouched motion.
- Full 1–4-player Firefight lifecycle sanitizer suite; deferred animation-buffer
  lifetime test (10,000 fenced frames, 91,770 consumers).
- 37 runtime configurations / 148 N64 translation units, both validated native
  fixtures, ordinary two-player profiling ROM and playable release ROM build.

## Reproduce

From a checkout wired to the private asset bank and owned source caches, retain
the old bank before exporting. The committed baseline private asset revision is
`eb0c53eeb2fd3894706319afeaea83d1fb444315`:

```sh
mkdir -p build/spartan-reload
git -C halo64-assets show eb0c53e:generated/interaction_assets.c > build/spartan-reload/before-interaction_assets.c
git -C halo64-assets show eb0c53e:frontend-files/interactions.bin > build/spartan-reload/before-interactions.bin
git -C halo64-assets show eb0c53e:frontend-files/player-hits.bin > build/spartan-reload/before-player-hits.bin
git show 9491bad4:port/n64/scene.c > build/spartan-reload/before-scene.c
build/n64-python/bin/python port/n64/pack_interactions.py
build/n64-python/bin/python port/n64/extract_combat.py
build/n64-python/bin/python port/n64/test_maps.py --spartan-motion --output-dir build/spartan-reload/host-motion
build/n64-python/bin/python port/n64/test_spartan_reload.py --baseline build/spartan-reload
build/n64-python/bin/python port/n64/test_interaction_assets.py
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/spartan-reload/host-firefight
build/n64-python/bin/python port/n64/test_deferred_animation.py
```

Build the fixture with `build.py --spartan-reload-qa --firefight --validate`, the
SDK/Tiny3D paths and corrected-ground Blood Gulch override recorded in
`provenance.json`. The baseline additionally uses
`--scene-source build/spartan-reload/before-scene.c`. Give each a separate output
directory named `before` or `after` under `build/spartan-reload`. Build the
ordinary smoke case with `--pve-squad --pve-players 2 --pve-qa 3 --profile`
(`opening-2` directory), and the playable case with `--firefight --preset release`
(`playable` directory). All use the canonical model bank.

`capture.py ROM SETTINGS LOG` runs one owned Ares process and stops at 72
readback frames. Save `before-native.log` and `after-native.log` in the capture
directory. Never run captures concurrently. `compare.py CAPTURE OUTPUT`
decodes both logs and reproduces the photos, previews and pixel checks.
`collect.py CAPTURE` verifies the build comparison and archives test logs and
the completed `opening-2-native.log` summary. Copy the comparison's
`pixel-checks.json` beside this report. The exact SDK, compiler versions, build
options and Ares settings hash are recorded in `provenance.json`.
