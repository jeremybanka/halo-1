# Covenant symmetry and anatomy appraisal — 28 October 2026

The previous crunchy bank's independent collapses left unequal silhouettes,
a narrow Grunt mask/head and an inadequately represented Hunter arm. This
revision restores those shapes and centers the upright piece ahead of the
Warthog windshield. It is a visual appraisal candidate, using the same
`--pve-crunch` selection rules with a new private bank.

## Authoring and limits

Grunt, Elite and Jackal bind meshes now use mirrored halves at all three tiers,
including face winding, colors, material boundaries and mirrored bone weights.
The skeletons and animation clips remain the original source data; a firing or
walking pose is naturally asymmetric. Symmetry does not mean mirroring poses.

The Grunt skull/mask and per-bone volume supports are protected during reduction.
Its coarsest tier restores the torso and limbs as well as the head. Six-angle
comparisons selected the Jackal half that retains the elbow and beak outlines;
the other half created a web between the arm and torso and was rejected.

The Hunter needs a different treatment. Its source shield and cannon arms have
different bone lengths and share a connected mesh with its torso and legs.
Splicing mirrored torso faces into those preserved arms opened gaps. That
candidate was rejected after backface tests exposed the joins. The final mesh
preserves the connected shell, uses Blender's bilateral reduction constraint,
protects the source head and complete arms, and mirrors the separate back spines.
This retains the Hunter's intentional anatomical/equipment asymmetry; it is not
an assertion that the entire Hunter is mathematically mirror-identical.

The Warthog fixture is translated laterally onto the glass center in the near
and far meshes. No triangle, color, UV, index, vehicle rig, seat or collision
changes. Its four unique corners move; every other world model is identical.
The micro mesh already omits this part and is byte-identical.

## Shape validation

Source-far vs coarsest-tier silhouette intersection-over-union, averaged across
eight matched animation poses and six angles on a 192-pixel diagnostic canvas:

| Actor | Previous crunchy | Corrected |
|---|---:|---:|
| Grunt | 82.0% | 94.1% |
| Elite | 88.7% | 88.6% |
| Jackal | 83.4% | 88.3% |
| Hunter | 80.7% | 93.0% |

The same audit includes 28- and 16-pixel masks, bind views, isolated head/arm
regions, and red-lost/cyan-added difference sheets. These are geometric overlap
metrics, not perceptual scores. Regional masks select bone-influenced faces and
can include part of a shoulder/neck; inspect the full-body views alongside them.

Mean additional pixels exposed by disabling backface culling fall from 3.46 to
1.71 for the Hunter (the rejected splice reached 181.2), and from 113.94 to
41.04 for the Jackal. Grunt remains effectively zero; Elite is 9.44 → 9.81.
The source meshes already include some open/detail surfaces. These checks detect
new gross gaps; they do not claim every source mesh is a closed manifold.

Native route: 71 matched frames, four views each, including the middle tier and
all three Warthog representations. Exact camera/pose states are recorded in
`pixel-checks.json`. Eight Spirit frames and the Warthog micro frame remain
pixel-identical. The existing Jackal energy-shield render omission is not fixed
by this task; source shield hit behavior is unchanged.

## Geometry cost

| Actor | Original far loads | Previous crunch loads | Corrected crunch loads | Corrected triangles |
|---|---:|---:|---:|---:|
| Grunt | 784 | 104 | 304 | 232 |
| Elite | 776 | 254 | 352 | 264 |
| Jackal | 920 | 238 | 584 | 482 |
| Hunter | 1,464 | 304 | 826 | 736 |

Restoring anatomy adds work. The corrected small tier still saves 61%, 55%, 37%
and 44% of the original far vertex loads respectively. The Jackal now has more
triangles than its original far tier despite fewer vertex loads, because color
coalescing reduces loads while mirroring adds center seams. This is a fidelity
tradeoff for appraisal, not a further performance optimization.

## Native performance

| Players | Previous crunchy FPS | Corrected FPS | Change |
|---|---:|---:|---:|
| 1 | 40.70 | 35.80 | -12.0% |
| 2 | 20.83 | 17.78 | -14.6% |
| 3 | 11.20 | 9.95 | -11.2% |
| 4 | 5.71 | 4.90 | -14.2% |

These samples have at least one living human and landed enemies. The separate
all-humans-alive scope is retained in the raw results. The same scripted live
fixture does not imply identical sampled combat states after geometry changes
shift frame timing. Restored anatomy costs approximately 11–15% FPS here.
Four-player crowded performance is still far below 30 FPS.

Both versions use the same
runtime, source behaviors, map, LOD gates and audio settings; the geometry banks
and small Warthog correction differ. Ares v148, NTSC 320×240, 8 MiB, audio enabled.
45 observations per run, first five discarded. Live profile captures and frozen
pixel readbacks are separate. These are not new SummerCart64 measurements.

## Verification and reproduction

- Exact reflected faces/weights/colors/winding for the mirrored regions.
- Original hit meshes, weapon grips, clip samples/counts/durations retained.
- 473,856 packed pose evaluations across all interpolation bins pass against
  independent pre-change loops; cache and fenced pose-owner tests pass.
- All packed samples lie inside their all-tier clip bounds; batch limits pass.
- Centered Warthog changes only six expanded corners per tier; all other model
  previews and the micro bank remain identical. Interaction data regenerated
  byte-identically; provenance hashes refreshed.
- Final native photos/performance ROMs and a normal controller-playable release
  build link successfully.

Scripts and numerical evidence: `benchmarks/covenant-symmetry/`.
Private source/bank/photo evidence: `halo64-assets/assets/covenant-symmetry/`.
Local interactive viewer: `build/n64-covenant-symmetry/comparison.html` in the
original research checkout. Work happened in its isolated PvE checkout.

The Blender entry point is `benchmarks/covenant-symmetry/author.py`, followed by
`bake_pve_blender.bake()` and `benchmarks/covenant-symmetry/pack.py`.
`run.py build baseline` must run before installing the centered world bank;
`run.py build candidate` runs after it. Both use the same crunchy selection
flags—neither uses `--pve-crunch-baseline`. `run.py capture VERSION` owns only its
own Ares process. `audit.py`, `silhouettes.py`, `parts.py`, `collect.py` and
`compare.py` reproduce the checks and viewer. Public evidence contains metrics,
scripts and text logs; source art, baked motion and native pixels stay private.
