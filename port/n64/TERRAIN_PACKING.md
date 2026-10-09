# Ordered terrain batching

`pack_assets.py` uses `pack_terrain.py` to reduce vertex transforms while keeping
all 1,870 reduced terrain triangles, their corner order, winding and quantized
positions. It retains the existing material and 12-unit spatial-cell groups.
Within each group, batches grow to at most 60 paired vertices and 120 indices.
Their combined vertex/index footprint fits Tiny3D's shared DMEM limit.

The terrain uses repeating 32×32 textures. UVs are rounded at 32 units per texel
before batching. One integer 1,024-unit offset per axis recenters each batch into
signed 16-bit storage. The packer checks equivalence to the previous per-triangle
quantizer: every triangle differs by a constant whole-texture repeat, preserving
perspective interpolation and wrap sampling. A different texture size or an
unrepresentable UV span fails explicitly. Each triangle's UV edge differences
also fit signed16, as required by Tiny3D's attribute-gradient setup.

Vertices share a position and UV only when all original RGB channels are within
8/255 of an immutable representative. Representatives are never averaged or
modified, so successive merges cannot accumulate color error. The packer checks
every expanded corner. Collision data is unchanged.

Run portable fixtures and validate the emitted C independently:

```sh
python3 port/n64/test_pack_terrain.py
python3 port/n64/validate_terrain.py
```

The independent validator expands the emitted indices, checks alignment, bounds,
DMEM limits and material/cell boundaries, and compares positions, triangle order,
original shading and per-triangle UV periods against the source JSON.

The local replay probe covered 1,132 cameras: mean terrain vertex loads fell
from 810 to 691 per view (14.65%), with no sampled camera requiring more vertex
loads. Wider batch bounds increased submitted terrain triangles by 0.62%.
Sixteen native 160×120 software texture comparisons showed identical pixels for
UV recentering alone and a maximum 5/255 output color change with bounded color
sharing. These are offline estimates, not hardware performance or RDP precision
measurements; ares validation and the quiet completion benchmark remain the
runtime checks. Probe data and images are local under
`build/n64/performance-audit/terrain-batch-probe/`.
