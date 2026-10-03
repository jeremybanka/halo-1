# Scorpion cannon visibility repair

The tactical reduction left fourteen cannon triangles in the near Scorpion and
four disconnected sheets in its far LOD. Enlarging those sheets retained gaps.
The performance recipe now replaces only this rigid cannon surface with a closed,
inward-wound tapered tube. It is an intentional N64 silhouette adjustment, not an
exact export of the original high-detail geometry.

`scorpion_barrel.py` derives the node named `frame cannon`, its original axis,
the existing muzzle position, and the light sleeve's two longitudinal boundaries
from locally extracted data. The cross-section is 0.18 × 0.14 Halo units at the
root and 0.14 × 0.12 at the muzzle. A 0.35-unit root overlap connects the reduced
turret housing; the original muzzle does not move. These settings are tracked in
`world_performance.json` and applied after the normal near/far reductions by
`reduce_extended.py --performance-profile`.

The shell has sixteen geometric positions and twenty-eight triangles: four
rectangular rings, twelve side quads, and two end quads. Two rings follow the
original light sleeve boundaries. Shaft and sleeve retain distinct original
materials. Their unlit RGB is sampled from the corresponding original face
interiors, avoiding atlas-edge bleed, then passed through the ordinary lighting
and protected color-weld packer. No texture or proprietary mesh data is stored in
the recipe. All shell corners remain rigidly attached to the original cannon
bone, which belongs to the existing turret pitch group.

## Actual packed cost

| Bank | Triangles before → after | Stored vertices before → after | Batches before → after |
| --- | ---: | ---: | ---: |
| Scorpion near | 366 → 380 | 426 → 444 | 10 → 11 |
| Scorpion far | 186 → 210 | 256 → 282 | 5 → 6 |

The near counts include two existing alignment triangles. Before padding, the
near mesh changes from 364 to 378 triangles. Combined vertex storage grows by
704 bytes and indices/batches by 232 bytes: **936 bytes total**. Other geometry,
animations, attachment poses, material/color budgets, and broad culling bounds
remain unchanged. Scorpion's tiny-model entry still aliases its ordinary far
LOD; there is no separate Scorpion micro mesh.

## Reproduce

Run from the repository root, using a Python environment with NumPy and Pillow.
`BLENDER` and `PYTHON` below denote the local executable paths.

```sh
"$BLENDER" --background --factory-startup --python port/n64/reduce_extended.py -- \
  build/n64/assets/extended-raw.json build/n64/assets/extended-reduced.json \
  --performance-profile
"$PYTHON" port/n64/pack_extended.py build/n64/assets/extended-reduced.json \
  --output build/n64/generated
"$PYTHON" port/n64/generate_micro_lods.py --assets build/n64/assets \
  --verify-generated build/n64/generated --output build/n64/assets/micro-lods.json \
  --blender "$BLENDER"
"$PYTHON" port/n64/pack_micro_lods.py
"$PYTHON" port/n64/validate_assets.py
"$PYTHON" -m unittest discover -s port/n64 -p test_scorpion_barrel.py
"$PYTHON" port/n64/test_vehicle_culling.py
```

Regenerate micro provenance after repacking, even though all twelve dedicated
micro meshes are unchanged: their report must reference the current ordinary
model bank. The Blender process uses factory startup and does not alter an open
interactive scene. Generated data remains under ignored `build/`.

## Verification and limits

Local evidence is in `build/n64/performance-audit/scorpion-barrel/`. The `before/`
directory preserves the old reduced inputs, packed model bank, and audit metrics.
`candidate-proof.json`, `actual-c-proof.json`, `recipe-proof.json`,
`active-bank-proof.json`, and the final hero/native/articulation
PNGs document the comparison. These are offline model renders, not ares captures.

- Eight matching original/before/after directions, plus 48-, 24-, and 12-pixel
  extents and turret yaw/pitch poses.
- Mean source-silhouette IoU near 0.94658 → 0.94188; far 0.84904 → 0.85312.
  This intentionally thicker barrel is not pixel-identical to the Xbox mesh.
- Actual emitted C geometry, indices, RGB, material barriers, animation data and
  bounds match the packer contract. All 102 non-Scorpion static arrays are byte
  identical; only the two Scorpion vertex/index/batch sets change.
- A complete isolated Blender quality → performance rebuild reproduced the
  reviewed payload exactly. The twelve dedicated micro payloads, their emitted
  C and their preview remain byte-identical; their refreshed provenance binds
  the new ordinary model bank.
- The refreshed 59-entry audit changes only its two Scorpion rows; the other
  57 rows and all twelve micro comparisons are identical. All original model
  comparisons remain within the existing 0.03 source-IoU loss budget. See
  `final-audit-proof.json` for input hashes and the exact comparison results.
- Unit checks enforce a closed manifold shell, inward winding, unchanged muzzle,
  rigid weights, original sleeve colors, immutable inputs, and rejection of mixed
  rig weights or repeated application.
- The portable current-pose harness loads ordinary and micro gate bounds and
  checks 12,288 articulated poses, including 4,096 wheel poses and 294,912 fixed
  corner coordinates under AddressSanitizer/UndefinedBehaviorSanitizer.

The existing far hull's coarse panels remain unchanged. Hero-sized offline views
expose those preexisting gaps; this repair is confined to the cannon. Target
appearance and timing require the new ROM's own validation; earlier performance
measurements do not establish the cost of this revision.
