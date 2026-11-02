# ODST BDU armor

Stacked on Jorge (#13), ODST is an independent armor choice for all four
profiles at 8 MiB. It has 100 health and **zero shields**, including on respawn
and Firefight resupply. It cannot consume overshields. Ordinary ammunition,
health, damage and weapon zoom rules still apply.

The standard Halo 3: ODST helmet/body supplies the design. Its visor stays
bright cyan. Only the original crown stripe carries profile or team color;
armor, fabric, backpack and personal forearm plates remain neutral. The armor
selection summary reads **ODST BDU**. Collision and hit regions still use CE.

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

## Source and reduction

The process follows [CHARACTER_DEMAKE.md](CHARACTER_DEMAKE.md), including the
later [Jorge near/far lessons](JORGE_LODS.md). The discarded pre-policy attempt
is not an input. The untouched extraction and earlier solid `covered/` model
remain separate from the new `game-base/` and accepted `game-scale/` artifacts
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

`reduce_odst_game.py` always starts from the untouched extracted surfaces.
It explicitly omits small fasteners, straps, knife/sheath and selected far
layers. Helmet shell, visor and crown paint share geometry during reduction;
the chest and shoulders keep original curved surfaces. Hands and forearm
volumes use retained source contour points. The original torso, upper sleeves,
legs and boots remain a continuous reduced garment, with protected boot/limb
extrema. Recessed source-fitted lower sleeves and pack lining supply local
continuity. The hidden garment front is fitted behind the chest/waist opening;
its displacements are recorded separately from source correspondence.

Armor overlap follows Jorge's 5% fit, capped at 16 mm, with a one-unit minimum
on the approximately 6 mm packed grid. Hidden backing is excluded from that
expansion. Nearest-source faces, barycentrics, normalized skin weights, explicit
component decisions, sampled reduction error and fit offsets are retained.
The coverage repair list restores audited original source faces, rather than
halving a damaged mesh again. Failed budget/coverage candidates are kept in
ignored build storage; the original accepted solid library is unchanged.

## Cost and evidence

| Body, including pack | Native vertices | GLB vertices | Packed vertices | Triangles |
|---|---:|---:|---:|---:|
| ODST near | 625 | 2,305 | **738** | 770 |
| Standard Spartan near | — | — | 562 | 328 |
| ODST far | 402 | 1,337 | **464** | 447 |
| Standard Spartan far | — | — | 250 | 135 |

GLB counts include UV, color and flat-normal splits; packed vertices measure
the actual game cost. The previous ODST used 3,656 / 2,048 packed vertices. This is a similar vertex
tier to the reduced Spartan/Jorge bodies, not triangle-count or rendering-cost
parity. The independent near/far bank is **802,784 bytes**. Resident geometry
plus the shared two-endpoint cache uses 30,992 bytes; each player needs
19,232 bytes per fenced frame slot for both body outputs. Personal
first-person plates remain 282 vertices / 264 triangles over CE's glove/sleeve
backing. Weapons are counted separately.

The packer uses the same 48 per-channel color bound as CE. Opaque cache optimization
uses full quantized animation trajectories as vertex identities, keeps bind
coplanar precedence, and verifies unchanged geometry across every authored
pose. Coordinates remain exact on the selected 512-unit grid. Seven near and
four far runtime samples per clip stream through two bounded endpoint buffers;
original durations, ODST-specific sockets and conservative bounds are retained.

- 128 quantized coverage probes: four poses, eight views, 64/96-pixel targets,
  both LODs; **zero new enclosed background pixels**. Existing anatomical gap
  growth is recorded separately. Matched intact-source and Spartan comparisons
  are in `review-game-scale/`.
- 96 separate local depth probes inspect chest, forearm and pack fronts.
  Broad plate fronts remain clear of backing. Oblique joint returns are
  reported separately, including narrow cuff overlap; a filled body silhouette
  alone does not pass this check.
- Both independent editable LODs pass 454 Blender skinning samples. Body-only,
  meter-unit GLBs round-trip all 39 clips across 390 authored-key and 390
  playback-clock samples, with maximum error 0.474 mm against a 1 mm gate.
- Actual C streamed loader/decoder under ASan/UBSan: 4,680 cases, both LODs,
  four phases, endpoints, looping, clamping, blending, sockets and reloads.
  Custom first-person binding passes 1,409 production poses.
- Gameplay input tests cycle pistol, sniper, rocket and unsupported AR zoom
  with VISR on/off. Native fixtures compare ordinary/VISR focal lengths and
  exercise unzoomed, 2× and 10× views, HUD, cyan allies/viewmodels,
  camouflage, and partial/total environmental occlusion.

Ares v148 / paraLLEl-RDP checks use 8 MiB. Captures, logs and ROM hashes are
in `native-game-scale/`, with the latest friendly/viewmodel cyan checks in
`native-friendly-cyan/`. Multiplayer and Firefight releases are 62,488,576 and
65,175,552 bytes, within 64 MiB. These are emulator and asset-allocation checks,
not physical-console performance or full-match peak-memory qualification.
The inherited `gunner>0` replay fixture still fails on unchanged parent/main;
a full regression-suite pass is not claimed.

## Reproduction

Raw archives/caches, derived assets and screenshots stay in ignored build
storage or the private asset submodule, never the public source repository.
Use the locally owned cache and shared resources for a fresh extraction.

```sh
build/n64-python/bin/python port/n64/extract_odst.py --cache /path/to/maps/c100.map --ce halo64-assets/assets/extended-raw.json --output halo64-assets/assets/odst-policy/source
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/reduce_odst_game.py -- halo64-assets/assets/odst-policy halo64-assets/assets/odst-policy/game-base
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/repair_odst.py -- halo64-assets/assets/odst-policy port/n64/odst_game_coverage_faces.json halo64-assets/assets/odst-policy/game-scale game-base reorder
build/n64-python/bin/python port/n64/pack_odst.py halo64-assets/assets/odst-policy/game-scale/solid.json halo64-assets/generated/odst
build/n64-python/bin/python port/n64/review_odst.py halo64-assets/assets/odst-policy halo64-assets/generated/odst halo64-assets/assets/odst-policy/review-game-scale --candidate game-scale
build/n64-python/bin/python port/n64/audit_odst_clearance.py halo64-assets/assets/odst-policy/game-scale halo64-assets/assets/odst-policy/review-game-scale/armor-clearance.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/odst_library.py -- halo64-assets/assets/odst-policy game-scale game-scale/library
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python port/n64/validate_odst_exports.py -- halo64-assets/assets/odst-policy game-scale game-scale/library
build/n64-python/bin/python port/n64/certify_odst.py
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/odst-release
build/n64-python/bin/python port/n64/build.py --preset release --firefight --output-dir build/odst-firefight
```

Synchronize the generated `odst.bin` into `halo64-assets/frontend-files/` before
certification. Builds check source/file fingerprints. QA fixtures use
`--odst-qa 0` (palettes/LODs), `1` (cloak), `2` (first-person actions),
`3` (teams), `4` (HUD/viewmodel), `5` (pistol 2×), `6` (sniper 2×),
`7` (sniper 10×), `8` (ally partial/enemy hidden), `9` (enemy partial/ally hidden), `10` (mixed three-player grid cache).
Omit `--preset release` for these staged inspection fixtures; add
`--validate --rspq-buffer-kib 32`. Published asset and release hashes are in
[`benchmarks/odst/validation.json`](benchmarks/odst/validation.json).
