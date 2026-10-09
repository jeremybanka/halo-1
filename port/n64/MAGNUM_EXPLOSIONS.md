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

The silhouette follow-up matches the raised barrel's side profile and narrow
upper section to the source, and carries the magazine's diagonal through its
lower section and base plate. World conversion now uses the common gun-root
basis: source vertices already contain each part's bind rotation. Applying
the differing world magazine bind rotation again had straightened the model.
First-person animation still uses each part's original bone transform.

`audit_magnum_silhouette.py` overlays source, previous and revised meshes with
identical coordinates, scale and camera. It covers side, top, front and
three-quarter views for both the world mesh and original first-person idle
pose. World silhouette IoU changes from .773/.926/.855/.823 to
.851/.925/.878/.886; FP idle from .813/.928/.895/.872 to .852/.929/.924/.884.
This measures occupied silhouette area, not texture fidelity or every pose.

The first-person gun now has 268 triangles; with hands, 466. The barrel/profile
follow-up adds 32 triangles over the first rectangular proxy. UV seams use
728 loaded vertices; ready-animation scratch is 8,736 bytes within a bounded
9 KiB bank budget. The near world proxy has 256
triangles and omits the FP reload cartridge. Original far and micro pickup
silhouettes remain; they are not used for the held/first-person gun.
The texture remains 4 KiB. Sharing UV planes across coplanar triangles avoids
unnecessary seams and animation vertices.

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

The silhouette revision's quiet 4 MiB Ares paced30 replay presented 1,998 poses
in 75.017 s: 26.6 FPS overall, 27.7 combat, 25.6 vehicles, with 135 KiB live free. P95 was
66.8 ms and the worst presentation interval was 267.4 ms. These are averages,
not evidence of a 25/30 FPS floor. The preceding textured proxy measured
26.5/27.8/25.3 with 143 KiB live free. The prior flat proxy measured 26.4/27.7/25.1.
The pre-refinement release measured 26.8/27.8/25.9 in the preceding audit.

Silhouette evidence: `build/n64/magnum-silhouette-audit/comparison.html`, with
registered overlays, matching idle/reload/melee captures and a fresh quiet
timing run. All four model-pose pages report zero RDP errors/warnings. The
first-person bank adds 2,548 bytes and ready scratch grows from 8,064 to 8,736
bytes; texture bytes are unchanged. Asset, DMA and hand-seam checks pass.

Earlier texture/explosion evidence: `build/n64/magnum-explosion-audit/comparison.html`, including
matching Ares poses, a multi-angle source audit, recordings, decoder logs and
the native performance screenshot. The playable ROM is
`build/n64/halo-blood-gulch-paced30-rspq32k.z64`.
