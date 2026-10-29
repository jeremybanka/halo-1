# Enemy vehicle reproduction and evidence

Read [PVE_VEHICLES.md](../../PVE_VEHICLES.md) for behavior and fidelity boundaries.
Commands run in the isolated `build/n64-pve-squad/source` checkout. Existing
roster and Jackal-shield candidates are prerequisites. Accepted banks and the
original dirty research checkout are preserved. This checkpoint is published
with PR #12; the candidate remains opt-in for appraisal.

## Generate the private bank

Use the existing Python environment (Reclaimer, NumPy, Pillow), owned CE cache
extraction, and accepted symmetric Covenant assets:

```sh
build/n64-python/bin/python port/n64/extract_enemy_vehicles.py
build/n64-python/bin/python port/n64/bake_enemy_pilots.py
build/n64-python/bin/python port/n64/prepare_enemy_vehicle_ai.py
build/n64-python/bin/python port/n64/pack_enemy_vehicles.py
build/n64-python/bin/python port/n64/extract_vehicle_audio.py
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/validate_assets.py
```

Packing calls `pack_vehicle_details.py` to append human Shade interaction/hit
clips and the Wraith hatch, and `pack_vehicle_hud.py` for source reticle masks.
Do not call the detail append step twice without resetting
through `pack_enemy_vehicles.py`. Canonical pilot hit samples and visual samples
share the expanded ROM motion file with separate offsets and exact host/native
byte checks. Existing accepted assets are not replaced.

`refresh_maps.py` regenerates the unchanged accepted Blood Gulch map and verifies
byte identity before refreshing the game.c input hash in the private map report.
It is needed after game.c edits because that file supplies the existing teleporter
initializer. Builds use the accepted corrected-ground map override.

## Host checks

```sh
build/n64-python/bin/python port/n64/test_maps.py --enemy-vehicles --output-dir build/pve-vehicles/host
build/n64-python/bin/python port/n64/test_maps.py --enemy-vehicles --firefight --output-dir build/pve-vehicles/host-match
build/n64-python/bin/python port/n64/test_maps.py --navigation --enemy-vehicles --output-dir build/pve-vehicles/host-navigation
build/n64-python/bin/python port/n64/test_maps.py --modes --enemy-vehicles --target-math --output-dir build/pve-vehicles/host-modes
```

The first command executes production vehicle/contact/available-seat paths with
ASan/UBSan. The second exercises finite waves and existing roster/shield behavior.
The navigation command checks exact route results; the last verifies PvP rules
and strict source spawn ratings with the vehicle feature compiled in. See logs;
these are different claims from native visual validation.

## Native builds and captures

```sh
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/build_checks.py --photo --play
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/build_checks.py --players 4 --fixtures 7
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/build_checks.py --players --fixtures --maps
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/build_checks.py --players --fixtures --probe
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/capture_probe.py
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/capture_checks.py --photo
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/capture_checks.py --players 4 --fixtures 7
build/n64-python/bin/python port/n64/benchmarks/firefight-preparation/capture_maps.py build/pve-vehicles --settings build/pve-vehicles/ares.bml
```

The playable and all-map ROMs use the maintained release preset (LTO, 30 FPS
pacing, three display surfaces and 32 KiB RSP queues). Diagnostic timing remains
uncapped with the same 16 KiB queues as the preceding roster measurements.
SDK/tiny3d paths are explicit in `build_checks.py`. Build options and runtime input
hashes are retained in each manifest. Capture helpers launch and terminate only
their own Ares subprocess, using task-local settings. Run captures serially. The
maps cycle is a residency/menu regression, excluded from FPS; it disables audio
blocking only in its own copied settings file.

Fixture 8 places all four vehicle types together with infantry to the 6/8/10/12
actor cap. Fixture 9 uses one Ghost plus infantry to the same cap. Fixture 7 checks
the full infantry roster with the vehicle bank resident. Fixtures 7/8 restart at
tick 600. Each timing capture has 45 observations; five initial warm-ups are
discarded, and restarted intervals stay in the sample. Report engaged and
all-player-alive scopes separately. Damage/deaths remain real; these are not
identical-state comparisons with old infantry workloads.

`PVE_PHASE` counters are per rendered frame, potentially containing several
simulation ticks. `COLLISION` partitions each simulation tick into director,
humans, vehicle AI, vehicle physics/contact, infantry AI/combat, projectiles and
after-work. Terrain/hit counters are nested; do not add them again. The collector
divides totals by recorded tick count. Vehicle telemetry records mounted shots.

## Appraisal artifacts

The current playable ROM removes the earlier occupied-seat hijacking prototype.
Its targeted checks are isolated from the original 1–4-player matrix:

```sh
build/n64-python/bin/python port/n64/test_maps.py --enemy-vehicles --output-dir build/pve-vehicles/ce-entry/host
build/n64-python/bin/python port/n64/test_maps.py --enemy-vehicles --firefight --output-dir build/pve-vehicles/ce-entry/host-match
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/refresh_maps.py
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/ce_entry.py build
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/ce_entry.py capture
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/ce_entry.py collect
```

Save the two host command outputs as `ce-entry/host-tests.log` and
`ce-entry/host-match.log`. This revision repeats 42 native photo pages and the
45-observation four-player overload fixture. `ce-entry.json` binds those fresh
results to their builds. The old matrix, all-map cycle and old host logs remain
historical evidence, with the five changed source files frozen under the private
archive's `evidence/ce-entry/previous-inputs`. Do not overwrite those original
builds when reproducing the current revision.

```sh
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/viewer.py
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/archive.py
build/n64-python/bin/python port/n64/benchmarks/enemy-vehicles/validate.py
```

`collect.py` produced the historical nine-case matrix; do not rerun it against new
builds and retain the original provenance label. `viewer.py` decodes 42 native
pages into four-camera PNGs, records exact pose/camera inputs, and generates LOD
and before/after differences. Its baseline is the
saved `hud-only-photos-native.log`, after source reticle correction and before
scratch lifetime changes; its candidate is now the available-seat revision.
Preserve that capture and the earlier pre-cache-fix /
pre-HUD-fix pair; do not substitute a fresh candidate and call it a baseline.
The viewer is written to the original checkout's `build/n64-enemy-vehicles/`.
Native PNGs are inspected; browser-render verification is not claimed.

Public records contain numerical logs, tests, hashes and reproducible scripts.
Private art, sound, hit/animation payloads, frame readbacks and manifests remain
under `halo64-assets/assets/enemy-vehicles`. ROMs remain local. The original failed
allocation log is preserved separately from the final passing matrix. Archiving
does not push the candidate.
