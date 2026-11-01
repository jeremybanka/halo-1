# Playable Jorge: intermediate reduction

The current asset is the [metallic armor and symmetry refinement](JORGE_REFINEMENT.md).
This document records the preceding half-budget checkpoint, which remains unchanged.

Jorge is the fifth selectable profile in the multiplayer front end. Matches still
support one to four controllers. His profile preserves the black helmet band,
yellow breastplate, asymmetric shoulders, gray-brown backpack and quiet CE-derived
paint. The existing N64 AR follows his own animated right-hand socket.

This checkpoint deliberately retains extra seam coverage before the final reduction
and dedicated low-LOD pass. The same Jorge mesh is used at both render distances.

| Body metric | Repaired input | Playable checkpoint | Standard Spartan |
|---|---:|---:|---:|
| GLB vertices | 2,183 | 1,194 | — |
| Native Blender vertices | 1,800 | 1,141 | — |
| Triangles | 2,858 | 1,778 | 328 near / 135 far |
| Packed N64 vertices | — | 2,008 | 562 near / 250 far |
| Retained component objects | 59 | 49 | — |

The export vertex reduction is **45.3%**. A strict 1,092-vertex limit was relaxed for
joint coverage. Native vertices, GLB UV/normal splits, and Tiny3D batch/color copies
are different counts; the component CSV records the native and exported budgets.
The rifle is separate from the body budget (140 triangles).

## Geometry and appearance

The reduction starts from the unchanged `coverage-repair/jorge-coverage-repair.blend`.
It removes ten covered fittings, resamples redundant contour points, and reduces
interiors independently. Armor-to-fabric boundaries, closed volumes, extrema and
surface-distance checks constrain each component. Original armor shapes remain.

Fitted back faces close clean open armor loops. The original thigh garment and
shoulder support surfaces were retained where reduction weakened coverage.
Small overlap allowances are capped at 16 mm; the repaired green collar frame and
left rump armor remain fixed. Eighteen original triangles form local seam backing.
No invisible connector was restored beneath the backpack.

The game bakes the existing CE atlas into vertex colors, with the standard
Spartan's fixed lighting formula and bright visor treatment. The editable Blender
and GLB keep the packed 256×256 atlas and two materials. Game positions use
512 units per Halo unit (about 6 mm), avoiding the seam cracks introduced by the
standard Spartan's coarser 128-unit position grid.

## Gameplay integration

`character.h` separates five profiles from four player slots. Join selection,
profile controls, portraits, pregame/results names, scoreboard cache keys and HUD
colors include Jorge. Profile uniqueness still prevents duplicate selections.

The original 85-bone Reach skeleton remains in the editable asset. CE motion is
retargeted into 39 states: eleven core clips, ready, six crouch/landing clips, and
seven vehicle seat groups with stable/enter/exit motion. Unarmed vehicle and melee
states do not force the left hand onto an invisible rifle. Existing first-person
Spartan arms and weapon animations are shared.

`jorge_render.c` reads a separate DragonFS bank. Only the mesh and two requested
pose endpoints occupy RAM; all 1,530 frames remain in ROM. Jorge has his own pose
layout, animated grip and per-clip bounds. His near/far buffers alias deliberately.
The index conversion is repeated on each fresh bank load, including allocator
address reuse. Fenced release handles that alias once.

This intermediate model requires **8 MiB / Expansion Pak**. The 4 MiB menu shows
that requirement and blocks ready/launch for Jorge; the four existing profiles
remain available. This is a geometry/animation integration checkpoint, not a new
performance acceptance result or a gameplay handicap implementation.

## Validation and artifacts

The private asset submodule contains `assets/jorge/playable-half/`:

- `jorge-playable-half.blend`, body GLB and `-with-rifle.glb`.
- `before-after.png`, `standard-comparison.png`, `motion-contact-sheet.png`.
- Per-view textured and exact packed-game renders.
- `component-budgets.csv`, reduction/export/coverage/runtime reports.
- Original source motion extraction, baked pose arrays and packed preview data.

The source hash is unchanged. The four previously accepted clip poses remain exact.
All 39 clips / 1,530 frames round-trip exactly through the binary bank, including
weapon sockets, and fit their culling bounds. Front-end tests run with address and
undefined-behavior sanitizers. Independent GLB re-import checks cover all 39 clips
at 195 sample poses, with maximum bidirectional surface error below 0.051 mm.
The final model comparison ROM ran in Ares through idle, run, fire, reload, death,
jump, melee, throw, crouch and ready; its capture is `jorge-in-game-proof.mp4`.

The normal, model-QA and menu-QA ROMs build successfully. Ares currently has the
Expansion Pak disabled: the production selection guard correctly prevents Jorge
from readying on that profile. The 8 MiB menu/match lifecycle run is pending
permission to enable the emulator setting temporarily. The render-only fixture
uses less RAM than a full four-player match and is not a 4 MiB release qualification.

At game scale, 140 quantized view/pose checks open **zero new enclosed holes**.
Enlarged 256×320 diagnostic renders retain up to nine new isolated seam pixels;
this is not a claim that the assembly is watertight. Existing authored nonmanifold
joins are retained, with no new internal nonmanifold edges. The five matched views
and all-state contact sheet remain the visual review evidence for the next pass.

## Reproduce

Use the repository's Blender 5.2 and Python environment. In Blender background mode,
add `port/n64` to `sys.path`, open the repaired source, and run
`finalize_jorge_playable.py -- --rebuild`. This runs the component reduction,
shell backing, overlap fitting, source seam patches, coverage gate, animation bake,
GLB export and textured reference renders. It never saves over the repaired source.

Then run:

```sh
build/n64-python/bin/python port/n64/pack_jorge.py
build/n64-python/bin/python port/n64/test_jorge_bank.py
# Run preview_jorge_playable.py in Blender background mode next.
build/n64-python/bin/python port/n64/review_jorge_playable.py
build/n64-python/bin/python port/n64/build.py --preset release --output-dir build/n64-jorge
```

`--jorge-qa` produces the separate animated Spartan comparison ROM.
`--jorge-frontend-qa --initial-map wizard --preset release` selects Jorge through
production controller navigation and exercises three match/load/result cycles,
including pause/quit-confirmation/resume. These QA modes are not enabled in the
playable release.
