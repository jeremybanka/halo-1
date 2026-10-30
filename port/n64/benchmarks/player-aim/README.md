# Visible player aiming — 30 October 2026

On-foot players now visibly aim up and down. The CE aiming screen composes over
the current movement and weapon action, including crouching, sustained firing
and reloading. The held weapon and animated collision surfaces follow the same
node pose. This work starts at main `f40fefee`; it retains main's independent
locomotion clock and the moving-fire and moving-reload fixes.

## Source behavior and implementation

`source/models/model_animations.c:1583` (`aiming_screen_apply`) supplies the
signed grid limits, yaw-then-pitch interpolation and selected node channels.
`replacement_animation_apply` at line 876 and
`source/units/units.c:10479` (`unit_preprocess_node_orientations`) establish the
base → replacement/action → aiming order. Normal aiming leaves zero residual
head-look pitch; melee and grenade throws use head look without the weapon aim
screen. Body yaw already follows player yaw, so the relative aiming yaw is zero.

The exporter reads the owned cyborg graph and preserves the approved mesh,
weights, colors and existing base/action sample counts. Uncompressed Reclaimer
overlay exports include a leading default frame; it is removed from the aim
grid, whose neutral pose is its center cell. Source-channel tests independently
read the original tag bytes to check that convention.

Nineteen node-local poses use signed 16-bit quaternion channels at 1/32767 and
positions at 1/4096 unit. Each aligned ROM frame is 272 bytes. Two frames are
streamed through a 544-byte scratch buffer. Normalized quaternion interpolation
composes standing and crouching separately, then blends the stance. Four cached
node hierarchies are shared by render LODs, the right-hand marker and hit tests.
Unchanged poses reuse their revision; unchanged collision surfaces reuse their
group bounds. No pose bank is loaded wholesale into RDRAM.

Skinning handles 192 unique points for the 562-vertex near mesh and 96 for the
250-vertex distant mesh. Color/normal seam duplicates copy an earlier result.
Bind positions are pretransformed into bone space; rigid vertices avoid weight
blending. Bounded coordinate rounding uses the CPU conversion instruction.
Overlay sampling decodes and interpolates only masked channels, and exact
grid cells fetch one frame. The CPU scratch reuses existing animation workspace.
Writes to render buffers remain deferred until a view requests them and obey the existing frame fences.
An analytic bound covers all normalized rotations and stance/action blends.

The existing shared rifle/AR body rig and forward stride remain. This is not the
complete CE unit animation state machine or a set of new weapon-specific body
stances. Seated and dead players retain their existing authored paths.

## Native evidence and performance

The native photo fixture covers ten states at five pitches, from −85.5° to
+85.5°, with four viewing angles in each framebuffer. States include standing,
running, running fire, crouching, crouched running fire, moving reload in both
stances, airborne, ready and melee. Baseline and candidate use identical frozen
state and assets; only the renderer differs. `compare.py` archives exact PNGs,
difference ×4, a contact sheet, per-frame pixel counts and build/log hashes at
private `assets/player-aim-appraisal/`. Both validated captures complete 51
frames (50 states plus a repeated first state), with no assertion or RDP
validation errors/warnings. Visual inspection confirms that the body and held
weapon follow pitch through firing and reload, while the legs retain their
standing, running or crouched pose. All 50 sampled comparisons change; neutral
poses can also differ because node interpolation replaces baked-vertex blending.
Photo readback is never timed.

Performance is measured separately in Ares, NTSC 320×240, 8 MiB, audio enabled,
paced 30 FPS, three surfaces and 32 KiB queues. `controlled.py` fixes four
players' positions and continuously varies pitch, crouch, gait, firing and
reload. It removes shots and AI so both renderers receive the same workload.
`run.py --settings build/player-aim/ares.bml --repeat 1` also measures the ordinary live replay, whose different aimed hit
surfaces can change combat trajectories. Those live averages cannot isolate
animation cost. Native emulator measurements are not physical cartridge timing.

The matched fixed-state run measures:

| Measurement | Main renderer | Aiming renderer |
| --- | ---: | ---: |
| CPU acquisition rate (paced) | 29.913 FPS | 29.877 FPS |
| Mean acquisition interval | 33.430 ms | 33.470 ms |
| p95 acquisition interval | 33.508 ms | 34.050 ms |
| Animation phase | 11.345 ms | 17.089 ms |
| Wait phase | 8.252 ms | 2.230 ms |
| Body + held triangles / frame | 3,047 | 3,300 |

The original run records a **5.744 ms** animation-phase difference in this
continuously changing four-player fixture. See the compiler-option caveat below
before attributing that difference solely to aiming. The
conservative aim bounds also submit more body/weapon geometry. Average paced
rate changes by −0.12%; this is not a claim of zero overhead. The initial
implementation took 25.359 ms in animation and missed the frame budget. Seam
reuse, bone-local bind points, bounded rounding and masked-channel sampling
reduced that cost by 32.6% before acceptance. `controlled.json` and its native
logs record the final measurement.

The ordinary 75-second replay measures **22.581 → 23.888 presented FPS**;
p95 is **66.866 → 66.860 ms**. Its combat and vehicle windows are reported
separately in `performance.json`. This is one sequential final pair after the
warm-up; the improved whole-run average is not evidence that aiming is free,
because changed collisions alter who survives and which work is visible.
Minimum sampled free heap is **3,784,168 → 3,759,624 bytes** in that replay.

**Historical comparison note:** the later Warthog muzzle audit corrected
`--scene-source` so alternate renderer filenames retain `scene.c`'s
`-fno-finite-math-only` option. The timings above preserve the original runs and
predate that correction; their baseline did not have identical compiler flags.
Use them as historical observations, not an isolated cost attribution. The
[Warthog audit](../warthog-muzzle/README.md) uses the corrected comparison path.

## Storage

| Resource | Cost |
| --- | ---: |
| Added streamed node bank | 150,960 B |
| Frame scratch | 544 B |
| Resident text/data/BSS delta, quiet replay ELF | +24,168 B |
| Complete playable Firefight ROM | 60,456,960 B |

The playable ROM remains below the 64 MiB cartridge limit. The matched replay
ROMs both include the node bank, so their 16,384-byte ROM-size difference does
**not** include the new streamed payload. `storage.json` separates ROM size
from the ELF resident sections. The original precomposed banks remain for
seated/dead fallback and existing code paths; this does not reclaim their ROM
space.

## Validation and reproduction

`test_player_aim.py` checks 558 original source-grid channels, 245 independent
signed-grid interpolation cases and 292,320 skinned vertex samples. The skin
oracle starts from the original approved mesh positions and weights; it also
checks collision movement, marker orthogonality, pose-cache reuse and bounds.
The maximum skin difference after the optimization is zero output units in
this sample set (the general tolerance is one 1/128-unit rounding step).

The existing moving-fire and moving-reload sanitizer tests cover actual game
input. The deferred animation test covers 10,000 fenced frames and 91,770
consumers. All **48 runtime configurations / 192 target translation units**
compile.
The full 1–4-player Firefight sanitizer suite and playable ROM build pass.
`configs.log`, `host-firefight.log`, `host-motion.log`, `deferred.log` and
`source-checks.json` retain the results.

Two older structural contracts already fail on untouched main `f40fefee`:
`test_scene_equivalence.py` rejects the changed `reset_view_state` against its
historical extraction checkpoint; `test_render_prepare.py` cannot resolve all
current inline/include helpers. `baseline-contracts.log` records those baseline
failures. Neither test was weakened to claim a passing full suite. The
non-PvE build also needed an unused-parameter annotation for main's damage
region parameter; host runners now link main's HUD damage bank. Regenerating
Blood Gulch after that annotation produced byte-identical map data; only its
input provenance hash changed.

From a checkout wired to the private bank and owned source caches:

```sh
build/n64-python/bin/python port/n64/extract_player_aim.py
build/n64-python/bin/python port/n64/test_player_aim.py
build/n64-python/bin/python port/n64/test_maps.py --spartan-motion --output-dir build/player-aim/host-motion
build/n64-python/bin/python port/n64/test_deferred_animation.py
build/n64-python/bin/python port/n64/benchmarks/player-aim/controlled.py build
build/n64-python/bin/python port/n64/benchmarks/player-aim/controlled.py run --settings build/player-aim/ares.bml
```

Build the photo fixture with `build.py --player-aim-qa --validate` and explicit
SDK/Tiny3D paths. Build its baseline with the additional
`--scene-source build/player-aim/baseline-scene.c`, extracted from `f40fefee`.
Use output directories `build/player-aim/photos` and `photos-baseline`.
The existing `benchmarks/spartan-motion/capture.py ROM SETTINGS LOG` captures
51 frames (50 states plus the repeated first frame). Save `native.log` in each
directory, then run:

```sh
build/n64-python/bin/python port/n64/benchmarks/player-aim/compare.py build/player-aim halo64-assets/assets/player-aim-appraisal
```

The complete playable recipe retains the latest Firefight roster, shield and
vehicle LOD banks:

```sh
build/n64-python/bin/python port/n64/build.py --firefight --preset release \
  --pve-crunch --pve-roster --pve-jackal-shields --vehicle-distance-lods \
  --pve-model-bank build/vehicle-lods/bank --enemy-vehicle-bank build/vehicle-lods/bank \
  --map-bank-override build/pve/ground/bloodgulch.map64 \
  --sdk "$SDK" --tiny3d "$TINY3D" --output-dir build/player-aim/release
```

`collect.py` verifies that only the renderer differs between the matched
fixtures, archives compact native logs and records hashes and ELF sizes. The
private `builds.json` retains all seven exact build manifests.

Source scripts, compact test/measurement logs and hashes are public. Derived
game imagery, packed node data and capture build manifests stay in the private
asset bank. ROMs and full pixel-readback logs remain local.
