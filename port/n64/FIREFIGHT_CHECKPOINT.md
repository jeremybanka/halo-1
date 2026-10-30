# Firefight checkpoint — 2026-10-30

This checkpoint publishes the work since `031e79f5`: Wraith/Shade distance
LODs, shared vehicle clearance and Wraith firing checks, selectable Onslaught
and Gauntlet fights, M64 controls/three-player presentation, damage feedback,
and scoped terrain/HUD corrections. The private submodule supplies the exact
banks, source-derived artwork and comparison archives. No merge is included.

## Review and evidence

| Change | Public report / benchmarks | Private comparison page |
| --- | --- | --- |
| Wraith/Shade distance LODs | [Report](VEHICLE_DISTANCE_LODS.md), [evidence](benchmarks/vehicle-lods/README.md) | `assets/vehicle-lods/evidence/comparison.html` |
| Wraith aim and shared clearance | [Report](VEHICLE_SIMULATION.md), [evidence](benchmarks/vehicle-simulation/README.md) | `assets/vehicle-simulation/viewer/comparison.html` |
| Onslaught and Gauntlet | [Rules](FIREFIGHT_FIGHTS.md), [evidence](benchmarks/firefight-fights/README.md) | `assets/firefight-fights/comparison.html` |
| Duke/Bond, wide P3, damage arrows/flash | [Report](M64_PLAYTEST.md), [evidence](benchmarks/m64-polish/) | `assets/m64-polish/comparison.html` |
| Close terrain and weapon-specific scopes | [Report](SCOPE_RENDERING.md), [evidence](benchmarks/scope-fix/) | `assets/scope-fix/comparison.html` |

Open the private HTML pages from a local checkout to use their images and diff
filters. Archive pages omit ROM download links; ROMs remain local. The private
`assets/firefight-checkpoint/comparison.html` links all five galleries.
Historical reports describe their original stop-for-appraisal state; this
checkpoint publishes those results without relabeling them as fresh benchmarks.

## Measured outcomes and limits

The Wraith/Shade distance tiers cut the matched four-camera hull loads from
11,808 to 3,724 at tick 60 and the serialized hull interval from 24.491 to
9.818 ms. Detailed views and collision remain unchanged. Coarse silhouettes
have documented compromises; the candidate is enabled by the explicit
`--vehicle-distance-lods` flag in the current playable build.

Shared clearance and deferred Wraith obstruction checks reduce four-player
stress vehicle AI from 5.845 to 2.363 ms/tick and total simulation from 31.034
to 28.391 ms/tick. The engaged stress average rises from 3.55 to 4.40 FPS;
with all four humans alive it is 2.96 to 3.19 FPS. The one-Ghost four-player
control is essentially unchanged at 16.00 to 16.02 FPS. These are uncapped
Ares fixtures with 8 MiB and audio, not whole-match averages or hardware FPS.
Paired native movement/aim/shot state and 27 before/after framebuffer pages
remain identical for the simulation optimization.

The M64 playtest used the Insane overclock and was reported as mostly smooth,
with occasional arrival drops. This is qualitative feedback. Stock-clock
four-player 30 FPS is not established. The flashlight remains a surface-light
approximation with patching on uneven terrain; the source-derived AI and
Firefight rules retain the limitations described in their reports.

Onslaught keeps its original player-scaled schedule. Gauntlet uses the solo
quantity for every party size and increases source ranks/weapons while retaining
squad diversity. P3 has the wide bottom view. Duke is the default and Bond
preserves the prior N64 scheme. Source damage arrows and the brief screen flash
sit behind the HUD. Pistol/sniper shapes remain distinct, sniper marks are
crisp/aligned, and close scoped terrain no longer disappears. The near-depth
query is conservative and budgeted; foreground visibility can trade distant
depth precision, as documented. Original CE trigger behaviors are unchanged.

## Current verification

`benchmarks/firefight-checkpoint/verify.py` repeats the address/undefined-sanitized
controls/menu/frontend, game damage, both fights, full Firefight lifecycle and
enemy-vehicle checks without overwriting historical logs. Scope mask, conservative
triangle clipping and camera tests also pass. The latest native release and
scope QA binaries are checked against all recorded compiler-input and ROM hashes.
The recorded 47 runtime configurations / 188 target translation units pass.

The scope route includes 22 matched camera poses across 1–4 players. Distant
world pixel comparisons exclude intentionally changed HUD stamps; all 15,140
checked pixels are identical. The native sniper marking center differs from
the reticle by only half a pixel. Frozen photos are not performance tests.

The current playable ROM is 60,293,120 bytes, SHA-256
`49a0298e9c5b071b6fd7b1d1aace040dcaf07ca1a57194d1e5115de26ab233fb`.
Its local review is `build/n64-scope-fix/comparison.html` in the research checkout.
Its build and the archived scope photos predate the packaging commit; their
recorded commit IDs are intentionally retained alongside exact input hashes.

## Restore and build

Initialize the private submodule and run `port/n64/setup_assets.py --verify`.
Restore the existing enemy-vehicle bank to `build/pve-vehicles/bank`, copy that
bank to `build/vehicle-lods/bank`, and add the archived
`assets/vehicle-lods/bank/vehicle_distance_data.c`. Restore the corrected Blood
Gulch map as described in [PVE_SQUAD.md](PVE_SQUAD.md) and
[PVE_VEHICLES.md](PVE_VEHICLES.md). The current explicit build command is:

```sh
TMPDIR=/private/tmp build/n64-python/bin/python port/n64/benchmarks/scope-fix/build.py play
```

The helper records the full release flags, SDK and Tiny3D paths; adjust the
machine-specific paths on another system. The private checkpoint stores exact
compiler inputs as content-addressed gzip blobs, plus release/QA manifests.
`port/n64/benchmarks/firefight-checkpoint/archive.py` completes and verifies the
five evidence archives, their static gallery links, and a publication manifest.
The normal private `bank-manifest.json` additionally covers every staged payload.
