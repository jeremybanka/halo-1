# Local pause menu appearance

`menu_draw.c` uses the original Xbox Halo menu fonts and pause-box artwork,
extracted from the user's local `bloodgulch.map`. The menu is an adaptation to
320×240 with a readable full-screen Controls page. It preserves the original
typeface and colors; its new Setup and per-player control pages are not replicas
of an original Xbox screen.

## Source evidence

The extraction resolves tag paths, rather than assuming numeric IDs. In the
provided USA Rev 2 map they are:

| Resource | Tag | Use |
| --- | ---: | --- |
| `ui\large_ui` | 1431 | Titles and selectable items |
| `ui\small_ui` | 1432 | Mappings, owner, help and navigation |
| `ui\shell\bitmaps\pausebox2_left` | 1722 | Left panel edge |
| `ui\shell\bitmaps\pausebox2_center` | 1724 | Panel center |
| `ui\shell\bitmaps\pausebox2_right` | 1726 | Right panel edge |
| `ui\shell\multiplayer_game\pause_game\resume_game_button` | 1728 | Large-font and blue-color reference |

The Resume widget text color is RGB `(40,150,255)`. Focused white is `0.8` per
channel, as defined by `global_ui_white_*` and used by focused text rendering in
`source/interface/ui_widget.c`. The dimmer uses RGBA `(0,0,0,170)`, sampled from
`ui\shell\bitmaps\semi_transparent_grey`. The original pausebox widgets expose
159 pixels of their 256-pixel-high texture. We crop that visible area and make
nine small slices; the new panel expands these slices to `(18,14)–(302,226)`.

`source/text/draw_string.c` positions each glyph at cursor minus bitmap origin.
The N64 renderer retains those bearings and original advances. It subsets
ASCII 32–95, uppercases the menu copy, and converts original A8 coverage to I4
using nearest rounding. Font bitmaps are not spatially resampled during
extraction; the RDP scales them when drawing. One transparent texel around every
glyph prevents bilinear filtering from reading an adjacent glyph. An empty
source space has a negative bitmap width; the converter canonicalizes its
empty dimensions to zero while preserving its advance.

## Reproduction and integration

Use the existing Reclaimer/Pillow asset environment:

```sh
build/n64-python/bin/python port/n64/extract_menu_assets.py
build/n64-python/bin/python port/n64/test_menu_assets.py
```

The script writes original-source PNG references under `build/n64/assets/menu`
and `menu_data.c` plus `menu-report.json` under `build/n64/generated`. These
derived assets stay ignored. The report records source map, source helper and
header hashes, original font alpha hashes, tag paths, source metrics, and the
generated C hash in `generated_sha256`. Re-running extraction deterministically
regenerates the bank from the local map. No downloaded fonts or copied asset
blobs are required in the repository.

Compile `menu_draw.c` and generated `menu_data.c`. Call `bg_menu_draw_init()`
once after graphics initialization; it creates static texture views without
heap allocation. Call `bg_menu_draw(&menu)` after flushing scene triangles.
The renderer uses an explicit RDP pipe sync at entry, sets a full-screen
scissor, and pushes/pops RDP draw mode. The caller continues to own viewport,
scene, menu input/state, and gameplay suspension.

The bank contains 18,704 bytes of glyph/pixel payload, or 18,840 bytes including
target descriptor tables/alignment. The renderer object currently contains
7,896 bytes of static working storage. Its bounded queue holds 320 glyphs; all
48 page/owner/style/row layouts use at most 283. Text is grouped by its four
4-KiB font atlas pages so each used page is uploaded only once per menu draw.

## Behavior and checks

The visible owner is always labeled. Setup stays visible but disabled for
players 2–4. Controls shows the selected player's style and all authoritative
bindings from `controls.c`; the vehicle note distinguishes Banshee ascent and
descent from secondary fire. Menu navigation and preference persistence belong
to `menu.c` and its portable tests, not to this renderer.

`test_menu_assets.py` checks source glyph metrics, alpha rounding, transparent
filter guards, TMEM page size, empty glyph handling, and determinism. Both C
files compile with the target toolchain under `-Wall -Wextra -Werror`.
The ignored `build/n64/controls-menu-qa` directory holds a host trace of the
actual draw layout and CPU previews. All 48 layouts fit within the panel.
These CPU previews approximate filtering and alpha blending; target screenshots
and RDP validation are the authority for final rendered appearance and command
correctness.
