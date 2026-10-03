# Xbox asset conversion

All raw game data, intermediate Blender scenes and generated C remain in ignored `build/n64/`. The source disc supplied by the user is required. The generated ROM is not a substitute for that source data.

The base map extraction/reduction instructions are in `README.md`. The expanded multiplayer assets use the same Python 3.11 environment with Reclaimer 2.11.2 and Pillow:

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

`extract_extended.py` takes `--maps` and `--output`. It reads Blood Gulch and the supplied `a30.map` for the Banshee, which is absent from the Xbox Blood Gulch cache. Eight retail multiplayer weapons, both grenades, the Spartan, Warthog, Ghost, Scorpion, health pack, overshield and camouflage come directly from Blood Gulch. Vehicle meshes have approximately 240-triangle close views and 80-triangle distant views. Both grenade meshes have at most 20 triangles. Flamethrower source assets found in that cache are retained in the ignored extraction/reduction intermediates for an optional PC ruleset; they are omitted from default Xbox asset packing.

The first-person meshes combine the original weapon model and original cyborg hands. Their source animation graph names are matched to each mesh's bone names. The weapon graph supplies the combined skeleton, including the weapon's magazine, slide and other movable parts. Geometry is reduced to approximately 120 weapon triangles plus 100 hand triangles per weapon. Idle, firing, reload/overheat and melee clips are baked from the source animations. Default first-person packing emits only the eight Xbox multiplayer weapon rigs. The unused flamethrower table slot aliases the AR model and all four matching clips, preserving stable IDs and safe fallback behavior without retaining another mesh or animation bank. `pack_firstperson.py --pc-extras` restores the optional ninth rig, whose source has no firing clip and explicitly uses idle for that clip. Omitting the first-person flamethrower assets saves 96,792 resident bytes.

Third-person clips include idle, running, firing, reload, death, airborne, melee, grenade throw and a Warthog driver pose. The one-shot death uses the original tag’s 46 frames and 46/30-second duration; Reclaimer’s synthetic loop-closing copy of the initial standing pose is omitted, so the final pose remains grounded. Reduction transfers source bone weights to the reduced vertices before offline skinning. The runtime interpolates the resulting compact position frames. Original overlay clips apply only their flagged transform channels in the original engine's multiplication order. These are reduced samples of the original animation, not a complete animation-graph implementation.

The Spartan has 170-triangle and 60-triangle meshes with the same clip samples and timing. Warthog and Scorpion high-detail meshes are partitioned using the original skinning palettes. Four tire hubs, gun mounts, turrets and barrels retain their original bone pivots. The generated part ranges share the whole vehicle's vertex buffer. An odd triangle group receives one degenerate triangle so every part starts on an even vertex and ordinary whole-model drawing still works. Tire spin and turret angles are supplied by the runtime simulation rather than a complete retail vehicle animation graph.

The Spartan's original `right hand` marker is evaluated at each sampled animation frame. Its player-local position and orientation drive third-person weapon attachment. Positions use Halo units; quaternions use Hamilton XYZW in the converted Y-up basis and are compatible with Tiny3D's quaternion transform constructor.

Xbox rigid vertices with an invalid first palette slot and a valid second slot are normalized before passing through Reclaimer; otherwise its JMS constructor discards the valid bone. Animated first-person positions are quantized at 256 units per Halo unit, with a render matrix scale of `BG_SCALE / BG_FP_SCALE`. Terrain and third-person positions use 32 units per Halo unit.

Audio is decoded from original Xbox ADPCM to signed 8-bit mono PCM at 11,025 Hz. The default bank preserves 39 stable slots, with 38 populated events backed by 35 unique clips: shots, reloads, explosions, engine loops, player/UI effects, announcer lines and the map's outdoor ambience. The Banshee engine and fuel-rod bomb shot come from `a30.map`; the Warthog gun uses the original chaingun firing sound. Scorpion primary fire uses the same explosion sound as its original firing effect, while Ghost and Banshee primary fire use the original plasma-rifle sound. Those three source-identical events share existing PCM buffers after extraction verifies byte equality. The unused flamethrower sound slot contains no samples in the Xbox bank; `--pc-extras` restores it as the 36th unique clip. One source permutation per sound is retained. Ordinary one-shot tails are limited to four seconds and engine/flamethrower/ambient loop samples to two seconds. Warthog gun and Banshee bomb tails are limited to 0.6 and one second respectively; the runtime supplies mixing and spatial attenuation.

HUD sprites use original bitmap sequences and crop bounds. Multiplayer shield, health and radar assets follow `ui\\hud\\cyborg_mp`. Original white intensity is tinted to the HUD's blue/green palette, then packed to RGBA16 with one-bit alpha. This reduces transparency precision. `hud-layout.json` preserves the original tag anchors, offsets, scale, color and sequence settings for review. Vehicle reticles use the original Warthog, Ghost, Scorpion and Banshee bitmap sequences. Pistol and sniper scopes use original split-screen masks (tags 503 and 1207) reduced to 64×64 I8, half-size pieces from the five sniper tick bitmaps (1204), and original zoom labels (501). These add 14,304 bytes. The runtime darkens through the original mask alpha; Xbox scope blur and night vision are not reproduced.

For a HUD-only refresh, the following commands re-extract the original artwork and metadata, then regenerate only HUD arrays without rebaking or repacking models/audio:

```sh
build/n64-python/bin/python port/n64/extract_extended.py --hud-only
build/n64-python/bin/python port/n64/pack_extended.py --hud-only
```

Default Xbox packing omits flamethrower world, first-person and audio arrays, recovering 123,610 resident bytes. The world and first-person table slots alias existing AR assets, while the audio slot is empty; enum ordering remains stable. Extraction/reduction intermediates retain the original PC-extra assets. To include their arrays for a future optional ruleset, regenerate both banks explicitly:

```sh
build/n64-python/bin/python port/n64/pack_extended.py --pc-extras
build/n64-python/bin/python port/n64/pack_firstperson.py --pc-extras
```

These switches add assets only; they do not enable a different gameplay ruleset.

The commands above regenerate every extended output directly from the extracted disc caches: gameplay and projectile metadata, both Spartan LODs and their poses, right-hand attachments, vehicle part ranges and pivots, weapon/vehicle HUD sprites, and audio. No one-off JSON edits or external Blender scene state are required.

Generated APIs live in `asset_models.h`, `asset_firstperson.h` and `asset_hud.h`. Reports under `build/n64/generated/` contain triangle counts and byte budgets. The extracted tags supply geometry, motion and presentation data; game rules and vehicle physics remain separate runtime code.
