# Jorge: surgical shoulder experiment

This replaces the primitive-reconstruction approach with a test on Jorge's original large left shoulder. It is a shoulder experiment, not a completed whole-character reduction or game integration.

## Result

| Version | Triangles | Reduction from A | Operation |
| --- | ---: | ---: | --- |
| A | 1,924 | — | Untouched extracted geometry, UVs and vertex normals |
| B | 844 | 56.1% | Remove ten disconnected fastener components; keep the complete original plate and mount |
| C | 758 | 60.6% | B plus conservative, constrained edge collapse and original surface-attribute transfer |
| D | 758 | 60.6% | Direct edge collapse of A, with identical attribute restoration and exact count matching |

The largest saving comes from recognizing expendable parts. Ten approximately 2 cm fasteners use 1,080 triangles. The primary plate uses 828; its separate mounting structure uses 16. B preserves those 844 original triangles verbatim, including their original UVs and normals. No primitive replacement, global decimation or bevel-loop removal is used in B.

C preserves the plate silhouette more closely than D in the three measured views. The advantage is modest visually at small display sizes; B's removal of expensive fasteners is the strongest result. A lower-count C candidate produced unwanted flattening and was rejected. Preserving selected edges alone is insufficient: surface error also needs to limit reduction.

## Files

All outputs are under `halo64-assets/assets/jorge/shoulder-study/`:

- `jorge-shoulder-study.blend`: all four variants, packed images, original 85-node Reach skeleton, matched studio. C is initially visible; enable A/B/D individually in the Outliner for inspection. They occupy the same original coordinates.
- `shoulder-A.glb` through `shoulder-D.glb`: separate skinned exports with embedded color and normal images. C is the constrained candidate; B is the conservative culling-only candidate.
- `comparison-textured.png`, `comparison-clay.png`, `comparison-wire.png`: front, side and three-quarter views, four columns, identical framing and lighting.
- `comparison-small.png`: 128-pixel shoulder previews.
- `comparison-poses.png`: rest, raised arm, aiming and shoulder-pad articulation checks.
- `renders/`: the 40 individual comparison and pose renders at 540 × 540.
- `shoulder-original.json`: preserved extracted reference, including UVs, original normals, skin weights, source vertex indices and all skeleton nodes.
- `component-inspection.json`, `study-report.json`: component inventory and measured validation.
- `textures/`: decoded original normal map and portable baked material textures.

The original RAR, whole-character source JSON and original reference Blender file were not overwritten. The rejected primitive reconstruction remains separate and is not used here.

## Procedure and constraints

1. Inspect the original shoulder in Blender. Analyze connected components on a disposable position-welded copy, carrying stable original face IDs through topology operations.
2. Produce B by selecting the two major components' original faces. Retain source positions, winding, UV coordinates, vertex normals and the rigid bone attachment. The ten small fasteners are the only removed components.
3. For both C and D, weld coincident positions while retaining per-corner UVs and normals; remove degenerate geometry from the working copies. A and B stay unchanged.
4. For C, identify actual mesh boundaries, UV discontinuities and geometric creases above 30 degrees. Also test for original split-normal discontinuities above 28 degrees; none add constraints in this piece. These thresholds are shoulder-specific candidate constraints, not a universal Spartan preset.
5. Protect 342 vertices on 372 distinct edges using a reduction weight group. Apply Blender collapse reduction conservatively (requested ratio 0.90 of B). Verify every protected edge exists afterward and every protected endpoint remains exactly stationary. This is verified preservation; the modifier weight alone is not treated as a guarantee.
6. Restore corner attributes within the original UV charts. At newly positioned vertices, interpolate from the nearest original triangle in the corresponding chart. Because reduced triangulation still distorts some of the original texture parameterization, retain that UV layer for inspection and create a separate atlas for C and D. Bake surface color and tangent-space normals from B onto C, and from A onto D. Both reduced variants receive the same 512 × 512 bake treatment.
7. Search D's collapse ratio until its actual triangle count exactly equals C. Final D requires no extra subdivision or triangle padding.
8. Measure retained-surface deviation and reject C if any sampled deviation exceeds 1 mm. This is a sampled limit, not a continuous mathematical bound. No attempt is made to force the earlier 600-triangle whole-character target onto this shoulder experiment.

This first pass demonstrates selective component culling plus constrained reduction. It does **not** yet implement semantic bevel-loop detection. That needs to distinguish redundant bevel strips from intentional transitions on each armor region before it is applied broadly.

## Validation

On 3,968 samples of the retained plate and mount (source vertices, triangle centroids and edge midpoints):

| Measurement | C | D |
| --- | ---: | ---: |
| RMS distance to reduced surface | 0.096 mm | 0.392 mm |
| Maximum sampled distance | 0.779 mm | 1.932 mm |

Sampling deliberately excludes the removed fasteners. Distances are one-way from the retained source surfaces to the reduced surfaces, not a symmetric Hausdorff metric. The rendered front, side and three-quarter silhouette masks provide an additional check. Exact per-view intersection-over-union measurements are in `study-report.json`.

C has no zero-area faces, loose vertices or nonmanifold edges beyond the original open boundaries. Its sixteen welded boundary edges belong to the original open mounting structure. A contains thirteen source degenerates; it remains untouched for comparison. Split-UV reference meshes have more topological boundary edges than their welded counterparts, so those raw counts are not directly comparable.

All original shoulder vertices are weighted 100% to `b_l_shoulderpad` (source node 39). The full 85-node hierarchy and local bind transforms are preserved. Four pose checks compare evaluated vertices against the expected rigid bone transform; maximum error is below 0.0003 mm. This validates this rigid shoulder attachment only. It does not establish that hands, undersuit or multi-bone deformation regions will simplify successfully.

GLB validation checks actual triangle counts, index bounds, finite positions/UVs/normals, normalized normals and skin weights, all 85 joints, the correct weighted bone, and both embedded textures. The source JSON hashes are checked after export.

## Textures and presentation

The source contains a usable 256 × 256 CTX1 normal map. It retains shallow features after the separate fastener geometry is culled. Existing diffuse/color-mask textures and that normal map provide the surface appearance for every variant. The mask is tinted with the same Jorge color approximation on A–D. A portable base-color texture is baked, and the D3D normal map's green channel is inverted for Blender/glTF. C and D then receive selected-to-active color and normal bakes on separate 512 × 512 atlases to preserve the original surface appearance despite changed triangulation. These transfer existing detail; they do not invent new detail. The complete Reach runtime shader is not recreated.

Untextured and wireframe sheets disable the normal map. They still use original/interpolated vertex normals, consistently across variants. The normal map and texture projection have not been validated inside the game renderer. The exported GLBs are inspection assets, not a game-ready runtime integration.

## Reproduction

Run `jorge_shoulder_study.build()` from Blender with `port/n64` on `sys.path`. It creates an isolated scene and writes a standalone library without replacing the user's live project. The original extracted source files and textures must be present in this checkout.

Then run in a background Blender process:

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  -b halo64-assets/assets/jorge/shoulder-study/jorge-shoulder-study.blend \
  -t 6 -P port/n64/jorge_shoulder_study.py -- --export --render
build/n64-python/bin/python port/n64/compare_jorge_shoulder.py
```

The background step bakes portable material inputs, exports A–D, saves a normal standalone Blender project and renders comparisons. The comparison script validates the exports and source hashes before assembling the sheets.
