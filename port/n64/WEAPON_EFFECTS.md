# Weapon firing and charging effects

All eight Xbox multiplayer weapons now draw source-based muzzle flashes in
first person and on other players' held weapons. The plasma rifle alternates
its original upper/lower muzzle markers. The plasma pistol grows a green
corona and tapered candle while charging, sustains it at full charge, and
removes it on release, weapon switch, death, boarding, melee or overheating.

The sniper adds a short warm streak that widens into gray smoke and fades over
1.25 seconds. Its endpoint is the actual hitscan result, including spread,
terrain and target interception. Rendering starts at the firing-pose muzzle
so the shooter's entire trail does not collapse into the reticle. A one-pixel
minimum ribbon width preserves visibility in four-player splitscreen.

## Original assets and deliberate reductions

`extract_weapon_effects.py` follows the original Blood Gulch weapon firing
references to the particle tags and sprite sheets. It extracts the selected
source sequence, tint, radius and lifespan; the sniper contrail supplies its
texture, color stages and width envelope. Plasma overcharge uses bitmap 6 of
`weapons\plasma rifle\overcharge`'s original soft-flare bitmap group, plus its
soft corona bitmap. Marker positions follow the same source animation samples
and clip clocks as the packed first-person guns. World effects use the source
held-model markers and current hand attachment matrix.

Eight 16×16 RGBA sprites occupy 8 KiB; 176 frames of two animated markers occupy
2,112 bytes. A firing event uses one quad, charging uses three, and a sniper
trail uses four. Up to four trails survive concurrently. There is a fixed
32-quad limit per camera, with separate immutable storage for four cameras in
each of the two fenced geometry slots (16 KiB total vertex storage).
Effects depth-test against the gun/world but never write depth. Rendering
restores blending, depth writes and the untextured solid-model state.

The many original emitter particles collapse to one representative sprite;
casings, muzzle lights, heat haze and the full Xbox particle/lens-flare shaders
are not reproduced. Source additive textures use a bounded alpha approximation
because direct N64 additive blending can overflow. Charging color/lobes and
trail drift are inexpensive approximations; these are not a complete port of
the original effects solver. Vehicle firing rigs are outside this handheld
weapon pass. No gameplay random samples, damage or projectile behavior change.

## Build and checks

```sh
build/n64-python/bin/python port/n64/extract_weapon_effects.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py
build/n64-python/bin/python port/n64/build.py --effects-qa --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The build rejects stale source/marker data using the generated report's hashes.
The host sanitizer suites drive actual firing events for all eight weapons,
empty-weapon behavior, charge growth/hold/release/cancellation, exact sniper
terrain and target hits, trail expiry and bounded reuse. Ordinary gameplay,
vehicle physics, replay and six existing showcase checks also run.

`--effects-qa` is a separately labeled, scripted four-player fixture. Four
10-second phases exercise human weapons, Covenant weapons/rockets, staggered
plasma charging, and world muzzle/trail views. It refills ammunition and health
for demonstration; it is not a performance benchmark. An early fixture moved
players 2 and 4 laterally without recomputing the floor, placing them below the
terrain and interfering with respawn. The corrected fixture samples ground
height after positioning. Its regression runs two complete cycles and checks
all players remain alive and above the terrain on every tick.

Local Ares screenshots, recordings, source sprite references, timing data and
ROM hashes are in `build/n64/weapon-fx-audit/`. They contain owned game assets
and remain ignored by Git. Emulator timing does not certify console hardware.

Ares 148 validation reports zero RDP errors or warnings. The quiet 75-second
NTSC, 4 MiB, five-buffer VI benchmark measures 28.6 FPS overall, 29.0 combat,
28.1 vehicles, with 65 KiB heap remaining. The preceding build measured
28.8 / 29.0 / 28.5 FPS and 101 KiB free. Combat P95 remains 33.4 ms; vehicle
P95 is 66.8 ms. The existing four-player 30 FPS target remains unmet.

The later [magnum/explosion pass](MAGNUM_EXPLOSIONS.md) adds one 16×16 energy-cloud sprite to this bank and reuses the vehicle fire/smoke textures for ordinary detonations. The labeled effects fixture now includes a fifth page of staged primed frag, plasma, rocket and cannon projectiles; detonation and drawing run through production code.

## First-person reload / overheat refinement (2026-10-09)

The AR and rocket reloads previously retained only eight evenly spaced poses.
Linear interpolation across these large gaps rounded off the hand contacts and
rigid magazine/cartridge turns. `pack_interactions.py` now skins every original
30 Hz frame onto the approved meshes, keeping the existing indexed geometry.
AR reload uses 87 frames; rocket partial/empty reloads use 111/125 frames. The
AR counter shares the same dense timeline. Gameplay retains the original
empty-reload timer even when the visual partial-reload sequence finishes early
(`source/items/weapons.c`, `weapon_magazine_start_reload`).

The plasma pistol previously stretched its nine-frame overheated loop across
the entire cooldown. It now uses the original normal and supercharge entry
clips (34/24 frames), vent loop (9), and closing clip (24). Three bounded green
wisps use the owned `plasma overheat` particle and original animated vent
markers. The existing demake heat accumulation/cooling rules remain; closing
is aligned to their recovery threshold, so this is not a claim of full retail
heat-state parity.

Rocket labels have white RGB and carry their lettering in alpha. Baking only
RGB made solid white sheets, which also intersected the quantized shell. The
renderer now samples the original mask in a 64×32 RGBA16 atlas with point
filtering and alpha rejection. Label planes sit 1.5 coordinate steps above
the shell, with their original rigid bone attachments retained for all poses.
`repair_rocket_decals.py` makes this separation reproducible and idempotent.

The streamed pose cache remains 8 × (8,736 + 128) = 70,912 bytes, and all
first-person vertex counts are unchanged. Added resident textures are 4 KiB
for rocket lettering and 1 KiB for the vent particle; service metadata adds
less than 1 KiB. At most six extra triangles draw for the local vent effect.
The larger animation bank lives on ROM.

`--reload-qa --paced30 --rspq-buffer-kib 32` stages AR, plasma pistol, empty
rocket and partial rocket reloads in four views; alternating cycles exercise
normal and charged overheat entries. Use `--validate --rspq-buffer-kib 8` for
the diagnostic build. Local videos, comparisons and ROM identities are in
`build/n64/reload-audit/`. Native sanitizers, pose bounds/DMA checks and dense
keyframe preservation checks are separate from Ares visual/performance QA.

Final Ares verification (4 MiB): all 37 release lifecycle steps pass, with
29 KiB free during the staged match and 341 KiB on return to the main menu.
The 8 KiB-queue reload diagnostic reports zero RDP errors/warnings. The quiet
32 KiB-queue replay measures 24.3 FPS overall, 26.2 combat, 22.5 vehicle;
P95 66.8 ms, maximum 200.5 ms, 44 KiB live heap free. The previous build was
24.4 / 26.3 / 22.7 FPS. The >25 FPS vehicle gate remains open.
