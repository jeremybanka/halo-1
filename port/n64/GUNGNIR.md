# GUNGNIR armor

GUNGNIR is a separate armor choice in the existing four-profile setup. It has
100 health and 150 base shields, requires 8 MiB, and keeps ordinary weapon,
damage, pickup and respawn rules. Overshields add the normal 200 points and
decay back to 150. SWAT and Team SWAT continue to require ODST.

The normal cartridge remains one game: `halo-64.z64` includes local multiplayer,
SWAT and Firefight together. The combined cartridge fits within 64 MiB; the
paced release is approximately 63.5 MiB. Smaller multiplayer-only builds are explicit
diagnostics through `--no-firefight`, rather than a separate release.

The flashlight action toggles movement autopilot. Duke maps that action to B.
Bond retains B for reload/interact and currently has no flashlight binding.
While enabled, `AUTO` appears at the top center of the player's view. No
autopilot label is shown while disabled.

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

The reviewed private snapshot is
`assets/gungnir/demake-20261102/`. Source checkpoints, original textures, the
shoulder pilot, independent rig, BLEND, colored GLBs, first-person binding and
all positive and negative audit observations are retained there.

| Body | Native vertices | GLB vertices | Packed vertices | Triangles |
|---|---:|---:|---:|---:|
| GUNGNIR near | 892 | 898 | 1,064 | 1,298 |
| GUNGNIR far | 675 | 678 | 784 | 893 |
| Standard Spartan near / far | — | — | 562 / 250 | 328 / 135 |
| Jorge near / far | 603 / 349 | 603 / 349 | 670 / 390 | 949 / 556 |
| ODST near / far | — | — | 754 / 492 | 789 / 476 |

All costs exclude the separately drawn 140-triangle production rifle. GUNGNIR
has a separately reduced far mesh; these counts do not establish equal rendering
cost. Its 1,227,168-byte animation/mesh bank uses its own trajectories and sockets.

The bank passes 2,984,142 independent Blender/bake vertex comparisons,
780 colored GLB reimport samples, 4,680 sanitized streamed C decode cases and
1,409 production first-person poses. The largest Blender/bake coordinate error
is under 0.004 mm. Manual firing while autopilot runs is tested through the
actual weapon path, alongside the all-map movement checks.

Finite appearance review accepts the retained small deviations. The 3,744 body-only probes report at most
36 new enclosed background pixels; the sparse runtime bank reports 45. Those
include projection changes between separate limbs and isolated vehicle poses,
and small local seams. The plate-depth audit reports a two-pixel
ankle overlap in an 80-pixel part closeup. The intact-source controls report
zero gaps and zero lost plate pixels. Quantized zero-area triangle samples are
also retained in the shape report. These are observations, not passed zero-gap
gates. The largest highlighted gaps cross separate limbs; the ankle deviation
occupies 2/821 near or 1/898 far source-visible plate pixels in that enlarged
probe. Source comparison and native whole-body/vehicle review accepted these
deviations while retaining every raw result and the finite-review limits in
`appearance-validation.json`.

The outward rear-frame revision restored the original lateral rails. Front-side
review subsequently exposed the missing inward faces: an assembled silhouette
mask could not detect their culling. `repair_gungnir_shells.py` restores the
original inward frame and edge returns, preserving the approved exterior and
native skin. Six front/oblique part comparisons recover 95.46–97.46% of the
source frame's eroded interior, against 0–2.50% before. The certificate now
requires these front-side checks as well as the rear depth checks.

The complete source belt/codpiece retains its lower tip, previously shortened
by about 104 mm. Original plate contours replace radial inward-face filtering;
continuous pelvis backing is locally recessed by at most 30 mm. The new
24-probe codpiece depth audit reports zero near overlap and at most three
far passenger pixels in an 80-pixel closeup. These small residual differences
are explicitly accepted after source and native review. Rear source-visible
loss remains below 6% (maximum 5.54%); the existing 2/1-pixel ankle overlap and
strict global zero-loss failure remain recorded. The parent source is retained
in `stages/gungnir-shell-parent-v1`; the raw reports and acceptance records
preserve the scope of every check. The shell/belt repair adds 126/128 packed
vertices and 122/109 triangles over that parent, with a separate reduced far
mesh. Helmet, chest, shoulders and limb plate geometry remain unchanged.

The latest shell/codpiece revision is inspected in a separate Ares instance
with one full camera and four near/far cameras, all four palettes and zero RDP
errors/warnings. Screenshots and ROMs remain local; only build assets and
required validation inputs are pushed to the private repository.

Earlier functional Ares inspection covers near/far bodies and four palettes, personal arms,
weapon and vehicle services, off-axis aiming in one-to-four-player layouts,
normal 2x/10x zoom, mixed armor selection and a live movement-autopilot match.
The combined cartridge boots with Multiplayer and Firefight in the same menu.
Free-heap captures are samples, not a peak-memory measurement. The extended
Firefight quit/cancel cycle exposed missing synchronization between rotated
damage-image strips. The fix preserves source pixels, UVs and transforms while
explicitly synchronizing texture memory and tile descriptors. The final native
four-player restart/quit/cancel/cleanup cycle returns to normal multiplayer
with zero RDP errors and warnings. Diagnostic history is retained separately
from the geometry/export checks; emulator acceptance does not establish
physical-console performance.

## Verification

Run disk-heavy commands through the main checkout's workspace runner, with a
fresh output and declared growth estimate, as required by `WORKSPACE_POLICY.md`.
The maintained checks are:

- `test_maps.py --gungnir`: actual sanitized gameplay, controls, aiming,
  movement-only ownership and all thirteen map routes.
- `test_maps.py --firefight`: armor vitals, enemy damage, resupply/respawn and
  the finite one-to-four-player Firefight lifecycle.
- `test_maps.py --gungnir-frontend`: the sanitized mixed-armor menu cycle,
  live autopilot commands, manual fire and three matches with quit/resume.
- `test_damage_tiling.py`: 48 sanitized geometry/TMEM cases and 120 uploads,
  continuous filtered coverage and screen coordinates within 0.0001 pixel.
- `test_gungnir_controls.py`: legacy mappings, gestures, setup and HUD layout.
- `review_gungnir.py`: independent intact-source versus quantized body views;
  `--packed` also exercises sparse runtime endpoint interpolation.
- `audit_gungnir_clearance.py`: retained plate fronts versus original visible
  armor interiors, including the rear frame, with missing plate coverage and
  retained-plate depth overlap reported separately.
- `repair_gungnir_shells.py` and `audit_gungnir_shells.py`: source inward returns,
  complete codpiece contour, front-side culling and unchanged outer armor.
  Follow the surface repair with `recess_gungnir_cloth.py --only-region codpiece
  --limit-mm 30`, then run all assembled, part-depth, packed and native checks.
- `repair_gungnir_back.py`: restore and reduce the intact rear torso exterior
  from the preserved `stages/gungnir-rear-parent-v1` input; follow with
  `recess_gungnir_cloth.py --back-only --limit-mm 20` in a fresh output.
- `audit_gungnir_rear.py`: matching rear material/part views at bind, idle,
  run, reload and passenger poses.
- `gungnir_source_calibration.py`: intact-source controls for those audits.
- `gungnir_library.py` and `validate_gungnir_exports.py`: actual Blender skinning
  against the independent bake and 780 reimport samples across both LODs.
- `test_gungnir_runtime.py`: actual streamed C decoder, alternating LODs,
  four players, sockets, blending, loop endpoints and repeated bank reloads.
- `test_gungnir_firstperson.py`: 1,409 production poses through the C binding,
  all four palettes and preservation of weapon colors.

Native inspection fixtures use `--gungnir-qa 0..6` for body/LODs, off-axis
aiming, normal zoom, personal weapon services, rear armor, viewport alignment and shell/codpiece orbit views. `--gungnir-qa-views 1..4`
selects the viewport layout. Bank overrides require an isolated QA build.
`--gungnir-frontend-qa` drives mixed armor and movement through the real menus;
`--gungnir-field-qa` reuses the production weapon/vehicle inspection against CE.
Native visual, memory and RDP results must be identified separately from host
tests and successful ROM compilation.

`--showcase gungnir-aim`, `gungnir-follow`, `gungnir-elite` and `gungnir-panic`
stage labeled, single-camera recording encounters. Other local players supply
the opponents and friendly leader. Camera, firing and opponent inputs are
scripted; GUNGNIR supplies its actual aim and movement assistance. Weapon
damage, shields, reloads, navigation and deaths use the production simulation.
The aim scene holds the camera still. Follow selects a friendly and then looks
away while continuing to follow. `test_maps.py --gungnir-showcase` checks all
four encounters under ASan/UBSan, including manual fire during autopilot.

Keep ROM builds and gameplay videos local. The private asset repository receives
only the inputs and validation data required to build; do not upload ROM payloads.

Reticle placement uses the actual viewport's original Halo safe-window center.
HUD sprites, the acquisition circle, world projection and viewmodel projection
share that anchor. Camera count is separate from human actor count for aim-cone
selection. This matters for single-camera encounters with four human actors and
for the wide bottom viewport in three-player mode. The old count-based HUD call
already existed on main in `f40fefee` (#12); GUNGNIR's recording scenes exposed
its mismatch. Normal matching one/two/three/four-player layouts retain their
original safe-window offsets. QA page 5 keeps four combatants with 1–4 cameras,
projects the actual forward ray through Tiny3D, and asserts its marker stays
within 0.1 pixel of the reticle while cycling unzoomed, 2x and 10x views.
