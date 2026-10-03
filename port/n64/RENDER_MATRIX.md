The renderer keeps the camera at Tiny3D matrix-stack depth zero and reserves one
entry for sibling objects after drawing terrain. Each object uses
`t3d_matrix_set(matrix, true)`. Tiny3D loads the camera from the preceding stack
entry and multiplies it by the new object matrix, exactly as its ordinary push
operation does. One pop at the end restores depth zero before the next viewport
replaces its view and projection.

Vehicle part matrices already contain hull, turret and barrel transforms from
CPU preparation. Held weapons already contain the body and hand transforms.
First-person matrices are also complete world matrices. None requires a nested
RSP stack level, and no transform or projection calculation was changed.

For N object draws, the old path recalculated the current matrix 2N times:
one push and one pop per draw. The sibling path recalculates it N+1 times,
plus one inexpensive stack-pointer advance. It eliminates the intervening
camera loads, normal-matrix normalization and camera/projection products that
the following object would immediately replace. Triangle order, matrices,
vertices, materials, animation and the geometry-slot fence remain unchanged.

`test_render_matrix.py` checks the actual application call sites and installed
Tiny3D stack semantics, then symbolically compares every matrix multiplication
operand and order over varied one-, two- and four-view sequences. Empty views,
zoom changes and all object categories are included. The symbolic comparison
does not assume floating-point associativity or approximate fixed-point math;
the same operands reach the same unchanged RSP operations.

```sh
python3 port/n64/test_render_matrix.py --tiny3d /path/to/tiny3d
```

Matching-bank snapshots at replay ticks 480, 1148 and 2078 are pixel-identical
before and after the sibling change: all 427,500 compared pixels match in each
pair. The raw image and ROM hashes are saved in
`build/n64/performance-audit/sibling-matrix/pixel-results.json`, with the
immutable source baseline alongside them. This establishes those snapshots'
image equivalence; it does not establish a performance gain or replace command
validation of other scenes.

Individual near-vehicle parts also use conservative frustum bounds. Preparation
transforms each packed part's local box with the exact current matrix used to
draw that part, including wheel spin, turret yaw and inherited barrel pitch.
The existing combined vehicle bound is unchanged. A visible near vehicle may
skip a part only when that part's outward-rounded box lies outside a frustum
plane. Invalid or overflowing bounds keep the part visible. Far vehicles,
geometry, LOD thresholds and triangle order are unchanged.

The part boxes occupy 1,176 bytes and are CPU-only; RSP commands borrow no pointer
to them. They are refreshed before all views, independently of the two fenced
geometry slots. The loop can reject every part without disturbing the sibling
stack's unconditional final pop.

```sh
python3 port/n64/test_vehicle_culling.py --tiny3d /path/to/tiny3d
```

This sanitizer test compiles the actual preparation functions and generated rig
tables with the installed Tiny3D matrix/frustum functions. It verifies all eight
corners of each actual fixed-point pose, including rotating wheels and composed
turret/barrel transforms. It also checks that each tested frustum rejection
places every transformed corner outside the rejecting plane, and that invalid
bounds remain visible. Host sine/cosine replace the SDK's target trig functions;
the bound and matrix still consume the same computed values. Target snapshot
and command validation remain separate gates. The pre-part source is preserved
in `build/n64/performance-audit/part-frustum-probe/main-before.c`.

The part-culling target pairs at ticks 480, 1148 and 2078 also match exactly,
with zero changed pixels in each 427,500-pixel game crop. The corresponding
proof is `build/n64/performance-audit/part-frustum-probe/pixel-results.json`.

Nonblocking `rspq_flush()` calls after terrain and each viewport wake the RSP
before subsequent CPU work and audio mixing. They add no drawing commands or
waits. Three additional matched target pairs are pixel-identical; their ROMs,
raw PNGs and comparisons are under `performance-audit/view-flush/snapshots/`.
Moving the existing depth clear before CPU-only preparation also preserves
graphics command order. `test_render_flush.py` and `test_render_prepare.py`
check these properties against the installed SDK. Their timing benefit must
be measured separately: flushing reduced paced misses from 19 to 14 in the
75-second replay, while the depth-clear move alone left 14 misses.

Animation decoding is deferred until the first body or held-weapon draw for
each player, after terrain submission. All cameras, bounds and the union of
requested detail levels remain eager. The first use decodes every requested
body level and attachment once, writes back the held matrix, and marks that
player ready; later views cannot rewrite those borrowed buffers. First-person
initialization, tinting and decoding similarly precede the existing draw.
The same two geometry-slot fences protect all output writes.

Actual-bank sanitizer comparisons cover 2,400 schedules plus 7,200 independent
schedules, including both detail levels, held-only visibility and first-person
guards. Another 20,000 scheduling fixtures check write ownership and profiling
attribution. Target snapshots at ticks 480, 1148 and 2078 have zero changed
pixels across 1,282,500 compared pixels. Evidence is under
`performance-audit/deferred-animation/`. This preserves the image but has not
demonstrated a cadence improvement: the four-buffer replay retains six missed
deadlines before and after the change.

Viewport visibility now includes a four-native-pixel submission margin at all
four edges. `render_visibility.h` derives the side planes from the final
camera/projection product, including the source-derived Xbox reticle offset.
Only CPU AABB rejection is widened: the actual projection, near/far planes,
Tiny3D triangle clipping and per-player RDP scissor are retained. Side planes
are deliberately unnormalized because the AABB test uses only their signs.
Particle bounds also use the same outward rounding and overflow fallback as
model bounds, instead of truncating floating bounds inward.

`python3 port/n64/test_render_visibility.py` compiles the actual installed
Tiny3D AABB function and probes all four edges, all supported viewport sizes,
camera rotations, asymmetric projections and 1×/2×/10× zoom. Each strict and
target-math sanitizer run checks 143,856 points: visible edge points and the
two-pixel bleed remain submitted, while distant off-screen points are rejected.
It also verifies the projection and near/far planes remain unchanged. This
host check proves conservative CPU submission; target raster clipping and
frame cost require separate Ares verification.
