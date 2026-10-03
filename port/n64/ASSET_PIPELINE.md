# Xbox asset conversion

All raw game data, intermediate Blender scenes and generated C remain in ignored `build/n64/`. The source disc supplied by the user is required. The generated ROM is not a substitute for that source data.

The base map extraction/reduction instructions are in `README.md`. The expanded multiplayer assets use the same Python 3.11 environment with Reclaimer 2.11.2, Pillow and NumPy:

```sh
build/n64-python/bin/python port/n64/extract_extended.py --include-source-lods
/Applications/Blender.app/Contents/MacOS/Blender --background --python port/n64/reduce_extended.py -- build/n64/assets/extended-raw.json build/n64/assets/extended-reduced.json --performance-profile
build/n64-python/bin/python port/n64/pack_extended.py
build/n64-python/bin/python port/n64/extract_firstperson.py
/Applications/Blender.app/Contents/MacOS/Blender --background --python port/n64/reduce_firstperson.py -- build/n64/assets/firstperson-raw.json build/n64/assets/firstperson-reduced.json --performance-profile
build/n64-python/bin/python port/n64/pack_firstperson.py
build/n64-python/bin/python port/n64/validate_assets.py
```

The Blender scripts also run through MCP using `reduce_extended(source, output)` and `reduce_firstperson(source, output)`. They create separate scenes and save separate `.blend` libraries; they do not overwrite the user's existing scene or project. The full extraction and reduction were rerun from the disc caches for verification. On this Mac, a sandboxed background Blender process can fail during Metal initialization before Python starts. The working MCP equivalent loads the same maintained scripts, without depending on existing scene objects:

```python
from pathlib import Path
root = Path('/Users/jem/dojo/halo-1')  # Set to your checkout.
for name in ('extended', 'firstperson'):
    script = root / f'port/n64/reduce_{name}.py'
    namespace = {'__name__': f'n64_{name}'}
    exec(compile(script.read_text(), str(script), 'exec'), namespace)
    namespace[f'reduce_{name}'](
        str(root / f'build/n64/assets/{name}-raw.json'),
        str(root / f'build/n64/assets/{name}-reduced.json'))
```

That MCP example reproduces the earlier quality preset. For the performance preset, use the command-line invocations above, which also regenerate the extended quality reference used by the tactical recipe. Run the packing commands and validation after reduction.

`extract_extended.py` takes `--maps` and `--output`. It reads Blood Gulch and the supplied `a30.map` for the Banshee, which is absent from the Xbox Blood Gulch cache. Eight retail multiplayer weapons, both grenades, the Spartan, Warthog, Ghost, Scorpion, health pack, overshield and camouflage come directly from Blood Gulch. Highest references always use the normal `__base` superhigh source permutation. The performance recipe explicitly selects authored intermediate LODs or refines the approved higher-detail reduction for each nearby model. Distant world models start from original authored geometry. The previous pipeline accidentally started several nearby models from already-reduced Xbox geometry; the source Spartan, for example, now has 2,016 rather than 310 triangles. The performance bank has 242–366 nearby and 134–198 distant vehicle triangles, including rigid-part padding. Grenades have 62 frag and 48 plasma triangles. The Banshee is baked into the original `stand closing` terminal canopy pose before both LODs are reduced; the raw model bind pose has its canopy open. This is a static flight pose, not runtime opening/closing animation. Flamethrower source assets found in that cache are retained in the ignored extraction/reduction intermediates for an optional PC ruleset; they are omitted from default Xbox asset packing.

The first-person meshes combine the original weapon model and original cyborg hands. Their source animation graph names are matched to each mesh's bone names. The weapon graph supplies the combined skeleton, including the weapon's magazine, slide and other movable parts. The performance guns use 193–328 triangles plus 191 hand triangles; indexed packing then removes repeated vertex transforms without removing faces. All 16 first-person Needler crystals are retained. Idle, firing, reload/overheat and melee clips are baked from the source animations. Default first-person packing emits only the eight Xbox multiplayer weapon rigs. The unused flamethrower table slot aliases the AR model and all four matching clips, preserving stable IDs and safe fallback behavior without retaining another mesh or animation bank. `pack_firstperson.py --pc-extras` restores the optional ninth rig, whose source has no firing clip and explicitly uses idle for that clip.

Third-person clips include idle, running, firing, reload, death, airborne, melee, grenade throw and original Warthog driver, rifle-passenger and fixed-gunner poses. The passenger and gunner each retain four pose samples at both Spartan LODs, with matching animated hand attachments. The one-shot death uses the original tag’s 46 frames and 46/30-second duration; Reclaimer’s synthetic loop-closing copy of the initial standing pose is omitted, so the final pose remains grounded. Reduction transfers source bone weights to the reduced vertices before offline skinning. The runtime interpolates the resulting compact position frames. Original overlay clips apply only their flagged transform channels in the original engine's multiplication order. These are reduced samples of the original animation, not a complete animation-graph implementation.

The performance Spartan has 310-triangle and 127-triangle meshes with the same clip samples and timing. Its nearby mesh preserves an original authored Xbox LOD, including the source armor part boundaries. Eleven motion clips are checked in multiple poses for visible seams. The earlier quality preset retains its 460/151-triangle meshes. Shared `geometry_reduce.py` protects materials, connected features and moving parts, interpolates skin weights during collapse, and constrains distorted vertices back to source surfaces. Hands, scopes, barrels, crystals and tires receive explicit feature budgets. Warthog and Scorpion high-detail meshes are partitioned using the original skinning palettes. Four tire hubs, gun mounts, turrets and barrels retain their original bone pivots. Each part has its own range of indexed batches within the vehicle buffer. Logical triangle ranges retain their original degenerate alignment faces; indexed batches independently pad vertex pairs. Tire spin and turret angles are supplied by the runtime simulation rather than a complete retail vehicle animation graph.

The Spartan's original `right hand` marker is evaluated at each sampled animation frame. Its player-local position and orientation drive third-person weapon attachment. Positions use Halo units; quaternions use Hamilton XYZW in the converted Y-up basis and are compatible with Tiny3D's quaternion transform constructor.

Xbox rigid vertices with an invalid first palette slot and a valid second slot are normalized before passing through Reclaimer; otherwise its JMS constructor discards the valid bone. Positions use 256 units per Halo unit for first-person models, 128 for the Spartan, and 1,024 for static world objects. The latter prevents small dropped weapons from collapsing under the terrain's coarser 32-unit precision. Instance transforms and vehicle pivots use the matching scales; terrain remains at 32.

`model_colors.py` bakes full-resolution source diffuse textures into per-corner colors, sampling inward from UV seams. UVs use image-row coordinates consistently. Original Xbox multipurpose blue-channel color-change masks preserve the Spartan's dark undersuit and visor while tinting armor for each player; first-person hands use the same masks. Glass and meter materials have explicit flat-color approximations. Fine markings, glossy reflections, transparency and emissive effects are not reproduced by this vertex-color representation.

`pack_animation.py` shares identical complete motion tracks across triangle corners and stores each clip relative to an integer origin using unsigned-byte offsets. Packing verifies every decoded frame and corner equals its quantized source; out-of-range offsets fail the build. Clip samples, durations and interpolation are unchanged. Generated reports record compressed and uncompressed animation bytes for the selected preset and indexed vertex layout. Two RSP-fenced geometry slots and three independent display buffers keep the larger models within the base 4 MiB configuration.

Audio is decoded from original Xbox ADPCM to signed 8-bit mono PCM at 11,025 Hz. The default bank preserves 39 stable slots, with 38 populated events backed by 35 unique clips: shots, reloads, explosions, engine loops, player/UI effects, announcer lines and the map's outdoor ambience. The Banshee engine and fuel-rod bomb shot come from `a30.map`; the Warthog gun uses the original chaingun firing sound. Scorpion primary fire uses the same explosion sound as its original firing effect, while Ghost and Banshee primary fire use the original plasma-rifle sound. Those three source-identical events share existing PCM buffers after extraction verifies byte equality. The unused flamethrower sound slot contains no samples in the Xbox bank; `--pc-extras` restores it as the 36th unique clip. One source permutation per sound is retained. Ordinary one-shot tails are limited to four seconds and engine/flamethrower/ambient loop samples to two seconds. Warthog gun and Banshee bomb tails are limited to 0.6 and one second respectively; the runtime supplies mixing and spatial attenuation.

HUD sprites use original bitmap sequences and crop bounds. Stored textures omit transparent padding while retaining one filtering border texel and the original layout dimensions/offsets; no visible texels are removed. Multiplayer shield, health and radar assets follow `ui\\hud\\cyborg_mp`. Original white intensity is tinted to the HUD's blue/green palette, then packed to RGBA16 with one-bit alpha. This reduces transparency precision. `hud-layout.json` preserves the original tag anchors, offsets, scale, color and sequence settings for review. Vehicle reticles use the original Warthog, Ghost, Scorpion and Banshee bitmap sequences. Pistol and sniper scopes use original split-screen masks (tags 503 and 1207) reduced to 64×64 I8, half-size pieces from the five sniper tick bitmaps (1204), and original zoom labels (501). The generated report records their current storage budget. The runtime darkens through the original mask alpha; Xbox scope blur and night vision are not reproduced.

For a HUD-only refresh, the following commands re-extract the original artwork and metadata, then regenerate only HUD arrays without rebaking or repacking models/audio:

```sh
build/n64-python/bin/python port/n64/extract_extended.py --hud-only
build/n64-python/bin/python port/n64/pack_extended.py --hud-only
```

Default Xbox packing omits flamethrower world, first-person and audio arrays. The world and first-person table slots alias existing AR assets, while the audio slot is empty; enum ordering remains stable. Extraction/reduction intermediates retain the original PC-extra assets. To include their arrays for a future optional ruleset, regenerate both banks explicitly:

```sh
build/n64-python/bin/python port/n64/pack_extended.py --pc-extras
build/n64-python/bin/python port/n64/pack_firstperson.py --pc-extras
```

These switches add assets only; they do not enable a different gameplay ruleset.

The commands above regenerate every extended output directly from the extracted disc caches: gameplay and projectile metadata, both Spartan LODs and their poses, right-hand attachments, vehicle part ranges and pivots, weapon/vehicle HUD sprites, and audio. No one-off JSON edits or external Blender scene state are required.

Generated APIs live in `asset_models.h`, `asset_firstperson.h` and `asset_hud.h`. Reports under `build/n64/generated/` contain triangle counts and byte budgets. The extracted tags supply geometry, motion and presentation data; game rules and vehicle physics remain separate runtime code.

## Conservative runtime bounds

`pack_bounds.py`, called by the normal extended pack, derives bounds from the
exact quantized positions. Pickup boxes and origin-centered weapon radii include
both nearby and distant meshes. Each rigid vehicle part has its own local box;
the runtime transforms these boxes with the same current wheel, turret and
barrel matrices used for drawing, then unions them with the distant vehicle
mesh. This covers changing poses without a generic oversized radius or a
finite set of sampled turret angles.

Each Spartan clip has a box containing every quantized frame of both LODs.
Linear vertex interpolation stays within these endpoint intervals. The original
hand-marker position intervals, expanded by the equipped weapon's radius,
contain the weapon under every normalized interpolated hand rotation. Clip
selection occurs once per frame and is shared by visibility and animation,
including throwing, dying, crouching and all three Warthog seats. Body and held
weapon visibility are tested independently. A weapon may remain visible at an
edge after its owner leaves the view, and vice versa.

`render_bounds.h` transforms boxes with center/extents, then rounds minima down
and maxima up to signed render coordinates. It adds one render unit before
rounding to cover final 16.16 matrix coefficient error. Packing and validation
reject geometry whose local coordinate magnitudes would violate that margin;
unrepresentable runtime bounds keep the object visible rather than wrapping.
Vehicle and pickup matrices are constructed once per frame before visibility
checks and reused for drawing. The current Xbox bank adds 1,444 bytes of bounds
metadata; it changes no model positions, faces, colors or animation samples.

Run the maintained bounds checks along with the full asset contract:

```sh
build/n64-python/bin/python port/n64/test_pack_bounds.py
build/n64-python/bin/python port/n64/validate_assets.py
clang -std=c17 -O1 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Iport/n64 port/n64/test_render_bounds.c -lm -o build/n64/test-render-bounds
build/n64/test-render-bounds
```

The C test checks 240,000 transformed corner coordinates against the final
fixed-point matrices, as well as negative-coordinate rounding and overflow.
The asset validator checks every emitted static/part box, both character LODs'
animation endpoints, hand markers and weapon radii against the actual bank.

The ignored `performance-audit/bounds-probe/` study reproduced 1,132 source
replay cameras and estimated approximately 666 fewer model triangles and
1,278 fewer submitted model vertices per four-view frame using current rig
boxes and clip bounds. These are **offline culling estimates**, excluding
terrain and first-person work, not measured frame-time savings. That estimate
conservatively counted nearby held weapons and grouped body/held visibility;
the final runtime tests their visibility independently. Emulator completion
timing must establish the actual performance gain and its worst-frame limits.

## Model comparison audit

The performance presets retain the highest source meshes as references and
choose authored Xbox intermediate geometry or a further reduction of the
approved model per asset. `world_performance.json` is the tracked world recipe;
the first-person allocations live in `reduce_firstperson.py`. Omitting
`--performance-profile` reproduces the earlier quality preset.
The world performance command regenerates its own quality reference, so it
does not depend on an ignored experimental candidate file.

`pack_mesh.py` preserves triangle positions and winding while sharing coincident
vertices within explicit per-model RGB bounds. `MODEL_COLOR_TOLERANCES` is the
shared map used by both packers and the independent C validator: the reviewed
Xbox models use 48/255, except the near/far Ghost at 24/255 and the first-person
rocket at 32/255. The Ghost exceptions retain its narrow red wing markings;
the rocket exception retains its copper-brown housing. Optional PC flamethrower
models remain at 24/255, and an unknown model name fails packing until reviewed.
Each report records the applied map. Every corner supplies its original
material identity. Different materials and different team-mask bytes cannot
share a vertex, even when their positions and RGB match. Terrain remains on
its separate 8/255 packer with exact texture/UV identities.
Static meshes reorder
adjacent faces to reuse more vertices within each batch, while preserving
coplanar overlap precedence and rigid-part boundaries. Animated meshes and
first-person rigs retain their original triangle order. Every color comparison
uses an immutable original corner, so successive merges cannot accumulate drift.
Animated corners may merge only when every quantized position in every
exported clip matches. Each batch has at most 60 vertices and 120 indices,
including alignment padding, within Tiny3D's shared DMEM limit. Packers verify
the expanded triangle geometry, material identity, color bound, masks and motion
identities. `validate_assets.py` separately decodes the emitted C vertex/index
arrays and every first- and third-person animation endpoint. It verifies that
the preview JSON expands to those exact C positions, colors and masks, and
checks conservative bounds against the resulting geometry.

The current world bank stores 4,920 vertices, including 578 distant-pickup
vertices; first-person rigs store 4,264. The preceding bank with the same
geometry and a uniform 24/255 bound used 5,690 and 4,774 respectively. Its
immutable C, previews, reports and hashes remain under the local
`color-weld-large-probe/before-generated/` directory. All 44 packed meshes match
their selected reviewed candidates exactly. The 59-entry comparison covers
eight angles and native 48/24px or distant-pickup 12/8px extents. All paired
silhouette masks are identical. Mean source color-block error across the 46
existing entries is 0.062920, versus 0.060666 for the preceding bank and 0.060617
for the approved quality baseline. Larger bounds soften broad surface shading;
the explicit exceptions address the two observed color-region failures.
Needler needles, rocket bands, lights, optics, armor and glove separation remain
distinct in independent visual review. These are offline checks, not an FPS
measurement; the local replay-frequency estimate is 791 fewer submitted
vertices per four-view frame, about 8.40% of major scene geometry.

Current generated payload sizes are recorded in `extended-report.json` and
`firstperson-report.json`. The world bank uses 78,720 vertex bytes, 31,064
index/batch bytes, 756 team-mask bytes and 89,760 animation bytes. The complete
first-person payload uses 340,382 bytes, including 68,224 vertex bytes and
246,278 animation bytes. Culling metadata remains 1,444 bytes. Audio and HUD
payloads remain 586,557 and 124,794 bytes. These figures exclude C pointer tables,
alignment padding and runtime working buffers; they are not total resident RAM.

The `bounded_near` recipe reduces Warthog/Ghost/Scorpion to
318/242/366 packed triangles, currently using 298/244/426 loaded vertices after
the per-model color packing above. It runs after
the authored-LOD reduction and constrains accumulated vertex displacement to
0.05/0.025/0.08 Halo units. Lights, windshield, gun pedestal and barrel tip,
Ghost illuminated faces, and Scorpion cannon/tread sheets are explicitly
pinned. A surviving triangle that would change its nearest-source rigid
group is pinned and the collapse repeated. No saved candidate file is needed:
the full Blender performance recipe regenerates exactly the same output.
Banshee, distant models, pickups, Spartan poses and first-person geometry remain
unchanged by this bounded-reduction pass. Eight-angle mean
source silhouette IoU remains within 0.03 of the approved quality baseline;
native 48/24px views also retain the defining gaps and colors. The local
`near-vehicle-candidates/` audit preserves the prior RGB24 bank, comparisons,
clean-rebuild evidence and measured geometry counts. Its replay-weighted
submission savings are an offline estimate, not an emulator timing result.

The Scorpion rig now follows the source `stand fixed aim-still` channels:
node 7 (`frame turret rotator`) supplies yaw and node 8 (`frame turret`)
supplies pitch. The aiming gun and cannon are children of node 8. The broad
turret therefore pitches with the barrel; the previous partition moved only
children 9/10 and visibly separated the barrel from its housing. The source
rotation flags are 384, with no translation or scale channels. The local
audit retains before/after articulated renders and the original tag evidence.

For a performance comparison, freeze the approved bank and highest references
under `build/n64/performance-audit/before/` and `reference/`, then run:

```sh
build/n64-python/bin/python port/n64/audit_models.py --output build/n64/performance-audit --performance
```

This report labels the columns original / approved quality / optimized. It
keeps the earlier quality audit intact and reports triangle savings together
with silhouette loss, rather than measuring improvement over an obsolete
low-detail baseline.

`audit_models.py` generates `build/n64/model-audit/index.html`, 46 comparison sheets and machine-readable `metrics.json`. It compares original highest-detail meshes with full diffuse textures, frozen prior packed C geometry/colors, and the current packed preview geometry/colors. Eight matching views include front, rear, sides, three-quarter, top and low angles. Additional 160×120 fit-to-model renders and 48/24-pixel extent probes expose small-screen losses. Four Spartan colors and both character/vehicle LODs are included, together with world weapons, first-person rigs, gun-only views, hands, grenades and pickups.

Keep the pre-change raw/reduced JSON and generated model C files in `build/n64/model-audit/before/`; keep highest-detail raw references in `build/n64/model-audit/reference/`. The audit deliberately requires these preserved inputs rather than silently treating a regenerated model as the old baseline. Run after both packing commands, while the generated banks are stable:

```sh
build/n64-python/bin/python port/n64/audit_models.py
```

The report records SHA-256 provenance for source, prior, revised, packed and texture inputs. Its silhouette overlap and color-error metrics complement visual review; they do not measure human recognition. Reference renders use neutral diagnostic lighting and simplified glass/meter materials, not the Xbox renderer. They intentionally disable backface culling to expose holes and therefore do not replace emulator checks. At 24 pixels, dark team armor and thin gun features remain difficult to read; small markings, the health-pack cross and fine tread detail are still lost. All generated comparison images and original game data remain local and ignored by Git.

The performance report also includes 13 new distant pickup entries, for 59
displayed entries in total. Their 12/8-pixel strips compare the new distant mesh
with the approved nearby mesh; they have no prior distant baseline and are
excluded from the 46-entry silhouette-loss aggregate.

Saved `runtime-*-results.json` files in the report directory supply a separate
benchmark history, including all/combat/vehicle phases, mean/p95/worst frame
intervals, submitted-vertex averages/peaks, screenshot links and original ROM
hashes. Top-level phase timings are explicitly labeled CPU frame acquisition.
Optional `gpu_completed` phase dictionaries use the same fields and are shown
as RDP completion / `display_show` callback cadence; this is still distinct
from actual VI scanout. Missing completion measurements remain marked as
missing. Explicit GPU-fence diagnostics appear separately because their
serialized submission is not comparable to normal runs. Acquisition averages
above 30 FPS do not establish sustained 30 FPS, especially with p95 intervals
above 33.33 ms. To refresh this evidence without rerendering model images:

```sh
build/n64-python/bin/python port/n64/audit_models.py --performance --html-only \
  --output build/n64/performance-audit
```
