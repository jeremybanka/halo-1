# Compact N64 HUD

The HUD keeps Halo's corner layout while using smaller, upright pixel art for
the N64 framebuffer. `hud_pixels.h` defines a 64×128 IA4 bank (4,096 bytes),
initialized once and never modified during rendering. Counters, bars, grenade
silhouettes, reticles and status text share one upload per viewport. The 4×6 glyphs use
integer coordinates and point sampling. Digits and letters use the same navy
shadow, offset one pixel down and right, to stay consistent in mixed text and
readable over the scene. The main color is RGB (100, 220, 255).

The AR magazine has 20 columns of three rounds: every one of its 60 rounds
remains individually represented. The filled portion depletes from the right;
partial columns account for the last one or two rounds. The meter is 39×11
pixels, below the loaded count; reserve ammo remains beneath it. The on-gun
counter is unchanged. Pips and health cells have centered, even backing instead
of a diagonal drop shadow. Other Xbox weapons retain their individual magazine
capacities. Energy weapons show battery charge numerically and a heat
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
Add `--hud-qa-page 0` through `--hud-qa-page 12` to hold a single page.
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

## Compact prompts and receipts

Gameplay text uses mixed case in the same native 4×6 font. Lowercase and
`+`, `!`, `.` occupy formerly empty atlas cells: the 4,096-byte bank, existing
digits, meters and reticle pixels are unchanged. `test_hud_prompts.py` checks
every changed pixel against the preceding bank and rejects overlap with old art.
Text stays at integer coordinates with point sampling and a five-pixel advance.

Weapon prompts distinguish a free inventory slot (`Hold [use] Pick up`) from
replacement (`Hold [use] Swap for`). An original weapon messaging silhouette
identifies the target. `pack_prompt_icons.py` bakes the Xbox `hud_msg_icons`
sequences into a separate, immutable 2,048-byte IA4 bank, at most 31×12 pixels
per weapon. The sniper coverage threshold retains its thin, connected barrel.
Local native-pixel corrections close the pistol trigger guard, open the AR
thumb hole toward the stock and recover its stepped top profile, and connect
the rocket launcher's under-barrel rail while removing a detached rear pixel.
Long weapons use an identity row above the bottom prompt in four-player views;
short ones fit inline. The font never shrinks. The source silhouettes and packed
data remain in the private bank. Normal ROM builds consume that bank without
reopening the source disc or importing extraction dependencies.

Vehicle prompts name both action and vehicle: `Drive Warthog`, `Gunner Warthog`,
`Ride Scorpion`, `Flip Ghost`. N64-style use shows B; Xbox-style use shows C-left.
The persistent exit hint stays removed. `Reloading`, `Overheated`, and the extra
`HEAT` caption are removed; animations, audio and heat/battery graphics remain.

`hud_messages.c` maintains four 16-byte receipts per player (256 bytes total,
plus two 32-bit counters), without allocation. Examples are `+ Assault Rifle`,
`+50 Assault Rifle`, `+1 Frag Grenade`, `+3 Plasma Grenades`, `+ Health Pack`,
`+ Overshield`, and `+ Active Camo`. Ammo events carry the actual transferred
rounds, separately from acquiring a weapon. Repeated ammo or item receipts merge
quantities, refresh their timestamp and move newest; expired slots are reused,
then the oldest entry is replaced if full. Death receipts are broadcast, with
profile identities matching the score screen. Multi-kill/spree notices are local.

The Xbox's two-second uptime and two-second power-1.9 fade are preserved at
30 Hz. A 61-byte alpha table avoids transcendental math in the draw path;
text and shadows fade together. At most two receipt lines appear in split-screen,
three in a full view, above the interaction prompt and beside the unchanged radar.
Long text wraps at spaces. Messages are fed after every simulation tick, including
catch-up ticks, and cleared for each new match/restart. Pause freezes their age.

Original USA Rev 2 `default.xbe` embeds the missing multiplayer text directly:
`You killed %s`, `Double Kill!`, `Triple Kill!`, `Rejoin in %d`, and
`Hold BACK for score`. The port uses compact equivalents, including `Rejoin in n`
and `Killing Spree!`; four-or-more rapid kills use `Killtacular!`. A depleted
weapon offers `Switch [weapon silhouette]` only if the stowed weapon has ammo,
using R for N64 controls or C-up for Xbox controls. It is suppressed during
reload/readying. The initial 15-second score hint shows `Hold [R] Scores`
only for Xbox-style controls, where the existing score binding is available;
interaction prompts and receipts take priority. No control binding changes.

Pages 7/8 inspect all eight Xbox weapon prompts with alternating B/C-left;
9 inspects staged receipts; 10 covers staged kill/award/overshield/rejoin text;
11/12 cover one- and two-player placement, including reload/vent states without
invented labels. These frozen fixtures verify the real renderer, not live kills
or frame rate. Native integration tests separately verify actual partial ammo,
grenade, power-up and kill events, queue pressure, profile identity and expiry.
Current screenshots and quiet VI evidence are in `build/n64-prompt-audit/`.
