# GUNGNIR armor

GUNGNIR is a separate armor choice in the existing four-profile setup. It has
100 health and 150 base shields, requires 8 MiB, and keeps ordinary weapon,
damage, pickup and respawn rules. Overshields add the normal 200 points and
decay back to 150. SWAT and Team SWAT continue to require ODST.

The flashlight action toggles movement autopilot. Duke maps that action to B.
Bond retains B for reload/interact and currently has no flashlight binding.

| Input while enabled | Movement |
|---|---|
| D-pad Up | Follow the living player under your aim, including a friendly |
| D-pad Left/Right | Use the game's Elite movement strategy |
| D-pad Down | Use the game's panicking Grunt movement strategy |

Follow keeps the selected player when you look elsewhere. Camera, firing,
grenades, reload, weapon selection and interaction remain manual. Toggling off
restores manual movement immediately. Autopilot pauses while mounted and
resumes on foot; it does not board or drive vehicles. Death resets it to off.

The unzoomed HUD has a large faint cyan acquisition circle. The reticle and
held weapon point toward the visible enemy nearest its center. Terrain and
vehicle hulls block acquisition; allies and completely invisible units are
excluded. Weapon spread still applies. Zoom disables the enhanced assistance
and keeps ordinary weapon zoom behavior. Personal-weapon passengers retain
assistance; vehicle-mounted weapons retain their normal controls.

## Movement implementation

`prepare_gungnir_strategy.py` extracts the original Elite, Grunt and panic
transition functions from `source/ai/`, with source hashes. The independent
four-player adapter uses the same class parameters as NPCs. Weapon, grenade
and campaign callbacks do not issue human actions. Elite shield retreat,
emergence, pursuit and explosive-danger decisions select movement goals;
Grunt mode uses blind panic and fleeing.

`bake_autopilot_nav.c` uses production selected-map floors and standing capsule
clearance to generate thirteen GNV3 navigation banks. Runtime steering supplies
ordinary biped inputs. The shared path service expands at most 256 nodes per
tick and preserves directed authored teleporters. It stops when no route is
available and repaths when stuck. Ladders and vehicle navigation are outside
this on-foot planner.

The banks load on first use and are released on map unload/reset. The current
independently decoded maximum dynamic navigation allocation is 262,480 bytes;
that is not a total match-memory measurement. The host proof covers every
eligible Slayer start's proximity to a graph node and one actual reachable
follow route on each map, rather than every spawn pair or jump edge.

## Source and demake

The owned retail Reach assembly uses `objects\characters\spartans\spartans`
from `m05.map`, head permutation `player_kelly`, HP/Parafoil chest equipment,
paired Base Security shoulders and the Buckler wrist attachment. The intact
assembly has 16,853 source vertices, 19,353 triangles and 82 native bones.
Its off-center gold optic is intentional.

The process follows [CHARACTER_DEMAKE.md](CHARACTER_DEMAKE.md) and
[JORGE_LODS.md](JORGE_LODS.md): preserve the untouched reference, inspect
physical components, compare the shoulder cleanup/reduction pilot, establish
motion on the native rig, then reduce original armor and garment surfaces with
explicit omissions and source correspondence. Coverage, plate depth, source
fit and packed cost are separate checks. A candidate that fails them remains
a candidate; an export or decoder pass does not approve its appearance.

The editable library keeps the original reference and independent native
Reach rig. Thirty-nine CE gameplay clips are adapted to its proportions and
own grip socket. Helper/finger motion and support-arm solving are explicit
approximations, rather than Reach's procedural controllers. Body-only GLBs
retain skin, UVs, unlit vertex colors and all actions. Their unused NORMAL
attribute is omitted to avoid artificial flat-normal vertex splits; the BLEND
retains editable geometry and normals.

The N64 bank contains GUNGNIR's own quantized trajectories and grip samples.
Vertices merge only when their complete relevant animated trajectories agree.
Positions use 512 units per Halo unit, encoded as a frame origin and three
9-bit planes. The loader holds the selected mesh and two frame endpoints.
First-person forearm plates use the production CE glove/sleeve cage and weapon
clocks. There are no first-person legs or independent service clocks.

Private source, libraries, stage decisions, previews and validation evidence
belong in `halo64-assets/assets/gungnir/`; runtime data belongs in
`halo64-assets/generated/gungnir/`. Generated ROMs do not replace those inputs.
Normal builds require a hash-bound `gungnir-validation.json` integrity
certificate. Its `publication_approved` field distinguishes a development bank
from an appearance-accepted bank; the build prints the candidate status and
preserves it in the ROM manifest.

## Current review state

This PR is a development draft. The private snapshot is
`assets/gungnir/demake-20261102/`. Source checkpoints, original textures, the
shoulder pilot, independent rig, BLEND, colored GLBs, first-person binding and
all positive and negative audit observations are retained there.

| Body | Native vertices | GLB vertices | Packed vertices | Triangles |
|---|---:|---:|---:|---:|
| GUNGNIR near | 726 | 727 | 868 | 1,117 |
| GUNGNIR far | 512 | 512 | 598 | 727 |
| Standard Spartan near / far | — | — | 562 / 250 | 328 / 135 |
| Jorge near / far | 603 / 349 | 603 / 349 | 670 / 390 | 949 / 556 |
| ODST near / far | — | — | 754 / 492 | 789 / 476 |

All costs exclude the separately drawn 140-triangle production rifle. GUNGNIR
has a genuinely reduced far mesh; these counts do not establish equal rendering
cost. Its 983,392-byte animation/mesh bank uses its own trajectories and sockets.

The candidate passes 2,511,528 independent Blender/bake vertex comparisons,
780 colored GLB reimport samples, 4,680 sanitized streamed C decode cases and
1,409 production first-person poses. The largest Blender/bake coordinate error
is under 0.004 mm. Manual firing while autopilot runs is tested through the
actual weapon path, alongside the all-map movement checks.

Appearance acceptance remains open. The 3,744 body-only probes report at most
34 new enclosed background pixels; the sparse runtime bank reports 44. Those
include projection changes between separate limbs and isolated vehicle poses,
as well as seams requiring review. The plate-depth audit reports a two-pixel
ankle overlap in an 80-pixel part closeup. The intact-source controls report
zero gaps and zero lost plate pixels. Quantized zero-area triangle samples are
also retained in the shape report. These are observations, not passed zero-gap
gates. The guide's final assembled/native review must resolve them.

No GUNGNIR ROM has yet been visually inspected in Ares: the host Mac was locked.
Native checks still need the body and far transition, first-person services,
off-axis aiming and zoom in all layouts, mixed armor selection, map/match
lifecycle, peak memory and RDP validation. Successful compilation and host
tests do not stand in for those checks.

## Verification

Run disk-heavy commands through the main checkout's workspace runner, with a
fresh output and declared growth estimate, as required by `WORKSPACE_POLICY.md`.
The maintained checks are:

- `test_maps.py --gungnir`: actual sanitized gameplay, controls, aiming,
  movement-only ownership and all thirteen map routes.
- `test_maps.py --firefight`: armor vitals, enemy damage, resupply/respawn and
  the finite one-to-four-player Firefight lifecycle.
- `test_gungnir_controls.py`: legacy mappings, gestures, setup and HUD layout.
- `review_gungnir.py`: independent intact-source versus quantized body views;
  `--packed` also exercises sparse runtime endpoint interpolation.
- `audit_gungnir_clearance.py`: retained plate fronts versus original visible
  armor interiors, with the raw depth overlaps retained for inspection.
- `gungnir_source_calibration.py`: intact-source controls for those audits.
- `gungnir_library.py` and `validate_gungnir_exports.py`: actual Blender skinning
  against the independent bake and 780 reimport samples across both LODs.
- `test_gungnir_runtime.py`: actual streamed C decoder, alternating LODs,
  four players, sockets, blending, loop endpoints and repeated bank reloads.
- `test_gungnir_firstperson.py`: 1,409 production poses through the C binding,
  all four palettes and preservation of weapon colors.

Native inspection fixtures use `--gungnir-qa 0..3` for body/LODs, off-axis
aiming, normal zoom and personal weapon services. `--gungnir-qa-views 1..4`
selects the viewport layout. Bank overrides require an isolated QA build.
Native visual, memory and RDP results must be identified separately from host
tests and successful ROM compilation.
