# Spartan locomotion during sustained fire — 28 October 2026

Spartans now continue their standing or crouched stride while firing. Previously,
each shot reset the shared animation clock and selected a whole-body firing clip
baked over idle. Muzzle flash also disabled the crouch locomotion blend.

## Source behavior and implementation

CE's `unit_handle_weapon_state_change` selects a weapon recoil overlay;
`unit_animation_start_overlay_action` stores it separately from the base action,
and `unit_preprocess_node_orientations` applies it to the current node pose
(`source/units/units.c`, functions at lines 3453, 3380 and 10479).

The port now advances a separate locomotion clock. The existing source
`stand rifle ar fire-1` overlay (five frames at 30 Hz) is composed with four
source bases: standing idle/run and crouched idle/run. These combinations are
skinned offline into ROM poses for both approved Spartan LODs, the right-hand
attachment and the original animated collision surfaces. Runtime interpolation
uses independent gait and shot phases, including intermediate crouch amounts.
Higher-priority ready, reload, melee, grenade, landing and seat actions retain
their existing paths. Source triangles, weights, colors and hit regions remain.

Native inspection also caught inherited root displacement in the crouch walk.
The exporter now removes that displacement from both render and collision
poses; the movement solver owns translation through the world. A bank-level
regression checks that both LODs and all five recoil samples articulate without
translating or snapping back across the loop.

This is an adaptation of CE's layering, not its complete animation graph:
the existing shared AR body recoil and common forward movement cycle remain.
Weapon-specific third-person recoil, directional strafing cycles and airborne
layering are outside this correction. First-person firing is unchanged.

## Native evidence and memory

- Ares v148, NTSC 320×240, 8 MiB. Native RDP readback captures 51 frames per
  version: 21 standing and 30 crouched, from four simultaneous angles.
- The fixture holds the actor at a fixed world position and resets shot age
  every three ticks while gait advances. Native images exercise the near LOD;
  exported-bank checks cover both LODs. Actual movement plus automatic fire is
  tested separately with real game input on the host.
- The before renderer is `scene.c` from `0f215b373bbe0f21a97501ee258da74bd01378fe`.
  Both ROMs use the same fixture, game state and final asset bank. This isolates
  the rendering change; it is not a replay of two live combat trajectories.
- Exact PNGs, paired GIF previews and the comparison page are in the private
  bank at `assets/spartan-motion-appraisal/`. Raw pixel-readback logs and ROMs
  stay local. `provenance.json` records their hashes and build input hashes.
  Capture manifests record the pre-commit parent revision; their content hashes
  identify the tested working-tree code. The earlier root-motion prototype is
  excluded from these results.
- Visual bank: 9,455,056 → 12,107,536 bytes; hit bank: 792,528 → 1,285,008.
  Combined ROM increase: **3,144,960 bytes**. Mesh complexity is unchanged.
- Largest pose-pair slot remains 8,736 bytes. The existing eight large and eight
  small cache slots still allocate **70,912 bytes** total; the atlas is streamed,
  not resident in RDRAM. Small pose descriptors, cache keys and a player clock
  add metadata; this is not a claim of zero total RAM growth.

An ordinary two-player Firefight smoke run completed 75 one-second observations.
After five warm-up samples, the living-human/landed-enemy subset averaged
**24.04 FPS** (47 observations, range 16–44). Whole-window mean was 30.80 FPS;
minimum sampled free heap was 853,248 bytes. This is an uncapped emulator run,
not cartridge timing, and not a new 1–4-player optimization comparison. Changed
hit poses can change deaths and combat trajectories. The image-dumping fixture
is never used for performance claims. See `opening-2-native.log` and
`opening-2-results.json` for the smoke capture and breakdown.

## Validation

- Actual automatic-fire movement: 23 shots in two seconds, uninterrupted gait;
  4.264 world units standing and 1.775 crouched. Fixed-shot-age collision scans
  change 33 standing and 38 crouched silhouette rays as gait advances.
- Source action priorities, 7,572 ROM frames, aligned DMA ranges, conservative
  bounds, source timings, approved first-person skins and crouch root ownership.
- Firefight full-set lifecycle for 1–4 players; all 26 multiplayer presets across
  13 maps, including source spawn weighting; deferred animation-buffer lifetime.
- 34 runtime configurations / 136 target translation units; release ROM and
  ordinary two-player profiling ROM built successfully.
- Host sanitizer suites cover movement, interactions, shields, collision,
  damage, weapons, effects, replay and vehicle showcase. The old replay test
  assumed all pilots survived the preceding duel. The new hit poses expose that
  assumption: the two-loop run covers three vehicle kinds. The test now also
  starts the real vehicle stage from a fresh replay and still requires coverage
  of all four kinds across the runs, without changing gameplay or disabling damage.

`map-dependency-check.json` records a narrow dependency refresh: the map packer
reads only the teleporter declaration from `game.c`; that declaration and the
packer were verified unchanged. Only the report's whole-file input hash changed;
map bank bytes did not.

## Reproduce

From a checkout wired to the private asset bank and owned source caches:

```sh
build/n64-python/bin/python port/n64/test_maps.py --spartan-motion --output-dir build/spartan-fire/host
build/n64-python/bin/python port/n64/test_interaction_assets.py
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/spartan-fire/host-firefight
build/n64-python/bin/python port/n64/blam/test_vehicle.py --output-dir build/spartan-fire/host-general
```

Build the native fixture with `build.py --spartan-motion-qa --firefight` and
the SDK, Tiny3D and corrected-ground Blood Gulch override used by the Firefight
benchmarks. The before build additionally uses `--scene-source` pointing to
the baseline renderer above. Each version needs its own `--output-dir`.
`capture.py ROM SETTINGS LOG` runs one owned Ares process and stops at 51 frames.
`compare.py CAPTURE_DIRECTORY OUTPUT_DIRECTORY` decodes `before-native.log` and
`after-native.log` into native PNGs and paired previews. Never run captures in
parallel or use this readback fixture for timing.
