# Covenant model reduction appraisal — 28 October 2026

The Hunter and Spirit can be made substantially cheaper without flattening their
recognizable shapes. The candidate reduces their vertex loads by **52–57%** and
**71–74%**, respectively. The crowded mixed-enemy fixtures gain **10–25% FPS**;
ordinary openings gain only **1–4%**. Four-player Firefight still needs much more
work to approach 30 FPS. This prototype remains opt-in for visual appraisal.

## Native results

Ares v148, native N64 programs, NTSC 320×240, 8 MiB, audio enabled. Each cell is
baseline → candidate mean FPS in the living-human/landed-enemy subset after five
warm-up observations. These are fresh paired fixtures against the current
Spartan locomotion fix, not comparisons against an older navigation run.

| Players | Ordinary opening | Change | Crowded mixed squad | Change |
| --- | ---: | ---: | ---: | ---: |
| 1 | 38.17 → 39.83 | +4.3% | 19.68 → 24.60 | +25.0% |
| 2 | 24.09 → 24.32 | +1.0% | 10.83 → 13.00 | +20.0% |
| 3 | 24.16 → 24.52 | +1.5% | 6.00 → 6.77 | +12.8% |
| 4 | 5.32 → 5.45 | +2.4% | 3.05 → 3.36 | +10.2% |

There are 75 one-second observations per ordinary run and 45 per crowded run.
The crowded encounter resets every twenty simulated seconds and includes
Hunters. Real damage, deaths and respawns remain enabled. Whole-window and
all-humans-alive summaries are in [results.json](benchmarks/covenant-models/results.json).
Matched inputs do not imply pixel-identical combat trajectories. The native
frozen photo fixtures are separate and are never used for timing.

## What changed

| Model | Near triangles | Far triangles | Near loads | Far loads |
| --- | ---: | ---: | ---: | ---: |
| Hunter | 2,006 → 1,306 | 2,006 → 1,138 | 3,378 → 1,606 | 3,378 → 1,464 |
| Spirit | 2,956 → 944 | 2,956 → 860 | 4,228 → 1,232 | 4,228 → 1,084 |

These are body-only loads for one instance in one camera. Far meshes previously
aliased near for both models. The Spirit also gains distance LOD selection and
reuse of an unchanged door pose. The candidate uses somewhat broader color
sharing only for the reduced meshes, while retaining exact quantized positions,
full motion trajectories, material IDs and tint boundaries. The measured gain
therefore includes mesh reduction, batching, material fixes and Spirit caching.

The Hunter keeps its broad shield, head, exposed body regions, fuel-rod weapon
and back spines. The Spirit keeps its forked hull, passenger compartments and
articulated doors. Open and articulated seams, material regions and supporting
outline vertices constrain Blender's collapse modifier. Original corner colors
are transferred through the reduction so new UV interpolation cannot smear an
unrelated part of the atlas across the shield. Grunt, Elite and Jackal triangles
and source animation clips are unchanged.

Canonical gameplay definitions, collision surfaces, weak points, weapon grips,
navigation, AI selectors and encounter rules remain identical. The build override
can replace only the visual C bank and streamed visual poses. The approved bank
and the normal build remain unchanged pending appraisal.

## Where the benefit lands

NPC animation preparation in the crowded fixtures falls as follows. These are
sampled-frame CPU counters over the whole post-warm-up window, not the filtered
FPS subset, and they are nested within preparation.

| Players | Before NPC preparation | Candidate NPC preparation | Saved |
| --- | ---: | ---: | ---: |
| 1 | 25.08 ms | 17.68 ms | 7.40 ms |
| 2 | 29.68 ms | 20.06 ms | 9.62 ms |
| 3 | 27.06 ms | 19.32 ms | 7.74 ms |
| 4 | 32.49 ms | 25.19 ms | 7.30 ms |

In the four-player crowded capture, average submitted loads fall from **77,198
to 61,707 per rendered frame**. NPC preparation drops from 32.49 to 25.19 ms,
but sampled simulation is still 141.24 ms and CPU draw submission 55.10 ms.
Simulation can contain multiple catch-up ticks. These means must not be added
or inverted to reconstruct the filtered FPS number, and nested AI/animation
counters must not be added again. RSP/RDP drain instrumentation is disabled in
these runs; zeros in those fields do not mean zero graphics cost.

The ordinary opening has no Hunters in the observed first wave. Its actors
remain mostly unchanged, and Spirit savings only apply while the transport is
visible. That explains why a large per-model reduction produces a small
ordinary-match FPS change. Even the crowded candidate still has substantial
unchanged actor animation, simulation, player and draw-submission work.

Minimum sampled free heap improves in every case. For four players it changes
from 699,112 to 817,344 bytes in the ordinary run and from 756,104 to 991,496
bytes in the crowded run. These are sampled free-heap minima, not a complete
memory high-water proof. The candidate supplies two real LODs, so its streamed
motion bank grows slightly despite cheaper individual meshes.

## Visual and soundness audit

The native photos provide 52 matched frames from four simultaneous cameras:
near/far Hunter idle/run/melee, Spirit door phases, Jackal shield up/down and
firing, Grunt/Elite idle/run, plus a Spartan overlapping the Jackal shield.
The comparison page supports side by side, single-image, blink and amplified
RGB differences. Far meshes are deliberately shown close enough to inspect;
models are suspended above terrain to expose feet and undersides.

The additional CPU audit compares 72 poses/angles at packed position precision.
Minimum silhouette intersection-over-union is **93.8% / 92.9%** for Hunter
near/far and **97.0% / 93.5%** for Spirit. At most three additional backface-only
pixels appear in the sampled Hunter views; none in Spirit. This is supporting
evidence, not a guarantee for every angle or animation frame.

The audit found inherited material problems: source two-sided details were
backface-culled and included energy surfaces wrote opaque depth. Candidate
batches retain the original two-sided flags. The Spirit beam and near Grunt
inset lights now blend after all opaque actors, pickups and grenades, with depth
testing but no depth writes. Armor remains fully opaque. An initial alpha-pass
placement before Spartans was corrected before the final timing captures.

**Unresolved existing defect: the Jackal's visual shield is missing entirely.**
The source superhigh mesh contains 76 shield triangles, but the chosen low and
superlow meshes contain none. Their shield masks are therefore empty, even
though gameplay uses the original shield collision. Native shield-up/down pairs
are pixel-identical in both versions, including the Spartan-overlap views.
Those views expose the omission; they do not validate Jackal alpha rendering.
The reduction leaves Jackal geometry unchanged. A focused follow-up should bring
the 76-triangle shield into both LODs as an independently controlled surface,
then verify its break/recovery, gaps, coloring and depth against actors.

CE's animated, layered additive shield/tractor-beam shader is still approximated
by baked source colors and standard alpha. Shield noise, full source coloring
and sorting between intersecting energy effects remain limitations. This is not
a claim of complete shader parity.

Quantization still collapses some tiny Hunter faces: across the baked animation
samples, at most 19 source triangles become degenerate, versus 15 candidate near
and six candidate far. Spirit has zero in either version. There were no new
large holes or obvious winding failures in the inspected images. Tests also
verify finite weighted geometry, surviving material regions, opaque/energy
separation, 1,004 bounded animation frames and unchanged hit/attachment data.

## Evidence and appraisal boundary

[Benchmark README](benchmarks/covenant-models/README.md) records exact reproduction,
matching, counter interpretation and limitations. Raw perf logs, build hashes,
source-input comparisons, asset checks, quantization results and host test logs
are saved beside it. Native screenshots, Blender output and candidate banks
are kept privately. The local appraisal page is
`build/n64-covenant-models/comparison.html` in the original research workspace.

ASan/UBSan Firefight and squad tests pass; the deferred-animation fence test
passes 10,000 frames; 36 runtime configurations / 144 target translation units
compile. Native model capture uses RDP validation. The normal-play candidate
ROM is provided separately from timing and photo ROMs. The native 39-step
four-player frontend fixture passes restart, quit and return to multiplayer
with actor/transport allocations exercised.

Stop here for visual appraisal. These results support retaining the Hunter and
Spirit shapes at much lower cost; they do not establish a four-player 30 FPS
solution or justify automatically replacing the approved art.
