# Blood Gulch for Nintendo 64

A four-player local Slayer demake built with libdragon and Tiny3D. It boots on
an emulated **4 MiB N64**, using the supplied Xbox disc for map, model,
animation, HUD and audio data. The Windows/desktop build is separate.

This is a playable N64 implementation, **not a complete port of Blam**.
Original Blam data arrays, object-header allocation and movable memory pools
now store live projectiles. Source-derived timing, deterministic random and
hand-attachment quaternion interpolation also run in the game. Rendering and
most gameplay still use reduced N64 systems. An optional 8 MiB build uses the
original Blam BSP traversal and the complete Blood Gulch collision topology
for floor queries and raycasts.
[BLAM_STATUS.md](BLAM_STATUS.md) records the concrete compile/link/memory audit
and remaining engine work.

## Play

Load `build/n64/halo-blood-gulch.z64` in ares as a Nintendo 64 cartridge.
Four views start immediately. Assign Gamepads to controller ports 1–4 in ares,
then configure physical controllers or keyboard mappings in Settings → Input.
Player 1's Start menu selects one, two or four players and restarts the match.
Slayer ends at **25 kills**, with a winner panel and announcer audio.

| N64 control | Action |
| --- | --- |
| Stick up/down | Walk, or drive forward/backward |
| Stick left/right | Turn / aim |
| C-left/right | Strafe; steer the Scorpion hull |
| C-up/down | Look up/down |
| A | Jump; hold to raise the Banshee |
| Z | Fire primary weapon |
| B | Reload / pick up a nearby weapon / enter or exit a vehicle |
| R | Switch between the two carried weapons |
| L | Throw grenade; hold for mounted secondary fire |
| D-up | Cycle weapon zoom |
| D-down | Melee |
| D-left | Switch grenade type |
| D-right | Crouch; lower the Banshee |
| Player 1 Start | Pause / match options |

Approach the Warthog's left side for the driver, right side for the front
passenger, or rear for the gunner, then press B. The nearest available entry
marker selects the seat.

The Scorpion's stick aims its turret independently; C-left/right steer its
hull. Z fires the cannon and L fires the machine gun. The Warthog has a driver,
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
- Original HUD artwork, digits, shield/health bars, grenade icons, vehicle
  reticles and multiplayer radar opacity. Pistol/sniper zoom adds reduced
  original split-screen masks, sniper markings and 2×/10× labels. Layout is
  adapted to the N64 viewports.
- Original decoded shots, reloads, explosions, engines, footsteps, player
  effects, teleporters, announcer lines and outdoor ambience. A bounded stereo
  mixer supports simultaneous split-screen sound.

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
build/n64-python/bin/python port/n64/pack_assets.py \
  build/n64/assets/bloodgulch-reduced.json
```

Then follow the six expanded extraction/reduction/packing commands in
[ASSET_PIPELINE.md](ASSET_PIPELINE.md), which also extract the Banshee from
`a30.map` and bake the first-person rigs. Finish with:

```sh
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
| Blood Gulch BSP | 5,503 → 1,870 triangles |
| Spartan | 460 nearby / 151 distant triangles |
| First-person gun + hands | 467–587 triangles per weapon; 211 shared hand triangles |
| World weapons | 174–274 triangles |
| Vehicles | 554–808 nearby / 235–271 distant triangles, including part padding |
| Grenades | 62 frag / 64 plasma triangles |
| Model animation storage | 484,257 bytes after lossless track sharing and clip-local byte offsets |
| World materials | 17 × 32×32 RGBA16 |
| World vertex storage | 91,104 bytes |
| Collision mesh and grid | 80,506 bytes |
| Color/depth buffers | 614,400 bytes: triple 320×240 color + depth |
| Gameplay objects | fixed player/vehicle pools; bounded Blam arena for 48 projectiles; no per-tick system-heap allocation |
| Audio | 11,025 Hz source PCM, 22,050 Hz stereo output; 14 bounded voices |

Each camera independently culls world chunks and objects. Cached RSP display
blocks, distant model LODs, batched HUD digits, and two sets of matrices
and animated vertices reduce work. The three display color buffers remain
independent. RSP fences protect geometry buffers before reuse.
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

```sh
build/n64-python/bin/python port/n64/test_pack_animation.py
build/n64-python/bin/python port/n64/audit_models.py
```

```sh
python3 port/n64/blam/prepare_core.py
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 -Ibuild/n64/blam-core \
  -Wno-multichar -Wno-unused-function -fno-strict-aliasing -fwrapv \
  port/n64/test_game.c port/n64/game.c port/n64/blam/runtime.c \
  port/n64/blam/core.c build/n64/generated/collision_data.c -lm -o build/n64/test-game
build/n64/test-game
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 -Ibuild/n64/blam-core \
  -Wno-multichar -Wno-unused-function -fno-strict-aliasing -fwrapv \
  port/n64/test_replay.c port/n64/replay.c port/n64/game.c \
  port/n64/blam/runtime.c port/n64/blam/core.c build/n64/generated/collision_data.c \
  -lm -o build/n64/test-replay
build/n64/test-replay
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 -Ibuild/n64/blam-core \
  -Wno-multichar -Wno-unused-function -fno-strict-aliasing -fwrapv \
  port/n64/test_showcase.c port/n64/showcase.c port/n64/game.c \
  port/n64/blam/runtime.c port/n64/blam/core.c build/n64/generated/collision_data.c \
  -lm -o build/n64/test-showcase
build/n64/test-showcase
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

The revised model build was checked in ares v148 with Metal and the Expansion
Pak disabled. Four-player profile scenes left about 135 KiB of heap headroom.
The revised RDP validation replay reported zero errors and zero warnings
through combat and vehicle phases; its recording is included in the local audit.
The extra geometry has a performance cost: selected heavier four-view combat
and mixed vehicle scenes rendered around 9–11 FPS. These samples are not a
full-run minimum/maximum or a locked frame-rate guarantee. Counters measure
emulated N64 time; emulator VPS measures host playback speed separately. The
30 Hz simulation clock is independent of rendering.

The original-BSP profile's earlier validation used ares v147 with an 8 MiB
Expansion Pak and reported zero RDP errors/warnings and about 3,634 KiB of heap
headroom. Those measurements predate the model revision. Real N64 hardware
and four physical controllers have not been tested. RDP validation adds
substantial overhead and is not a release-build performance measurement.

## Gameplay videos

`record_ares.swift` records only the requested ares window and its application
audio using macOS ScreenCaptureKit (macOS 15+). `video_probe.swift` verifies
video/audio tracks, measures audio amplitude and exports a frame for inspection.
`video_clip.swift` copies a selected time range without generating or altering
gameplay frames. Its optional playback-rate argument changes timing for a
clearly identified slow-motion copy. The final recordings and ROM checksums are local artifacts in
`build/n64/videos/` and `build/n64/release-manifest.json`.

```sh
xcrun swiftc -parse-as-library port/n64/record_ares.swift -o build/n64/record-ares
xcrun swiftc -parse-as-library port/n64/video_probe.swift -o build/n64/video-probe
build/n64/record-ares halo-blood-gulch-replay build/n64/videos/gameplay.mp4 90
build/n64/video-probe build/n64/videos/gameplay.mp4 10 build/n64/screenshots/gameplay.png
```

Focused recordings are `banshee-flight.mp4`, `frag-double-kill.mp4`,
`warthog-passenger.mp4`, `shotgun-kill.mp4`, `needler-supercombine.mp4` and
`needler-homing.mp4` in `build/n64/videos/`. An additional
`needler-homing-quarter-speed.mp4` shows the same recorded projectile at 0.25×
playback speed. All six use staged encounters and normal gameplay inputs,
with game audio and an on-screen SCRIPTED label.

## Remaining limits

This remains a demake, not Xbox gameplay parity or the complete original
engine. Vehicle physics, material damage, homing, collision and effect systems
are simplified. Animation is sampled from a subset of source clips; there is
no complete animation graph, ragdoll or inverse kinematics. The coarse bases,
solid-color sky, flat model shading and reduced effects remain visible.
There is no campaign, networking, bots, CTF/ball objective rules, saved games,
or full Xbox shader/lightmap pipeline. HUD art is original, but menus and status
text remain simplified. Scope masks use alpha darkening instead of the Xbox
convolution/blur effect, and sniper night vision is not implemented. The PC-only
flamethrower is retained in development source data but its resident model,
animation and audio arrays are omitted by default. Both asset packers accept
`--pc-extras` to include those arrays; the Xbox scenario and replay still omit it.

Source `bloodgulch.map` SHA-256:
`50fe52406f075d975e24100a65b26ff696458023dd3509878953052ab0ef858f`.
Neither derived game assets nor generated ROMs are committed. The user's
`n64-3d-splitscreen` project informed rendering and split-view buffer management.
