# Firefight drawing audit — 28 October 2026

**The next substantial move is a screen-size-driven Covenant LOD tier, beginning
with vertex shading simplification and then reducing detail below pixel scale.**
The expensive crowded views genuinely show most of the squad. More culling is
useful, but it cannot remove their main cost without removing visible enemies.
No gameplay, model, animation or hit-geometry optimization is adopted here.

The audit follows preparation commit `c39213e85a752de967fe1e56ab4fca61f5f9c12b`.
It uses the same opt-in Hunter/Spirit bank, corrected Blood Gulch terrain and
native Ares v148 renderer as the preceding appraisal. All numbers below are
four-player, 320×240 output: **160×120 pixels per camera**.

## What each camera submits

The matched crowded fixture at tick 60 (two simulated seconds), with all four
humans alive, submits **60,138 loads across four cameras**. The preceding live
crowded capture averaged 61,629, so this snapshot is near that aggregate load;
it is not an average of the live run.

| Vertex loads | P1 | P2 | P3 | P4 | Total |
|---|---:|---:|---:|---:|---:|
| Terrain/world | 1,422 | 1,470 | 1,432 | 1,498 | 5,822 |
| Covenant bodies | 11,152 | 11,152 | 11,152 | 11,152 | 44,608 |
| Covenant-held guns | 1,188 | 1,188 | 1,188 | 1,188 | 4,752 |
| Spartans and their held guns | 294 | 856 | 294 | 856 | 2,300 |
| Pickups and effects | 140 | 156 | 140 | 156 | 592 |
| First-person guns/hands | 516 | 516 | 516 | 516 | 2,064 |
| Vehicles / Spirit | 0 | 0 | 0 | 0 | 0 |
| **Total** | **14,712** | **15,338** | **14,722** | **15,366** | **60,138** |

Covenant bodies alone are **74.2%** of loads; bodies plus guns are **82.1%**.
The terrain is already around the earlier 1,500-load map budget. That was a map
budget, not an allowance covering twelve enemies, other players and weapons.
Sky/HUD rectangles are outside this vertex-load counter; small effect loads use
the existing renderer accounting. Body counts include both opaque and alpha
batches exactly once, although their dispatch occurs in separate passes.

The twelve bodies are four Grunts, three Elites, three Jackals and two Hunters.
They are all using the existing **far** meshes in this view. Sharing their CPU
pose preparation does not share camera transforms or triangle processing: every
camera submits its own visible instances to the graphics pipeline.

## What actually changes the image

For each frozen state, the native renderer draws two complete baselines, then
omits each actor (body, energy surfaces and held weapon) in turn, omits the
Spirit, omits all NPC-held guns, and draws a final complete baseline. Every
normal fixture's three baselines match all RGBA16 bits. The difference counts
therefore measure contribution to the final image, including occlusion by terrain,
other actors, the first-person model and HUD. They are not counts of visible
triangles, and a zero difference in one frame is not a safe runtime occlusion rule.

At crowded tick 60, **47 of 48 submitted actor/camera instances change pixels**.
Their combined difference masks occupy 366 / 243 / 459 / 415 pixels in P1–P4:
**1.3–2.4% of each 19,200-pixel viewport**. This is the union of omission effects,
not a geometric surface-area measurement. Individual results are:

| Far body | Loads each | Triangles | Median changed pixels | Visible difference height |
|---|---:|---:|---:|---:|
| Grunt | 784 | 342 | 29 | 4–10 px |
| Elite | 776 | 368 | 39 | 2–13 px |
| Jackal | 920 | 449 | 17.5 | 1–14 px |
| Hunter | 1,464 | 1,138 | 54 | 12–14 px |

Pixel results include held guns and partial occlusion. The height is the bounding
height of the visible difference, not the full unoccluded silhouette. It must not
be used directly as an LOD selection bound. A far Spartan costs 250 loads; the
existing vehicle body meshes are roughly 244–450, before any separately drawn
parts. These are comparisons of submitted representations, not equal-size models.

The initial crowded state at tick 1 has all four humans alive and **48/48** actor
instances contributing pixels. Tight bounds around the actual animated body and
held gun reject **zero whole actor instances** in either living-party snapshot.
The current common two-unit-radius NPC box is loose, but tightening it cannot
solve these views. At tick 60 one 900-load actor instance changes no final pixels;
its tight body box still intersects the frustum.

Later, at ticks 180 and 360, all humans are dead and the cameras differ. Eighteen
of 48 submitted actor instances have zero pixel contribution, totaling 17,236
loads. Tight current-pose bounds can reject 8,608 of those loads. That is a real
secondary opportunity, **not a representative saving for four living players**.

Other states clarify the scope: the ordinary opening at tick 900 draws five
retained corpses in each camera and costs 36,574 total loads, including 21,472
body loads. A staged delivery at tick 300 costs 36,870, including 4,928 Spirit
loads. Four passenger instances are entirely hidden in that delivery. The earlier
opening/delivery captures contain no visible Covenant and are retained as controls,
not used to claim cheap combat.

## Where drawing time goes

A separate frozen diagnostic drains the RSP queue after each category. The second
complete frame supplies timings, avoiding the first frame's census print calls.
These are **serialized diagnostic spans**, not production frame time or independent
chip occupancy. The CPU can still perform lazy Spartan/first-person preparation
inside draw; that is included in those submission spans.

| Across four cameras | CPU category submission | Remaining RSP queue drain |
|---|---:|---:|
| World, including sky setup | 5.80 ms | 12.99 ms |
| Covenant bodies + guns | **0.79 ms** | **86.67 ms** |
| Spartans + held guns | 5.27 ms | 4.55 ms |
| Pickups | 0.50 ms | 1.70 ms |
| Effects / alpha-pass dispatch | 3.82 ms | 3.66 ms |
| First person | 11.04 ms | 5.56 ms |

The Covenant category accounts for about **87.45 ms** of serialized submission
plus drain. With an empty scissor suppressing 3D pixel output, it remains
**87.42 ms** (0.78 ms submission, 86.65 ms drain). Counts and poses are unchanged.
This strongly supports transform/clip/triangle-command work as the dominant
Covenant cost, rather than shading the final visible pixels. It does not separate
vertex transformation from triangle setup or measure every RDP cycle. The alpha
pass is dispatched later, under effects; body load counts already include it.

Simply making the CPU enqueue NPC commands faster has little headroom here.
Even a zero-cost CPU submission of this category would save less than one
millisecond in this diagnostic. Its repeated graphics work is the large target.

## Why lossless rebatching alone is insufficient

Vertex loads are not unique anatomical points. A vertex also carries shading
attributes, so the same animated position may need several separate records.
The far Grunt has **173 distinct full-animation position trajectories**, but
**774 distinct motion-plus-attribute records** and 784 submitted loads. Equivalent
far counts are 249 / 762 / 776 for Elite, 302 / 911 / 920 for Jackal, and
596 / 1,399 / 1,464 for Hunter.

An inventory compares every authored clip's complete position trajectories and
normal/color/UV attributes, including shield-state distinctions. Even an ideal
unlimited vertex cache merging every exactly identical record could remove only
**239 of the 11,152 body loads per camera (2.1%)** in this squad. Real 64-slot
batching may retain more. Lossless deduplication cannot buy a multi-fold reduction.

There is more room if distant shading differences can be simplified. That can
retain every triangle, every positional animation sample and the exact silhouette,
while allowing formerly split vertices to share. The 173/249/302/596 counts are
lower bounds ignoring those appearance distinctions and batching constraints,
**not achieved runtime loads or permission to flatten material colors**.

## Recommended next prototype

1. **Build a small-screen Covenant tier, starting with Grunt, Elite and Jackal.**
   Keep the current near/far meshes for larger views and zoom. Select per camera
   from a conservative projected animated bound, with hysteresis. The current
   Euclidean-distance threshold does not explicitly budget projected pixels.
2. **Simplify shading before shape.** Retain all motion trajectories and triangles
   in the first candidate; merge low-impact baked color differences within
   compatible material regions, then repack. Preserve armor regions, faces,
   hands, weapons, methane tanks, shields and distinctive spikes. Compare the
   images at their actual 160×120 viewing size and enlarged for diagnosis.
3. **Add a more economical mesh only where that tier remains too expensive.**
   Spend vertices on outline and articulated joints; remove subpixel interior
   detail. Preserve every animation's timing and interpolation, independent
   attachments, and canonical hit meshes. Validate walk/fire/melee/death/exit
   poses from multiple angles, not only an idle front view. Proposed starting
   targets are roughly 120–180 loads for Grunts, 160–240 for Elites/Jackals and
   300–450 for Hunters at small screen sizes. These are experimental budgets,
   not a claim that those qualities have already been achieved. Promote to the
   existing mesh whenever the projected error would become visible.
4. **Include the inexpensive supporting wins.** NPC-held guns currently bypass
   the existing projected-size weapon LOD. Its ordinary far threshold would save
   1,920 loads here, **3.2% of the whole frame**. Precomputed conservative visual
   bounds can avoid the demonstrated offscreen work without scanning vertices
   each frame. Give settled corpses the same screen-size budget; do not interrupt
   their death animation or change collision/gameplay to erase rendering costs.

A roughly 2,000–3,000-load distant squad per camera, instead of 11,152 body loads,
would put this scene near **22,000–26,000 total loads across four cameras**, including
existing weapon LOD savings. That is a substantial target (about 57–63% fewer
loads), still **not proof of 30 FPS**. Vertex count does not scale all costs linearly.
The present geometry drain exceeds the entire 33.33 ms frame allowance, and the
previous report still measures about 13.76 ms per simulation tick and 19.31 ms
preparing a crowded frame. Fewer output vertices should also reduce preparation,
but fresh uncapped 1–4P checks must establish the resulting overlap and frame rate.
The synchronous arrival hitch remains a separate stability issue.

The next acceptance criterion should be preserved visible silhouettes and
animation at the selected screen sizes, plus a measured reduction in RSP work.
No animation throttling, billboard replacement, enemy-count reduction or hit-mesh
simplification is needed to test this strategy. Existing missing Jackal shield
visuals remain a separate correctness issue; they must not be treated as a desirable
simplification when judging its recognizable shape.

## Evidence

[Drawing benchmark directory](benchmarks/firefight-drawing/README.md): exact census,
model inventory, frozen omission results, serialized timing controls, input hashes
and reproduction. Native pixels and the interactive inspection viewer remain
private/local. This is an audit and proposal; ordinary rendering is unchanged.
