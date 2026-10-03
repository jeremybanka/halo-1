# Blam code in the N64 demake

This ROM is **not the complete Blam engine**. Its renderer, collision, weapon and
vehicle simulation are N64 implementations. The local game-clock, seeded random
and hand-attachment quaternion interpolation routines are source-derived Blam
code used by the game. Baking original model animations and using original HUD
art does not make the renderer or gameplay simulation the original engine.

`blam/runtime.c` records the source of each adapted routine:

| Adapter | Repository source | N64 boundary |
| --- | --- | --- |
| Local 30Hz clock | `source/game/game_time.c`, `source/cseries/cseries.h` | Original local catch-up arithmetic and seven-tick limit; caller runs the returned ticks. No network clock or saved-game allocator. |
| Seeded random and ranges | `source/math/random_math.c` | Original LCG with explicit 32-bit wrap, used for weapon spread. |
| Hand-attachment rotation | `source/math/real_math.c` | Original shortest-hemisphere normalized quaternion interpolation, with zero-length identity fallback; XYZW arrays match the extracted animated hand poses used to position held weapons. |

The offline overlay-baking fix follows `overlay_animation_apply`: multiply
**overlay rotation by base rotation**, add translation only for nodes with the
translation flag, and retain base values for unflagged components. Reclaimer
supplies base defaults for unflagged components; applying those as deltas
doubles limb lengths. The reduction pipeline respects rotation and translation
flags. All nine selected clips have unit scale and no animated scale flags;
scale-channel animation is not implemented by the reduction pipeline.

## Direct engine build probe

Run `python3 port/n64/blam/probe_engine.py`. It writes commands, logs and a JSON
report to `build/n64/blam-probe/`. The probe uses the actual VR4300/O64 cross
compiler, existing XDK declarations, MSVC spelling adapters, and the repository's
forward-declaration generator. It does not modify original engine files.

GCC 16.2 compiled all seven sampled original translation units: random math,
game time, data arrays, model animation, objects, rasterizer and DirectSound.
This establishes that these C modules can compile for the CPU; it does not
establish that the whole engine links or runs. Section garbage collection and
relocation inspection found these unresolved boundaries for selected entrypoints:

| Entry point | Referenced external symbols | Examples |
| --- | ---: | --- |
| `seed_random` | 0 | Self-contained arithmetic |
| `game_time_update` | 15 | `game_tick`, network clock, frame/interpolation hooks |
| `data_new` | 5 | Allocator, assertions, C-series memory/string wrappers |
| `animation_get_node_orientations` | 10 | Tag data, model defaults, quaternion helpers |
| `objects_update` | 74 | Object types, collision partitions, animation, effects, AI, sound |
| `rasterizer_frame_begin` | 1 | `_rasterizer_frame_begin` platform backend |
| `platform_sound_dsound` | 58 | `DirectSoundCreate`, DirectSound buffers/streams, Xbox timers |

These counts are per entrypoint, not a total unresolved-symbol count for a full
link. Ordinary C-library functions are included. This is a representative probe,
not a compile audit of every translation unit.

The current native engine configuration reserves 16MiB of game state
(`port/linux/include/halo_port_capacity.h`). Its tag, texture and sound cache
capacities are 22+22+4MiB (`source/cache/physical_memory_map.c`), totaling 64MiB
before executable code, framebuffer and stack. These are configured capacities,
not a proof of the minimum possible memory footprint. They exceed even an
Expansion Pak N64's 8MiB and require a new allocation/streaming design. The
original tag cache also carries Xbox addresses and little-endian serialized
structures; compiling the C source does not translate those assets for a
big-endian N64.

A complete Blam port therefore still requires a linked N64 platform boundary,
reduced/streamed game-state and tag storage, verified endian and structure
layouts, original object/weapon/vehicle integration, and RSP/RDP/audio backends.
The existing demake only implements part of that work.

## Runtime checks

```sh
cc -std=c17 -O2 -Wall -Wextra -Werror -ffp-contract=off \
  port/n64/blam/test_runtime.c port/n64/blam/runtime.c -lm \
  -o build/n64/test_blam_runtime
build/n64/test_blam_runtime
```

Checks cover known Xbox-width random states, render-rate-independent 30Hz ticks,
pausing/catch-up behavior, quaternion endpoints, known rotation midpoints,
shortest-hemisphere interpolation, unit length, input/output aliasing and the
zero-length identity fallback. The same runtime cross-compiles warning-free for
VR4300/O64. Compile this module without fast-math to retain the source arithmetic;
renderer-specific fast-math flags should not apply to it.
