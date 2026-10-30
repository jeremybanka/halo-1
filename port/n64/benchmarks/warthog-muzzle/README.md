# Warthog muzzle flash — 30 October 2026

The Warthog chaingun now shows its source muzzle flash on actual shots. The
effect follows the rendered gun through turret yaw, elevation and hull motion,
and is shared by every split-screen view. This change builds on player aiming
commit `9bd15eef` and retains the recent main firing/reload fixes.

## Cause and source animation

`weapon_effects.c` deliberately excludes mounted shots from personal weapon
effects. That prevents a driver or gunner from flashing the infantry weapon
they carried before boarding. There was no corresponding mounted flash draw
path; setting the vehicle's generic `flash` timer did not draw anything.

The owned `vehicles\warthog\warthog gun` weapon links
`vehicles\warthog\effects\warthog gun fire`. Its flash emitter uses:

- `effects\particles\flash\flash h generic`, attached to `primary trigger` on
  node 8 (`frame gun`), with a 0.1-unit forward offset;
- a white, self-illuminated, screen-facing sprite with radius 0.275–0.2875 unit;
- three initial sequence variants, each containing one sprite, with no loop
  or final sequence, and `animate_once_per_frame` enabled;
- no random starting angle or angular velocity.

`source/effects/particles.c:particle_next_sequence`, `particle_next_frame` and
`particle_update_frame_time` show that the initial sequence is a random variant,
then the particle ends when that one-frame sequence finishes. The tag's 0.3 s
lifespan does not make this a 0.3 s glow. `source/render/render_particles.c`
transforms attached particles through their object's current node matrix;
`source/render/render_sprite.c` applies the sprite registration point.

The separate four-frame vehicle `firing` model overlay translates the chain and
gun and rotates barrel node 13. This patch attaches the flash to the port's
existing posed gun matrix. That separate mechanical recoil/spin overlay remains
outside this muzzle-flash change.

## Implementation and bounds

`extract_warthog_flash.py` preserves all three source shapes, crop registration,
the source marker/offset and the mean source radius. The sprites are reduced to
16×16 RGBA32 using the same bounded-alpha approximation as existing weapon
effects. The private bank stores the extracted imagery, packed data and source
hashes; the public repository contains the recipe and audit only.

Real gunner fire events set one pending flash for that vehicle. Preparing a
rendered frame consumes the pending state once; all views then see the same
variant. A shot survives simulation catch-up until a frame can display it.
Variants cycle deterministically, without consuming gameplay randomness.
Trigger release creates no new flash. Reset and inactive vehicles suppress old
state. Driver/passenger shots cannot masquerade as chaingun shots.

The renderer uses the existing gun-part matrix, including the full hull basis.
Flash bounds are prepared with that pose and cached alongside the vehicle's
other bounds. They are culled separately from the body, so a flash near a screen
edge remains visible without expanding vehicle-body submissions. The effect
uses the existing frame-fenced, per-view quad workspace, depth testing and
non-depth-writing transparency. It costs two triangles per visible firing gun
per view and retains the four reserved first-person effect slots. No new vertex
buffer allocation or particle pool is needed.

Visible flashes share one render-state setup per viewport. Consecutive guns
using the same variant also share the texture upload; each quad still owns its
separate fenced vertex slice. The empty-mask path submits no drawing work.

## Validation and native evidence

The host sanitizer test fires 24 real mounted shots, sees all three variants,
and checks agreement across four view consumers, catch-up, release, reset,
inactive vehicles and driver/passenger filtering. Existing infantry firing,
charge, sniper trails and explosion state tests still pass. All 49 runtime
configurations / 196 translation units compile. The deferred buffer test still
passes 10,000 fenced frames and 91,770 consumers.

The validated native fixture alternates resting/firing poses and covers level,
left/right yaw, downward/upward elevation and a tilted hull. The first 25 frames
use four external angles; the next 25 retain the production gunner camera.
Each capture includes the repeated first state for 51 readbacks. Baseline and
candidate use the same frozen state and assets, with only `scene.c` changed.
**All 25 resting frames are pixel-identical; all 25 firing frames change**
(80–1,108 pixels across the four-view framebuffer). `compare.py` enforces both
conditions. Both captures complete with zero RDP validation errors/warnings. The private `assets/warthog-muzzle-appraisal/` gallery retains exact
PNGs, differences, previews and build/log hashes. Readback captures are never
used for timing.

`controlled.py` measures a separate four-Warthog scene at a worst-case firing cadence:
all four guns emit every simulation tick. Both variants receive identical fixed
state and continuously varying pitch, without AI, damage or physics divergence.
The run uses Ares, NTSC 320×240, 8 MiB, audio enabled, paced30 and 32 KiB queues.
These are emulator measurements, not physical cartridge timings. An initial
fixture run overflowed an unsigned coordinate on the baseline before measuring;
that diagnostic setup error was corrected and the failed run is excluded.
The comparison build now also preserves `scene.c`'s compiler flags when using
an alternate filename; a regression assertion checks exact option equality.
Earlier measurements with the mismatched flag are excluded.

The final sequential pair runs for 75 measured seconds after warm-up. The
baseline reproduced its earlier result exactly. `controlled.json` and the
compact native logs bind these results to the ROM hashes:

| Measurement | Before flash drawing | Batched flash drawing |
| --- | ---: | ---: |
| CPU acquisition rate (paced) | 28.047 FPS | 27.234 FPS |
| Mean acquisition interval | 35.654 ms | 36.719 ms |
| p95 acquisition interval | 66.823 ms | 66.843 ms |
| Object phase | 1.227 ms | 2.371 ms |
| Triangles / frame | 10,135 | 10,167 |
| Minimum sampled free heap | 3,890,784 B | 3,888,720 B |

The continuous-fire fixture loses **2.90%** acquisition rate. Its 32 added
triangles are exactly four guns × four views × two triangles. This is a
100%-duty presentation stress test; the real mounted gun fires at 12 Hz and
does not flash on every 30 Hz tick. It is not a whole-game FPS prediction.
Both ROMs include the same event handling and asset bank; the comparison
isolates the renderer integration. Neither reports queue overflow or geometry
fence waits. Per-phase timings can include downstream pipeline stalls.

The complete playable release uses **5,216,628 B** of ELF text/data/BSS,
**5,480 B** more than the preceding player-aiming release. That includes the
three textures' **3,072 B**. Both playable ROMs remain **60,456,960 B** because
of cartridge padding. The matched stress ROMs include the same textures, so
their size difference is not the complete feature storage cost. `storage.json`
keeps those comparisons separate.

## Reproduce

Use a checkout wired to the private bank and owned source cache:

```sh
build/n64-python/bin/python port/n64/extract_warthog_flash.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py --only weapon-effects --output-dir build/warthog-muzzle/host
build/n64-python/bin/python port/n64/test_deferred_animation.py
build/n64-python/bin/python port/n64/benchmarks/warthog-muzzle/controlled.py build
build/n64-python/bin/python port/n64/benchmarks/warthog-muzzle/controlled.py run
```

The native fixture is `build.py --warthog-flash-qa --validate` with SDK/Tiny3D
overrides. Its baseline adds `--scene-source build/warthog-muzzle/baseline-scene.c`
from `9bd15eef`. Use `photos` and `photos-baseline` output directories below
`build/warthog-muzzle`. The existing
`benchmarks/spartan-motion/capture.py ROM SETTINGS LOG` captures the 51 frames;
save each as `native.log`. Then run:

```sh
build/n64-python/bin/python port/n64/benchmarks/warthog-muzzle/compare.py build/warthog-muzzle halo64-assets/assets/warthog-muzzle-appraisal
build/n64-python/bin/python port/n64/benchmarks/warthog-muzzle/collect.py
```

The playable build retains the current Firefight/roster/shield/vehicle LOD flags
and corrected-ground map from the player aiming release. Exact options,
toolchain revisions and input hashes are retained in the private build
manifests. Source code, compact logs and hashes remain public; ROMs and full
pixel-readback logs remain local.
