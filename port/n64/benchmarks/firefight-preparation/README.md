# Firefight NPC preparation reuse — 28 October 2026

This appraisal follows the collision-cache prototype at
`1ab58a383edbe0d12c0457feb25d598ed60a2e4d`. Both sides include that optimization,
the current reload fix and the same opt-in Hunter/Spirit model bank. No model,
animation, hit mesh, AI, navigation, encounter, camera or LOD asset is changed.
See [the appraisal](../../FIREFIGHT_PREPARATION.md) for final performance results.

## Reuse and exact arithmetic

The original renderer already prepares a needed NPC LOD once for all cameras.
This prototype addresses repeated work within and across preparation calls:

1. A **192 KiB CPU-only ROM-span cache** retains aligned animation frame pairs.
   Thirty-two descriptors key the exact ROM start and length. FIFO allocation
   invalidates every overlapping span before overwrite, including wraparound.
   A returned pointer is consumed before the next request; it is never given
   to the RSP. Map/scene release clears the descriptors. This replaces the old
   single 98,336-byte transfer window; it does not retain the whole motion bank.
2. Actors with the **same species, LOD and existing pose key** can use one
   prepared vertex buffer and its command blocks within the current fenced
   frame slot. The key retains clip, frame pair, existing 8-bit interpolation
   fraction and Jackal shield state. Only earlier prepared owners are eligible.
   Each actor keeps its own body and gun matrices. Ownership resets each frame;
   no mutable vertex buffer is borrowed across the two in-flight frame slots.
3. Interpolated tracks use the renderer's existing eight-byte aligned packed
   position writer, preserving each vertex's normal and all color/UV fields.
   The NPC decoder explicitly retains **arithmetic `>>8` rounding**. The existing
   Spartan 16-bit decoder divides by 256 and would change negative deltas, so it
   is not substituted. Spirit track interpolation likewise runs once per unique
   track before scattering into packed vertices.

There is no animation update throttling, phase quantization change, geometric
reduction or shared hit-pose approximation. Hit sampling remains independent.
The original fenced buffer ownership and release wait remain in place.

## Memory

`memory.json` records native ELF sections and symbols. Additional linked BSS is
**115,184 bytes (112.48 KiB)**:

- Motion cache including metadata: 197,008 bytes, replacing a 98,336-byte window.
- Aligned decoded tracks: 65,536 bytes, replacing 49,152 bytes.
- Frame-local pose keys/owners and linker alignment account for the remainder.

The 60-byte preparation counter block exists in both diagnostic builds and is
absent from release. Shared poses may avoid some lazy actor-buffer allocations;
the fixed BSS delta does not assume a permanent heap saving.

## Verification

`test_pve_preparation.py` extracts independent original decode/scatter loops
from the revision above. It tests the actual approved and opt-in motion banks,
using the production cache, decoder, packed scatter and extracted owner lookup.

- **631,808 exact packed poses / 941,677,568 vertices** across both banks: every
  species, LOD, clip and frame pair, all 256 interpolation fractions, and
  Jackal shield states. Normals are deliberately varied to detect overwrites;
  the entire packed buffer, including colors and UVs, must match.
- Per bank, 3,000 cache requests cover hits, reset, overlapping allocation,
  wraparound and 98,336-byte requests. Every live cached byte is checked
  against its ROM address pattern, so stale metadata is detected.
- Per bank, 4,000 alternating-slot ownership simulations exercise 38,910 shared
  and 37,870 distinct poses, species/LOD/shield changes and visibility changes.
  Owners must be earlier, prepared actors in the same frame. These test the
  production lookup; they do not emulate the RSP.
- The existing deferred-animation lifetime harness checks 10,000 fenced frames
  and shuffled 1–4 camera consumers in both diagnostic and release modes.
- The collision oracle still passes **37,440 exact movement steps** and
  **686,256 exact hit comparisons** with 234,017 hits. Full 1–4P Firefight lifecycle,
  arrivals, damage materials, reserves, recycling and restart tests pass.
- **42 runtime configurations / 168 target translation units** compile.
- Native photographs use the previous **52-state, four-camera inspection route**,
  both LODs and articulated poses, with RDP validation. `compare.py` requires
  matching camera/actor logs and **all sixteen bits of every RGBA16 pixel** to
  match. The RGB difference filter amplifies differences fourfold. These fixtures
  inspect individual models and occlusion; the host ownership test separately
  stresses multi-actor sharing.
- A separate native four-player frontend lifecycle exercises actor/ship buffers
  through restart, quit and return to ordinary multiplayer.
- A supplementary native fourteen-match residency cycle covers all thirteen
  multiplayer maps with Firefight compiled in and the canonical model bank.
  This checks the additional fixed memory cost outside Firefight as well.

Host logs, pixel checks and native frontend results are archived here. Native
photos and their raw pixel logs are private/local; they do not belong in this
public source repository.

## Measurement contract

- Ares v148, NTSC 320×240, Expansion Pak 8 MiB, audio enabled, native N64 code.
  These are emulator results, not fresh physical-cartridge measurements.
- Baseline/candidate × opening/crowded × 1–4 players. Both versions compile the
  same sources and assets; only `--pve-prep-baseline` differs. Collision acceleration
  stays enabled in both. This is a matched comparison after the previous task,
  not a comparison against older navigation or model appraisals.
- Opening QA3 records 75 observations. Crowded QA4 records 45 and resets its
  mixed encounter every twenty simulated seconds. Real damage and deaths remain
  active. Discard five warm-up observations; headline FPS requires living humans
  and landed enemies. Whole-window and all-humans-alive subsets are also retained.
- `NPC_PREP` reports **one sampled rendered frame per observation**, not continuous
  totals. It splits visibility, buffer/key work, matrices, ROM-span lookup/transfer,
  decode, scatter, writeback and grip work. Counts include pose requests, local
  pose hits, shared poses, motion-pair hits and DMA bytes. Reported reuse ratios
  aggregate these sampled counts, not every frame in the run.
- `ship_us` covers the entire ship preparation service; its motion fetch also
  appears in `motion_us`. Do not add those overlapping timers. The old overall
  NPC timer ends before the final body/gun matrix writebacks, identically on
  both sides. Counter bookkeeping and other small work can leave a remainder.
- Existing `PVE_PHASE` frame sections include catch-up simulation ticks.
  `COLLISION` instead accumulates over thirty actual simulation ticks. These
  have different windows from filtered FPS. Nested services must not be added
  to their parents, nor sampled averages inverted to reconstruct FPS.
- Separate serialized four-player graphics checks under `gpu/` measure outstanding
  RSP work and the subsequent RDP tail. They include audio pumping and possible
  backpressure, not independent total chip occupancy. Their FPS is excluded from
  the headline matrix. Zero ordinary-run drains mean that diagnostic is disabled.
- Each case has one fresh capture. Timing changes can alter sampled combat
  windows even with matched assets, rules and controls. Small differences are
  not statistical proof. Provenance records exact inputs and ROM/log hashes.

## Reproduce

Use the existing owned private assets, corrected-ground Blood Gulch override,
installed N64 SDK/Tiny3D and Python environment. `MODEL_BANK` may point at
`halo64-assets/assets/covenant-model-appraisal/bank`. No Blender re-export is needed.

```sh
build/n64-python/bin/python port/n64/test_pve_preparation.py
build/n64-python/bin/python port/n64/test_maps.py --collision --output-dir build/firefight-preparation/host-collision
build/n64-python/bin/python port/n64/test_maps.py --firefight --output-dir build/firefight-preparation/host-firefight
build/n64-python/bin/python port/n64/test_deferred_animation.py

build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/run_matrix.py build --output build/firefight-preparation/matrix --model-bank MODEL_BANK
build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/run_matrix.py capture --output build/firefight-preparation/matrix --model-bank MODEL_BANK --settings ARES_SETTINGS
build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/collect.py build/firefight-preparation/matrix
```

The runner accepts explicit SDK/Tiny3D paths. `--resume` is valid only for complete
logs from unchanged ROMs. Run one emulator at a time. Build the separate graphics
pair with `--gpu --kinds perf --players 4` in `build/firefight-preparation/gpu`.

Build photo ROMs using `--pve-squad --pve-model-qa --validate --pve-model-bank
MODEL_BANK`, the same SDK/Tiny3D and `--map-bank-override`, and distinct output
directories `photo-before` / `photo-after`. Only before adds `--pve-prep-baseline`.
Build the frontend fixture with `--firefight --firefight-qa 4 --validate`, the same
bank/override and `--output-dir build/firefight-preparation/frontend-4`.
`capture_checks.py CAPTURE --settings ARES_SETTINGS --model-bank MODEL_BANK`
then serializes both photos, graphics checks and the frontend fixture.

For the supplementary residency check, build `--firefight --maps-cycle --validate`
with the canonical model bank (omit `--pve-model-bank`), the same map/SDK/Tiny3D
and `--output-dir build/firefight-preparation/maps-cycle`. Run
`capture_maps.py build/firefight-preparation --settings ARES_SETTINGS`. Its
1,200-second limit allows fourteen full matches and all 223 frontend steps.
Only this lifecycle check disables audio blocking; it is excluded from every
FPS/profiling comparison. Audio and the ordinary performance settings remain
unchanged in the matched matrix.

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/collect.py build/firefight-preparation/gpu --gpu --output port/n64/benchmarks/firefight-preparation/gpu
build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/compare.py build/firefight-preparation LOCAL_APPRAISAL
```

A playable appraisal uses `--firefight --preset release --pve-model-bank MODEL_BANK`
with the same map/SDK/Tiny3D in an isolated output directory. It includes no
baseline control or preparation/collision instrumentation. The model candidate
remains opt-in, independently of the preparation changes.

Reanalyze public archived timing logs without private assets or ROMs using
`collect.py port/n64/benchmarks/firefight-preparation --logs-only --output OUTPUT`;
use the `gpu/` input and add `--gpu` for that pair. Saved log hashes are checked.
The independent pose oracle requires the baseline Git revision to be available
in shallow checkouts. Parent revision fields identify the pre-commit checkout;
exact file hashes identify the measured working tree.
