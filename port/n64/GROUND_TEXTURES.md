# Blood Gulch ground color and resolution

The ground material is a 64×64 CI4 texture with a 16-entry RGBA16 palette. It
uses the same 2,048 pixel bytes as the previous 32×32 RGBA16 texture, plus a
32-byte palette and 34 bytes of per-material format/size descriptors before
alignment. It retains 3,023 environment triangles, 225 batches, 79,648 vertex
bytes and 34,816 total texture pixel bytes. Collision is byte-identical.

## Source color bake

`extract_ground.py` reads the owned Xbox Blood Gulch shader and four original
bitmaps. Base alpha selects sand; inverse alpha selects grass. The source uses
100× sand detail, 60× grass detail and 12× micro detail. The exporter filters
these detail maps to the footprint of its 512×512 bake, samples with bilinear
wrap, and reproduces the original blend and two double-multiply stages.
It then downsamples to 32, 64 and 128 pixels for comparison.

`pack_assets.py` defaults to the 64-pixel baked result. Its nondithered 16-color
palette is quantized to actual RGBA16 values. Only the ground's UV scale changes
from 32 to 64 texels per repeat; whole-period batch recentering remains exact.
The RDP palette is enabled for the ground material and disabled before ordinary
RGBA textures or models. The palette is uploaded once per visible ground
material per camera. There is no new terrain pass or per-frame heap allocation.

This reproduces the diffuse color contribution, not the complete Xbox render.
Original lightmaps, camera-dependent detail mips and output gamma remain absent;
the existing directional vertex shading is unchanged. Sixteen colors trade
subtle tonal variation for sharper grass/path coverage. This is intentionally
not a global green tint.

## Resolution experiments

- Original 32×32 base only: baseline native Ares views.
- Baked 32×32 RGBA16: separates color changes from resolution.
- Baked 64×64 CI4: selected native Ares experiment.
- Baked 128×128 CI4: offline comparison only. Its 8,192 pixel bytes do not fit
  the 2 KiB available for pixel data in N64 palette mode. It would require
  texture tiling with additional geometry splitting or texture changes; that
  renderer and its performance cost have not been implemented or tested.

The separately named `--ground-qa` ROM alternates four player-height and four
elevated frozen cameras. It is for matching images and RDP validation, not FPS.

```sh
build/n64-python/bin/python port/n64/extract_ground.py
build/n64-python/bin/python port/n64/pack_assets.py build/n64/assets/bloodgulch-reduced.json
build/n64-python/bin/python port/n64/test_ground_texture.py
build/n64-python/bin/python port/n64/test_pack_terrain.py
build/n64-python/bin/python port/n64/build.py --ground-qa --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --frontend-qa 4 --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

For the diagnostic alternatives, pass `--ground-size 32 --ground-style base`
or `--ground-size 32 --ground-style blended` to `pack_assets.py`. Repack with
its defaults to restore the selected asset bank. Build checks reject changed
source/bake/packing inputs or a mismatched generated terrain bank. All extracted
images and generated geometry remain under ignored `build/` paths.

Local native screenshots, all three visual ROMs, the offline 128-pixel reference,
source provenance, tests and timing live in `build/n64/ground-experiment/`.

The final quiet Ares 148 / NTSC / 4 MiB, five-buffer, 75-second replay measures
28.5 FPS overall, 29.0 in combat and 28.0 around vehicles, versus
28.6 / 29.1 / 28.2 before. Free heap remains 46 KiB at this precision.
Combat P95 is 33.4 ms; vehicle P95 is 66.8 ms. The first palette-state version
measured 28.2 / 29.0 / 27.5; avoiding redundant state commands reduced its cost.
These are emulator samples, not console certification; sustained 30 FPS remains
unmet. Native visual fixtures report zero RDP errors and warnings.
