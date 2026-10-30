# Small-screen Covenant LOD appraisal — 28 October 2026

This prototype follows the [drawing census](FIREFIGHT_DRAWING.md). It adds a
third, deliberately angular Covenant representation and applies the existing
projected-size weapon LOD to NPC-held guns. It is opt-in with `--pve-crunch`
and the private three-tier visual bank. The approved bank remains unchanged.

## Art and selection

| Actor | Existing far loads | Crunch loads | Load reduction | Existing far triangles | Crunch triangles |
|---|---:|---:|---:|---:|---:|
| Grunt | 784 | 104 | 86.7% | 342 | 84 |
| Elite | 776 | 254 | 67.3% | 368 | 176 |
| Jackal | 920 | 238 | 74.1% | 449 | 196 |
| Hunter | 1,464 | 304 | 79.2% | 1,138 | 260 |

Blender collapse reduction protects silhouette supports and characteristic
head/hand/foot/spine vertices, transfers normalized bone weights and retains
source material regions. Four representative colors per material replace fine
vertex-color gradients. Existing near/far models and the Spirit remain exact.
The Grunt tank, Elite stance, Jackal proportions and Hunter shield/spines remain
recognizable. The weapons are independently attached using unchanged source
hand motion.

The first Elite/Jackal meshes were too thin. Six-angle animated silhouette
comparisons caught the loss, and the final candidate restores limb volume:
Elite mean silhouette intersection-over-union increased from 64.0% to 88.6%;
Jackal from 70.7% to 83.5%. Final 192-pixel diagnostic means are Grunt 82.2%,
Elite 88.6%, Jackal 83.5%, Hunter 80.9%. These are geometric mask overlaps, not
perceptual quality scores or promises of pixel identity. The 28/16-pixel audits
and enlarged native views are included for appraisal. Eight poses per species
cover idle, two running phases, fire, melee, death, flee and evade.

Each camera independently selects the tier from the full, unclipped projected
box. Bounds enclose all packed samples of the current clip across all tiers;
interpolated poses remain inside those bounds. Enter below 28 pixels and retain
it until the box reaches 34 pixels, with a half-pixel projection margin. Bounds
are transformed once per actor, then projected per camera. Near-plane crossings,
invalid bounds, existing near-LOD selections and zoom retain the detailed mesh.
Hysteresis is keyed by actor generation/species and cleared on scene release.
It suppresses threshold oscillation; it does not blend different topologies.

This works in all 1–4 player layouts using actual viewport dimensions. It does
not use the visible remainder of a clipped/occluded body to justify a coarse mesh.
All original animation samples, durations and interpolation remain; there is no
animation throttling. Pose sharing and the fenced two-slot buffers support all
three tiers. Source hit meshes, weak points, shields, movement, AI, enemy counts
and encounter rules are untouched.

## Native results

Active combat mean FPS after warm-up, with living players and landed enemies:

| Players | Ordinary: before → crunchy | Crowded: before → crunchy |
|---|---:|---:|
| 1 | 44.74 → **53.38** | 31.40 → **40.75** |
| 2 | 24.57 → **29.82** | 16.43 → **20.65** |
| 3 | 27.04 → **27.45** | 8.50 → **10.95** |
| 4 | 6.88 → **9.25** | 4.43 → **5.52** |

The all-four-humans-alive subset improves **6.95 → 8.86 FPS** in the ordinary
encounter and **4.16 → 5.55 FPS** crowded. This is a real gain in both living-party
subsets, but four-player remains far from 30 FPS. Two-player ordinary averages
29.82 FPS with a 21 FPS sampled minimum; that is not locked 30. The small change
in the three-player opening is not a meaningful established improvement.

Four-player mean submitted loads across the full post-warmup sampled window
fall **47,402 → 25,765** ordinary and **61,686 → 33,023** crowded. Those averages
include later deaths and are separate from the active-combat FPS filter.
NPC preparation falls 7.54 → 5.72 ms ordinary and 14.42 → 12.81 ms crowded.
Crowded preparation does not shrink in proportion to mesh size: per-camera
visibility/LOD selection grows 0.60 → 4.26 ms, and mixed camera distances can
require two representations of an actor in the same frame.

The same crowded sample has 18.94 → 17.33 ms whole-frame preparation and
55.28 → 40.18 ms drawing/submission. These are overlapping pipeline counters,
with possible queue backpressure, not isolated chip occupancies. Simulation
remains roughly **13.5–13.7 ms per actual 30 Hz tick**. A slow rendered frame
can contain several simulation catch-up ticks; the observed 80.92 ms candidate
simulation per sampled rendered frame is not an 80.92 ms single AI tick.

Final matrix, fixed-camera measurements and exact provenance are recorded in
[`benchmarks/covenant-crunch`](benchmarks/covenant-crunch/README.md).

The matched crowded tick-60 camera state falls **60,138 → 24,770 loads**
(**58.8% fewer**), within the previous 22,000–26,000-load proposal. Body loads
fall 44,608 → 11,160 and held guns 4,752 → 2,832. Forty-seven of 48 actor/camera
instances use the new tier; one Hunter retains its existing far mesh because
its full projected bounds exceed the threshold. Per-camera totals become
5,580 / 6,206 / 6,750 / 6,234, with body contributions 2,500 / 2,500 / 3,660 /
2,500. Tick 1 selects all 48 coarse bodies and totals 23,956 instead of 60,700.

No previously contributing actor becomes a zero-pixel instance in any of the
four matched combat states. At crowded tick 60, 47/48 actor/camera instances
contribute to the image in both versions. All ten census captures keep their
baseline frames bit-stable through the omission sequence. The coarse art does
change silhouettes and shading; this is visibility preservation, not pixel
identity of the simplified meshes.

A fixed-state serialized category control reduces the Covenant span from
**87.43 to 32.39 ms** across four cameras: CPU queuing 0.76 → 1.03 ms and remaining
RSP drain 86.67 → 31.36 ms. World (18.90 ms), first-person rendering (16.66 ms),
other players (9.88 ms) and effects (7.74 ms) remain significant in that control.
These serialized category spans are diagnostics, not additive production frame
timing or independent GPU utilization. The separate live serialized pair reduces
mean outstanding RSP wait 87.05 → 49.93 ms, with RDP tails 0.035 → 0.044 ms.

The next savings should come from cheaper conservative LOD selection and the
remaining graphics/submission work, while preserving the stronger final
silhouettes. This prototype reaches the proposed geometry budget, not the
four-player 30 FPS target. Further blind limb reduction is not justified by
the visual audit: restoring the Elite/Jackal outlines was the right tradeoff.

The paired native programs use the same three-tier bank, same runtime sources,
same corrected Blood Gulch render override and same diagnostics. The baseline
switch selects only the old body/gun LODs. Thus the change measures selection
and use of the new art rather than an unrelated bank or preparation revision.

Ares v148, NTSC 320×240, 8 MiB, audio on. Live profiling is uncapped; the
controller-playable build retains the release configuration. These are fresh
native-program emulator measurements, not new cartridge tests. Single captures
per case do not establish small differences as statistically significant.

## Memory

Against the preceding two-tier preparation build, the diagnostic ELF adds
18,736 bytes of initialized data and 688 bytes of BSS, including 192 bytes of
per-camera hysteresis state. The comparison baseline also contains the full
three-tier bank; its extra state differs by only those 192 bytes. Vertex buffers
remain lazy and fenced. Different cameras can require multiple tiers for one
actor, so a smaller mesh does not guarantee every heap allocation disappears.
The motion bank adds 322,640 cartridge bytes (2,132,048 → 2,454,688).
The original 192 KiB ROM-pair cache and hit-pose storage remain unchanged.
`memory.json` records linked sections and relevant symbols; live logs record
minimum free memory separately.

## Verification and limits

- 52 native four-angle model frames: **30 unchanged near/Spirit controls match
  every RGBA16 bit**. The 22 coarse-tier frames deliberately differ and expose
  the simplification at close inspection distances.
- Fixed combat photographs retain the same camera, actor, animation and health
  state. Their omission controls distinguish body/gun submissions from actual
  final-image contributions. They are not live FPS measurements.
- 576 CPU silhouette comparisons: four species × eight poses × six angles ×
  three image sizes. Native captures remain the rendering authority; the CPU
  audit does not reproduce RDP AA, transparency or perspective.
- **1,274,007 packed animation coordinates** fit the all-tier clip bounds.
  Timing parity, track ranges, batch limits and normalized skin weights pass.
- **473,856 exact packed poses / 429,558,272 vertices** match the independent
  original interpolation/scatter loops, including all 256 interpolation bins
  and shield states. This proves arithmetic/animation scheduling, not equality
  between geometrically different tiers.
- **70,031 conservative projected-box cases** pass independent double-precision
  checks, plus zoom, near-plane, hysteresis and recycled-actor cases.
- 45 runtime configurations / 180 target translation units compile. The
  existing deferred ownership harness passes 10,000 fenced frames in both
  diagnostic and release modes. The 1–4P Firefight lifecycle host suite passes. The native validated
  four-player start/restart/quit/return-to-multiplayer route also passes, with
  no RDP errors or warnings in the captured checks.

The pre-existing missing Jackal energy-shield render mesh remains unresolved:
its selected original render LODs already omit those source shield faces.
Shield collision still works. This prototype preserves that behavior; it does
not claim to repair all source shader/mesh discrepancies. Native and CPU
silhouette sheets expose remaining aesthetic compromises for appraisal.

## Reproduction

The private bank and authoring/evidence archive are at
`halo64-assets/assets/covenant-crunch/`. See the benchmark README for exact
commands. The runtime flag requires a matching three-tier bank; ordinary
canonical/two-tier builds retain their existing array sizes and behavior.

The authoring chain is `reduce_pve_crunch.py` in Blender, original skeleton
baking via `bake_pve_blender.py`, then `pack_crunch.py` and `pack_pve.py
--model-candidate --visual-only`. The last step produces visual assets only;
canonical simulation/navigation/hit data remain the build inputs. The private
archive includes the authored `.blend`, source geometry, final baked poses,
palettes, packed bank, native photographs and exact build provenance.
