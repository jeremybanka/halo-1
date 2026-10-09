# Yellow visors and vehicle destruction

The source Spartan low/superlow meshes merge the visor into their armor shader.
`pack_extended.py` recovers the broad visor panels from the highest original
visor material's bounds. Both LODs use RGB 255/224/18 with a zero team mask,
compensating for absent Xbox reflection shading and small split-screen views.
This changes eight near faces and two far faces without changing geometry,
animation positions, helmet armor or other models.

## Original vehicle references

The owned Xbox b40 Ghost and Banshee collision tags both reference
`vehicles\wraith\effects\death explosion`. That source combines a warm fire
cloud, a bright initial flare, blue-gray metal panels, drifting smoke, burning
flame and sparks. It is not simply a plasma-colored sphere. The exporter keeps
the full original effect and particle-system metadata in its local report.
The source sound is `sound\sfx\weapons\frag grenade\expl`, already present as
`BG_S_EXPLOSION`; no duplicate audio bank is needed.

`extract_vehicle_visuals.py` takes the original `~damaged low` permutations:
278 Ghost triangles and 200 Banshee triangles, with their burned source diffuse
colors. It packs five representative 16×16 sprites (5 KiB). At micro distances,
Covenant wrecks use the existing silhouette with a charred tint. Warthog and
Scorpion wrecks reuse the existing articulated geometry with a dark burnt tint;
these are deliberate extensions, not invented claims about original CE human
vehicle destruction assets.

## Lifetime and resource bounds

A lethal hit kills/ejects occupants once and emits a typed vehicle-destruction
event. The inactive vehicle record persists as an unpowered wreck for 12 seconds,
blinks four times during its last two seconds, then stops rendering and simulating.
The existing 20-second vehicle respawn timer still restores a healthy vehicle at
its original home. Wrecks cannot be boarded, targeted, or used to block players
or live vehicles. Their terrain contacts, gravity, bounce and angular motion
use the retained original rigid-body integrator with powered mass points removed.
Ghost antigravity and Banshee thrust therefore stop on death.

Only four destruction bursts can exist at once. Metal fragments are analytic
billboards, not additional physical objects. Flames last three seconds; two
advected smoke puffs fade by eight seconds. These replace the original dozens
of particles and do not reproduce every shader, scorch decal or emitter.
The shared effect vertex bank remains 32 quads per camera and reserves four
quads for first-person feedback. There are no new per-frame heap allocations.
Burned Covenant geometry has its own conservative bounds. All temporary
combiner state is restored before other models draw.

## Verification

```sh
build/n64-python/bin/python port/n64/pack_extended.py
build/n64-python/bin/python port/n64/pack_micro_lods.py
build/n64-python/bin/python port/n64/extract_vehicle_visuals.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py
build/n64-python/bin/python port/n64/test_render_matrix.py
build/n64-python/bin/python port/n64/test_vehicle_culling.py
build/n64-python/bin/python port/n64/test_vehicle_pose_cache.py
build/n64-python/bin/python port/n64/build.py --model-qa --validate
build/n64-python/bin/python port/n64/build.py --destruction-qa --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --frontend-qa 4 --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --frontend-qa 4 --validate --paced30 --paced30-buffers 4
```

The destruction fixture stages one low-health vehicle at a time and fires a real
rocket. Four inspection cameras omit their first-person weapon models. The
Banshee is held airborne before the shot; its destruction, fall and settling are
live simulation. Each 26-second page includes explosion, wreck, blinking,
removal and respawn. This is labeled QA footage, not a performance benchmark.
Host sanitizer checks cover four actual kills, a falling Banshee, all blink
phases, expiration, respawn, empty seats and surviving observers. Existing
vehicle, combat, two-loop replay and six gameplay-showcase checks also pass.

Local imagery, video, source metadata, timing and ROM hashes are kept under
`build/n64/destruction-audit/`. Original assets remain ignored by Git.

Full front-end graphics validation uses four display buffers in 4 MiB. The
additional validator instrumentation exceeds the remaining memory when five
buffers are used, failing at match entry. The production five-buffer build is
checked separately through the same 37-step menu, match, results and return flow.

The final quiet Ares 148 / NTSC / 4 MiB five-buffer run measures 28.6 FPS overall, 29.1 in combat and 28.2 around vehicles, compared with 28.6 / 29.0 / 28.1 previously. Free heap is 46 KiB versus 65 KiB. Combat P95 is 33.4 ms and vehicle P95 is 66.8 ms. This is one emulator sample; the existing 30 FPS target remains unmet and console timing is unverified.
