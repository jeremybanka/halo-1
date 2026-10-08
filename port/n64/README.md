# Blood Gulch for Nintendo 64

A four-player local Slayer demake built with libdragon and Tiny3D. It boots on
an emulated **4 MiB N64**, using the supplied Xbox disc for map, model,
animation, HUD and audio data. The Windows/desktop build is separate.

This is a playable N64 implementation, **not a complete port of Blam**.
Original Blam data arrays, object-header allocation and movable memory pools
now store live projectiles. Source-derived timing, deterministic random and
hand-attachment quaternion interpolation also run in the game. All four vehicle
drive routines and the shared mass-point rigid-body solver now run from the
reconstructed original source, using retail physics tags. Rendering and
most gameplay still use reduced N64 systems. An optional 8 MiB build uses the
original Blam BSP traversal and the complete Blood Gulch collision topology
for floor queries and raycasts.
[BLAM_STATUS.md](BLAM_STATUS.md) records the concrete compile/link/memory audit
and remaining engine work.

The remaining-weapon model audit and connected first-person hand repair are
documented in [WEAPON_OCCLUSION.md](WEAPON_OCCLUSION.md). Menu backdrop, sniper
display, first-person sleeves and original base geometry repairs are covered
in [GEOMETRY_REPAIRS.md](GEOMETRY_REPAIRS.md).
Source-based muzzle flashes, sniper smoke trails and sustained plasma charging
are documented in [WEAPON_EFFECTS.md](WEAPON_EFFECTS.md).
The source grass/sand bake and 64×64 paletted ground experiment are documented
in [GROUND_TEXTURES.md](GROUND_TEXTURES.md).

## Play

Load `build/n64/halo-blood-gulch-paced30-buffers5.z64` in ares as a Nintendo 64
cartridge for the recommended four-player presentation profile. Build it with
`build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5`.
The ordinary `halo-blood-gulch.z64` retains the unpaced presenter.
The latest quiet four-player Ares replay with the baked 64×64 ground measures
**28.5 displayed FPS overall / 29.0 in combat / 28.0 around vehicles**, with
46 KiB heap remaining. The 30 FPS target is not yet met. See
[GROUND_TEXTURES.md](GROUND_TEXTURES.md) and `build/n64/ground-experiment/`
for matching views and timing. Earlier pacing and model-audit measurements
predate later changes and are historical comparisons.
The original-style front end opens first. Follow **Multiplayer → Split Screen →
Select Profile → Blood Gulch → Slayer**. Join and ready one to four controllers;
three players use three quadrants. Assign Gamepads to controller ports 1–4 in ares,
then configure physical controllers or keyboard mappings in Settings → Input.
Any active player can press **Start** to pause and own the menu. Another
player's Start transfers ownership; the current owner's Start resumes.
**Setup** is enabled only for Player 1 and offers Restart Match or Quit Game.
**Controls** changes only the menu owner's layout. Player count is set by joining
controllers in the front end.
Every player starts with **N64** controls. Each player's choice survives match
restarts and player-count changes, but is not saved across power cycles.
The front-end Slayer preset ends at **15 kills**, followed by the original
Postgame Carnage Report and return to map selection. Debug replays retain their
25-kill default. See [FRONTEND.md](FRONTEND.md) for the menu tree, source
provenance, verification, and current limitations.

| Action | N64 (unchanged default) | Xbox style |
| --- | --- | --- |
| Walk / drive forward and backward | Stick up/down | D-up/down |
| Turn / aim horizontally | Stick left/right | Stick left/right |
| Strafe / slide the Ghost | C-left/right | D-left/right |
| Look up/down | C-up/down | Stick up/down |
| Jump on foot / brake in a vehicle | A | A |
| Fire primary weapon | Z | Z |
| Reload / pick up / enter or exit a vehicle | B | C-left |
| Switch carried weapon | R | C-up |
| Throw grenade; hold for mounted secondary fire | L | L |
| Cycle weapon zoom | D-up | C-right |
| Melee | D-down | B |
| Switch grenade type | D-left | Hold R, press C-up |
| Crouch / vehicle crouch modifier | D-right | C-down |
| View scores | — | Hold R |
| Pause / menu ownership / resume | Start | Start |

In the menu, D-pad or stick up/down moves the highlight, **A** selects, and
**B** goes back or resumes from the root. Left/right or A changes the selected
player count or control style. See [CONTROLS.md](CONTROLS.md) for ownership,
button-edge behavior and vehicle controls.

Approach the Warthog's left side for the driver, right side for the front
passenger, or rear for the gunner, then press **B** with N64 controls or **C-left**
with Xbox style. The nearest available entry marker selects the seat; HUD
interaction prompts show **B** or **C-LEFT** for that player's selected layout.
In Xbox style, holding R shows scores in that player's view without pausing.
R + C-up switches grenade type instead of switching weapons; scores stay visible until R is released.

Aim sets the vehicle's desired heading; the chassis responds through its
original solver. The moving Scorpion steers toward turret aim. Z fires its cannon and
L fires the machine gun. The Warthog has a driver,
independent turret gunner and passenger. Ghost and Banshee have forward plasma
weapons; the Banshee's L fires its secondary projectile. The tank also carries
two passengers. Both original rooftop teleporter pairs lead to their original
exits with a short re-entry cooldown.

## Implemented content

- Four independent players, cameras, shields, health, inventory, scores,
  respawns, motion sensors and weapon-specific reticles.
- Assault rifle, pistol, plasma pistol, plasma rifle, Needler, shotgun,
  sniper rifle and rocket launcher. Fragmentation and plasma grenades,
  charge/overheat, reloads, zoom, melee, tracking needles and supercombine.
  The assault rifle carries an animated on-weapon ammo counter using the Xbox
  digits; the Needler's crystals retract with its loaded ammunition.
- Warthog, Ghost, Scorpion and Banshee driving/flying, seats, mounted weapons,
  vehicle damage and respawning. The Banshee is an added demake option; its
  original model comes from the supplied campaign map, not Xbox Blood Gulch.
- Original weapon/power-up placements where present, plus extra weapon
  spawns to make the Xbox catalog accessible; health, grenades, overshield,
  active camouflage, and the original teleporters.
- Reduced original Spartan motion and first-person weapon/hand animation for
  idle, firing, reload/overheat and melee. Third-person motion includes running,
  jumping, throwing, death and separate Warthog driver, passenger and gunner
  poses. Warthog wheels and mounted
  weapon parts move; tank hull and turret aim separately.
- Compact cyan pixel HUD: upright 4×6 type, flatter shield/health bars,
  grenade silhouettes, and all 60 individual AR rounds in three rows.
  Weapon/vehicle reticles use symmetric pixel masks based on the originals; the original
  multiplayer motion sensor retains its artwork, opacity, size and placement.
  Pistol/sniper zoom uses reduced original masks and sniper markings with
  native 2×/10× labels. See [HUD_PIXELS.md](HUD_PIXELS.md).
  Reticles and aiming projection use the original Xbox title-safe centers,
  including the split-screen offsets; see [RETICLE_LAYOUT.md](RETICLE_LAYOUT.md).
- Original decoded shots, reloads, explosions, engines, footsteps, player
  effects, teleporters, announcer lines and outdoor ambience. A bounded stereo
  mixer supports simultaneous split-screen sound.

## Visibility and weapon display QA

The CPU culler submits geometry through a four-pixel margin beyond each view,
with conservative rounded effect bounds shared by all players. RSP triangle
clipping and the viewport scissor still use the actual view. See
[RENDER_MATRIX.md](RENDER_MATRIX.md), [RETICLE_LAYOUT.md](RETICLE_LAYOUT.md),
[FIRSTPERSON_AMMO.md](FIRSTPERSON_AMMO.md) and
[SCORPION_BARREL.md](SCORPION_BARREL.md) for source behavior and deliberate
N64 adaptations.

The local comparison gallery is `build/n64/visibility-weapon-qa/index.html`.
It includes source/before/after Scorpion views at several pixel sizes, actual
Ares four-player ammo screenshots, a live firing/reload recording, and an
edge fixture compared against disabled CPU bounds rejection. Timing and RDP
validation are separate tests bound to the exact ROM hashes in `builds.json`.
The canonical local `build/n64/release-manifest.json` identifies the current
recommended ROM; older six-showcase recordings retain their original provenance.

## Build

Run from the repository root. Assets and ROMs remain in ignored `build/n64/`;
only conversion and runtime source are tracked.

Requirements: Python **3.11** with `requirements.txt`, Blender 5.2.2,
libdragon with MIPS GCC 16.2, built Tiny3D, and the supplied Xbox USA Rev 2 disc.
The tested SDK revisions are libdragon
`494f1f586d3d6d5fc65b516a8ce29ccf42f85e15` and Tiny3D
`ec557373e986b5e041cc102a7ff787eb07921937`.

The default SDK locations are the sibling projects
`../n64-2048/.build/libdragon` and `../n64-3d-splitscreen/.build/tiny3d`.
Elsewhere pass `build.py --sdk /path/to/libdragon --tiny3d /path/to/tiny3d`,
or set `N64_INST` and `TINY3D_DIR`.
The normal build also needs the matching libdragon source checkout, defaulting
to the SDK's sibling `libdragon-src`, or supplied with `--libdragon-source`.
It builds a local CPU command-queue override with two 16 KiB buffers so CPU
work can overlap queued graphics. The shared SDK is unchanged. Use
`--rspq-buffer-kib 0` for the slower unmodified-SDK fallback; see
[RSPQ.md](RSPQ.md) for provenance checks and controlled comparisons.

```sh
# Reuse the existing venv and extracted maps when available.
python3.11 -m venv build/n64-python
build/n64-python/bin/pip install -r port/n64/requirements.txt
extract-xiso -x -d build/assets/halo-retail \
  'Halo - Combat Evolved (USA) (Rev 2).xiso.iso'

build/n64-python/bin/python port/n64/extract_assets.py \
  build/assets/halo-retail/maps/bloodgulch.map
blender --background --factory-startup --python port/n64/reduce_assets.py -- \
  build/n64/assets/bloodgulch-raw.json build/n64/assets/bloodgulch-reduced.json
build/n64-python/bin/python port/n64/extract_ground.py
build/n64-python/bin/python port/n64/pack_assets.py \
  build/n64/assets/bloodgulch-reduced.json
```

Then follow the six expanded extraction/reduction/packing commands in
[ASSET_PIPELINE.md](ASSET_PIPELINE.md), which also extract the Banshee from
`a30.map` and bake the first-person rigs. Finish with:

```sh
build/n64-python/bin/python port/n64/extract_menu_assets.py
build/n64-python/bin/python port/n64/validate_assets.py
build/n64-python/bin/python port/n64/build.py
build/n64-python/bin/python port/n64/build.py --demo
```

On this Mac Blender is `/Applications/Blender.app/Contents/MacOS/Blender` and
the XISO extractor is `build/tools/extract-xiso-build/extract-xiso`.

`--demo` produces the separately labeled `halo-blood-gulch-replay.z64`.
It drives the same simulation using deterministic inputs: 36 seconds of
nearby four-player weapon combat, followed by 39 seconds of vehicle gameplay,
including a Warthog gunner sequence. Staged starting/respawn positions and
loadouts are specific to this showcase; deaths, shots, boarding and driving
use the live gameplay rules. It is **scripted footage**, not a recording of
four human controllers. `--profile` adds N64 timing/memory counters;
`--validate` enables the expensive libdragon RDP command validator.
Instrumented ROM names end in `-validation` or `-profile`, preserving the
uninstrumented cartridge.

`--menu-qa --validate --paced30 --paced30-buffers 5` builds a separate scripted
menu test. It injects raw controller samples through the production input path,
checks all four menu owners, both styles, permissions, player counts and match
restart, then holds its `40/40 PASS` page. This is automated input verification;
the normal cartridge uses physical controller input. Original menu assets and
their adaptation are documented in [MENU_STYLE.md](MENU_STYLE.md).

`--benchmark` runs the four-player replay for a 75-second measured interval
after a one-second warmup, with no live diagnostic text. Its result pages
separate CPU frame acquisition from RDP completion / `display_show` callback
cadence and list the eight slowest completed frames with their scene metadata.
An additional page observes VI surface selection and counts fresh simulation
poses, repeated poses, skipped poses, retrace gaps and input-sample latency.
`--vi-benchmark` retains only that observer, with CPU/RDP profiling, draw
counters and live diagnostic text disabled. It is the preferred presentation
timing check. These emulator results do not establish real N64 hardware speed
or physical button-to-photon latency.
Add `--scores-benchmark` to `--vi-benchmark` to hold the Xbox score panels open
in all four views throughout the same replay. That separately named ROM checks
the overlay cost; the ordinary quiet run measures gameplay with panels closed.
`--snapshot-tick N` instead advances exactly N fixed replay ticks before
drawing, then repeatedly renders the frozen scene/HUD without input, menu or
FPS text. Snapshot ROMs are pixel-comparison fixtures, not performance tests;
they cannot combine with demo, showcase, benchmark, profile or validation modes.

To build the original BSP collision profile, enable the Expansion Pak in ares:

```sh
build/n64-python/bin/python port/n64/blam/tags/export_collision.py
build/n64-python/bin/python port/n64/build.py --blam-bsp
```

This produces `halo-blood-gulch-blam-bsp.z64` and requires **8 MiB RAM**.
`--blam-bsp` also combines with `--demo`, `--showcase`, `--profile` and
`--validate`. The original collision bank occupies 666,468 bytes. Floor and
ray traversal use the original BSP; player wall pushing still uses the reduced
triangle grid. It is an engine integration profile, not a completed Blam port.

Six focused recording scenarios also have separate ROM names:

```sh
build/n64-python/bin/python port/n64/build.py --showcase banshee
build/n64-python/bin/python port/n64/build.py --showcase frag-double-kill
build/n64-python/bin/python port/n64/build.py --showcase warthog-passenger
build/n64-python/bin/python port/n64/build.py --showcase shotgun-kill
build/n64-python/bin/python port/n64/build.py --showcase needler-supercombine
build/n64-python/bin/python port/n64/build.py --showcase needler-homing
```

For example, the first command produces
`build/n64/halo-blood-gulch-showcase-banshee.z64`. These scenarios stage positions
and loadouts, then drive ordinary gameplay inputs through the same simulation.
On-screen captions report observed game events. They are labeled **SCRIPTED**
and are intended to make specific actions reproducible in ares recordings.
Build these ROMs serially because the compiler object directory is shared.

## Memory and rendering

| Resource | Budget |
| --- | ---: |
| Blood Gulch BSP | 5,503 → 3,023 triangles; all 1,688 original architecture triangles retained |
| Spartan | 310 nearby / 127 distant triangles |
| First-person gun + hands | 391–526 triangles per Xbox weapon; 198 shared hand triangles |
| Sniper display | Four existing triangles use a separate 1,640-byte bank at 1/4096-unit precision |
| On-weapon AR counter | +4 triangles / +8 transformed vertices per visible AR |
| World weapons | 140–274 nearby triangles; separate distant pickup/held models |
| Vehicles | 242–380 nearby / 134–210 distant triangles, including part padding |
| Grenades | 62 frag / 48 plasma triangles |
| Model animation storage | 289,000 bytes after exact motion-track sharing and indexed vertices; scope and ammo supplements listed separately |
| World / first-person model vertices | 5,032 / 4,372; 150,464 vertex bytes combined, excluding the separate micro and scope banks |
| Ammunition display assets | 3,200-byte AR atlas + 1,056-byte panel animation + 18,128-byte Needler overlay = 22,384 bytes |
| AR counter runtime | 1,024 bytes of mutable digit buffers; eight cached command blocks |
| World materials | 17 × 32×32 RGBA16 |
| World vertex/index storage | 79,648 / 18,736 bytes |
| Conservative model bounds | 1,444 bytes; near/far unions and per-clip/part metadata |
| Collision mesh and grid | 72,238 bytes with shared float vertices |
| Color/depth buffers | 921,600 bytes with five color surfaces + depth; 768,000 with four; 614,400 for the ordinary triple-buffer build |
| Gameplay objects | fixed player/vehicle pools; bounded Blam arena for 48 projectiles; no per-tick system-heap allocation |
| Audio | 11,025 Hz source PCM, 22,050 Hz stereo output; 14 bounded voices |

Each camera independently culls world chunks and objects. Indexed vertex
batches, cached RSP display blocks, projected pickup/held-weapon LODs, cropped
HUD textures, and two sets of matrices and animated vertices reduce work.
Model indexing preserves positions, winding, original material identity, team
masks and complete animation trajectories. Its explicit per-model RGB limit is
48/255, with Ghost models kept at 24/255 and the first-person rocket launcher at
32/255 to preserve their identifying markings. Each shared color is an immutable
original corner; errors cannot accumulate through successive merges. The terrain
packer retains its separate 8/255 limit. The 59-entry audit checks identifying
colors at native target sizes.
Only visible character LODs are animated. Display color surfaces remain
independent of the two fenced geometry slots. RSP fences protect geometry
buffers before reuse.
Sibling object matrices avoid redundant camera reloads; exact current-pose
vehicle-part bounds skip offscreen parts using another 1,176 CPU-only bytes.
See [RENDER_MATRIX.md](RENDER_MATRIX.md) for the matrix-stack contract.
Animation writes use the CPU cache followed by explicit writeback. The game
uses Blam's local 30 Hz scheduler with bounded catch-up.

## Verification

The model comparison audit covers all eight Xbox multiplayer weapons in world
and first-person forms, shared hands, all four Spartan colors at both LODs,
four vehicles at both LODs, both grenades and three pickups. Each of 46 entries
compares original highest-detail source, preserved prior packed output, and
revised packed output from eight matching angles, with 160×120 and 48/24-pixel
size probes. See [ASSET_PIPELINE.md](ASSET_PIPELINE.md#model-comparison-audit)
for reproduction and the limits of these offline reference renders.
Thirteen additional distant pickup entries use 12/8-pixel size probes and are
excluded from that 46-entry aggregate because they have no prior distant bank.
The final 59-entry report keeps all 46 existing comparisons within a 0.03 loss
of source silhouette IoU relative to the approved quality build; this is an
offline shape check, not a frame-rate measurement.

The additional tiny-model audit covers twelve entries from eight angles,
at 4/6/8 pixels with four subpixel placements: 1,152 native-size comparisons.
Five rejected candidates retain their existing far models. The new layer is
restricted to already-distant pickups and vehicles in four-player views,
with zoom off and conservative projected bounds below 7.5 pixels. It adds
386 stored vertices and leaves the original 59-entry bank unchanged. See
[MICRO_LODS.md](MICRO_LODS.md) for recipes, quality decisions and target checks.

```sh
build/n64-python/bin/python port/n64/test_pack_animation.py
build/n64-python/bin/python port/n64/test_pack_mesh.py
build/n64-python/bin/python port/n64/test_pack_bounds.py
build/n64-python/bin/python port/n64/test_pack_terrain.py
build/n64-python/bin/python port/n64/test_geometry_bounded.py
build/n64-python/bin/python port/n64/test_vehicle_parts.py
build/n64-python/bin/python port/n64/test_render_matrix.py
build/n64-python/bin/python port/n64/test_render_segments.py
build/n64-python/bin/python port/n64/test_rspq_override.py
build/n64-python/bin/python port/n64/audit_models.py
```

```sh
# Regenerates vehicle/core/BSP data, then runs native/game/replay/showcase sanitizers.
build/n64-python/bin/python port/n64/blam/test_vehicle.py
cc -std=c17 -O2 -Wall -Wextra -Werror -ffp-contract=off \
  port/n64/blam/test_runtime.c port/n64/blam/runtime.c -lm \
  -o build/n64/test_blam_runtime
build/n64/test_blam_runtime
```

Tests use the generated map collision data and cover independent input,
terrain/ray traversal, weapon behavior and terrain occlusion, shields,
headshots, ammunition, grenades, supercombine, vehicle seats and weapons,
teleporters, power-ups, match completion/restart, and extended four-player
stress. The replay test runs two complete demo loops under ASAN/UBSAN.
The six focused showcase tests start with full shields and health, then verify
actual flight, driver/front-passenger seating, same-tick frag double kills,
shotgun kills, seven-hit Needler supercombines, and a single homing needle
turning before impact. They also verify kill ownership through awarded scores.

The final maintained tiny-model build was checked in ares v148 with Metal and
the Expansion Pak disabled. Its 95.743-second four-buffer graphics validation
recording ended with **zero RDP errors and zero warnings** through combat,
vehicles and respawns. All 2,826 video frames and the audio decode cleanly;
seven inspected full frames, including the actual final frame, retain clean
cumulative counters. The exact ROM, source and bank hashes, full-frame proofs,
audio measurements and known vehicle-camera limitations are in
`performance-audit/micro-production/validation-report.json`. An earlier
158.957-second private candidate run also passed. Neither diagnostic recording
is release-performance evidence.

Before the tiny-model layer, the audited model bank with indexed terrain, sibling matrices and
per-part culling completed 3,030 four-player frames over 75.018 measured seconds
at **40.3 FPS average** using the original presenter, guard band 2 and a 16 KiB
RSP queue. Completion intervals were **35.2 ms at p95 and 55.6 ms worst**;
255 frames exceeded 33.33 ms, so this does not establish sustained 30 FPS.
Combat averaged 40.3 FPS with 34.1 ms p95; vehicle scenes averaged 40.4 FPS
with 36.2 ms p95. Submitted vertices averaged 8,255 and peaked at 16,720.
These are RDP full-sync completion / `display_show` callback measurements,
not CPU acquisition intervals or VI scanout timing. The four result pages,
ROM hash and transcribed values are preserved in the local
`performance-audit/runtime-final48-results.json` and its linked recording.
Tail categories describe the completing scene's submitted geometry, not
per-category GPU time. The longest interval includes the replay's reset at
75 seconds; it remains in the reported distribution.
Emulator VPS measures host playback speed separately; the 30 Hz simulation
clock is independent of rendering.

The optional `--paced30` presenter avoids repeated simulation poses and queues
four-view presentation at every second VI retrace. New benchmark builds also
measure fresh displayed poses, missed deadlines and latency separately from
CPU and RDP throughput. See [PACING.md](PACING.md); compilation and portable
tests alone do not establish its target performance.
Before the tiny-model layer, quiet runs improved from 14 missed deadlines with three surfaces
to six with four and three with five, at respective mean input-sample-to-VI
latencies of 68, 100 and 129 ms. The remaining gaps are in vehicle scenes;
none of those earlier runs established sustained nominal 30 FPS. Exact phase results,
source differences and the memory/latency tradeoff are recorded in the pacing
notes and local audit. The default presenter is unchanged.

With the reviewed tiny-model layer, the final maintained four-buffer build
holds **nominal 30 FPS throughout the 75.017-second ares stress replay**:
2,244 fresh poses, all exactly two VI retraces apart, with zero missed
deadlines, duplicate displayed poses or dropped simulation ticks. Combat and
vehicle phases both pass. NTSC timing is truncated to 29.9 FPS on the result
page; its p95 and maximum interval are 33.4 ms. Six intermediate poses were
skipped. Input-sample-to-VI latency is 100 ms mean / 102 ms maximum, and live
free heap is 906 KiB. Exact evidence is in
`performance-audit/runtime-micro-production-four-results.json`.

This is ares timing, not physical-console validation. Ares v148 does not charge
physical RDP pixel, blending, antialiasing, depth and framebuffer-memory costs
to emulated CPU Count. See [PACING.md](PACING.md) for the source audit, measured
latency and remaining hardware limits.

The original-BSP profile's earlier validation used ares v147 with an 8 MiB
Expansion Pak and reported zero RDP errors/warnings and about 3,634 KiB of heap
headroom. Those measurements predate the model revision. Real N64 hardware
and four physical controllers have not been tested. RDP validation adds
substantial overhead and is not a release-build performance measurement.

## Gameplay videos

`record_ares.swift` records only the requested ares window and its application
audio using macOS ScreenCaptureKit (macOS 15+). `video_probe.swift` verifies
video/audio tracks, measures audio amplitude and exports a frame for inspection.
The recorder accepts an optional final PNG path. It writes a complete BGRA
screen-stream buffer directly, without H.264 decoding, filtering or cropping;
use this output for exact comparisons of frozen snapshot ROMs.
`video_clip.swift` copies a selected time range without generating or altering
gameplay frames. Its optional playback-rate argument changes timing for a
clearly identified slow-motion copy. The final model recordings, exact source
segments, audio checks and ROM checksums are local artifacts in
`build/n64/videos/micro-lod/index.html` and its `showcase-manifest.json`. The
previous optimized-bank recordings remain in `build/n64/videos/optimized/`;
earlier recordings are also preserved.

```sh
xcrun swiftc -parse-as-library port/n64/record_ares.swift -o build/n64/record-ares
xcrun swiftc -parse-as-library port/n64/video_probe.swift -o build/n64/video-probe
build/n64/record-ares halo-blood-gulch-replay build/n64/videos/gameplay.mp4 90
build/n64/video-probe build/n64/videos/gameplay.mp4 10 build/n64/screenshots/gameplay.png
# Optional direct screen-buffer PNG, useful with a frozen snapshot ROM:
build/n64/record-ares halo-blood-gulch-snapshot-1350 build/n64/videos/snapshot.mp4 3 build/n64/screenshots/snapshot-raw.png
```

Before recording, set ares **Settings → Drivers → Defocus** to **Block input**
instead of **Pause**. Otherwise moving focus to the terminal can produce an
entire video of one frozen frame. Start the recorder, wait for
`Recording ares window`, then choose **Nintendo 64 → Reset** so the clip includes
the opening events around two seconds. Keep the window visible and verify that
the scene advances. For benchmark captures, allow time for the CPU, RDP and both
tail pages plus the fifth VI page; a CPU-only capture cannot establish
completed-frame pacing or fresh displayed poses. Restore
**Pause** after the final recordings. When navigating ares through accessibility
tools, inspect only the relevant Drivers controls rather than expanding the
large shader/settings menu tree.

Focused recordings are `banshee-flight.mp4`, `frag-double-kill.mp4`,
`warthog-passenger.mp4`, `shotgun-kill.mp4`, `needler-supercombine.mp4` and
`needler-homing.mp4` in `build/n64/videos/micro-lod/`. An additional
`needler-homing-quarter-speed.mp4` shows the same recorded projectile at 0.25×
playback speed. All six use staged encounters and normal gameplay inputs,
with game audio and an on-screen SCRIPTED label. The shotgun encounter needs
two shots against full shields. The homing clip demonstrates a single launch
and shield hit rather than a kill. These focused one-, two- and four-view
scenes are gameplay evidence; the separate four-view benchmark measures timing.

## Remaining limits

This remains a demake, not Xbox gameplay parity or the complete original
engine. Vehicle dynamics use the original reconstructed solvers with bounded
world services; material damage, homing, biped collision and effect systems
remain simplified. Animation is sampled from a subset of source clips; there is
no complete animation graph, ragdoll or inverse kinematics. The coarse bases,
solid-color sky, flat model shading and reduced effects remain visible.
There is no campaign, networking, bots, CTF/ball objective rules, saved games,
or full Xbox shader/lightmap pipeline. HUD counters and status text use native
pixel artwork alongside original radar/reticle assets. Scope masks use alpha darkening instead of the Xbox
convolution/blur effect, and sniper night vision is not implemented. The PC-only
flamethrower is retained in development source data but its resident model,
animation and audio arrays are omitted by default. Both asset packers accept
`--pc-extras` to include those arrays; the Xbox scenario and replay still omit it.

Source `bloodgulch.map` SHA-256:
`50fe52406f075d975e24100a65b26ff696458023dd3509878953052ab0ef858f`.
Neither derived game assets nor generated ROMs are committed. The user's
`n64-3d-splitscreen` project informed rendering and split-view buffer management.

Yellow visor compensation and source-based vehicle explosions/wrecks are documented in [VEHICLE_DESTRUCTION.md](VEHICLE_DESTRUCTION.md).
