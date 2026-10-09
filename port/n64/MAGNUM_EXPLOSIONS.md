# Magnum and handheld explosion refinement

The M6D uses a box-built Blender proxy rather than a further decimation pass.
The slide, raised barrel housing, black grip, open trigger guard, sights,
magazine and muzzle are closed planar pieces, dimensioned against the owned
Xbox first-person bind mesh. Their original moving-part bones drive idle,
firing, reload, melee and ready clips. Existing hand geometry is retained.
The first-person pistol uses the owned Xbox diffuse texture, reduced to a
64×32 RGBA16 atlas (4 KiB). Source UV planes transfer onto matching proxy
faces with bone and normal constraints. Source RGB is reduced to 45% before
shading; the brightest atlas channels are 96/95/100, with darker grip and
side panels. A white final row preserves existing hand vertex colors and
solid dark sights/muzzle. Point sampling preserves crisp surface detail.
The world proxy uses colors sampled from this same adapted atlas.

The first-person gun has 236 triangles versus 231 previously; with hands,
434 versus 429. UV seams increase packed loaded vertices from 536 to 672
and batches from 11 to 13. Sharing UV planes across coplanar triangles avoids
76 redundant vertices; ready-animation scratch stays at 8,064 bytes. The near world proxy has 224
triangles and omits the FP reload cartridge. Original far and micro pickup
silhouettes remain; they are not used for the held/first-person gun.
The full first-person bank, including the atlas, grows by 4,458 bytes compared
with the previous reduction.

`magnum_geometry.py` is the reproducible Blender recipe. Reapply it after
both general model reduction passes, before packing:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python port/n64/magnum_geometry.py
build/n64-python/bin/python port/n64/pack_firstperson.py
build/n64-python/bin/python port/n64/pack_extended.py
build/n64-python/bin/python port/n64/pack_fp_ammo.py
build/n64-python/bin/python port/n64/pack_interactions.py
build/n64-python/bin/python port/n64/extract_weapon_effects.py
build/n64-python/bin/python port/n64/generate_micro_lods.py --assets build/n64/assets --verify-generated build/n64/generated --output build/n64/assets/micro-lods.json
build/n64-python/bin/python port/n64/pack_micro_lods.py
```

`magnum-refined.blend`, `magnum-texture.png`, the reduced meshes and generated payloads remain in
the private asset submodule. The source/previous/current multi-angle audit is
a neutral offline rendering of actual geometry, not retail Xbox footage.
The Ares pose captures use the normal model/animation/depth paths. Their
static fixture now clears weapon-ready time so each page shows its intended
pose instead of freezing the first frame of the ready animation.

Frag and rocket tags both reference `weapons\frag grenade\effects\explosion med`.
Its warm fire cloud and rising gray smoke replace the old opaque octahedron.
Plasma grenades and Needler detonations use their original shared energy-cloud
bitmap, with separate cyan and pink source color/lifetime stages. Existing
vehicle fire/smoke textures are reused; one additional 16×16 RGBA32 energy
sprite costs 1 KiB. Extracted reports retain source particle-system fields and
verify both human-weapon effect links.

This is a bounded visual approximation, not the complete Xbox particle solver.
Two analytic lobes replace the source's 10–35 emitted particles. Blasts retain
12 fixed slots and share the existing 32-quad pool, with a 12-quad blast cap per
camera, distance reduction and room reserved for first-person feedback.
Sprites test depth without writing it. No gameplay RNG, damage, fuses, radius,
projectile or audio behavior changes. Coincident vehicle death bursts replace
ordinary blast visuals as before. Particle collision, scorch decals, dynamic
lights and full additive shaders are not reproduced.

Host sanitizer checks cover all weapon effects, bounded blast replacement,
expiry/reset, coincident vehicle suppression, live showcases and destruction.
The first-person validator independently decodes every bank's indices,
materials, team masks and animation endpoints, plus pistol UV seams, hand
white-texel coordinates and the dark opaque RGBA16 atlas. The legacy full-world validator still assumes three Scorpion parts (the
existing hatch makes four) and does not reproduce the packer's low-LOD visor
material recovery. Those unrelated pre-existing assertions prevent a full
world-validation pass; the first-person decoder and targeted geometry checks
are run independently.
An independent Pillow comparison against the original diffuse confirms the
saved atlas matches box averaging × 0.45 within half a byte, without gamma
brightening. The interaction decoder verifies 1,969 ROM frames and all DMA
ranges; workspace lifecycle and hand-seam checks pass as well.

Ares validation through all five four-player effects pages reports zero RDP
errors/warnings. The primed-projectile page stages positions/fuses solely to
expose blast color stages; it is not a gameplay or performance benchmark.

The final quiet 4 MiB Ares paced30 replay presented 1,989 poses in 75.017 s:
26.5 FPS overall, 27.8 combat, 25.3 vehicles, with 143 KiB live free. P95 was
66.8 ms and the worst presentation interval was 267.4 ms. These are averages,
not evidence of a 25/30 FPS floor. The prior flat proxy measured 26.4/27.7/25.1.
The pre-refinement release measured 26.8/27.8/25.9 in the preceding audit.

Local evidence: `build/n64/magnum-explosion-audit/comparison.html`, including
matching Ares poses, a multi-angle source audit, recordings, decoder logs and
the native performance screenshot. The playable ROM is
`build/n64/halo-blood-gulch-paced30-rspq32k.z64`.
