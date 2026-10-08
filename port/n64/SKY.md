# Blood Gulch sky color

The previous world background was a constant RGB (150, 185, 216). It did not
use the Xbox sky asset. This made the visible sky pale even well above the
horizon.

`extract_sky.py` reads the owned Blood Gulch cache's `mp clear afternoon`
model and `sky clear blue` Chicago shader. For 33 elevations, it raycasts the
original dome, interpolates the original UVs, samples the base bitmap with
bilinear filtering, and averages 96 azimuths. This preserves the base layer's
pale horizon and deeper blue-violet upper sky without an arbitrary saturation
or brightness multiplier. The generated 99-byte RGB ramp and provenance report
remain under ignored `build/n64/generated` alongside the other extracted assets.
Builds reject stale extraction inputs.

`sky.h` reconstructs the sky direction from the actual view/projection matrices,
including pitch, zoom and the Xbox aim offset. Camera translation has no effect.
`sky_draw.h` draws a two-column, four-row shaded grid behind the terrain, replacing
the old color clear. This costs 16 RDP triangles per viewport (64 with four
players), uses no texture/TMEM bank, and writes no depth. Its temporary vertex
array is 360 bytes on the stack. Ordered RGB dithering reduces 16-bit color
banding; terrain/HUD rendering restores its normal state immediately afterward.
The triangles are included in the existing render counters.

This is a base-color approximation, not the complete Xbox sky shader: clouds,
stars, planets, the Halo ring, and Xbox display gamma are not reproduced by this
change. The azimuth average and coarse screen grid also simplify the dome.

Regenerate and verify:

```sh
build/n64-python/bin/python port/n64/extract_sky.py
build/n64-python/bin/python port/n64/build.py --aim-qa 2 --validate
build/n64-python/bin/python port/n64/build.py --aim-qa 0 --validate
build/n64-python/bin/python port/n64/build.py --hud-qa --hud-qa-page 4 --validate
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

Local Ares captures and matching before/after views live in
`build/n64/sky-audit/comparison.html`. Upward and level four-player views plus
single-player framing were inspected with zero RDP errors/warnings. This visual
pass is not a new frame-rate benchmark.
