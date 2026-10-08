# Plasma weapon display repair

The first-person exporter approximated `shader_transparent_meter` with a solid
green material and discarded its alpha mask. The Plasma Pistol's two source
faces therefore appeared as a filled square, while the Plasma Rifle's reduced
curved meter sheet crossed the purple housing. The original pistol bitmap's
alpha contains a horseshoe; the rifle bitmap contains a much finer heat-gauge
pattern. These are simplified geometry replacements, not the Xbox meter shader.

`plasma_meters.py` replaces only those two materials, retaining the weapon
shells, hands, UVs, weights, and original animation clocks. The pistol uses an
angular open U, lifted 2/256 Halo units along its original display normal. The
rifle uses a narrow strip under the upper housing. They follow the original
`frame face` and `frame gun` bones respectively, including ready animations.
The replacement adds four pistol triangles and removes two rifle triangles.

The ordinary 1/256-unit animation coordinates collapsed the pistol's narrow
faces during some melee interpolations. Both meters now use 1/4096 coordinates
and real depth testing, sharing the existing sniper display workspace. The U
needs eight vertices and the rifle strip four; the existing twelve-vertex
buffers and matrices are sufficient. No new per-player allocation is required.
First-person bank payload grows by 198 bytes (including finer display poses;
excluding C descriptor/alignment overhead). The ordinary body banks lose ten
loaded vertices. The meters remain static green approximations; this change
does not add dynamic battery/heat-gauge behavior.

The full Blender reduction calls the repair automatically. To update only the
existing reduced bank:

```sh
build/n64-python/bin/python port/n64/plasma_meters.py
build/n64-python/bin/python port/n64/pack_firstperson.py
build/n64-python/bin/python port/n64/pack_fp_ammo.py
build/n64-python/bin/python port/n64/pack_interactions.py
build/n64-python/bin/python port/n64/extract_weapon_effects.py
```

`assets/plasma-meters.blend` is a separate geometry-review scene with simple
material colors; Ares captures are the color/occlusion evidence. When exporting
a newly created Blender scene, assign it to the window and update its view
layers before `bpy.data.libraries.write` (Blender 5.2 can crash while copying a
scene whose object bases have not been refreshed).

Verification commands:

```sh
build/n64-python/bin/python port/n64/test_plasma_meters.py
build/n64-python/bin/python port/n64/test_scope_geometry.py
build/n64-python/bin/python port/n64/test_fp_hand_seams.py
build/n64-python/bin/python port/n64/test_fp_ammo.py
build/n64-python/bin/python port/n64/validate_assets.py --firstperson-only
build/n64-python/bin/python port/n64/build.py --plasma-qa 0 --validate
```

The plasma test independently decodes the emitted finer pose arrays and tests
36,864 integer interpolation samples, plus every ready-animation interval.
The sniper's existing 18,432 samples still pass. The first-person validator
decodes all eight body meshes, indices, colors, team masks and animation
endpoints. The old whole-game validator currently stops at its stale three-part
Scorpion assertion (the existing hatch rig has four parts); that unrelated
check is not reported as passing.

`--plasma-qa 0/1` freezes pistol/rifle idle, firing, overheat and melee poses;
`2/3` shows four samples of their ready animations. These are visual fixtures,
not FPS measurements. All four passed in Ares with zero RDP errors/warnings.
Native before/after captures, ROMs and timing evidence live in
`build/n64/plasma-audit/`. Performance and the release lifecycle are recorded
there separately.

The final quiet four-buffer VI replay measures 26.7 FPS overall, 28.7 in combat
and 24.9 in the vehicle section; the preserved previous ROM repeats
26.9 / 28.8 / 25.1 in the same Ares configuration. Free heap is 53 KiB in both
timing fixtures. Final p95 intervals are 66.8 / 33.4 / 66.8 ms, with a 267.4 ms
maximum overall/combat and 66.9 ms vehicle maximum. The small vehicle-phase
regression remains below the development target and is recorded in the parity
checklist; this is not a sustained 25/30 FPS or hardware acceptance claim.
The release-matched four-player frontend fixture shows 11 KiB free heap during
combat (the benchmark omits the full menu lifecycle's memory/code footprint).
