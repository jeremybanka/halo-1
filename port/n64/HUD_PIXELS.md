# Compact N64 HUD

The HUD keeps Halo's corner layout while using smaller, upright pixel art for
the N64 framebuffer. `hud_pixels.h` defines a 64×128 IA4 bank (4,096 bytes),
initialized once and never modified during rendering. Counters, bars, grenade
silhouettes, reticles and status text share one upload per viewport. The 4×6 glyphs use
integer coordinates and point sampling. Centered navy digit outlines keep counters readable on
both the sky and dark terrain. The main color is RGB (100, 220, 255).

The AR magazine has 20 columns of three rounds: every one of its 60 rounds
remains individually represented. The filled portion depletes from the right;
partial columns account for the last one or two rounds. The meter is 39×11
pixels, below the loaded count; reserve ammo remains beneath it. The on-gun
counter is unchanged. Pips and health cells have centered, even backing instead
of a diagonal drop shadow. Other Xbox weapons retain their individual magazine
capacities. Energy weapons show battery charge numerically and a labeled heat
bar. Red indicates overheating; shield depletion and low health also use red,
with yellow for intermediate health and an additional overshield layer.

Weapon and vehicle reticles use native 24×24 masks based on their source
silhouettes (pistol/sniper ink is centered in 10×10 / 6×6 footprints). Each
12×12 quadrant maps exactly to 12×12 screen pixels, with explicit integer UV
increments for mirror pairs. Even extents place the geometric center on the
original integer aim anchor in every viewport. There is no fractional texture
scaling or independent rounding of cropped bitmap offsets. Plasma pistol,
Ghost and Banshee retain their intentionally different upper/lower halves.
`pack_hud_reticles.py` regenerates the compact masks from the local Xbox bank,
with explicit preservation of subpixel vehicle/range-mark details.
The aiming anchor and camera projection are unchanged. Scope masks and sniper ticks are unchanged; zoom labels use the
new font. **The motion sensor is unchanged**, including source art, colors,
filtering, size, position, range and moving-target rules.

## Visual verification

```sh
build/n64-python/bin/python port/n64/build.py --hud-qa --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The frozen HUD fixture cycles every 20 seconds through AR 60/59/20/0;
pistol/needler/shotgun/sniper; energy/overheat/rocket/respawn; scopes and damaged
health/shields; one player; two players; and vehicle reticles. It uses the production renderer
and HUD with staged gameplay values, and is not a performance test.
Add `--hud-qa-page 0` through `--hud-qa-page 6` to hold a single page.
Local screenshots, matching before/after views and timing evidence are in
`build/n64/hud-audit/`. The quiet VI replay is the separate timing check.

Initial HUD revision, in Ares (NTSC, 4 MiB): all six original fixture pages rendered with zero RDP
errors/warnings, including the separately held two-player page. The matched
motion-sensor region is pixel-identical before/after. The 75.017-second quiet
four-player replay measured 28.6 FPS overall / 29.1 combat / 28.1 vehicles,
compared with the preceding build's 28.5 / 29.0 / 28.0. Free heap at the result
screen increased from 46 to 53 KiB. This does not meet the separate sustained
30 FPS target, and is emulator evidence rather than a console measurement.

Pixel-grid correction evidence is in `build/n64/hud-grid-audit/`. Matching Ares
captures verify zero horizontal/vertical mask differences for the AR, pistol,
needler, shotgun and sniper (the previous revision had 10–50 mismatched pixels
per axis). The four AR displays contain exactly 60/59/20/0 illuminated pips;
each is exactly 1×3 framebuffer pixels. For these measurements, sample the
even NTSC VI output columns and account for its leading blank scanline.
The interleaved VI interpolation samples are not extra framebuffer pixels.
Presentation images use integer enlargement to avoid adding uneven pixel widths.
The aim-layout regression passes all 20,000 projected shot-ray checks.
All eight weapon reticles, four vehicle reticles, and scoped overlays were
checked in Ares with zero RDP errors/warnings. The correction's quiet replay
measured 28.7 / 29.0 / 28.3 FPS overall/combat/vehicles, with 86 KiB free heap.
The larger shared atlas avoids the old per-reticle scaled sprite blocks.
