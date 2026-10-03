# Blood Gulch for Nintendo 64

A standalone libdragon/Tiny3D demake of Halo's Blood Gulch, targeting the
original N64's 4 MB of RAM. The existing desktop port remains a separate build.
This proof of concept implements local splitscreen deathmatch: movement,
turning, strafing, looking up/down, jumping, terrain/wall collision, hitscan
rifles, ammunition, reloading, health, scoring, and respawning.

It starts with two horizontal views. Player 1 can switch to four quadrants or
one full view. Each visible player has independent simulation, camera, and HUD.

## Build

Run commands from the repository root. Game assets and ROMs stay in ignored
`build/n64/`; the repository contains extraction/build code only.

Requirements:

- Python **3.11**, with `port/n64/requirements.txt` installed in a venv.
- Blender 5.2.2 (the reduction was tested both through MCP and in background mode).
- A built libdragon SDK with MIPS GCC 16.2.0. Tested libdragon source revision:
  `494f1f586d3d6d5fc65b516a8ce29ccf42f85e15`.
- Built Tiny3D revision `ec557373e986b5e041cc102a7ff787eb07921937`.
- Your original Xbox USA Rev 2 `bloodgulch.map` (cache version 5).

The working SDKs from the sibling `n64-3d-splitscreen` and `n64-2048` projects
are used by default. Elsewhere, pass `--sdk /path/to/libdragon --tiny3d
/path/to/tiny3d` to `build.py`, or set `N64_INST` and `TINY3D_DIR`.
The reference project's `scripts/bootstrap-libdragon.nu` and
`scripts/bootstrap-tiny3d.nu` document installation of these pinned versions.

```sh
python3.11 -m venv build/n64-python
build/n64-python/bin/pip install -r port/n64/requirements.txt

# Skip this if the supplied ISO has already been extracted.
extract-xiso -x -d build/assets/halo-retail \
  'Halo - Combat Evolved (USA) (Rev 2).xiso.iso'

build/n64-python/bin/python port/n64/extract_assets.py \
  build/assets/halo-retail/maps/bloodgulch.map

blender --background --factory-startup --python port/n64/reduce_assets.py -- \
  build/n64/assets/bloodgulch-raw.json \
  build/n64/assets/bloodgulch-reduced.json

build/n64-python/bin/python port/n64/pack_assets.py \
  build/n64/assets/bloodgulch-reduced.json
build/n64-python/bin/python port/n64/build.py
```

On this Mac, Blender's executable is
`/Applications/Blender.app/Contents/MacOS/Blender`; the existing XISO tool is
`build/tools/extract-xiso-build/extract-xiso`.
Use the existing `build/n64-python` environment instead of recreating it.
Reclaimer's optional tag-definition diagnostics are retained in
`build/n64/assets/reclaimer.log`. The extraction rejects invalid geometry and
entirely black diffuse images rather than silently packing corrupt assets.

Output: **`build/n64/halo-blood-gulch.z64`**.

For repeatable emulator checks, `build.py --demo` generates a separate
`halo-blood-gulch-replay.z64`. Its visibly labeled replay cycles through
two-player movement/firing, four-player movement/firing, and two/four-view
overviews. `--validate` additionally enables the libdragon RDP validator and
costs substantial CPU time; measure performance on the release build.

## Play in ares

Load the `.z64` as a Nintendo 64 cartridge. This machine's reference emulator
is `../n64-3d-splitscreen/.build/emulators/ares-v147/ares.app`, using OpenGL 3.2.
The ROM also boots with the Expansion Pak disabled (4 MB total RAM).

Select **Gamepad** for the desired Nintendo 64 controller ports, then assign
physical controllers or keyboard keys in **Settings → Input**. The game uses
ports 1–4 directly. Keyboard keys are chosen in ares, not hardcoded in the ROM.

| N64 control | Action |
| --- | --- |
| Stick up/down | Move forward/backward |
| Stick left/right | Turn |
| D-pad | Digital alternatives to the stick |
| C-left/right | Strafe |
| C-up/down | Look up/down |
| A | Jump |
| Z | Fire |
| B | Reload |
| Player 1 Start | Cycle 2 → 4 → 1 views |
| Player 1 L | Toggle canyon overview |
| Player 1 R | Reset the match |

The HUD shows health, magazine ammunition, and kills. Four hits defeat a player;
they respawn after two seconds. Inactive players are excluded from combat.

## Asset and runtime budgets

The pipeline reads the actual BSP, spawn locations, diffuse maps, and lowest
Xbox model LODs. Blender welds and decimates the environment and Spartan, then
the packer converts Z-up Halo coordinates to Y-up, fixed-point N64 vertices.

| Resource | Current budget |
| --- | ---: |
| Blood Gulch BSP | 5,503 → **1,870 triangles** |
| Spartan | 310 → **170 triangles** |
| Assault rifle | **36 triangles** |
| Environment vertex storage | 91,104 bytes |
| Textures | 17 × 32×32 RGBA16; 34,816 bytes total |
| RDP texture memory at one time | 2,048 bytes |
| Collision mesh and spatial grid | 80,506 bytes |
| Environment draw chunks | 202, at most 60 vertices each |
| Color/depth buffers | 614,400 bytes, 320×240, triple color + shared depth |
| Release ROM | 360,448 bytes in the tested build |

Chunks are culled separately for every camera. RSP display blocks are cached;
three matrix/viewport slots are protected by RSP fences. Textures are rebound
after each view's HUD. Gameplay is fixed at 60 simulation steps/second, with
bounded catch-up. Terrain raycasts for weapons run only when a player could
actually be hit.

## Verification

```sh
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 \
  port/n64/test_game.c port/n64/game.c build/n64/generated/collision_data.c \
  -lm -o build/n64/test-game
build/n64/test-game
```

The host integration test uses the generated Blood Gulch mesh. It covers floor
queries, ray intersections, movement isolation, jumping/landing, damage,
terrain occlusion, scoring, respawn, reload, and inactive players.

On 2026-10-02, both the live ROM and scripted replay booted in ares v147.
Observed release readings included 44 FPS at the initial two-player view,
34 FPS for four first-person views, and 42 FPS for two overview views;
the four-camera whole-map overview dropped to
16 FPS. These are spot observations, not a sustained performance guarantee.
The 4 MB replay showed **2,712 KB of free heap**. Screenshots are saved beside
the ROM. No real N64 or physical multiplayer-controller test has been performed.

## Current limits

This is an initial demake, with static player poses and a coarse collision mesh.
The reduced bases and close-up surfaces need further geometric cleanup. There
are no vehicles, grenades, weapon pickups, shields, CTF/teleporters, bots,
networking, audio, campaign, original lightmaps, or Xbox shader effects.
The sky is a solid color. The overview camera can see the unfinished outer
edges of the BSP. Four-player performance is lower when all cameras see most
of the map.

Source map SHA-256:
`50fe52406f075d975e24100a65b26ff696458023dd3509878953052ab0ef858f`.
Geometry and textures remain derived from the user's local game data; neither
those assets nor the generated ROM are committed. Rendering and split-view
buffer management were informed by the user's `n64-3d-splitscreen` reference.
