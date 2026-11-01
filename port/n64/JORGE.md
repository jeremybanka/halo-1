# Jorge semantic demake

> Historical rejected reconstruction. The inspection below remains useful, but
> the 600-triangle primitive model lost the armor's identity and is not the
> accepted asset or reduction recipe. Follow the
> [critical path and reusable workflow](CHARACTER_DEMAKE.md) and
> [current playable asset](JORGE_FIRSTPERSON.md).

The user-supplied retail Reach archive is read without modification. The
character is extracted from `m05.map`, with resources from the associated
retail caches. The field pack is a separate render model attached using the
character's authored `backpack` marker and parent-node transform.

## Inspection and simplification plan

The intact assembly has 33,208 triangles: 28,898 on the helmeted character and
4,310 on the field pack. It has 14 source shader definitions; the imported
reference separates the three character regions by material, plus the pack,
into 17 mesh objects. The source character has 85 skeletal nodes; the pack
has one. Original node transforms and weights remain in the source JSONs.

Preserve the tall protective collar, narrow copper visor and Grenadier helmet,
yellow chest armor with transverse coupling, asymmetric shoulder shells,
large field pack, wide gauntlets, and heavy boots. Match the original rest
pose and major component bounds. Replace surfaces with authored tapered
rings and extruded planar profiles. Consolidate fingers, armor seams, screws,
buckles, battle damage and small pouches. Remove invisible interior layers.
Do not use decimation, remeshing, or global topology collapse.

The reference uses original diffuse textures and UVs. Runtime armor colors
and visor metal are approximated for Blender presentation; it does not
recreate the Reach renderer. Diffuse alpha carries game shading information
and is ignored as transparency. Source PNGs remain unchanged.

## Assets and reproduction

Private deliverables are in `halo64-assets/assets/jorge/`:

- `jorge-original.json`, `backpack-original.json`: intact extracted geometry,
  UVs, material references, skin weights and original node hierarchy.
- `backpack-attachment.json`: original attachment transform.
- `jorge-original.blend`: intact assembled reference with packed textures.
- `source-inspection.json`: per-object triangle counts, dimensions and bounds.
- `jorge-lowpoly.blend`: editable semantic reconstruction and studio cameras.
- `jorge-lowpoly.glb`: exported character assembly.
- `renders/`: matching original and reconstructed front, back, left, right,
  and three-quarter renders, plus comparison sheets.
- `validation.json`: topology, dimensions, triangle count and export checks.

`reach_cache.py` extends the existing read-only cache reader using the retail
Reach layouts documented by the local Reclaimer source checkout. The parser
uses OpenSSL for the game's string-table encoding. `extract_jorge.py` extracts
the character or a named render model. `jorge_workshop.py` assembles the intact
reference. `jorge_rebuild.py` is the complete editable reconstruction recipe.

This deliverable is a static asset in the original rest pose. CE skeleton
binding, animation checks, ROM packing and character-selection/gameplay
integration are subsequent work.

## Final result and validation

The final assembly has **600 triangles**, **32 authored mesh parts**, and
**8 materials**, a 98.19% reduction from the intact character plus field pack.
Its dimensions are 1.427 × 0.966 × 2.305 m in the source rest pose; the reference
is 1.398 × 0.999 × 2.310 m. The GLB is rooted at one `Jorge` node.

Matching-camera silhouette intersection-over-union is 82.6% front/back,
80.9% left/right and 80.4% three-quarter. These are silhouette measurements,
not claims of texture or detail fidelity. The reconstruction uses simple
armor panels, tapered limb shells, mitten hands, a reduced field pack and
solid color regions instead of texture noise and fine mechanical detail.

Export and reimport both verify 600 triangles and matching world bounds.
All material indices are valid; positions are finite; no triangle has zero
area; closed parts have positive signed volume. The copper visor is an
intentional open overlay and the collar has a hidden open underside. These
are separate overlapping armor parts, not one watertight printable shell.

The source geometry JSON hash is unchanged after reconstruction. Exact
output checksums and per-part counts are in `validation.json`. Run
`compare_jorge.py` to regenerate the comparison sheets.
