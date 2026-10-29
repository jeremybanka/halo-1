# Jackal shields — appraisal candidate, 29 October 2026

The opt-in `--pve-jackal-shields` candidate restores visible shields to Minor and
Major Jackals at all three body LODs. It extends the local Firefight roster
candidate. Source collision and shield mechanics already operated; this restores
the missing visible surface and connects it to those mechanics. No AI, movement,
damage, scoring, wave or accepted body-geometry changes are made in this pass.
The candidate is published for appraisal with PR #12 and remains opt-in.

## Source and implementation

The original `characters\\jackal\\jackal`, `base00 superhigh` mesh contains a
76-triangle shield. The lower source LODs omit it. Those same 76 triangles now
serve every body LOD, retaining their source UVs and all openings. The source is
also checked against the pre-reduction `firefight-combat` extraction, so this is
not a reconstruction from an already simplified body.

Every shield vertex belongs entirely to source node 26, `frame shield`. Blender
converts the mesh to that bone's local coordinates and bakes the source attachment
tracks. At runtime one immutable mesh follows the animated forearm transform.
There is no additional per-actor animated vertex buffer. The body retains its
existing LOD/animation selection, while the shield follows its source pose.

Per visible shield, the addition is **76 triangles, 76 vertex loads and two
batches**, at every tier. Relative to the existing Jackal body alone, that is:

| Body tier | Previous vertex loads | With shield | Increase |
| --- | ---: | ---: | ---: |
| Near | 1,856 | 1,932 | 4.1% |
| Middle | 1,174 | 1,250 | 6.5% |
| Coarse | 584 | 660 | 13.0% |

These counts exclude the separately drawn weapon. All seven original roster
bank files remain byte-identical. `pve_jackal_shield.c` is the only added runtime
asset: a shared mesh, 32×32 source noise texture, attachment tracks and rank colors.

Named shield data in the final diagnostic ELF totals 14,304 bytes: 6,440 bytes of
sampled attachment tracks, 4,096 of texture, 1,688 of mesh arrays, 1,536 of fenced
actor matrices, plus small descriptors/tracking fields. That excludes code,
padding and recorded display-list allocations. `memory-symbols.json` preserves
the symbol sizes from `mips64-elf-nm -S --size-sort`. The matched diagnostic ROMs
grow from 57,720,832 to 57,737,216 bytes, an increase of 16 KiB.

Minor blue and Major gold come from source object color C. The source shield is
two-sided; the candidate renders both sides, tests opaque depth and does not write
depth. Shields are sorted back to front within each camera. Strength modulates
opacity. A short white flash follows shield loss; an exposed-body hit cannot
start or restart that flash. Per-actor generation tracking prevents a recycled
actor from inheriting another actor's flash.

The source material uses seven animated/additive stages. This is an explicit
one-pass N64 approximation, not full shader parity: one static noise texture with
rank tint, strength-dependent alpha and a white hit flash. Complete scrolling
noise, additive glow and depletion particles are not reproduced. Native checks
cover opaque foreground occlusion and transmitted rear-actor detail; they do not
prove every possible overlap with other translucent effects.

## Mechanics and visual validation

The source collision record specifies 100 base shield vitality, a **15-second
stun/recharge delay and zero recharge duration**. Restoration therefore happens
immediately after that delay. Difficulty scaling and the existing physical shield
continue to govern actual hits. Rendering follows the current shield value and
stops when it is zero or the actor is dead.

- The host suite uses real animated hit meshes. For each rank, its frontal ray
  grid finds 184 shield-intercepted rays and 157 exposed-body rays. Shield hits
  reduce shield only; a selected exposed-body shot reduces health without
  reducing shield. The exact rays are recorded in `benchmarks/jackal-shields/host.log`.
  An independent ray test of the restored visible mesh at the same idle phase
  confirms that the shield sample hits its triangles and the body-gap sample
  crosses no visible energy triangles.
- Plasma overcharge depletes the shield, which remains absent after 447 ticks
  (14.9 seconds) and is full after 453 ticks (15.1 seconds). Corpses do not recharge.
  These are production ticks, not a separate test implementation of the timer.
- The flash helper is exercised with the actual shield/body damage results:
  shield loss starts the flash, and a later body-only hit does not restart it.
- The complete ASan/UBSan Firefight roster suite passes: full finite sets and all
  fourteen formation routes at 1–4 players, lifecycle, source weapon/rank rules,
  exactly-once scoring and return to PvP.
- Geometry audit: 76 nondegenerate faces, zero nonmanifold edges, unchanged UVs/
  weights, and all 230 sampled source attachment poses agree within 0.000703 world
  units after quantization. Intermediate rotations use normalized quaternion
  interpolation, as the existing rigid weapon attachments do.

The native shield photo route contains **72 matched pages × four cameras**:
two ranks, three body LODs, and twelve states. States include full/quarter/hit,
depleted, production-ticked recharge, running, firing, and opaque actors in front
and behind. The before/after fixtures have matching coordinates, view targets,
yaw, crouch, pose phase and shield state. Actors are suspended for inspection;
all tiers are deliberately shown close up. Frames are native framebuffer
readbacks, not generated images.

All 24 inactive-shield pages are pixel-identical before/after. The recharged
surface matches full strength outside the changing caption. At every rank and
LOD, opaque foreground actor pixels correctly hide the shield, while rear-actor
detail remains visible through it. The eroded overlap test has 303–356 opaque
foreground samples per rank/LOD and 9/10/3 transmitted rear-actor samples for
near/middle/coarse, per rank. The three-pixel coarse result is a small sample, not a broad coverage
claim. The original 46-page roster route is also repeated with a fresh shield-off
control, which reproduces all 46 old pages exactly. With shields enabled, the
35 opaque non-Jackal pages remain pixel-identical. The three Jackal pages gain
their shields. Eight later cloaked-Elite pages use the existing noise alpha
comparison and show different dither pixels after the added shield draws; their
poses and cloak values match. Their full images and difference counts are retained,
but they are **not** counted as exact pixel matches or a statistical opacity test.

## Native measurements

Final matched measurements are recorded in `benchmarks/jackal-shields/results.json`
and their ROM/input/log hashes in `provenance.json`. The appraisal viewer includes
the same table. Both versions are rebuilt from the final source; only the shield
compile flag and new bank asset differ.

Ares v148, NTSC 320×240, 8 MiB, audio enabled, uncapped diagnostic ROMs. Each of
24 cases retains 45 observations, discarding five warm-ups. The primary mean uses
at least one human and enemy alive and no arrival underway; all-human-alive scope
and raw CPU counters are retained separately. These are native N64 ROM emulator
measurements, not fresh cartridge measurements. The playable ROM caps at 30 FPS.

Mean active-combat FPS, **shield off → restored**:

| Players | Original crowded mix | Expanded crowded roster | Ordinary opening |
| --- | ---: | ---: | ---: |
| 1 | 35.25 → 34.95 | 38.35 → 38.10 | 45.81 → 45.56 |
| 2 | 17.52 → 17.39 | 19.00 → 18.61 | 25.96 → 25.88 |
| 3 | 9.76 → 9.20 | 11.17 → 10.87 | 22.00 → 22.08 |
| 4 | 4.90 → 4.55 | 5.54 → 5.52 | 7.77 → 7.36 |

The restored shield has a modest cost in most cases, but is not free: the original
crowded four-player fixture falls 7.1% in this run and the ordinary four-player
opening falls 5.3%. The expanded crowded roster is much closer (0.4%). Different
death/arrival timings change which observations enter the active-combat mean.
Requiring all humans alive gives four-player means of 4.67 → 4.55 in the original
crowded mix and 4.67 → 4.50 in the expanded roster. The full counts/ranges are
retained; these are not statistical confidence bounds.

Four-player live CPU means across **all 40 retained observations**, a different
scope from the active-combat FPS table:

| Measurement, off → restored | Original crowded | Expanded roster | Ordinary opening |
| --- | ---: | ---: | ---: |
| Simulation per rendered frame, ms | 82.59 → 83.53 | 120.74 → 117.24 | 58.71 → 58.38 |
| Preparation per rendered frame, ms | 21.37 → 22.75 | 18.24 → 19.90 | 8.52 → 8.94 |
| Drawing per rendered frame, ms | 43.74 → 52.92 | 43.35 → 48.72 | 33.85 → 35.51 |
| Vertex loads per frame, all cameras | 42,529 → 43,535 | 40,873 → 41,546 | 26,193 → 26,196 |

The live drawing phase rises despite the small geometric addition. These counters
include submission/backpressure and frame-dependent workloads; they do not isolate
the alpha pass's RDP cost. The ordinary opening has almost unchanged submitted
geometry, which is another reason not to attribute every timing difference to
shield triangles. This restoration does not resolve the earlier Firefight CPU
and drawing bottlenecks or bring four-player play near 30 FPS.

Minimum reported free memory, off → restored: original crowded four-player
287,496 → 270,064 bytes; expanded roster 545,288 → 527,856; ordinary opening
286,920 → 269,488. The smallest observed headroom is about 263 KiB. No assertion,
RDPQ error or warning appears in the final captures. The local playable release
ROM is 57,720,832 bytes; it is a different build from the profiled ROM pair above.

The three scenarios repeat the earlier roster appraisal: original crowded mix
(QA 4), expanded crowded roster (QA 7), and ordinary opening (QA 3), each at 1–4P.
Live combat can diverge with frame pacing, so small differences in one pass are
not a precise isolated shield cost. CPU subphases are nested and device work can
overlap; the counters do not establish independent serialized RSP/RDP durations.
Opening captures do not certify every later wave's performance or memory peak.

## Reproduction and artifacts

See `benchmarks/jackal-shields/README.md` for preparation, Blender baking, packing,
host tests, native builds/captures, pixel checks and private archiving.
`collect.py --logs-only` reproduces numerical summaries and checks log hashes.

Local comparison: `build/n64-jackal-shields/comparison.html` in the original research
checkout, with before/after, ×4 difference and blink filters, all three timing
matrices and a playable ROM. Native PNGs are inspected directly; browser policy
prevents automatic local-file navigation, so browser rendering is not claimed.

Public numerical logs, checks, manifests and scripts are under
`benchmarks/jackal-shields/`. Source art, the complete candidate bank, compressed
native readbacks and photo evidence are preserved in the private
`halo64-assets/assets/jackal-shields/` archive. Owned map caches and ROMs are not
included in either repository's appraisal payload.
