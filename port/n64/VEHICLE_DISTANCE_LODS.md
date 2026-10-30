# Wraith and Shade distance LODs — local appraisal

The candidate replaces oversized distant hulls with two reduced, articulated
tiers. It is opt-in through `--vehicle-distance-lods`; the accepted bank is
unchanged. The existing Wraith/Shade near meshes, hit geometry, movement,
weapon values, seats and audio remain byte-identical.

## Geometry and selection

| Hull | Detailed loads / triangles | Middle loads / triangles | Coarse loads / triangles |
| --- | ---: | ---: | ---: |
| Wraith | 1,320 / 1,086 | 458 / 400 | 296 / 272 |
| Shade | 1,348 / 924 | 418 / 328 | 270 / 236 |

Counts include the packer's part-padding triangles. Middle tiers cut vertex
loads by 65.3% / 69.0%; coarse tiers cut them by 77.6% / 80.0% respectively.
Reduction is performed independently per rigid part in Blender, with symmetric
collapse and UV/material retention. Protecting connected-component extrema
prevents the Shade feet/barrels from collapsing into needles. Its gun retains
additional directional supports. The initially unprotected version was rejected.

The full current posed bounds select middle below 72 pixels and coarse below
28 pixels, using the existing conservative projection bound and half-pixel
margin. This applies to every split count. Zoom and near-plane intersections
retain detail; offscreen extents are not clipped away to force cheaper LODs.
These are deliberate art thresholds, not a guarantee of pixel equivalence.

Both new tiers retain the existing part ordering, pivots and exact current
part matrices. The Shade gun and Wraith gun/hatch therefore move at distance;
the previous far meshes were drawn as a single static hull. Render bounds
include all tiers under each part's current transform. No collision representation,
actor count, simulation frequency or AI decision policy changes.

## Visual appraisal

The native viewer is `build/n64-vehicle-lods/comparison.html` in the original
checkout. Its playable ROM uses the candidate tiers and the maintained release
preset. The viewer includes the following independent comparisons:

- 36 native inspection pages per build, four cameras each: eight angles,
  three poses and three requested tiers for each hull. Reduced tiers are forced
  at close range to reveal compromises. **All twelve detailed pages and all
  detailed-reference repeats are bit-identical.**
- Automatic-selection routes at ticks 1, 60 and 180. Cameras and hull poses
  match. Full-scene repeats are exact. **Removing all hulls makes before/after
  scenes bit-identical on all three routes**, isolating the visible changes.
- Clean eight-angle silhouette inspection of quantized meshes, with separate
  lost/added coverage. These are offline renders, not N64 screenshots.

At 28-pixel inspection size, mean silhouette overlap (intersection/union) is
95.9% / 91.4% for Wraith middle/coarse and 92.2% / 87.3% for Shade middle/coarse.
The Shade coarse tier is the stronger visual sacrifice; its worst measured angle
is 81.8%. Large inspection images expose faceting and simplified barrel/seat
detail. Native gameplay-scale photos are the appropriate companion appraisal,
not a substitute for these less flattering views.

All new packed material alpha is opaque. The culling audit includes lower and
oblique views; small backface-only coverage remains and is reported alongside
the source rather than calling the source's open shells watertight. Near geometry
is unchanged. The candidate keeps the three-leg stance, barrel span, Wraith
swept hull, moving gun and hatch; fine panel/recess detail is intentionally lost.

## Matched four-camera drawing

| Frozen route | Hull loads before | After | Reduction |
| --- | ---: | ---: | ---: |
| Tick 1 | 11,626 | 3,218 | 72.3% |
| Tick 60 | 11,808 | 3,724 | 68.5% |
| Tick 180 | 6,132 | 1,928 | 68.6% |

At tick 60, the Wraith selects middle in cameras 1/3 and coarse in 2/4;
Shade selects coarse in all four. Ghost and Banshee loads are unchanged.
Total scene submissions fall from 40,902 to 32,818 loads across the four cameras.

The serialized vehicle interval falls from **24.491 to 9.818 ms (59.9%)**.
CPU submission increases from 0.129 to 0.417 ms because the new distant hulls
submit independent moving parts. Queue drain falls from 24.362 to 9.401 ms.
That trade is favorable in this matched view. These serialized diagnostic spans
destroy overlap: they must not be added to production CPU frame times, nor
described as isolated pure RSP/RDP occupancy.

## Fresh live performance

Ares v148, NTSC 320×240, audio enabled, 8 MiB, uncapped timing ROMs.
Each of the sixteen captures has 45 observations; five warm-ups are discarded.
The table reports engaged samples (living player and enemy, no pending arrival).

| Players | Four-vehicle overload, before → after | One-Ghost control, before → after |
| --- | ---: | ---: |
| 1 | 16.85 → 17.50 FPS (26/26 samples) | 44.17 → 45.07 FPS (30/30 samples) |
| 2 | 8.76 → 9.51 FPS (37/37 samples) | 24.23 → 24.54 FPS (35/35 samples) |
| 3 | 8.10 → 8.28 FPS (40/40 samples) | 26.90 → 27.32 FPS (40/40 samples) |
| 4 | 3.60 → 3.65 FPS (40/40 samples) | 15.95 → 16.12 FPS (40/40 samples) |

**Four-player stress performance is essentially unchanged: 3.60 → 3.65 FPS.**
With all four players alive, the same comparison is 3.07 → 3.15 FPS across
27 samples per build. One/two/three-player overload means rise by about
3.9% / 8.6% / 2.2%. Small increases also occur in the one-Ghost control,
where no new hull is rendered; this single pair of captures does not establish
statistical significance for small changes. These are crowded fixtures, not
whole-match averages or a new cartridge claim.

| Four-player overload metric | Before | After |
| --- | ---: | ---: |
| Average submitted loads per rendered frame, all views | 41,634 | 35,787 |
| CPU simulation per rendered frame | 208.326 ms | 209.471 ms |
| Preparation per rendered frame | 14.381 ms | 15.213 ms |
| CPU drawing/submission interval per rendered frame | 51.704 ms | 49.739 ms |
| Total simulation per actual tick | 30.392 ms | 30.635 ms |
| Lowest free memory | 438,352 bytes | 400,816 bytes |

The graphics saving is clear at the matched distant camera, but the live
encounter moves vehicles closer and spends most time processing accumulated
fixed simulation ticks. Its average total load reduction is 14.0%, rather than
the frozen hull-only reduction of 68.5%. The simulation remains almost the
entire 33.33 ms budget per tick, before drawing. This pass therefore creates
graphics headroom without resolving the dominant live CPU cost.

The new meshes and recorded drawing blocks cost **37,536 bytes (36.7 KiB)**
in these native fixtures. No allocation failures or target assertions were
observed. Detailed coverage, source physics and AI are retained. The candidate
does not meet four-player 30 FPS.


## Validation and provenance

The projection regression passes 40,000 outward-box cases, including near-plane,
zoom and invalid-input guards. The runtime configuration check passes 45
configurations / 180 target translation units. The new native photo, live,
frozen and release builds exercise both feature-disabled and feature-enabled
paths. All 33 original candidate-bank files are byte-identical; added geometry
is finite and representable in the existing fixed-point format.

The baseline is public `031e79f5` / private `39a541d`, with the same current
runtime compiled without the opt-in LOD flag. Build manifests bind actual
compiler inputs; existing source controller/physics code is unchanged.
The disk-full capture is preserved as failed evidence and excluded from results.
Completed ROMs, source snapshots, framebuffers and numerical logs survive the
cleanup of redundant build intermediates.

See [reproduction and evidence](benchmarks/vehicle-lods/README.md). This pass
stops at appraisal; it does not adopt the candidate or implement the Wraith
firing-query/clearance optimizations proposed by the preceding audit.
