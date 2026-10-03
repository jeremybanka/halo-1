# Xbox asset conversion

All raw game data, intermediate Blender scenes and generated C remain in ignored `build/n64/`. The source disc supplied by the user is required. The generated ROM is not a substitute for that source data.

The base map extraction/reduction instructions are in `README.md`. The expanded multiplayer assets use the same Python 3.11 environment with Reclaimer 2.11.2, Pillow and NumPy:

```sh
build/n64-python/bin/python port/n64/extract_extended.py
/Applications/Blender.app/Contents/MacOS/Blender --background --python port/n64/reduce_extended.py -- build/n64/assets/extended-raw.json build/n64/assets/extended-reduced.json
build/n64-python/bin/python port/n64/pack_extended.py
build/n64-python/bin/python port/n64/extract_firstperson.py
/Applications/Blender.app/Contents/MacOS/Blender --background --python port/n64/reduce_firstperson.py -- build/n64/assets/firstperson-raw.json build/n64/assets/firstperson-reduced.json
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

Run that code in the connected Blender instance after both extraction commands, then run both packing commands and validation.

`extract_extended.py` takes `--maps` and `--output`. It reads Blood Gulch and the supplied `a30.map` for the Banshee, which is absent from the Xbox Blood Gulch cache. Eight retail multiplayer weapons, both grenades, the Spartan, Warthog, Ghost, Scorpion, health pack, overshield and camouflage come directly from Blood Gulch. Nearby models use the normal `__base` superhigh source permutation. Distant world models start from the original authored low-detail meshes. The previous pipeline accidentally started several nearby models from already-reduced Xbox geometry; the source Spartan, for example, now has 2,016 rather than 310 triangles. Final packed vehicles have 554–808 nearby and 235–271 distant triangles. Grenades have 62 frag and 64 plasma triangles. The Banshee is baked into the original `stand closing` terminal canopy pose before both LODs are reduced; the raw model bind pose has its canopy open. This is a static flight pose, not runtime opening/closing animation. Flamethrower source assets found in that cache are retained in the ignored extraction/reduction intermediates for an optional PC ruleset; they are omitted from default Xbox asset packing.

The first-person meshes combine the original weapon model and original cyborg hands. Their source animation graph names are matched to each mesh's bone names. The weapon graph supplies the combined skeleton, including the weapon's magazine, slide and other movable parts. Guns use 256–376 triangles plus 211 hand triangles, with a maximum of 1,761 real vertices. All 16 first-person Needler crystals are retained. Idle, firing, reload/overheat and melee clips are baked from the source animations. Default first-person packing emits only the eight Xbox multiplayer weapon rigs. The unused flamethrower table slot aliases the AR model and all four matching clips, preserving stable IDs and safe fallback behavior without retaining another mesh or animation bank. `pack_firstperson.py --pc-extras` restores the optional ninth rig, whose source has no firing clip and explicitly uses idle for that clip.

Third-person clips include idle, running, firing, reload, death, airborne, melee, grenade throw and original Warthog driver, rifle-passenger and fixed-gunner poses. The passenger and gunner each retain four pose samples at both Spartan LODs, with matching animated hand attachments. The one-shot death uses the original tag’s 46 frames and 46/30-second duration; Reclaimer’s synthetic loop-closing copy of the initial standing pose is omitted, so the final pose remains grounded. Reduction transfers source bone weights to the reduced vertices before offline skinning. The runtime interpolates the resulting compact position frames. Original overlay clips apply only their flagged transform channels in the original engine's multiplication order. These are reduced samples of the original animation, not a complete animation-graph implementation.

The Spartan has 460-triangle and 151-triangle meshes with the same clip samples and timing. Its armor is reduced as a joined shell, avoiding cracks caused by separately collapsing neighboring bone partitions. The nearby armor shell has zero open or nonmanifold edges. Shared `geometry_reduce.py` protects materials, connected features and moving parts, interpolates skin weights during collapse, and constrains distorted vertices back to source surfaces. Hands, scopes, barrels, crystals and tires receive explicit feature budgets. Warthog and Scorpion high-detail meshes are partitioned using the original skinning palettes. Four tire hubs, gun mounts, turrets and barrels retain their original bone pivots. The generated part ranges share the whole vehicle's vertex buffer. An odd triangle group receives one degenerate triangle so every part starts on an even vertex and ordinary whole-model drawing still works. Tire spin and turret angles are supplied by the runtime simulation rather than a complete retail vehicle animation graph.

The Spartan's original `right hand` marker is evaluated at each sampled animation frame. Its player-local position and orientation drive third-person weapon attachment. Positions use Halo units; quaternions use Hamilton XYZW in the converted Y-up basis and are compatible with Tiny3D's quaternion transform constructor.

Xbox rigid vertices with an invalid first palette slot and a valid second slot are normalized before passing through Reclaimer; otherwise its JMS constructor discards the valid bone. Positions use 256 units per Halo unit for first-person models, 128 for the Spartan, and 1,024 for static world objects. The latter prevents small dropped weapons from collapsing under the terrain's coarser 32-unit precision. Instance transforms and vehicle pivots use the matching scales; terrain remains at 32.

`model_colors.py` bakes full-resolution source diffuse textures into per-corner colors, sampling inward from UV seams. UVs use image-row coordinates consistently. Original Xbox multipurpose blue-channel color-change masks preserve the Spartan's dark undersuit and visor while tinting armor for each player; first-person hands use the same masks. Glass and meter materials have explicit flat-color approximations. Fine markings, glossy reflections, transparency and emissive effects are not reproduced by this vertex-color representation.

`pack_animation.py` shares identical complete motion tracks across triangle corners and stores each clip relative to an integer origin using unsigned-byte offsets. Packing verifies every decoded frame and corner equals its quantized source; out-of-range offsets fail the build. Clip samples, durations and interpolation are unchanged. The world and first-person animation banks occupy 139,419 and 344,838 bytes instead of 934,830 and 1,629,144 uncompressed bytes. Two RSP-fenced geometry slots and three independent display buffers keep the larger models within the base 4 MiB configuration.

Audio is decoded from original Xbox ADPCM to signed 8-bit mono PCM at 11,025 Hz. The default bank preserves 39 stable slots, with 38 populated events backed by 35 unique clips: shots, reloads, explosions, engine loops, player/UI effects, announcer lines and the map's outdoor ambience. The Banshee engine and fuel-rod bomb shot come from `a30.map`; the Warthog gun uses the original chaingun firing sound. Scorpion primary fire uses the same explosion sound as its original firing effect, while Ghost and Banshee primary fire use the original plasma-rifle sound. Those three source-identical events share existing PCM buffers after extraction verifies byte equality. The unused flamethrower sound slot contains no samples in the Xbox bank; `--pc-extras` restores it as the 36th unique clip. One source permutation per sound is retained. Ordinary one-shot tails are limited to four seconds and engine/flamethrower/ambient loop samples to two seconds. Warthog gun and Banshee bomb tails are limited to 0.6 and one second respectively; the runtime supplies mixing and spatial attenuation.

HUD sprites use original bitmap sequences and crop bounds. Multiplayer shield, health and radar assets follow `ui\\hud\\cyborg_mp`. Original white intensity is tinted to the HUD's blue/green palette, then packed to RGBA16 with one-bit alpha. This reduces transparency precision. `hud-layout.json` preserves the original tag anchors, offsets, scale, color and sequence settings for review. Vehicle reticles use the original Warthog, Ghost, Scorpion and Banshee bitmap sequences. Pistol and sniper scopes use original split-screen masks (tags 503 and 1207) reduced to 64×64 I8, half-size pieces from the five sniper tick bitmaps (1204), and original zoom labels (501). These add 14,304 bytes. The runtime darkens through the original mask alpha; Xbox scope blur and night vision are not reproduced.

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

## Model comparison audit

`audit_models.py` generates `build/n64/model-audit/index.html`, 46 comparison sheets and machine-readable `metrics.json`. It compares original highest-detail meshes with full diffuse textures, frozen prior packed C geometry/colors, and the current packed preview geometry/colors. Eight matching views include front, rear, sides, three-quarter, top and low angles. Additional 160×120 fit-to-model renders and 48/24-pixel extent probes expose small-screen losses. Four Spartan colors and both character/vehicle LODs are included, together with world weapons, first-person rigs, gun-only views, hands, grenades and pickups.

Keep the pre-change raw/reduced JSON and generated model C files in `build/n64/model-audit/before/`; keep highest-detail raw references in `build/n64/model-audit/reference/`. The audit deliberately requires these preserved inputs rather than silently treating a regenerated model as the old baseline. Run after both packing commands, while the generated banks are stable:

```sh
build/n64-python/bin/python port/n64/audit_models.py
```

The report records SHA-256 provenance for source, prior, revised, packed and texture inputs. Its silhouette overlap and color-error metrics complement visual review; they do not measure human recognition. Reference renders use neutral diagnostic lighting and simplified glass/meter materials, not the Xbox renderer. They intentionally disable backface culling to expose holes and therefore do not replace emulator checks. At 24 pixels, dark team armor and thin gun features remain difficult to read; small markings, the health-pack cross and fine tread detail are still lost. All generated comparison images and original game data remain local and ignored by Git.
