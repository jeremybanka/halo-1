# Native tag and collision bridge

This directory contains two separate paths. `export_collision.py` produces the
complete original Blood Gulch collision BSP for the source-derived Blam segment
traversal. The BGTG tools produce an audited native gameplay metadata prototype;
that package is not linked into the demake and does not make the original
`object_new`, `unit_update`, or weapon simulation runnable.

All commands read the user's locally extracted Xbox caches. Generated C, binary
packages, reports, cache names, and numeric game data remain in ignored `build/`.
The scripts need the Python 3.11 Reclaimer environment used by the asset pipeline.

## Exact collision BSP

After the normal asset extraction has written the decompressed map:

```sh
build/n64-python/bin/python port/n64/blam/tags/export_collision.py
python3 port/n64/blam/prepare_collision.py
build/n64-python/bin/python port/n64/blam/tags/test_collision_cache.py
```

The generated `build/n64/generated/blam_collision_data.c` exposes
`const blam_collision_bsp bg_blam_collision_bsp` through `blam/collision.h`.
Coordinates and planes remain in original Halo XYZ units. The gameplay boundary
must apply the existing map recentering and Y-up basis conversion; the packer
must not apply those transformations a second time. Explicit little-endian
decoding and exact hexadecimal float literals preserve each float32 value, and
the target C compiler provides big-endian N64 storage.

| Original array | Elements | Bytes |
|---|---:|---:|
| 3D BSP nodes | 12,071 | 144,852 |
| Planes | 4,616 | 73,856 |
| Leaves | 5,999 | 47,992 |
| 2D BSP references | 13,182 | 105,456 |
| 2D BSP nodes | 418 | 8,360 |
| Surfaces | 4,916 | 58,992 |
| Edges | 7,650 | 183,600 |
| Vertices | 2,704 | 43,264 |
| **Arrays plus 96-byte N64 root** | | **666,468** |

The existing reduced collision triangles/grid occupy 80,506 bytes. A theoretical
complete replacement would add about 586 KB of resident data. The implemented
`--blam-bsp` profile retains that grid for wall and cell-boundary queries, so it
adds the full 666,468-byte original bank instead, with code/BSS differences
measured separately (the unused old ray-stamp array saves about 16 KB). This is
the explicit 8 MiB original-BSP profile, not an unannounced increase to the base
4 MiB memory requirement.

The exporter validates every array index, leaf range, finite float, 3D/2D tree
cycle, and surface edge ring. Maximum source tree depths are 39 and 4; polygons
have at most eight edges. The host test compiles the real traversal and generated
bank with ASan/UBSan and compares 852 segments from all 71 player spawn locations
against an independent double-precision ray intersection with 5,468 triangles
formed from the original collision polygons. The measured result is 691 hits,
zero mismatches, and maximum hit-fraction error 0.00001052. The reference is the
original collision mesh; differences from the reduced render/collision mesh are
expected and are not treated as original-engine errors.

## Native gameplay metadata prototype

```sh
# Required once to create the original-header cross-compiler environment:
python3 port/n64/blam/probe_engine.py
build/n64-python/bin/python port/n64/blam/tags/layouts.py
build/n64-python/bin/python port/n64/blam/tags/audit.py
build/n64-python/bin/python port/n64/blam/tags/export.py
build/n64-python/bin/python port/n64/blam/tags/test_export.py
```

`layouts.py` reads the compiler invocation recorded by the engine probe. It
cross-compiles `sizeof`/`offsetof` expressions against the repository's original
headers, then reads a big-endian constant section without executing MIPS code.
The confirmed ABI has 32-bit pointers and `long`, 12-byte tag blocks, 16-byte tag
references, and 20-byte tag-data headers. The exporter uses the original cache
metadata and deliberately does **not** call Reclaimer's `meta_to_tag_data`:
conversion to HEK editing units would alter runtime tick-based values.

The roots are the eight Xbox multiplayer weapons, `cyborg_mp`, Warthog, Ghost,
Scorpion, and the campaign-cache Banshee. Recursive salted references reach
1,565 namespaced tags and 1,668,566 bytes of fixed structures and parsed
reflexives. This is the measured reachable graph, not a proven minimum resident
working set. The Blood Gulch and a30 namespaces retain duplicates because their
reference handles and parameters can differ. Geometry, animation frame payloads,
pixels, samples, and names are excluded from that fixed-metadata total; the audit
reports separately available raw payload bytes and does not claim an external
model stream was measured when Reclaimer did not load it.

The prototype exports every parsed field in 91 reachable tags of classes `bipd`,
`vehi`, `weap`, `proj`, `jpt!`, and `phys`, including all reachable tags of those
classes rather than only the root definitions. Their fixed/reflexive metadata
occupy 190,780 bytes. Padded allocations and paths for the complete registry
produce a 242,916-byte payload; the complete package is 294,504 bytes. The
remaining 1,474 entries retain their names and classes but explicitly have no
metadata. Calls to `bgtg_get` for those entries return null.

Reclaimer descriptors omit some runtime fields that are padding in editing tag
definitions. The maintained native-layout overlay preserves/swaps object runtime
flags, four function reciprocals, unit ping tick values, biped runtime movement
constants and bone indices, and weapon trigger recovery/acceleration values.
The exporter refuses unclassified nonzero metadata bytes. Current validation
compares 21,337 scalar field locations, including 329 runtime fields, directly
with the original little-endian source bytes. There are no unknown nonzero
ranges or omitted raw payloads in these six exported classes.

### BGTG/1 format and loader

All integers are big-endian u32 unless an original metadata field has another
documented width. The first eight words are magic `BGTG`, version 1, tag count,
record offset, relocation count, relocation offset, payload offset, payload size.
Each seven-word record contains a generated handle, primary class, two parent
classes, root metadata offset, root size, and path-string offset. An unbound
root has offset `0xffffffff` and size zero. Handles are `0x4e640000 + ordinal`,
making cross-cache references unambiguous while retaining an index/salt shape.

Each two-word relocation contains a payload-relative pointer-word offset and a
payload-relative target. The payload reserves four zero bytes for null, aligns
allocations to four bytes, retains original scalar values and fixed layout, and
places reflexive arrays contiguously. Tag-reference classes, names, name lengths,
and remapped handles are preserved. Tag-block definition pointers are zero;
the original `tag_block_get_element_with_size` tolerates this. Name strings remain
available because original debug tag-reference verification resolves names.

`tag_store.c` validates package boundaries, record IDs, null-terminated names,
bound/unbound ranges, pointer-word values, and sorted unique relocations before
exposing a view. `bgtg_relocate32` copies the payload and installs 32-bit target
addresses; it must receive the actual destination address on big-endian N64.
Host tests inspect those big-endian pointer words without casting native structs.
The package view must remain alive for registry access. Original `tag_get`,
datum allocation, object-type dispatch, and engine tag globals are not wired to
this prototype. Loader tests cover inheritance, missing entries, all 967
relocations, truncation, corruption, and 2,000 mutation cases under ASan/UBSan.

## What original object creation still needs

The reduced meshes are render assets, not native `mode`, `antr`, or `coll` tags.
Changing an object definition's model handle into `BG_M_*` would make
`object_new` read the wrong layout. A narrow **render** adapter can map a preserved
native model handle to a reduced mesh, but native skeleton/region/marker metadata,
animation graphs, and collision/vitality data must remain valid separately.

The compiler-verified ranges below are intentionally unbound. `layouts.json`
records exact sizes and ranges for the next implementation step:

| Structure | Bytes/ranges needed by native consumers |
|---|---|
| `model` (232 bytes) | markers 172–183; nodes 184–195; regions 196–207; geometries 208–219; shaders 220–231 |
| `model_node` (156 bytes) | translation 40–51; rotation 52–67; inverse matrix 104–155 (52 bytes, including scale) |
| `animation_graph` (128 bytes) | unit seats 12–23; first-person indices 72–83; nodes 104–115; animations 116–127 |
| `animation` (180 bytes) | runtime parent 66–67; weight 68–71; frame-info header 72–91; translation flags 92–99; rotation flags 108–115; scale flags 124–131; compressed offset 136–139; default-data header 140–159; frame-data header 160–179, plus their raw payloads |
| `collision_model` (664 bytes) | resistance 0–599; pathfinding box 616–639; spheres 640–651; nodes 652–663, plus per-node collision BSP topology |
| `damage_resistance` (600 bytes) | body vitality 8–11; shield vitality 204–207; recharge velocity 448–451; materials 564–575; regions 576–587; modifiers 588–599 |

`source/objects/objects.c:object_new` immediately reads model node count,
allocates node matrices/orientations, dispatches type creation, chooses regions,
initializes vitality, computes poses, creates attachments, and reconnects the
object to the world. The actual original per-unit behavior is `unit_update`;
the plural `units_update` only resets three timer values. Original weapon update
also needs native animation state, projectile/object creation, damage/material
rules, game-time/random state, inventory, and effect/audio boundaries. The full
recursive graph includes 369 effect tags alone, so substituting renderer IDs or
dropping effects silently is not a completed original gameplay engine port.

The exact world BSP path is independently usable now. It does not by itself
provide object collision models, capsule movement, vehicles, or unit simulation.
