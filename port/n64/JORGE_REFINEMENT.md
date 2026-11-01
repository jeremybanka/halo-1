# Jorge: metallic armor, central forms and first-person views

This checkpoint is preserved in `halo64-assets/assets/jorge/playable-refined/`.
The current bank is the [first-person and material update](JORGE_FIRSTPERSON.md).
The accepted `playable-half` checkpoint and earlier source models are unchanged.
Jorge remains the fifth profile, with the same gameplay dimensions, CE movement,
and shared first-person Spartan arms. This pass adds no character abilities.

| Body metric | Previous checkpoint | Refined |
|---|---:|---:|
| Exported GLB vertices | 1,194 | 1,372 |
| Native Blender vertices | 1,141 | 1,319 |
| Triangles | 1,778 | 2,097 |
| Packed N64 vertices | 2,008 | 2,282 |
| Component meshes / bones / animation clips | 49 / 85 / 39 | 49 / 85 / 39 |

The extra 178 exported vertices restore forms and coverage before the final
reduction. Budgets remain separate per component in `component-budgets.csv`.
The body still shares one near/far mesh; a dedicated low LOD is deferred.

## Appearance

All armor plates use broad light-to-dark metallic ramps derived from the retained
CE donor colors. The black helmet band, olive paint, yellow breastplate, red and
pale asymmetric shoulder armor, dark fabric and gray-brown backpack remain.
The gradient follows each plate's height and normals, with a symmetric normal
response. The GLB stores the result in `COLOR_0`; the N64 bank samples those same
colors. This is a fixed color bake, not a dynamic reflection effect. The two
editable materials also have metallic/roughness settings for Blender/GLB viewers.

The yellow chest, green collar frame, codpiece and abdominal plate have matched
center seams and mirrored topology/weights. Jorge's intentional shoulder/collar
attachment asymmetry is retained. The backpack is restored from the intact
199-vertex detail-pass reference, protecting its broad upper shoulder shape and
recessed center before reducing lower surfaces and mirroring it. Small symmetric
overlaps and seven mirrored pairs of source triangles retain seam coverage.

`standard-comparison.png` shows the actual packed CE Spartan, previous Jorge and
refined Jorge at the same scale. `before-after.png` covers all five viewpoints;
`motion-contact-sheet.png` covers every baked state. The BLEND, GLBs, original CE
atlas, packed previews, component budgets and validation reports are alongside them.

## Camera and interaction fixes

The first-person animation path previously rejected every seated player while
the drawing path allowed passengers to use personal weapons. That disagreement
could leave a passenger's first-person mesh uninitialized or stale. Animation and
drawing now use the same `bg_player_firstperson_weapon()` predicate: living,
unscoped, stable personal-weapon seats with a first-person camera are supported.
Drivers, gunners, entry/exit transitions, death and scoped views retain their
existing behavior. Model inspection now also hides the local player's body in
first person, matching ordinary gameplay instead of placing the camera inside it.

`--jorge-field-qa` runs real simulation inputs for nine weapons, their firing,
reload and melee states, four vehicle kinds, seven seat pose types, entry/exit,
and a passenger first-person view. Jorge is the upper view in first person and
the left-hand column in external comparisons; the standard Spartan is the other
subject. `--jorge-field-start N` starts on a chosen page (0–8 first person,
9–17 held weapons, 18–24 vehicles, 25 passenger first person).

`in-game-interactions.mp4` records the final refined model through held weapons,
all vehicle poses, passenger first person and the next first-person weapon cycle.
`interaction-comparison.png` selects twelve views from that recording;
`interaction-capture.json` records its ROM/source hashes and capture provenance.

The field fixture runs two first-person views or four external views on the
current 4 MiB Ares profile. This is not a four-player production memory or timing
qualification. The selectable intermediate Jorge still requires Expansion Pak /
8 MiB. The full 8 MiB menu-to-match lifecycle check remains pending permission to
temporarily change that emulator setting; this pass does not change it.

## Validation

- All five edited central components have exact geometric mirror correspondence.
- 140 quantized view/pose checks introduce zero new enclosed coverage holes.
- No zero-area faces, loose vertices, wire edges or added internal nonmanifold edges.
- Original 85-bone rig and accepted clip poses are unchanged; weights normalize.
- All 39 clips / 1,530 frames and weapon sockets serialize exactly and fit bounds.
- Independent GLB re-import: 195 poses, maximum surface error below 0.051 mm.
- Vehicle interaction sanitizer tests include first-person availability in all ten
  seat positions, entry, exit, scoped and dead states.
- Release and field-QA ROMs build. In-game captures exercise the rendering and
  camera paths; this is visual validation, not a new frame-rate acceptance result.

## Reproduce

Open `playable-half/jorge-playable-half.blend` in background Blender, add
`port/n64` to `sys.path`, and run `refine_jorge.py -- --build --bake --export`.
Then run `validate_jorge_refinement.py` against the refined BLEND. The validator
writes component/export reports and the coverage gate.

```sh
build/n64-python/bin/python port/n64/pack_jorge.py \
  --asset-dir halo64-assets/assets/jorge/playable-refined --name jorge-playable-refined
build/n64-python/bin/python port/n64/test_jorge_bank.py
```

For exact runtime renders, call `refine_jorge.configure()` before running
`preview_jorge_playable.py` in background Blender; use the same configuration
before `roundtrip_jorge_playable.py` with the refined BLEND open. Then run:

```sh
build/n64-python/bin/python port/n64/review_jorge_refinement.py
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/n64-jorge-refined
build/n64-python/bin/python port/n64/build.py --jorge-field-qa --jorge-field-start 9 --output-dir build/n64-jorge-field-final
```
