# Runtime maintenance baseline

This cleanup preserves the merged Blood Gulch checkpoint (`b3fba521`). It
creates boundaries for the optimization sprint without changing gameplay,
asset detail, pool capacities or the original vehicle solver arithmetic.

## Completed cleanup

- [x] A named release preset and a maintained validation runner.
- [x] Consistent formatting for the N64 integration code; named tick phases.
- [x] Separate scene rendering, display presentation, residency transitions
  and diagnostic fixtures behind explicit APIs.
- [x] Documented state authority, units, lifetimes and update order.
- [x] Shared interaction service IDs and explicit compiler contracts.
- [x] Optional cache, DMA and pool-pressure counters absent from release.

## Build and validate

Use the pinned private asset bank and the SDK requirements in [README.md](README.md).
Output directories below are inside the repository; builds do not overwrite
the shared bank's generated adapters or cartridge.

```sh
build/n64-python/bin/python port/n64/build.py --preset release \
  --output-dir build/n64-release

build/n64-python/bin/python port/n64/validate.py \
  --group host --group contracts --group assets --group equivalence --group target
```

The second command runs the native ASan/UBSan gameplay suites, standalone
header tests, renderer/input/audio contracts, asset checks, a checkpoint state
comparison, four linked ROM variants, and compilation of all 27 runtime
configurations. `build/n64-validation/results.json` records the outcomes.
Omit `--group target` when no N64 SDK is installed. The runner never reduces
or regenerates the immutable asset bank. Deliberate original-source adapter
regeneration is available separately through `blam/test_vehicle.py --regenerate`.

The release preset selects paced presentation, three display surfaces,
two local 32 KiB RSP command buffers and LTO. `--no-lto` permits comparison;
the conservative linker flags retain the per-unit arithmetic contracts.
Explicit options still permit experiments.
The legacy build without a preset keeps its original defaults. Snapshot
fixtures retain their unpaced presenter and are not timing measurements.
Every built ROM has a `.build.json` recording options, source/header hashes,
asset schema, runtime and private-bank commits, compiler and SDK revisions.
Uncommitted source edits are represented by hashes; the commit alone does not
identify such a build.

## Ownership and lifetimes

| Owner | Authoritative state | Lifetime / consumers |
| --- | --- | --- |
| `main.c` | Application mode, input edges, fixed-step accumulator, view count, simulation clock, geometry-slot fences | One application run; orchestrates the following modules |
| `game.c` | Players, inventory, match rules, pickups, vehicles, projectile handles and events | Match reset clears gameplay; readers must not silently mutate it |
| `scene.c` | Slot-local vertices/matrices/viewports, pose caches, display animation timestamps, recorded model commands | Geometry may be borrowed by RSP until its slot fence retires |
| `presentation.c` | Completed surface queue, VI observer, pacing mode and presentation metadata | Full-sync/VI callbacks manage surface ownership independently of geometry slots |
| `residency.c` | Ordered menu/gameplay load and release operations | Calls existing owners; it does not create a new allocator or eviction policy |
| `runtime_qa.c` | Staging and inspection cameras for diagnostic modes | Explicitly bound application clock/view count; absent in ordinary release |
| `sound.c` / `sound_mix.c` | PCM residency, playback voices and audio scheduling | Gameplay events are consumed by the presentation/audio path |
| `frontend.c` / `menu.c` | Profile identity, controller styles, navigation and menu ownership | Preferences survive match resets; no power-cycle persistence |

`bg_scene_prepare` may write a geometry slot only after `main.c` retires that
slot's RSP syncpoint. There are two geometry slots. Three release display
surfaces have a separate lifecycle; a surface's completion does not by itself
permit overwriting arbitrary geometry. Animation buffers and slot matrices
must remain intact until their borrowing commands complete. Residency releases
occur at the existing application transitions and preserve the original waits.

World coordinates use Halo world units; velocities use units per second and
angles use radians. The renderer scales world coordinates by `BG_SCALE`.
Floating gameplay durations use simulation seconds; source-clock tick fields
advance at 30 Hz. Presentation timestamps use the explicitly named microsecond
clock and must not substitute for simulation time.

For an active inventory slot, the player's scalar `ammo`, `reserve`, `heat`
and `overheated` values are authoritative. Slot arrays contain stowed values.
`store_inventory` synchronizes the active slot before switching, dropping or
transferring equipment. Reads or cache keys must respect this boundary.
`pickups.inc` remains a private inventory implementation inside `game.c` so
transfers can use those helpers atomically.

Projectile slots refer to original Blam object headers and a movable pool.
A returned projectile pointer can become stale after allocation or a later
tick; reacquire by slot. Pickup generations distinguish reused dynamic slots.
Map pickup slots remain permanent schedule owners. Drops share meshes and
never allocate a new model. The event array is a bounded batch: consume it
before clearing it for the next batch, and do not retain pointers across reset.

## Tick order

`bg_tick` clamps the step to at most 1/30 second, then:

1. Advances match time and pickup schedules.
2. Processes each player in index order: timers; dead-player respawn and
   early return; shields/heat/camo resources; control actions; movement;
   weapon actions; held-trigger state; teleport; last position; nearby pickups.
   Out-of-map death retains its original early return within that player.
3. If the match is still live, resolves player pairs, updates vehicles, then
   updates projectiles.

These named helpers preserve the checkpoint's ordering, floating arithmetic
and random stream. They are boundaries for later measurement, not permission
to reorder physics or batch state updates with different semantics.

## Numerical and asset contracts

The general integration retains its existing `-ffast-math`, trapping and
non-associative settings. Source clock/runtime, vehicle physics and collision
use their existing stricter per-unit flags, including disabled contraction;
vehicle adapters retain their aliasing and integer-wrap assumptions. Do not
apply a blanket flag change to the reconstructed source.

Scene and effect-bound units explicitly disable `finite-math-only`: their
conservative bounds must fail open on NaN/Infinity. `render_bounds.h` asserts
IEEE binary32 and checks exponent bits before quantizing. Both ordinary and
production-math test variants cover non-finite inputs. This does not change
the valid finite bounds outputs. Exact VR4300 word rounding avoids their libm
round trips after explicit range checks; [OPTIMIZATION.md](OPTIMIZATION.md)
records target rounding and checkpoint comparison evidence.

`interaction_services.def` is the shared ordered schema for C and Python.
IDs are explicit and contiguous; changing the order requires a coordinated
bank migration. `interaction_poses.h` holds SDK-independent service/pose
metadata; `asset_interaction.h` contains the renderer interface. Repacking
this cleanup preserved the entire interaction binary and definition data;
only the generated C header dependency and provenance report changed.

## Pressure counters

Build `--preset release --demo --telemetry` for cumulative pose-cache hits and
misses, pose DMA read count/bytes, terrain and floor-cache activity, terrain
overflow, projectile/event exhaustion, dropped-item reclamation/exhaustion,
and pose allocation/free calls. A once-per-wall-second log also reports heap
free bytes and the minimum of those samples. It is **not** the exact heap
high-water mark, largest contiguous allocation, or stack high-water mark.
Counters wrap at 32 bits and include activity since boot.

Without `--telemetry`, counter calls evaluate no arguments and generate no
counter array or reporting code. Quiet VI builds reject telemetry because its
logging would contaminate the timing measurement. Pool sizes and existing
pressure responses are unchanged: these counters expose behavior rather than
introducing growable pools or automatic ROM/RAM swapping.

## Evidence and remaining debt

The complete simulation trace matches the checkpoint for 15,300 ticks across
the four-player replay and six showcases: 144,166,856 bytes of compared state.
Thirty-seven extracted renderer functions retain the checkpoint's arithmetic
and command ordering. Asset, animation-buffer borrowing and presentation tests
cover separate contracts; emulator/hardware evidence remains necessary.

The release ELF uses 2,392,524 bytes of text/data/BSS, 360 bytes less than the
same-SDK checkpoint build. This is linked resident size, not total runtime
heap usage. No geometry buffers or gameplay pool capacities grew.

The >25 FPS vehicle-scene development gate and final 30 FPS pass remain open
in [BLOOD_GULCH_PARITY.md](BLOOD_GULCH_PARITY.md). Native traces do not certify
retail Xbox parity, and Ares timing does not certify physical hardware speed.
The cleanup's quiet Ares replay measured 24.1 FPS overall, 26.2 in combat and
22.2 around vehicles, with P95 66.8 ms, maximum 200.5 ms and 42 KiB free.
The local screenshot and exact loaded build manifest are saved in
`build/n64-cleanup/evidence/`.
`game.c` still contains substantial combat/vehicle integration, and diagnostic
fixtures still use private headers inside their dedicated translation unit.
Future cleanup should follow measured needs rather than expanding this pass
into a new engine framework.
