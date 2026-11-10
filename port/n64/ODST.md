# ODST BDU armor

Stacked on Jorge (#13), ODST is an independent armor choice for all four
profiles at 8 MiB. It has 100 health and **zero shields**, including on respawn
and Firefight resupply. It cannot consume overshields. Ordinary ammunition,
health, damage and weapon zoom rules still apply.

The standard Halo 3: ODST helmet/body supplies the design. Its visor stays
bright cyan and the mohawk-like crown stripe stays neutral grey. Profile or
team color is confined to the chest and shoulder plates, using a deliberately
muted 80/255 weight in the existing color multiplier. Helmet, fabric, backpack,
forearm plates and the crown stripe remain independent of profile/team color.
The armor summary reads **ODST BDU**. Collision and hit regions still use CE.

The normal flashlight control toggles VISR for that viewport:

- Background `#004411`, with a faint eight-pixel grid. An inverse barrel map
  makes the grid densest at the center and spreads it toward the edges.
- Living enemies, including fully cloaked enemies, are flat `#bbffcc` silhouettes.
- Allies and the wearer's arms, weapon or carried objective are flat
  `#3f8da6`, halfway between active HUD cyan (`#64dcff`) and inactive HUD cyan
  (`#193e4d`). Both HUD colors retain their existing brightness.
- The normal HUD stays visible. Terrain, scenery, vehicles and dropship hulls
  retain their normal depth, so both friendly and hostile silhouettes are
  partially or completely hidden by obstacles. Other world color/effects vanish.
- Pistol 2×, sniper 2×/10× and rocket zoom use the ordinary camera projection,
  scope HUD and viewmodel visibility predicate. Neighboring normal views are
  independent. The grid caches wide/narrow textures separately for mixed three-player
  layouts (48,000 bytes of shared renderer storage).

SWAT and Team SWAT require this armor, with pistol-only starts, no grenades,
no ground weapon pickups, no vehicles and no radar. The free-for-all/team
scoring and setup rules are documented in [MULTIPLAYER_MODES.md](MULTIPLAYER_MODES.md).
Both variants use the original Reach announcer recordings: **“SWAT. Slayer.”**

## Source and reduction

The process follows [CHARACTER_DEMAKE.md](CHARACTER_DEMAKE.md), including the
later [Jorge near/far lessons](JORGE_LODS.md). The discarded pre-policy attempt
is not an input. The untouched extraction and earlier solid `covered/` model
remain separate from the `game-base/`, accepted `game-scale/` body and latest
`helmet-budget/` artifacts
in the private `halo64-assets/assets/odst-policy/` library.

The owned source archive SHA-256 is
`d268d4211fbed914832215aab041765b74ef76bbb0ef12c68383603907dfa2d7`;
`c100.map` is
`487f02a4bc1fd1fbfaffa7b038cff6edfb8d1c9d230c90d5ebabff940964a1de`.
Retail build `13895.09.04.27.2201.atlas_relea`, tag
`objects\characters\odst\odst`, contains 8,647 triangles, 7,885 vertices,
55 bones and 78 physical region/material components before crown paint splitting.
Native geometry, UVs, weights, hierarchy, diffuse inputs, materials and the
component inventory are preserved. The editable BLEND includes the intact
55-bone reference and an explicit 19-bone CE gameplay adaptation. Its 39 CE
motion clips approximate source facial/finger/extra-bone behavior; these are
not original Halo 3 animations.

`reduce_odst_game.py` starts from untouched extracted surfaces. It explicitly
omits small fasteners, straps, knife/sheath and selected far layers. Original
chest and shoulder curvature is retained. The torso, upper sleeves, legs and
boots remain a continuous reduced garment; recessed source-fitted lower sleeves
and pack lining supply local continuity. Accepted body and blended neck geometry
remain unchanged by this helmet revision.

`odst_helmet_lods.py` independently reduces each helmet from one half of the
untouched source, then mirrors its geometry and source-derived vertex colors.
Compatible endpoint quadric collapses retain original source contour points.
Material boundaries and the center plane simplify along themselves rather than
locking every original vertex or migrating the stripe onto unrelated triangles.
The near model keeps more contour constraints; the far model prioritizes its
jaw and nape returns. Both retain a centered, connected grey crown stripe.

Local visor/brow return faces reuse the reduced rim points. One audited original
forehead face per side keeps its original position instead of receiving an
outward fit. Two near / three far original shoulder, pack and neck seam faces
restore assembled coverage; the source IDs and correspondence are recorded.
No accepted body point is moved. The earlier shared 216-triangle helmet remains
an independent checkpoint, not the input to this new reduction.

Body overlap uses Jorge's 5% fit, capped at 16 mm. The coarse helmets use an
8% fit with 1.6 times the lateral contribution, still capped at 16 mm, to keep
neck/temple joins covered. Their source-surface errors are measured separately
from the exact retained-point correspondence and explicit fit offsets. Budgets
remain soft at protected contours; acceptance checks the packed geometry.
The immutable `game-scale/packed-reference/` supplies the comparison camera.
All earlier accepted libraries remain unchanged.

## Cost and evidence

| Body, including pack | Native vertices | GLB vertices | Packed vertices | Triangles |
|---|---:|---:|---:|---:|
| ODST near | 648 | 2,361 | **754** | 789 |
| Standard Spartan near | — | — | 562 | 328 |
| ODST far | 423 | 1,423 | **492** | 476 |
| Standard Spartan far | — | — | 250 | 135 |

Helmet-only packed vertices, including rendering splits and cache duplication:

| Helmet | Original coarse model | Previous smooth model | Current |
|---|---:|---:|---:|
| Near | 72 | 196 | **80** |
| Far | 51 | 191 | **65** |

Current helmets have 48 / 40 geometric vertices and
82 / 66 triangles. The far helmet has separate reduced topology.
Counts exclude the neck and shoulder/pack seam repairs. GLB body counts include
UV, color and normal splits; packed vertices measure actual game cost.
The body bank is **828,496 bytes**. Resident geometry plus its shared
endpoint cache uses 32,128 bytes; each player needs 19,936 bytes per
fenced frame slot for both body outputs. This is a similar vertex tier to
Spartan/Jorge, not triangle-count or rendering-cost parity. Personal first-person
plates remain 282 vertices / 264 triangles; weapons are counted separately.

The packer uses the same 48 per-channel color bound as CE. Opaque cache optimization
uses full quantized animation trajectories as vertex identities, keeps bind
coplanar precedence, and verifies unchanged geometry across every authored
pose. Coordinates remain exact on the selected 512-unit grid. Seven near and
four far runtime samples per clip stream through two bounded endpoint buffers;
original durations, ODST-specific sockets and conservative bounds are retained.

- 128 quantized coverage probes: four poses, eight views, 64/96-pixel targets,
  both LODs; **zero new enclosed background pixels**. Existing anatomical gap
  growth is recorded separately. Matched intact-source and Spartan comparisons
  are in `review-helmet-budget/`; the earlier body review remains in
  `review-game-scale/`.
- Exact mirrored head coordinates and colors in authoring and production
  packing; independently reduced near/far helmets; centered, connected grey
  stripe after quantization. All four palettes leave the helmet unchanged and
  tint only chest/shoulder vertices at 80/255.
- Sampled source-surface p95 error stays below 25 mm for both fitted helmets.
  This is distinct from retained-point, animation and coverage checks.
- 96 separate local depth probes inspect chest, forearm and pack fronts.
  Broad plate fronts remain clear of backing. Oblique joint returns are
  reported separately, including narrow cuff overlap; a filled body silhouette
  alone does not pass this check.
- Both independent editable LODs pass 454 Blender skinning samples. Body-only,
  meter-unit GLBs round-trip all 39 clips across 390 authored-key and 390
  playback-clock samples, with maximum error below 1 mm.
- Actual C streamed loader/decoder under ASan/UBSan: 4,680 cases, both LODs,
  four phases, endpoints, looping, clamping, blending, sockets and reloads.
  Custom first-person binding passes 1,409 production poses.
- Gameplay input tests cycle pistol, sniper, rocket and unsupported AR zoom
  with VISR on/off. Native fixtures compare ordinary/VISR focal lengths and
  exercise unzoomed, 2× and 10× views, HUD, cyan allies/viewmodels,
  camouflage, and partial/total environmental occlusion.

Ares v148 / paraLLEl-RDP checks use 8 MiB. Captures, logs and ROM hashes are
in `native-game-scale/`, with the latest friendly/viewmodel cyan checks in
`native-friendly-cyan/` and the current profile/team palette and helmet checks in
`native-helmet-budget/`. Multiplayer and Firefight release sizes and hashes
are in the validation ledger; both remain within 64 MiB. These are emulator and asset-allocation checks,
not physical-console performance or full-match peak-memory qualification.
The inherited `gunner>0` replay fixture still fails on unchanged parent/main;
a full regression-suite pass is not claimed.

## Reproduction

Raw archives/caches, derived assets and screenshots stay in ignored build
storage or the private asset submodule, never the public source repository.
Use the locally owned cache and shared resources for a fresh extraction.

```sh
# Start from the preserved game-scale body and untouched source library.
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/refine_odst_helmet.py -- halo64-assets/assets/odst-policy halo64-assets/assets/odst-policy/helmet-budget
build/n64-python/bin/python port/n64/pack_odst.py halo64-assets/assets/odst-policy/helmet-budget/solid.json halo64-assets/generated/odst
build/n64-python/bin/python port/n64/review_odst.py halo64-assets/assets/odst-policy halo64-assets/generated/odst halo64-assets/assets/odst-policy/review-helmet-budget --candidate helmet-budget --baseline-packed halo64-assets/assets/odst-policy/game-scale/packed-reference
build/n64-python/bin/python port/n64/audit_odst_helmet.py halo64-assets/assets/odst-policy/helmet-budget halo64-assets/assets/odst-policy/game-scale halo64-assets/assets/odst-policy/review-helmet-budget/helmet-symmetry.json --packed halo64-assets/generated/odst
build/n64-python/bin/python port/n64/audit_odst_clearance.py halo64-assets/assets/odst-policy/helmet-budget halo64-assets/assets/odst-policy/review-helmet-budget/armor-clearance.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/odst_helmet_lods.py -- halo64-assets/assets/odst-policy halo64-assets/assets/odst-policy/review-helmet-budget/helmet-source-surface.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/odst_library.py -- halo64-assets/assets/odst-policy helmet-budget helmet-budget/library
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/validate_odst_exports.py -- halo64-assets/assets/odst-policy helmet-budget helmet-budget/library
cp halo64-assets/generated/odst/odst.bin halo64-assets/frontend-files/odst.bin
build/n64-python/bin/python port/n64/certify_odst.py
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/odst-release
build/n64-python/bin/python port/n64/build.py --preset release --firefight --output-dir build/odst-firefight
```

Synchronize the generated `odst.bin` into `halo64-assets/frontend-files/` before
certification. Builds check source/file fingerprints. QA fixtures use
`--odst-qa 0` (palettes/LODs), `1` (cloak), `2` (first-person actions),
`3` (teams), `4` (HUD/viewmodel), `5` (pistol 2×), `6` (sniper 2×),
`7` (sniper 10×), `8` (ally partial/enemy hidden), `9` (enemy partial/ally hidden), `10` (mixed three-player grid cache), `11` (muted team plates with profiles on the same team).
Omit `--preset release` for these staged inspection fixtures; add
`--validate --rspq-buffer-kib 32`. Published asset and release hashes are in
[`benchmarks/odst/validation.json`](benchmarks/odst/validation.json).
