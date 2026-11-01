# Jorge: full-model surgical cleanup baseline

The complete assembled Jorge model, including the backpack, has been inspected and cleaned using the shoulder study's component-culling approach. This is the baseline for a later automatic reduction pass. No global decimation, primitive reconstruction, bevel-loop collapse, or joint retopology has been applied.

## Result

- Original assembled character: **33,208 triangles** (28,898 character + 4,310 backpack).
- Clean baseline: **26,076 triangles** (24,574 character + 1,502 backpack).
- Removed: **7,132 triangles / 21.5%**.
- Of these, 7,128 belong to **66 explicitly inspected fastener components**. The remaining four are zero-area chest triangles.
- All 17 material/region groups were inspected. The original 176 physical components are reduced to **110 retained components**, each separately addressable for later work.

| Group | Original | Clean | Treatment |
| --- | ---: | ---: | --- |
| Gauntlets | 4,428 | 2,700 | Remove 16 approximately 1 cm fasteners; retain plates, straps and larger fittings |
| Large left shoulder | 1,924 | 844 | Remove 10 fasteners; retain the complete original plate and mounting structure |
| Right shoulder | 896 | 896 | Preserve the integrated shoulder shape |
| Forearm and hand armor | 1,308 | 1,308 | Preserve plates, hand armor and joint fittings |
| Hands and gloves | 2,134 | 2,134 | Preserve articulation and all original weights |
| Upper-arm armor | 880 | 880 | Preserve plates and shoulder connections |
| Elbow undersuit | 126 | 126 | Preserve deforming joint surfaces |
| Chest armor | 3,562 | 2,046 | Remove 14 fasteners and four zero-area faces; preserve chest shell and large fittings |
| Calf gear and collar | 2,559 | 2,559 | Preserve distinctive collar and calf attachments |
| Helmet | 2,624 | 2,624 | Preserve silhouette, face details and attachments |
| Visor | 278 | 278 | Preserve the entire surface |
| Torso and leg armor | 4,723 | 4,723 | Preserve original layered plates and mechanical connections |
| Body undersuit | 3,339 | 3,339 | Preserve original deformation topology for later controlled reduction |
| Scorch decals | 4 | 4 | Preserve markings |
| UNSC markings | 20 | 20 | Preserve markings |
| Shoulder damage | 93 | 93 | Preserve distinctive damage |
| Backpack | 4,310 | 1,502 | Remove 26 fasteners; preserve pack shell, tanks, straps and larger connectors |

Parts were not removed just because they were small. The helmet's small face fittings, forearm connectors, larger gauntlet elements, calf attachments and backpack connectors remain. Underlapping armor and undersuit surfaces also remain: this pass does not assume that something hidden in the rest pose remains hidden during animation.

The left shoulder uses the study's **844-triangle culling-only version B**, consistent with the rest of this baseline. The separately delivered 758-triangle constrained shoulder candidate is still available in `shoulder-study/`; it has not been mixed into this stage.

## Deliverables

Files are under `halo64-assets/assets/jorge/full-cleanup/`:

- **`jorge-surgical-cleanup.blend`**: full source reference, clean baseline, removed fasteners in a hidden reference collection, packed textures, original 85-bone skeleton and named component meshes. The clean version is initially visible.
- **`jorge-cleaned.glb`**: 26,076 triangles, 110 component meshes, 85 joints, embedded portable materials and textures.
- `jorge-source-reference.glb`: original 33,208-triangle assembled geometry for comparison.
- **`jorge-cleaned.json`**: the reduction input. It preserves original retained positions, UVs, decoded normals and weights exactly, with component IDs and source vertex/face mappings.
- `source-complete.json`: full derived inspection source, including decoded original normals, materials, skeleton, backpack attachment and provenance hashes.
- `component-inventory.json`: all 176 original components, bounds, areas, bone influences and original face IDs.
- `cleanup-selection.json`: explicit removed component IDs, removed face IDs and retained face IDs.
- `cleanup-report.json`: per-component decisions, per-group counts, candidate-mask counts, pose checks, GLB checks and silhouette measurements.
- `roundtrip-report.json`: independent GLB reimport checks.
- `comparison-textured.png`, `comparison-clay.png`, `comparison-wire.png`: front, back, left, right and three-quarter comparisons.
- `comparison-changed-components.png`: close comparisons of the four groups with removed geometry. The gauntlet view shows the left arm; its counts include both arms.
- `components-01.png` through `components-03.png`: all 17 material/region groups.
- `comparison-poses.png`: source and clean model under five diagnostic poses.
- `removed-details.png`: culled fasteners highlighted in red on the original model.
- `renders/`: individual full-character, component, gauntlet close-up, pose, removal-highlight and independent GLB renders.

The original RAR, original character/backpack JSON files, backpack attachment file, original reference Blender file, and previous shoulder study remain unchanged. The earlier rejected primitive reconstruction is separate and unused.

## Preparation for automatic reduction

Each retained mesh has `source_component`, `group`, `source_material` and `geometric_class` properties. Its original face and vertex IDs remain available as mesh attributes, and `source_normal` stores the original transformed normal vector separately from Blender's encoded loop normals.

Boolean point attributes identify candidate constraints:

- `candidate_boundary`: geometric open boundaries.
- `candidate_uv_seam`: UV discontinuities across geometrically shared edges.
- `candidate_normal_split`: original normal discontinuities above 28 degrees.
- `candidate_hard_edge`: geometric face-angle transitions above 30 degrees.
- `candidate_deformation`: vertices with multiple original skin influences.
- `candidate_identity`: all helmet and visor vertices.

The vertex group **`Reduction freedom - inspect before use`** assigns zero to the union of these candidates and one elsewhere. It is not a deform bone and does not alter skinning. These are conservative starting masks, not proof that every marked edge must remain forever or that every unmarked edge may safely collapse. The shoulder experiment showed that boundary protection alone does not bound surface or UV distortion.

For the next pass, reduce components individually and validate silhouette, sampled surface error, texture projection and pose behavior. Give helmet/visor surfaces the strongest protection, examine armor bevel strips separately, and treat undersuit/hands as deformation problems. Keep the stable source IDs so each proposed edit can be traced back or revised. Draw-call consolidation and game-format packing should follow, rather than destroying this editable component structure prematurely.

## Validation and limits

The original-to-clean JSON comparison verifies every retained face's winding and source mapping, and exact equality of its source positions, UVs, decoded normal values and weights. There are no remaining zero-area faces or unused vertices in the cleaned JSON. No valid retained surface is replaced or collapsed.

In Blender, retained positions and UVs have zero measured error. Float32 weight storage differs from the source by at most about 2.4e-8. Blender's custom-loop-normal encoding has a maximum vector difference of about 0.01275 (approximately 0.73 degrees) from the original direction; the exact transformed source vectors remain in `source_normal`, and the original decoded values remain in the JSON. This is an import/storage precision limit, not an intentional smoothing operation.

The original 85-node hierarchy and local bind transforms are retained. The backpack uses its original attachment transform and `b_backpack` influence. Retained vertices match the original's evaluated positions exactly in rest, aiming, stride, crouch/twist and hand/head diagnostic poses. These check for cleanup regressions; they are not animation clips and do not recreate Reach's runtime procedural fixup/jiggle controllers.

At the matched 640 × 800 render resolution, silhouette intersection-over-union against the original is:

| View | Overlap |
| --- | ---: |
| Front | 99.9910% |
| Back | 99.9902% |
| Left | 99.9665% |
| Right | 99.9703% |
| Three-quarter | 99.9938% |

GLB validation checks triangle counts, valid indices, finite attributes, unit normals on the clean model, normalized weights, all 85 original joint names, and embedded images. Independent reimport verifies the clean GLB against the source positions in both directions and produces a separate render. Blender's generated bone-display helper is excluded from character geometry counts.

## Materials

Original diffuse, color-mask and usable normal maps have been retained. Runtime color masks are converted to portable base-color textures on a full-UV bake plane; D3D normal-map Y is converted for Blender/glTF. Damage-decal color/opacity channels are repacked for portable rendering. Original model UV coordinates are unchanged; no surface-detail rebake or new UV atlas was needed for this culling-only baseline.

The visor and runtime armor colors remain presentation approximations shared by source and clean comparisons. The complete Reach material/lighting system is not recreated. The GLB is an editable, rigged baseline, not a runtime-integrated game asset; normal-map support and the cost of 110 component meshes still depend on the eventual target renderer.

## Reproduction

With the existing owned Reach cache extraction and preserved original JSON files present:

```sh
build/n64-python/bin/python port/n64/jorge_surgical_source.py
```

In Blender with `port/n64` on `sys.path`, run `jorge_surgical_cleanup.inspect()` and then `jorge_surgical_cleanup.build()`. These create isolated scenes and write derived files without overwriting the live user's project.

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  -b halo64-assets/assets/jorge/full-cleanup/jorge-surgical-cleanup.blend \
  -t 6 --python-expr "import sys; sys.path.insert(0, 'port/n64')" \
  -P port/n64/jorge_surgical_cleanup.py -- --export --render --details
build/n64-python/bin/python port/n64/compare_jorge_cleanup.py
/Applications/Blender.app/Contents/MacOS/Blender \
  -b halo64-assets/assets/jorge/full-cleanup/jorge-surgical-cleanup.blend \
  -t 6 --python-expr "import sys; sys.path.insert(0, 'port/n64')" \
  -P port/n64/validate_jorge_cleanup_blender.py
```

The original-face classification carries stable IDs through a disposable weld analysis, then assigns discarded coincident/degenerate reference faces back to their physical component. It never assumes that a post-weld face index is an original face ID. Explicit component selections and source hashes make the culling pass auditable.

## Shared-animation proof

The follow-on proof is in `halo64-assets/assets/jorge/animation-proof/`. It reuses the existing CE Spartan **idle, run, fire, and reload** motion on Jorge's retained 85-bone Reach skeleton. Jorge remains **26,076 triangles in 110 components**; the attached original CE assault rifle is a separate 764 triangles. The approximately 700-triangle goal remains a later reduction milestone.

`jorge-animation-proof.blend` contains four editable actions and an NLA demonstration sequence at frames 0–230. Press Play to see idle, three run cycles, four fire cycles, and reload. `jorge-animation-proof.glb` contains the same four named clips as independent animations, with embedded images. The overview video slows only the fire panel to one-quarter speed for readability; the four individual MP4s and exported actions retain their original durations.

| Clip | Original poses | Duration | Verified playback samples, including end |
| --- | ---: | ---: | ---: |
| Idle | 60 | 2.0 s | 61 |
| Run | 21 | 0.7 s | 22 |
| Fire | 5 | 0.166667 s | 6 |
| Reload | 88 | 2.933333 s | 89 |

The adapter calibrates the different CE/Reach limb axes, retains Jorge's original bind geometry and bone lengths, and maps 19 shared motion channels to the Reach rig. The extra spine bone interpolates torso motion; joint fixup bones blend neighboring motion. Other attachments retain their authored parent offsets. Fingers receive an explicit approximate grip because the CE skeleton has no finger animation. These are authoring approximations, not reconstructed Reach runtime controllers.

The existing fire overlay is composed against idle before retargeting. A two-bone support-arm adjustment follows the rifle contact point while preserving both arm-segment lengths. During reload, the support hand follows the original relative hand trajectory, rather than remaining pinned to the foregrip. The original unweighted `b_r_grip` node becomes the rifle socket. The rifle is rigid: magazine removal, bolt motion, muzzle effects, and audio are outside this body-motion proof.

Jorge's larger boots initially intersected the ground slightly. Root-height compensation is at most 31.54 mm at source poses. Additional root-only corrections sampled at 120 Hz remove a run interpolation dip of at most 13.12 mm. No leg is scaled or stretched. At the verified 30 Hz playback samples the lowest native vertex is within 0.00021 mm of the ground. This is a flat-ground preview, not terrain IK or a foot-sliding solver.

### Validation and reduction evidence

- All 174 original poses were checked against independent linear-blend skinning. Maximum positional disagreement was **0.00178 mm**.
- All 178 playback samples were compared after GLB reimport, in both vertex-distance directions for each component. Maximum exported-to-native deviation was **0.05327 mm**. The attached rifle also matched.
- Rest positions and UVs have zero measured change. Weights differ only by Blender float32 storage, at most 2.4e-8. Source JSON and baseline Blender file hashes remain unchanged. All 85 bones, 110 retained components, stable source IDs, and candidate reduction masks remain in the editable file.
- Front, side, back, and three-quarter pose views cover the major shoulders, backpack, elbows, hands, and knees. These are visual clearance checks, not a claim of exhaustive triangle-level collision freedom.
- `material-diagnostics.jpg` compares source-material, untextured, and vertex-RGB body rendering. The RGB diagnostic uses the existing `model_colors.bake_triangle` path and composited Jorge diffuse images without normal maps. Its **117 alpha-decal triangles are hidden only in that diagnostic**, because the current character rendering path cannot reproduce texture-alpha decals. The Blender/GLB proof retains them. The rifle keeps its source material in these body diagnostics.

`animation-report.json` records source hashes, calibration, per-clip errors, and the node order. `animation-roundtrip-report.json` records the independent export check. `component-motion-bounds.json` contains bounds over the original and 30 Hz samples; these bounds are not visibility or occlusion tests.

`motion-proof.npz` stores `bind_matrices`, `source_vertex_ids`, and for each clip:

- `<clip>_matrices` / `<clip>_seconds`: retargeted original source poses.
- `<clip>_playback_matrices` / `<clip>_playback_seconds`: final grounded 30 Hz playback poses, including the endpoint.

Matrices are in Blender armature space, in meters. For each bone, the skinning matrix is `pose @ inverse(bind)`. Vertex coordinates use `(Halo Y, -Halo X, Halo Z) * 3.048`. Bone order comes from the report. The `b_r_grip` matrix is the weapon transform; weapon-local points are raw Halo coordinates scaled by 3.048, without the character-axis rotation.

The current game uses baked vertex trajectories. Integration should bake **Jorge's own** vertices and socket samples from this adapter while retaining existing clip names, durations, and sampling conventions. CE vertex tracks and CE weapon attachment matrices cannot simply be copied unchanged. No game bank, character selection, or gameplay code was replaced by this proof.

The other seven shared clips still need the same checks before motion-based culling is considered safe. After that, use pose-aware visibility and silhouette evidence to remove hidden backing surfaces, then reduce bevels and consolidate parts sharing motion. Existing component bounds alone do not authorize deletion.

### Animation reproduction

Run background Blender with `port/n64` on `sys.path`:

1. Open the preserved `full-cleanup/jorge-surgical-cleanup.blend`; run `jorge_animation_proof.py -- --build --checks`.
2. Open the newly written `animation-proof/jorge-animation-proof.blend` in a fresh background process; run `jorge_animation_proof.py -- --export --motion`. The fresh process keeps the deliverable independent of the full cleanup reference scenes.
3. Open that final file; run `validate_jorge_animation.py` to verify the animated GLB.
4. Run `build/n64-python/bin/python port/n64/jorge_animation_preview.py --colors`; then run that script in background Blender on the proof file with `-- --render`.
5. Run `build/n64-python/bin/python port/n64/jorge_animation_preview.py --sheets --movies`. If the `ffmpeg` shim has no default version, set `JORGE_FFMPEG` to the installed binary path.

All these scripts write only derived proof outputs. Do not run the background-only `export_proof()` save step against the user's live Blender project.

## Tactical 5,000-vertex intermediate

The next asset is `halo64-assets/assets/jorge/tactical-5000/jorge-tactical-5000.glb`: **4,957 exported vertices and 4,877 triangles**, including Jorge's backpack and decals. Its 3,065 authoring vertices expand at UV/normal discontinuities during export. The accepted source was 20,757 exported vertices / 26,076 triangles. This is a vertex-budget milestone, distinct from the eventual approximately 700-triangle target.

The body-only GLB is the budgeted deliverable. `jorge-tactical-5000-with-rifle.glb` is a separate animation preview; the unchanged rifle adds 2,092 exported vertices / 764 triangles. The editable `.blend` includes that rifle as a separate object and preserves the proof's NLA sequence at frames 0–230.

All 110 physical components and the original 85-bone hierarchy remain. The reduction welds coincident positions only when skin weights agree, conservatively dissolves coplanar redundancy, and applies different collapse budgets per component. Reviewed minimum budgets protect boot volumes, lower-leg joints and backpack fittings. A surface-error-first weighting gives cleaner broad armor surfaces than strongly preserving every candidate crease. No primitive reconstruction or cross-component merge is used.

Retaining decimator-interpolated UVs proved cleaner than snapping reduced vertices back to the source and then resampling UVs. The final asset therefore retains interpolated UVs, original materials/normal maps, component-local sampled normals, and normalized nearest-surface barycentric skin weights with at most four influences. Changed topology no longer carries misleading exact source IDs: `nearest_source_face` and `source_barycentric` record the nearest reference surface instead.

The final asset has no zero-area faces, unused vertices or wire edges. Seven nonmanifold junctions already present in the source helmet and two torso fittings remain. Two new unused wire edges in an undersuit component were removed; this did not change any face-corner positions. It is not presented as a watertight mesh.

All 178 playback samples of idle/run/fire/reload are verified. Export-to-Blender positional error is below 0.06 mm. Body-only silhouette overlap is 96.97–97.97% across five idle viewpoints and four additional motion poses at 480 × 600. These are sampled-view measurements, not a guarantee at every angle. The body-only and armed exports have identical body geometry and equivalent named animation channels.

Geometric reduction is intentionally approximate: maximum sampled rest-surface deviation is about 42 mm locally, and reduced boot contact can differ by about 3.7 mm. Animated source-correspondence distances include both geometric approximation and interpolated skinning; the separate export round-trip metric measures serialization accuracy. The seven remaining clips and game integration are still pending.

The output folder contains a before/after video, matched textured/clay/pose sheets, per-component reports, silhouette masks, and validation JSON. `README.txt` explains the counts and files. The source proof file is preserved and hash-verified.

To reproduce in a background Blender process with `port/n64` on `sys.path`:

1. Open `animation-proof/jorge-animation-proof.blend`; run `jorge_tactical_reduce.py -- --build`.
2. Open the newly written `tactical-5000/jorge-tactical-5000.blend`; run `jorge_tactical_reduce.py -- --export --render --motion`.
3. Open that file; run `validate_jorge_tactical.py -- --validate --inventory --roundtrip --reference-renders --silhouettes`.
4. Run `build/n64-python/bin/python port/n64/compare_jorge_tactical.py --sheets --movie`; set `JORGE_FFMPEG` if an explicit ffmpeg binary is needed.

The reference motion frames from the preceding animation proof are reused by the comparison movie. Export/save operations belong in an isolated background process, preserving the live user's project.

## CE texture simplification

`halo64-assets/assets/jorge/ce-materials/` contains a separate CE-material variant of the tactical model. The body uses **one 256 × 256 color atlas and two materials**, down from 27 embedded images and 15 materials. No Reach normal maps remain. The atlas reuses actual CE Spartan diffuse regions and the original multipurpose blue armor mask, recolored to Jorge's olive, ochre, red, pale shoulder, charcoal and gold palette.

`jorge_ce_materials.py` bakes sixteen shared regions through Blender emission. Dominant-surface planar UV fits are component-local and use three-pixel tile insets. Broad CE panel, glove and rubber motifs replace Reach's fine surface noise; small side-face projections remain approximate. `material-report.json` records the donor hashes, source rectangles, tint values and per-component projection axes for later refinement. Donor images and the tactical source are preserved unchanged.

The old 11 alpha-decal overlays, totaling 75 triangles, are retired. The other 99 components retain their exact topology, positions, custom normals and skin weights. The result is **4,403 exported body vertices / 4,802 triangles** (2,981 authoring vertices), with the same 85-bone rig and four shared animation clips. Simpler UVs reduce export vertex splitting. This is a material pass, not progress to the eventual approximately 700-triangle target through further surface collapse.

`validate_jorge_ce_materials.py` verifies the source hashes, rest geometry, weights, normals, bind skeleton and all 178 playback samples. Retained native positions have zero measured change. The exported GLB round trip differs by at most 0.055 mm. The body GLB is 777,936 bytes; the rifle is supplied in a separate armed export. The Blender file packs the atlas and retains the NLA demonstration at frames 0–230.

`compare_jorge_ce_materials.py` creates matched five-view and pose sheets, a source/atlas provenance image and a 7.7-second before/after movie at original animation speed. The preceding tactical motion renders supply the before half. Reproduction steps and resource counts are in the asset folder's `README.txt`. No runtime character bank or gameplay behavior is changed.

## Restored colors and second surgical detail pass

`halo64-assets/assets/jorge/detail-pass/` restores the black helmet brow band using the original helmet paint mask and UV layout, while retaining CE-derived shading. The backpack is gray-brown. Lower-contrast CE luminance removes printed undersuit shapes and strong panel noise from the armor, giving broader, simpler color fields. The atlas remains 256 × 256, with two body materials and no normal maps.

`jorge_detail_pass.py` explicitly culls 35 small fittings: eight gauntlet buckles, eight forearm fasteners, two upper-arm tabs, four chest hinge ribs, four calf fasteners, two chin fittings, four spine plugs and three shallow backpack caps. Their surrounding armor, gauntlet straps, larger couplings and backpack lower connector remain. There is no global collapse or retained-surface modification in this pass.

The result is **3,867 exported vertices / 4,273 triangles**, down from 4,403 / 4,802: 529 triangles removed (11.0%). The 64 retained meshes contain 2,586 authoring vertices. Their positions, topology, normals, skin weights and source correspondence remain exact. `next_reduction_priority` properties identify protected design features, deforming parts and other armor for the next reduction pass. The approximately 700-triangle target remains pending.

`validate_jorge_detail_pass.py` checks the source hashes, retained surfaces, mesh health, bind skeleton, all 178 samples of the four clips, and the exported GLB. Native retained-vertex motion has zero change; round-trip error is below 0.055 mm. Sampled body silhouette overlap is 99.83–99.96% across five idle viewpoints and four motion poses. Existing source nonmanifold junctions remain; there are no new zero-area faces, unused vertices or wire edges.

`compare_jorge_detail_pass.py` provides matched stills and a 7.7-second before/after movie. The body GLB is 649,256 bytes. The separate armed export retains the unchanged CE rifle. The editable file packs the atlas, preserves the 85-bone rig and four actions, and opens with the NLA demonstration at frames 0–230. The preceding CE texture pass and all older assets remain unchanged. See the output folder's `README.txt` for reproduction steps.

## Half-budget component LOD and port AR

The accepted detail pass was checked in before reduction on `codex/jorge-component-reduction`: main repository `ecef9109`, assets submodule `2301790`. The next asset, `halo64-assets/assets/jorge/half-budget/`, has **2,123 body triangles / 2,318 exported vertices** (1,385 authoring vertices). Its 2,136-triangle cap is half the preceding 4,273 triangles, rounded down. All 64 components remain separate and individually within budget.

`jorge_half_budget.py` assigns explicit per-component caps, with higher retention for the helmet, visor, shoulders and closed strap forms. Compatible-position welding and conservative coplanar cleanup precede independent weighted collapse searches. Interpolated UVs, source-sampled normals and normalized barycentric skin weights are retained. Fifty-nine outlier vertices were clamped to within 20 mm of their parent surface. The source-to-reduced surface error can be larger where geometry was discarded; the maximum sampled deviation is 112 mm locally on the torso.

`component-budgets.json` and `.csv` expose all 64 allocations and actual results. The editable meshes retain the component IDs, caps, before/after counts and fresh parent-triangle/barycentric correspondence. The 13 unused budget triangles reflect attainable collapse counts rather than padding.

Jorge now carries the **actual 140-triangle N64 world AR**, using the quantized geometry and baked RGB from `halo64-assets/generated/model-preview.json`. Its inverse packing transform preserves the existing grip socket. The GLB exports its vertex colors with `KHR_materials_unlit`; native and exported positions and quantized RGB bytes are validated against the port asset. Both sides of the comparison use this AR. The weapon is excluded from Jorge's body budget.

All 178 samples across the four clips retain the exact bone motion. GLB reimport differs by less than 0.054 mm. Sampled silhouette overlap is 94.99–97.37% across nine views/poses. Weights have at most four normalized influences, and there are no zero-area faces, unused vertices or wire edges. Seven authored nonmanifold junctions remain. Reduced boot contact can differ by about 7.9 mm; this is an intermediate LOD, not a new terrain-contact solution. The approximately 700-triangle goal, remaining clips and runtime integration remain pending.

The output includes the editable file, body-only and armed GLBs, unchanged body atlas, per-component reports, matched stills and a 7.7-second comparison movie. `validate_jorge_half_budget.py` and `compare_jorge_half_budget.py` provide the checks and previews; reproduction commands are in the asset folder's `README.txt`.

## Coverage-first reduction from the 4,000-vertex checkpoint

The subsequent aggressive `vertex-1159` experiment was rejected for losing armor solidity. It is not the input to this stage. `solid-2000/` starts directly from the unchanged, hash-verified `detail-pass/jorge-detail-pass.blend`: **3,867 exported vertices / 4,273 triangles**.

The new result has **2,169 exported body vertices / 2,743 triangles**, with 1,790 authoring vertices, 59 retained components, the same 85-bone rig and four shared clips. The approximate 2,000-vertex target yields to coverage constraints. GLB counts include normal and UV splits and are not packed N64 vertex counts.

`jorge_solid_reduce.py` fixes original open rims and their skin weights, preserves each retained component's topological type, and rejects closed-volume changes beyond 10%. Component-local sampled surface error is bounded per region, with the 95th percentile limited to 20 mm. Closely aligned custom-normal splits are consolidated while major shading breaks and the helmet paint UV layout remain. Separate component decisions and source/final counts remain inspectable; individual caps do not force destructive reductions.

Assembly checks identified insufficient knee coverage during running. Those fabric patches, the upper-arm surfaces, and the boot overlap surfaces retain their source topology. Chest and backpack retain additional support geometry. Four forearm straps and the dangling backpack connector are removed. A local adjustment of up to 12 mm gives the lower codpiece front clearance over the underlying fabric. The black helmet band, gray-brown backpack, CE atlas and actual N64 AR remain.

`validate_jorge_solid.py` verifies mesh health, topology, UVs, normals, weights, source preservation, and exact shared bone motion across all 178 samples. Original rim motion differs only within floating-point precision; GLB reimport is checked separately. An assembled-body raster diagnostic compares 170 views/poses, with additional checks on six poses rounded to the port's Spartan coordinate grid. Reports distinguish new enclosed regions from outline changes around existing arm/leg gaps and retain small raster discrepancies. These are sampled diagnostics, not a guarantee of a watertight original asset or every possible camera/pose. Seven additional shared clips and runtime integration remain pending.

`compare_jorge_solid.py` supplies matched five-view, pose, and animation comparisons. The reference frames in `half-budget/reference` come from the exact same detail-pass source and use the same port AR. The new folder includes the editable Blender source, animated GLBs, component inventory, reports, and reproduction instructions.

## Collar, rump and concealed coverage repairs

`coverage-repair/` starts from the accepted `solid-2000/jorge-solid-2000.blend`, preserved unchanged. This is a local repair pass with no decimation. The green torso support is recessed 28 mm beneath the yellow collar; the yellow plate and red neckguard retain their original geometry. Both collar layers follow `b_torso`, making the adjusted clearance independent of the animation pose.

The undersuit now has fitted backing inside both thigh openings, the torso, and the shoulder sockets. Its original UVs and skin weights remain; the original perimeter is retained except for one fabric vertex tucked beneath the left thigh tip. Nine interior vertices close 114 boundary edges with 114 triangles. The tagged left rump seam receives one additional triangle following a bend in the neighboring fabric rim, and one fabric vertex is tucked 10.4 mm beneath the original armor tip. The new tip and fabric bend share the rigid upper-leg bone; their 14.56 mm overlap offset stays constant through all four clips. These patches preserve the original armor masses rather than replacing them with primitives.

The result has **2,183 exported body vertices / 2,858 triangles**, with **1,800 authoring vertices**. Relative to the accepted checkpoint, the repair costs 14 exported vertices and 115 triangles. The 59 components stay separate. Six components change; the other 53 retain their exact geometry, normals, UVs, weights and native motion. Edited custom normals are reapplied; Blender's re-encoding changes them by less than 0.3 degrees. The black helmet band, gray-brown backpack, two materials, packed CE atlas and actual 140-triangle N64 AR remain.

`validate_jorge_coverage_repair.py` checks original-face preservation, backing closure, finite and normalized weights, normals, UVs, the unchanged skeleton and rifle, all 178 animation samples, and GLB reimport. The new triangles remain nondegenerate throughout the animation. Native bone motion is unchanged; GLB reimport error is below 0.055 mm. A separate 70-view/pose comparison against the accepted input checks that the repair introduces no new enclosed raster gaps. Broader comparisons against the older detail-pass source retain small differences from the previous reduction; these local repairs do not make every separate source component watertight. Keep the native and quantized coverage diagnostics in subsequent reduction reviews.

`repair-report.json` records each added backing perimeter, center, skin assignment and the collar/rump offsets; `component-inventory.csv` separates the repair cost by component. Future reductions should preserve the closed garment backing, the fitted rump return, collar clearance, and animation continuity. Reduce interior detail without reopening those seams. The approximate 700-triangle goal and game integration remain later stages.

The folder contains editable Blender source, body-only and armed GLBs, close-up before/after sheets, matched five-view and pose renders, and a four-clip comparison movie. Reproduction commands are in `README.txt`; the scripts are `jorge_coverage_repair.py`, `validate_jorge_coverage_repair.py`, and `compare_jorge_coverage_repair.py`.
