# Jorge: matte pack, warm shoulder and personal first-person views

Current source: `halo64-assets/assets/jorge/playable-personal/`.
The accepted `playable-refined` checkpoint remains unchanged.

## Appearance

The backpack now has a matte gray-brown finish sampled from the original Reach
gear diffuse at 64×64. Original surface UVs are recovered by nearest-triangle
projection and retained in the BLEND. Small grime is compressed; the metallic
reflection band is removed. The N64 receives the baked vertex colors, so this
does not add a texture upload or render pass. The backpack's Blender material
has zero metallic and 0.95 roughness.

The pale heavy left shoulder (above the supporting arm) and hand plates use a
muted warm ochre finish. They remain distinct from the olive forearm/torso armor
without the former bright gray highlight. The black headband is unchanged.

`material-comparison.png` shows matched front/back views; `standard-comparison.png`
compares with the actual CE Spartan and the previous Jorge.

## First person

Four original Jorge forearm components form an additional **74 packed vertices /
88 triangles**. These are fitted to the CE arm proportions by wrist, elbow and
palm landmarks. The existing articulated glove/sleeve mesh forms continuous dark
backing, with coordinated olive and ochre glove colors. The original weapon
geometry, textures, display overlays and muzzle locations are unchanged.

Both forearm frames are recovered from the already animated CE glove vertices
using a bounded affine binding. Reload, melee, ready, overheat and passenger
animations therefore share the exact existing weapon clock. There is no new
per-frame animation bank. The additional arm buffer costs 1,184 bytes per live
frame slot per Jorge player; profile changes fence/release the buffers before
resizing. Standard Spartan profiles retain their original viewmodels.

Looking down draws **783 triangles** from Jorge's lower-body components, including
the connecting undersuit. The head and upper torso stay hidden. The close-range
foreground projection prevents the world near plane from cutting through the
thighs during crouching. Legs and arms share depth so they occlude each other. A small
local backward placement adjustment fits the larger Reach thighs under the CE
eye position; world bodies, collision, camera origin and aim are unchanged.
The legs use the normal body animation, including running and crouching.
Two inset cloth caps close the upper thigh openings exposed by this new angle.
They add 15 native vertices and 11 triangles; all accepted armor is untouched.

| Body metric | Previous refined | Current |
|---|---:|---:|
| Exported GLB vertices | 1,372 | 1,387 |
| Native vertices | 1,319 | 1,334 |
| Triangles | 2,097 | 2,108 |
| Packed N64 vertices | 2,282 | 2,264 |
| Components / bones / clips | 49 / 85 / 39 | 51 / 85 / 39 |

Component budgets remain in `component-budgets.csv`. The body still has one
near/far mesh. The final reduction and dedicated distant LOD remain separate work.

## Validation

- Every accepted source vertex, triangle and all 39 pose arrays compare exactly.
- All 39 clips / 1,530 frames and grip sockets serialize exactly into the ROM bank.
- GLB re-import checks five samples of all 39 clips against the editable rig.
- The actual C first-person binding passes address/undefined-behavior sanitizers
  on **1,409 production poses**: 198 core frames and 1,211 ready/service frames.
- Quantized forearm frame scale remains between 0.926 and 1.077 across those
  poses; no plate collapse or explosive extrapolation. Weapon colors are unchanged.
- Single-player field QA shows all nine weapon choices and standing/walking/crouching legs.
  The existing production flamethrower-to-AR viewmodel alias is retained.
- The selectable Jorge profile still requires 8 MiB. These visual tests use the
  existing 4 MiB Ares setting. The four-player first-person test reached a black
  screen on its first page at 4 MiB; the 8 MiB test is pending permission to
  temporarily enable Ares's Expansion Pak. Four-player rendering and production
  memory/frame timing are not yet qualified.

## Reproduce

In background Blender, open the preserved `playable-refined` BLEND, add
`port/n64` to `sys.path`, and run `personalize_jorge.py`. It writes the new BLEND,
GLBs, material changes, thigh caps, native forearm source and animation bake.

```sh
build/n64-python/bin/python port/n64/pack_jorge.py \
  --asset-dir halo64-assets/assets/jorge/playable-personal --name jorge-playable-personal
build/n64-python/bin/python port/n64/pack_jorge_firstperson.py
build/n64-python/bin/python port/n64/test_jorge_bank.py
build/n64-python/bin/python port/n64/test_jorge_firstperson.py
```

With the personal BLEND open, run `validate_jorge_personal.py`, then
`roundtrip_jorge_playable.py`. For runtime renders configure `personalize_jorge`
before running `preview_jorge_playable.py`, then run `review_jorge_personal.py`.

```sh
build/n64-python/bin/python port/n64/build.py --jorge-field-qa --jorge-field-start 26 \
  --output-dir build/n64-jorge-personal
build/n64-python/bin/python port/n64/build.py --preset release \
  --output-dir build/n64-jorge-personal-release
```

Field pages 26–28 show the full-screen look-down view while standing, walking
and crouching with one active player. Pages 29–37 exercise all nine weapons in
single-player. Pages 38–46 alternate mixed Jorge/CE profiles and four Jorges,
with different weapons and action timings per quadrant. Pages 47–49 exercise
four-player standing/walking/crouching look-down views.

Pages 0–8 compare first-person weapons with the standard Spartan;
Jorge is the upper view. Earlier held-weapon and vehicle pages remain available.
