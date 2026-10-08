# Compact N64 HUD

The HUD keeps Halo's corner layout while using smaller, upright pixel art for
the N64 framebuffer. `hud_pixels.h` defines a 64×80 IA4 bank (2,560 bytes),
initialized once and never modified during rendering. Counters, bars, grenade
silhouettes and status text share one upload per viewport. The 4×6 glyphs use
integer coordinates and point sampling. Navy shadows keep them readable on
both the sky and dark terrain. The main color is RGB (100, 220, 255).

The AR magazine has 20 columns of three rounds: every one of its 60 rounds
remains individually represented. The filled portion depletes from the right;
partial columns account for the last one or two rounds. The meter is 39×11
pixels, below the loaded count; reserve ammo remains beneath it. The on-gun
counter is unchanged. Other Xbox weapons retain their individual magazine
capacities. Energy weapons show battery charge numerically and a labeled heat
bar. Red indicates overheating; shield depletion and low health also use red,
with yellow for intermediate health and an additional overshield layer.

Weapon and vehicle reticles retain their source silhouettes, drawn 15% smaller
with point filtering and cyan tint. Their aiming anchor and camera projection
are unchanged. Scope masks and sniper ticks are unchanged; zoom labels use the
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
health/shields; one player; and two players. It uses the production renderer
and HUD with staged gameplay values, and is not a performance test.
Add `--hud-qa-page 0` through `--hud-qa-page 5` to hold a single page.
Local screenshots, matching before/after views and timing evidence are in
`build/n64/hud-audit/`. The quiet VI replay is the separate timing check.

Observed in Ares (NTSC, 4 MiB): all six fixture pages rendered with zero RDP
errors/warnings, including the separately held two-player page. The matched
motion-sensor region is pixel-identical before/after. The 75.017-second quiet
four-player replay measured 28.6 FPS overall / 29.1 combat / 28.1 vehicles,
compared with the preceding build's 28.5 / 29.0 / 28.0. Free heap at the result
screen increased from 46 to 53 KiB. This does not meet the separate sustained
30 FPS target, and is emulator evidence rather than a console measurement.
