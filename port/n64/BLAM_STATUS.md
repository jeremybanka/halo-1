# Blam engine integration on N64

The complete Blam engine is **not running on N64**. The running game now uses
original Blam object storage, in addition to the source-derived clock, random
and quaternion routines. The optional **8 MiB `--blam-bsp` build** also uses the
original Blood Gulch collision BSP and original traversal functions for terrain
rays and floor queries. Weapon, unit and vehicle behavior, wall pushing,
rendering and audio mixing still use the demake implementations.

## Code actually used by the game

| Runtime boundary | Original source | Active use and limits |
| --- | --- | --- |
| Local 30 Hz clock | `source/game/game_time.c` | Original local catch-up arithmetic and seven-tick cap; the caller invokes the demake tick. No original network clock or `game_tick`. |
| Seeded random and ranges | `source/math/random_math.c` | Original LCG with explicit 32-bit wrap, used for weapon spread. |
| Hand-attachment rotation | `source/math/real_math.c` | Original shortest-hemisphere normalized quaternion interpolation, used by animated held weapons. |
| Salted data arrays | `source/memory/data.c` | Actual original source allocates and validates the live projectile object headers. Stale handles are rejected. |
| Movable object memory | `source/memory/memory_pool.c` | Actual original source allocates/frees live projectile payloads and compacts holes while updating stable header references. |
| Object header creation/deletion | `source/objects/objects.c` | Exact `object_header_new` and `object_header_delete` functions connect the data array to the movable pool. Payloads remain demake projectile records, not native `projectile_datum` records. |
| BSP segment traversal, 8 MiB profile | `source/physics/collision_bsp.c`, `source/physics/bsp2d.c`, `source/math/real_math.h` | Complete original traversal/polygon/projection functions operate on the original map's eight collision arrays. Terrain shots, projectile obstruction, explosion occlusion and floor queries use this path. Wall pushing still uses the reduced triangle grid. |

`blam/prepare_core.py` and `blam/prepare_collision.py` generate build copies from
these repository sources. Original files stay unchanged. Each generated source
manifest records its input SHA-256 and bounded adaptations; generated source and
game data stay in ignored `build/n64/`.

The core boundary fixes the data-array name-derived salt to retain Xbox
little-endian byte order, makes salt shifts explicitly unsigned, and fixes the
original reverse iterator's extra read before an array with a leading hole.
The movable pool retains four-byte alignment on N64; host tests use native
pointer alignment. Target compile-time assertions verify the original 56-byte
data array, 56-byte pool, 24-byte block and 12-byte object-header layouts.
Projectile accessors reacquire movable payload pointers after allocation/ticks.

The collision boundary makes Xbox `long` fields explicitly 32-bit for agreement
between host tests and N64. It removes Xbox profiling-timer calls, retaining the
collision arithmetic. The eight array strides and 96-byte N64 root match the
original definitions. The bank is **666,372 bytes plus its 96-byte root**;
planes and positions preserve their exact source float32 values. Conversion
between Halo XYZ and the demake's coordinate system occurs at the game boundary.
This profile requires an Expansion Pak and has a separate ROM filename.

Original animation and HUD assets do not make their playback/rendering code the
original engine. The offline overlay baker follows `overlay_animation_apply`:
overlay rotation multiplies base rotation, translation applies only to flagged
nodes, and unflagged components retain the base pose. Selected clips have unit
scale; the reduction pipeline does not implement animated scale channels.

## Complete-source architecture audit

Run:

```sh
python3 port/n64/blam/audit_engine.py
```

The audit compiles **all 466 game translation units** selected by the repository's
native build manifest for **VR4300, O64, big-endian MIPS**. Eleven excluded source
files are third-party utilities/examples or x86 assembly support. All 466 compile
successfully with MSVC declaration/COMDAT adapters and conversion of the `ui64`
integer-literal suffix. It does not provide fake game or platform implementations.
This compile accepts diagnostics from the reconstructed source; it is not a
warning-free or full-layout certification. Xbox structured-exception syntax is
only made parsable, not implemented. An SDK symbol's presence also does not prove
ABI compatibility, particularly for Xbox's 16-bit wide-character interfaces.

A section-retaining partial link rooted at `game_initialize`,
`game_initialize_for_new_map`, `game_tick` and `game_frame` succeeds, but retains
**392 unresolved referenced symbols**. Therefore it is **not an executable**.
The report lists each symbol and its boundary; ordinary SDK library names and
missing reconstructed COMMON storage are included in that count. Examples:

- Xbox graphics: D3D resources, vertex submission, render states, transforms,
  pixel shaders, visibility tests and presentation.
- Xbox audio: DirectSound buffers, playback, volume, pitch and loop regions.
- Operating system, input, files, saves, clocks, synchronization and network APIs.
- Bink video and platform message/logging interfaces.
- Desktop-port network/interpolation/high-resolution UI hooks and reconstructed
  globals that are supplied outside the original source tree on desktop.

The retained object contains **2,157,609 text bytes, 146,513 data bytes and
3,007,162 BSS bytes: 5,311,284 bytes before dynamic game/tag pools, framebuffers
or platform backends**. This is a measured build with the existing native
capacity configuration, not a claim about the minimum possible port size.
That configuration separately reserves 16 MiB of game state, plus 22+22+4 MiB
of tag, texture and sound caches. Both static reachability and pool/streaming
budgets must change for an N64 executable. Merely resolving symbol names does
not solve those allocations or Xbox GPU behavior.

Commands, per-source diagnostics, retained relocation information and the JSON
report are in `build/n64/blam-engine-audit/`. Repeat `--root SYMBOL` to inspect
a narrower original entrypoint. `probe_engine.py` remains a smaller seven-unit
probe; its per-entrypoint missing-symbol counts are not the full-engine total.

## Native tag work and remaining engine boundaries

`blam/tags/` audits the actual supplied Xbox caches and exports a prototype
big-endian gameplay metadata package. The thirteen selected roots (eight retail
weapons, multiplayer cyborg, three Blood Gulch vehicle classes and campaign
Banshee) reach **1,565 namespaced tags**, with **1,668,566 fixed/reflexive metadata
bytes**, excluding raw bitmap/audio/model/animation payloads. Tag references are
resolved within that registry.

The prototype exports **91 gameplay tags** with **242,916 payload bytes**
(**294,504 bytes including registry/relocations**). Source-layout probes cover
runtime fields omitted by HEK descriptions. Its manifest reports zero unknown
nonzero ranges and no omitted raw payloads within these selected classes.
Validation compares 21,337 scalar locations, including 329 native runtime
fields, directly with the supplied cache bytes. The prototype loader validates
all 967 relocations and passes truncated/corrupted inputs plus 2,000 mutation
cases under sanitizers. Its C boundary also cross-compiles for VR4300/O64.
The other **1,474 registry entries remain explicitly unbound**, including model,
animation, collision-model, effects and rendering dependencies. This prototype
is not loaded by the ROM and does not activate original weapon or unit behavior.
The separately exported Blood Gulch structure collision BSP is the native asset
bank that is actually integrated.

Original `object_new` immediately consumes model nodes, regions/permutations,
collision vitality, animation and node matrices, BSP reconnects and attachments.
Replacing its model index with a reduced renderer ID cannot satisfy those
requirements. Full integration still needs native model/skeleton/collision-model
and animation metadata bound to the reduced geometry, a complete native tag
loader, original per-object `unit_update`/weapon/projectile/vehicle behavior and
its damage/effect/sound dependencies, and N64 render/audio/platform backends.
The original `units_update` function alone only resets timers; linking that
function would not constitute a unit simulation port. Original multiplayer
`game_initialize`/`game_tick` remain outside the running ROM.

## Reproducible checks

```sh
python3 port/n64/blam/test_core.py
build/n64-python/bin/python port/n64/blam/tags/export_collision.py
build/n64-python/bin/python port/n64/blam/tags/test_collision_cache.py
```

The core suite passes AddressSanitizer/UndefinedBehaviorSanitizer tests for
70,000 allocate/delete cycles, salt wrap and stale-handle rejection, capacity
failure, forward/reverse iteration, fragmentation, compaction backpointers,
reallocation preservation and failed object-allocation rollback. It also
cross-compiles and links both test ELFs against the actual N64 SDK with no
undefined symbols. Those standalone ELF checks are not emulator execution.

The collision suite covers solid transitions, back-facing hits, two-sided
polygon bounds and misses. Against the real map, **852 rays from all 71 original
spawn positions** match independent double-precision triangulation of the
original collision polygons: **691 hits, zero mismatches, maximum fraction
error 1.05e-5**. Array references, finite scalars, polygon edge closure and graph
acyclicity pass validation; maximum BSP3D depth is 39, BSP2D depth 4 and polygon
size 8 edges.

The game-level floor tests also cover queries starting above the map's sky
enclosure. That downward-facing surface is not walkable: floor selection
requires a positive upward normal and continues through ceilings. High and low
query ceilings therefore find the same ground rather than placing players on
the invisible map enclosure. The core traversal itself retains the original
collision response for general rays.

Host game, replay and all six showcase tests also pass ASan/UBSan with both
collision profiles. The corrected native-BSP replay exercised 1,278 shots,
43 deaths, 14 boardings and 824 Warthog gunner frames, with all eight weapons and
all four vehicle classes. The baseline's
reduced-grid/brute-triangle equality test is only applicable to the reduced
profile; the native bank has the independent original-polygon reference above.

`blam/test_runtime.c` additionally checks known random sequences, the 30 Hz clock,
pausing/catch-up and quaternion endpoints, shortest-hemisphere interpolation,
aliasing and identity fallback. Keep runtime/collision arithmetic free of
fast-math, with floating-point contraction disabled. Hardware/controller testing
and emulator ROM validation are reported separately in the main README.

The integrated 8 MiB replay validation ROM has also booted in ares with the floor
selection fix. Grounded combat and vehicle scenes reported **zero RDP errors and
zero warnings**, with approximately **3,634 KiB free** in the sampled scene.
The 4 MiB profile likewise reported zero errors/warnings, with approximately
175 KiB free. These are observed emulator snapshots, not minimum-free-memory or
physical-hardware guarantees. The native-profile screenshot is
`build/n64/screenshots/blam-bsp-validation.png`.
