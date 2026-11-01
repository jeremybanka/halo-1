# Halo 3: ODST armor

Stacked on the Jorge armor PR (#13). ODST is an independent, repeatable armor
choice for the four existing profiles, available with 8 MiB RAM. It has 100
health and **zero shields** on spawn, recharge, respawn and Firefight resupply.
It cannot consume overshields, has no shield bar or shield warning/charge audio,
and uses ordinary weapon, health and damage rules.

The normal flashlight control toggles VISR for its wearer. That viewport becomes
`#004411` with a subtle eight-pixel grid. Only living hostile units appear, as
flat `#bbffcc` silhouettes, including enemies with zero camouflage opacity and
occupants of closed vehicles. Allies, corpses, scenery, vehicles, weapons,
effects and HUD disappear. World depth is deliberately omitted: enemies remain
visible through walls. Each split-screen viewport makes this choice independently.

The body uses the standard helmeted **Halo 3: ODST** design. The visor is bright
cyan in every palette. Only the original painted crown stripe changes with
profile color, or red/blue team assignment. Armor, undersuit, pack and personal
first-person plates remain neutral. First person retains CE's animated glove and
sleeve backing with four original ODST forearm components; weapon colors and
clocks are unchanged.

## Fresh source and demake

This follows [CHARACTER_DEMAKE.md](CHARACTER_DEMAKE.md). The earlier ODST mesh
attempt is not an input. The source was extracted again from the owned archive
in Downloads, preserving the original archive and extracted caches. The private
library is `halo64-assets/assets/odst-policy/`:

- Archive SHA-256: `d268d4211fbed914832215aab041765b74ef76bbb0ef12c68383603907dfa2d7`.
- `c100.map`: `487f02a4bc1fd1fbfaffa7b038cff6edfb8d1c9d230c90d5ebabff940964a1de`.
- Retail build `13895.09.04.27.2201.atlas_relea`, tag
  `objects\characters\odst\odst`: 8,647 triangles, 7,885 vertices, 55 bones,
  78 physical region/material components before crown paint partitioning.

`source/` preserves native geometry, UVs, four-influence weights, hierarchy,
material metadata, diffuse inputs, component inventory and retarget decisions.
The independent BLEND also contains an editable native 55-bone reference rig.
Gameplay uses an explicit adaptation to the 19-bone CE hierarchy and its 39
motion clips. Facial/finger and extra source bone motion are approximated by
named CE anchors; these are not the original Halo 3 animations. Collision and
hit regions retain the existing CE model.

A shoulder pilot reduced 260 to 146 triangles before body reduction. Components
are reduced separately with source-face/barycentric correspondence, protected
rims, sampled surface-distance checks and closed-volume limits. Budgets are
soft: near permits 0.002 Halo units of rim movement and 0.006 sampled surface
error, with 90–110% closed volume; far permits 0.004 / 0.008 and 80–110% volume.
At 3.048 meters per Halo unit, those surface limits are about 18 / 24 mm.
They are sampled guards, not exhaustive geometric bounds.

| Preserved checkpoint | Near triangles | Far triangles | Purpose |
|---|---:|---:|---|
| `solid/` | 3,287 | 2,769 | Conservative source-surface baseline |
| `playable/` | 3,325 | 2,813 | Protect crown stripe and soften rim constraints |
| `runtime/` | 3,325 | 1,726 | Independent far reduction; omit selected small gear |
| `covered/` | 3,350 | 1,781 | Restore 25 / 55 audited original seam faces |

Each checkpoint retains geometry, weights, animation arrays, decisions and its
own editable BLEND and skinned body-only GLBs. Final restoration adds original
source faces, not a primitive reconstruction. Opposite winding sides of thin
surfaces retain separate export vertices. `stage-ledger.json` records parent and
artifact hashes. `review/` contains matched source/packed views and a comparison
with the actual 328 / 135-triangle CE body, using the same idle pose and camera.
This remains substantially heavier than CE; it is not a completed 700-triangle
optimization.

## Runtime cost and validation

| Body cost | Near | Far |
|---|---:|---:|
| Triangles | 3,350 | 1,781 |
| Packed N64 vertices | 3,656 | 2,048 |
| Tiny3D batches | 85 | 46 |
| Complete animated coordinate tracks | 1,957 | 1,179 |
| Resident original mesh bytes | 79,296 | 43,840 |
| Two frame endpoints | 13,312 | 8,064 |

The optional body bank is **2,542,592 ROM bytes**. Both meshes plus the shared
maximum endpoint cache use 136,448 bytes before per-player fenced output,
commands and first-person buffers. Per player, near plus far vertex output uses
91,264 bytes per frame slot. Personal forearms add 282 packed vertices / 264
triangles over the existing glove/sleeve mesh. These are asset costs, not total
match-memory measurements.

Coordinates use 512 units per Halo unit, approximately a 6 mm grid. Full
quantized trajectories determine sharing; bind-position equality alone does
not. Per-frame origins and three 9-bit coordinate planes preserve the selected
coordinates exactly. The runtime streams at most two endpoints, with seven near
and four far samples per clip (or fewer for shorter sources), retaining original
durations and ODST-specific grip sockets and bounds.

Validation evidence is kept separately:

- 454 authoring poses per LOD agree with independent Blender skinning within
  0.00001 Halo units. Both GLBs contain all 39 clips, with meter coordinates. Reimport checks
  390 authored-key and 390 intermediate clock samples; maximum measured
  position error is 0.469 mm against a 1 mm acceptance limit. Interchange
  animations are sampled at 300 Hz to preserve quaternion interpolation; the
  compact N64 bank remains independently packed at seven/four samples per clip.
- 128 quantized coverage probes: four poses, eight directions, 64/96-pixel
  targets and two LODs; zero newly enclosed background pixels. Existing gap
  growth is reported separately. This is not exhaustive animation coverage.
- Actual C bank loader/decoder under ASan/UBSan: 4,680 cases, alternating LODs,
  four player phases, looping, clamping, blending, sockets and bank reloads.
  Every serialized endpoint, socket and bound is also checked against the bake.
- Actual C first-person binding under sanitizers: 1,409 production poses, four
  profiles, ready/service/reload actions and unchanged weapon colors.
- Host gameplay/menu checks cover shieldless damage, pickups, regeneration,
  respawn, flashlight/VISR isolation, cloaked enemies, allies, all controller
  rosters, 13 maps / 26 presets and Firefight for 1–4 players.
- Ares v148 at 8 MiB: mixed normal/VISR views, zero-opacity targets, team
  exclusion, first-person plates and the scripted four-player menu lifecycle.
  Captures and ROM hashes are in `native/`. These are emulator checks, not
  physical-console performance or full-match peak-memory qualification.

Release ROMs compile at 64,241,664 bytes (multiplayer) and 66,928,640 bytes
(Firefight), within the 64 MiB cartridge limit. The inherited replay fixture's
`gunner>0` failure is documented in [ARMOR_SETUP.md](ARMOR_SETUP.md); a full
regression-suite pass is not claimed.

## Reproduction

Use the locally owned source caches with their shared resources. Raw game
caches, archives, derived models, textures and screenshots remain in ignored
build directories or the private asset submodule, never the public source repo.
Historical checkpoint artifacts are retained independently; the maintained
reducer produces the current runtime candidate.

```sh
build/n64-python/bin/python port/n64/extract_odst.py --cache /path/to/maps/c100.map --ce halo64-assets/assets/extended-raw.json --output halo64-assets/assets/odst-policy/source
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python port/n64/demake_odst.py -- halo64-assets/assets/odst-policy/source/odst-ce-raw.json halo64-assets/assets/jorge/playable-half/ce-motion-source.json halo64-assets/assets/odst-policy/runtime
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python port/n64/repair_odst.py -- halo64-assets/assets/odst-policy port/n64/odst_coverage_faces.json halo64-assets/assets/odst-policy/covered
build/n64-python/bin/python port/n64/pack_odst.py halo64-assets/assets/odst-policy/covered/solid.json halo64-assets/generated/odst
build/n64-python/bin/python port/n64/pack_odst_firstperson.py
build/n64-python/bin/python port/n64/review_odst.py halo64-assets/assets/odst-policy halo64-assets/generated/odst halo64-assets/assets/odst-policy/review
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python port/n64/odst_library.py -- halo64-assets/assets/odst-policy
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python port/n64/validate_odst_exports.py -- halo64-assets/assets/odst-policy
build/n64-python/bin/python port/n64/certify_odst.py
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/odst-release
build/n64-python/bin/python port/n64/build.py --preset release --firefight --output-dir build/odst-firefight
```

`setup_assets.py` links the generated bank into the ROM filesystem. Builds check
the certification's source and file fingerprints. Native fixtures use
`--odst-qa 0` (four palettes / LODs), `1` (VISR / cloak), `2` (first person),
`3` (teams), or `--odst-frontend-qa`; add `--validate --rspq-buffer-kib 32`.

The published private asset commit and release hashes are recorded in
[`benchmarks/odst/validation.json`](benchmarks/odst/validation.json).
