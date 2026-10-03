# On-weapon ammunition presentation

The AR shows its current magazine count on its animated weapon screen. The
Needler's sixteen visible crystals use the original twenty-one ammunition
states, indexed by loaded rounds **0 through 20**. These changes are local to
each player's first-person model; gameplay ammunition and the HUD are separate.

## Original data and N64 adaptations

The owned Xbox Blood Gulch AR model, `weapons\assault rifle\fp\fp` (tag 277),
uses the numeric shader `weapons\assault rifle\fp\shaders\numbers`. Its limit
is 60 and its bitmap has ten frames. Shader permutations 1 and 0 select the
tens and units digits. The corresponding logic is in
`source/rasterizer/xbox/rasterizer_xbox_transparent_geometry.c`; the ammunition
function in `source/items/weapons.c` is loaded rounds divided by magazine
capacity. Reserve rounds never enter the AR number.

`extract_fp_ammo.py` extracts those ten original glyph images and the source
shader metadata. `pack_fp_ammo.py` follows the two preserved numeric planes
through every reduced idle, fire, reload and melee keyframe. The supplemental
planes use 4096 units per Halo unit because the ordinary FP scale of 256 makes
this small display nearly degenerate. The two-digit area is deliberately twice
the original size about its animated center for 160×120 readability. A dark
opaque backing replaces the Xbox additive shader. It uses the original blue
glyphs, not a second HUD counter or a replacement font.

The source planes have the opposite facing convention from the general FP
bank. The counter therefore uses `CULL_BACK`, while the original FP draw keeps
`CULL_FRONT`. In the standing four-player CPU projection fixture, the first
player's screen spans approximately x119–130/y82–90; recoil stays within the
viewport. The weapon may leave the viewport during its original reload/melee
animation. The counter follows it and is never pinned to the HUD.

The Needler animation tag 1532 contains `first-person ammunition`, an
uncompressed overlay with 21 native frames. Reclaimer inserts a synthetic
default frame before an exported overlay; extraction removes that extra frame
before using loaded rounds as the index. Rotation multiplication and flagged
translation follow `overlay_animation_apply` in
`source/models/model_animations.c`. The sixteen crystal bones retain their
original depletion order and partially retracted poses. Their visible count
is not proportional to magazine count: some ammunition changes shorten a
crystal instead of removing another one.

Fully retracted source states rotate the crystal inside the opaque shell. The
N64 FP pass disables depth testing, so those wholly folded components become
degenerate triangles; otherwise the later pink triangles would show through
the shell. All partially and fully extended states retain their source
transformations at the existing FP precision. Only the rigid crystals receive
this overlay. A tiny original pinky-tip translation is outside this feature.

Original reload regrowth begins at source tick 44 and settles over five ticks,
as specified in `source/interface/first_person_weapons.c`. The demake's Needler
reload lasts one second, while the extracted mesh clip lasts 71/30 seconds.
The renderer normalizes both mesh animation and regrowth to the same source
clock; regrowth therefore occurs around 62–69% of the actual reload. Its
predicted completion uses `min(loaded + reserve, 20)`, matching this port's
reload rule. The original expression uses reserve-exclusive `rounds_total`.
This explicit state-model adaptation does not change ammunition or damage.

## Cost and ownership

The AR adds eight transformed vertices and four triangles per visible AR.
Its 100×16 RGBA16 atlas occupies 3,200 bytes and fits TMEM; panel animation is
1,056 bytes. The existing four baked digit triangles remain in the approved
FP bank to preserve all base indices and animation sharing. The eight small
counter buffers occupy 1,024 bytes across two geometry slots and four players.

The Needler adds no draw calls, indices or triangles. Complete crystal motion
trajectories are shared across all ammo states and four clips. The current
supplemental data occupies 18,128 bytes and updates 133 packed positions,
including three padding vertices. RGB, UVs, normals and all other vertices
remain unchanged. The base first-person bank is read only during generation.

`bg_fp_ammo_prepare` runs once with ordinary FP animation, before that player's
first vertex borrow. Counter buffers use the caller's two fenced geometry
slots. CPU writes are written back before RSP reads; Needler changes update
the already selected segmented FP buffer. The final 3D slot fence protects
both. Counter drawing preserves the RDP mode and matrix stacks and restores
the general FP draw flags before the next viewport.

The counter's direct Tiny3D strip does not mark libdragon's RDP autosync
resources as busy. `t3d_tri_sync()` submits its triangles but does not finish
their RDP pipe use. An explicit `rdpq_sync_pipe()` therefore follows the
counter strip flush and precedes `rdpq_mode_pop()`, which restores the
combiner and other RDP modes. The entry transition already receives the
ordinary autosync barrier: the recorded weapon block restores an unknown/busy
resource state, and the first counter mode change synchronizes it. The
explicit exit barrier adds one required RDP pipe sync per visible AR.
The six counter mode changes are enclosed by `rdpq_mode_begin/end` before
the texture upload. This emits the final combiner and other-mode pair once
instead of six times, saving ten RDP command words per visible AR without
changing the state used by its triangles. Mode push/pop and the explicit exit
pipe sync remain outside the batch.

Initialization records eight counter command blocks, one for each geometry
slot and player. Each block keeps the address of that player's mutable digit
buffer and the shared immutable atlas, index buffer and precision matrix.
Replaying it reads the latest prepared positions/UVs; it does not snapshot
their values at initialization. The per-view call only checks the indices and
runs the selected block, avoiding repeated mode and texture-upload CPU setup.
Mode push/pop still execute at replay time and preserve the caller's state.
The blocks are retained for the match session, and the existing geometry-slot
fences continue to protect the digit buffers.

## Rebuild and checks

Run after the ordinary first-person bank has been packed:

```sh
build/n64-python/bin/python port/n64/extract_fp_ammo.py
build/n64-python/bin/python port/n64/pack_fp_ammo.py
build/n64-python/bin/python -m unittest discover -s port/n64 -p test_fp_ammo.py
clang -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Iport/n64 port/n64/test_firstperson_ammo.c \
  build/n64/generated/firstperson_ammo_data.c -o build/n64/test-firstperson-ammo
build/n64/test-firstperson-ammo
python3 port/n64/test_deferred_animation.py
python3 port/n64/test_fp_ammo_blocks.py
```

`test_fp_ammo_game.c` links with the same game/core/collision sources as
`test_game.c` and verifies real 30 Hz firing, recoil, reload and per-player
ammo isolation. `audit_fp_ammo.py` uses NumPy and Pillow to create 160×120
per-player previews with the actual shifted projection, indexed colors and
ammunition poses. It is a CPU proxy, not RDP pixel or frame-timing evidence.
Target screenshots and gameplay recordings are required separately to assess
actual screen readability and the added rendering cost.

`test_fp_ammo_blocks.py` executes the actual initialization and draw helpers
through a host command recorder. It compares direct setup with replay for all
eight buffers, changes their contents after recording, and checks exact command
order, vertex addresses, restored PIPE tracking and both synchronization points.
It also checks the installed libdragon block-tracking implementation. This is
an ownership/command regression, not a substitute for target RDP validation.
