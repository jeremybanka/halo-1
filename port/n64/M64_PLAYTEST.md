# M64 playtest follow-up — 2026-10-30

The user played Firefight and Slayer Pro on a ModRetro M64 using the **Insane overclock**. They reported that play was almost always smooth, with a few brief drops when enemy waves arrived; fights felt meaningful and skill-based, and long-distance hit registration worked well. This is qualitative hardware feedback, not a measured FPS result and not evidence for stock-clock N64 performance.

## Changes

Three-player play gives P1/P2 the two 160×120 upper views and P3 a 320×120 bottom view. P3 uses the existing two-player wide-view FOV, title-safe aim/projection alignment and a correctly centered wide scoreboard. The vertical divider ends at the horizontal split. The same rectangle helper supplies rendering and score layout/validation.

**Duke is the default** for all four player profiles. The user explicitly confirmed D-pad movement and stick aiming. **Bond** is the previous N64 layout, renamed without altering its gameplay mappings.

| Duke button | Action |
|---|---|
| D-pad / stick | Move / aim |
| R / L | Fire / grenade (L remains mounted secondary fire) |
| B / A | Flashlight / switch grenade type |
| C-Up / C-Right | Switch weapon / melee |
| C-Down / C-Left | Jump / reload and held interaction |
| Z tap | Toggle zoom |
| Z + C-Up | Hold to show scores |
| Z + C-Down | Toggle crouch |
| Start | Menu |

A Z tap is an unused press/release shorter than 250 ms. Using either chord cancels that tap. Chords consume their C-button actions; releasing Z while C-Down is still held cannot trigger a vehicle rise/brake action. Each player owns their gesture state. Menus consume pending gestures, changes of control style clear them, and death/new-match/restart clear toggled crouch. Holding Z alone does not zoom on release. Controls are listed in the Controls screen; the in-game scores advice was removed following user review.

Damage indicators use the owned Xbox cache's `ui\hud\bitmaps\combined\hud_damage_arrows`, separate solo/multiplayer sequences, original ARGB `0xc8ff0000`, 10-source-pixel edge offsets, and visible source ticks 1–29 at 30 Hz. The 8-bit source alpha is retained instead of the ordinary HUD's one-bit alpha. Each human player has four independent, refreshable timers. Accepted shield/body damage from another actor latches a camera-relative direction; self/ownerless damage, friendly fire suppressed by Firefight, and charge immunity do not produce a misleading arrow. Death hides the arrows, and spawn/reset clears them.

The port computes yaw/pitch-relative quadrants from the damaging actor's position in its Y-up coordinates, with an additional above/below cue for steep angles. This is an adapter, not a claim that all reconstructed CE angular edge cases or projectile-origin semantics are byte-identical. Art/timing references: `source/interface/hud_unit.c:hud_render_damage_indicators`, `source/effects/player_effects.c:player_effect_start`, and `hud_definitions.h`. The arrows draw after the scope mask and before radar, reticle, meters, text and scores. Following screenshot review, top/bottom chevrons point inward; side chevrons also face inward. Original HUD layer order is deliberately changed to honor the requested layering.

The separate whole-screen damage flash is now restored as well. Each damage profile carries its owned CE tag's duration, priority, intensity cap, color and fade function. The assault-rifle profile is red with a 0.1-second duration and 0.2 pre-curve cap; the source applies its early (square-root) curve after scaling by remaining lifetime. Plasma, melee, explosions and vehicle attacks retain their respective tag settings. Source references are `player_effect_update_screen_flash`, `player_effect_get_screen_flash`, `transition_function_build_table` and `rasterizer_screen_flash` in the Xbox screen-effects renderer. The fade tables retain the source's 1024 entries and byte quantization. Zero-duration tags produce one simulation-tick pulse; priority/replacement rules prevent a short low-priority hit from overwriting a longer high-priority flash.

This flash draws over the scene/viewmodel and under the scope mask and all HUD elements, confined to the hit player's viewport. RDP reproduces lighten using destination attenuation followed by additive color. Its additive channel wraps above 1.5, so additive contributions are capped below 0.5 to avoid bright regions turning black; CE's ordinary AR red flash stays under that limit. Very bright effects and the Needler's original max blend use this bounded lighten approximation. It is presentation-only: no changes to damage, aiming or collision. Native frames compare the peak, halfway point and expired flash, plus plasma and combined flash/arrows.

B previously had no flashlight implementation to bind. The new on-foot surface light uses the cyborg light tag's 6-world-unit range, 20° falloff and 45° cutoff. It prepares a bounded footprint once per rendered frame per active lamp, shared by all cameras, with no work beyond the player-state check when off. It gathers nearby opaque render batches once per lamp, and uses 33 local surface rays (up to 16 extra boundary recasts to close the range fade) and 48 decal triangles per lamp, frame-fenced vertex/matrix storage and conservative rejection at surface discontinuities. This is an N64 surface-light approximation, not CE's full dynamic-light/cube-map or battery implementation; characters and vehicles are not relit. Coarse or sharply changing terrain can still break the footprint into visible patches, so the flashlight needs further visual polish. Its native off/on pair is included for visual review.

## Validation and artifacts

- Address/undefined-sanitized controls tests: 98,635 mapping comparisons, the unchanged exhaustive Bond oracle, Duke action/hold tests, Z threshold/chords/cancellation/player isolation and 32,768 score-mask checks.
- Menu and frontend tests cover defaults, independent profiles, ownership, style changes, restart and input consumption; the 40-step legacy menu fixture also passes with its explicit starting styles.
- HUD tests project 20,000 forward rays over ten viewports and ten zoom factors, including fixed-point projection rounding. All 1–4 view layouts cover the screen exactly without overlap.
- Actual game tests cover accepted damage, timer expiry, victim isolation, friendly-fire suppression, shield protection, ownerless/self hits, flashlight toggling and reset. Firefight fights, full lifecycle, roster and enemy-vehicle regressions pass.
- 46 runtime configurations / 184 N64 translation units compile.
- Twenty frozen Ares frames cover 1–4 players with/without arrows, Duke/Bond help, P3's wide scoreboard, flashlight off/on zoomed damage, and source damage-flash timing/isolation. These are native pixel readbacks, not FPS measurements.
- The Blood Gulch packed map reproduces byte-for-byte after the game-source change; movement/collision geometry is unchanged.

Evidence and reproduction scripts are in `benchmarks/m64-polish/`. Source-derived images and native pixels are kept locally and in the private assets working tree. The local review page is `build/n64-m64-polish/comparison.html` in the original research checkout. The playable ROM is linked there. No card copy, commit or push is performed by this pass.

Reproduce from this checkout using `build/n64-python/bin/python`:

```sh
python port/n64/extract_damage_hud.py
python port/n64/benchmarks/m64-polish/test_controls.py
python port/n64/benchmarks/m64-polish/test_game.py
python port/n64/benchmarks/m64-polish/refresh_maps.py
python port/n64/benchmarks/m64-polish/build.py photos
python port/n64/benchmarks/m64-polish/capture.py
python port/n64/benchmarks/m64-polish/build.py play
python port/n64/benchmarks/m64-polish/report.py
```
