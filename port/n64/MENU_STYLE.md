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
once after graphics initialization; it creates static texture views and records
the seven permanent score-panel command blocks described below. No block is
executed during this initialization. Call `bg_menu_draw(&menu)` after flushing
scene triangles.
The renderer uses an explicit RDP pipe sync at entry, sets a full-screen
scissor, and pushes/pops RDP draw mode. The caller continues to own viewport,
scene, menu input/state, and gameplay suspension.

The bank contains 18,704 bytes of glyph/pixel payload, or 18,840 bytes including
target descriptor tables/alignment. The renderer object currently contains
25,848 bytes of BSS working storage. Its bounded menu queue holds 320 glyphs; all
48 page/owner/style/row layouts use at most 283. Text is grouped by its four
4-KiB font atlas pages so each used page is uploaded only once per menu draw.

## Behavior and checks

The visible owner is always labeled. Setup stays visible but disabled for
players 2–4. Controls shows the selected player's style and all authoritative
bindings from `controls.c`; the vehicle note distinguishes Banshee ascent and
descent from secondary fire. Xbox style uses C-left for reload/use, C-up for
weapon switching, held R for scores, and R+C-up for zoom. The mapping fits eight
rows without reducing the text size; Start navigation remains in the footer.
Menu navigation and preference persistence belong
to `menu.c` and its portable tests, not to this renderer.

`test_menu_assets.py` checks source glyph metrics, alpha rounding, transparent
filter guards, TMEM page size, empty glyph handling, and determinism. Both C
files compile with the target toolchain under `-Wall -Wextra -Werror`.
The ignored `build/n64/controls-menu-scores-qa/host-layout` directory holds a
host trace of the final draw layout and CPU previews. All 48 menu layouts fit
within the panel.
These CPU previews approximate filtering and alpha blending; target screenshots
and RDP validation are the authority for final rendered appearance and command
correctness.

## Held-R scores

`bg_scores_draw(owner, x, y, width, height)` draws only within that player's
viewport, using the same font and panel bank. It reads `bg_player_count()` and
`bg_players[].score`; it never changes game state, input or pause state. The
caller decides when held R should display it and continues normal simulation.
The function restores the full-screen scissor after its draw.

The original Xbox split-screen path in
`source/game/game_engine.c::game_engine_rasterize_in_game_score` displays ranked
player rows and brightens the viewer's row. This adaptation retains those cues,
adds the local player-color swatches, and labels the numeric column **SCORE**.
It uses actual match score, including suicide penalties; it does not invent
separate kill, death or assist statistics. Equal scores share a rank, with player
index providing stable ordering. Only active players appear.

The compact four-player panel fits inside 160×120, while one- and two-player
views use larger text. It requires no extra texture bank. Separate host evidence under
`build/n64/controls-menu-scores-qa/host-layout` covers 21 scoreboard layouts,
signed scores and ties, all owners, glyph bounds and byte-identical game state
before/after drawing. Those score fixtures use at most 68 glyphs; the complete
32-bit signed-score range needs at most 100. Final target evidence is recorded
under `build/n64/controls-menu-scores-qa` as described below.

### Panel and text caches

Initialization prewarms all seven supported count/owner layouts: one full-screen,
two half-screen and four quarter-screen panels. Each has one immutable RDP block
for the background, nine panel slices and divider. Its 104-entry CPU glyph
array begins with 24 prewarmed records for the fixed headings. The full count,
owner and viewport dimensions are asserted before replay.

The complete glyph list and ranked player order are built when first displayed
and rebuilt only when an active player's integer score changes. Unchanged
frames perform no sorting, string formatting, glyph layout or full-list copy.
Inactive-player scores do not invalidate the cache. The original row rectangles
are still emitted every draw, followed by one combined text flush directly from
the CPU cache. Draw order and font-page uploads are unchanged. Within each font
page, primitive color is sent for the first glyph and whenever RGBA changes,
rather than redundantly for every glyph.

Cached score glyphs also retain the final quarter-pixel rectangle endpoints and
1/1024 texture increments. These are calculated after the same float-to-fixed
truncation as the SDK's scaled rectangle helper, then submitted through the
public `rdpq_texture_rectangle_raw` API with exact binary fractions. This removes
two integer divisions per score glyph on unchanged frames while preserving the
SDK's autosync and cycle fixups. A same-size union reuses the original position
storage; no extra BSS is needed. The prewarmed heading prefix is converted once,
and only newly laid-out score rows are converted on a score change. Clipped,
flipped or out-of-range future layouts retain the original scaled path;
degenerate rectangles remain skipped. Normal menu text keeps its scaled path.

The panel block restores its own combiner transitions; the caller explicitly
selects the flat combiner before row rectangles. All panel/font pixels have
permanent addresses. Glyph positions, colors and texture coordinates are copied
into literal RDP commands as the CPU flushes them. Queued GPU work never borrows
the mutable CPU glyph, score or order arrays, so rebuilding these lists requires
no GPU fence or mutable RSP command block.

The target `score_layouts` array occupies 17,948 bytes. Complete text caching adds
13,720 bytes beyond the fixed-panel/header cache, bringing total renderer BSS to
25,848 bytes. Seven SDK command blocks additionally consume heap storage at
initialization and remain allocated for the application's lifetime. There is no
lazy RDP recording, allocation or block retirement on the first or later held-R
frames, and no extra font upload introduced by caching.

`controls-menu-scores-qa/panel-cache-proof` records 63 ASan/UBSan host cases over
the seven layouts, signed scores and ties. Expanding the cached panel operations
produces the same 4,356 visible drawing operations as the original path, with
the same 63 font uploads. CPU nine-slice helper calls fall from 567 during those
draws to 63 during initialization only. This is an effective draw-operation
comparison, not a binary RDP-word, target-pixel or frame-rate result.

`controls-menu-scores-qa/text-cache-proof` covers 210 score draws and 70
interleaved menus. All 32,778 visible drawing operations and 420 font uploads
match the direct CPU-layout path. The 140 unchanged-score draws make zero
formatting calls, compared with 1,260 previously. Checks include ties, signed
scores through `INT_MIN`/`INT_MAX`, active/inactive player changes, temporary
menu-queue reuse, glyph bounds and unchanged game state. Target compilation
passes `-Wall -Wextra -Werror`; actual target validation and cadence are measured
separately.

`controls-menu-scores-qa/fixed-rect-proof` includes the installed SDK rectangle
header directly and intercepts its final four command words. All 28,722
rectangles and 32,782 visible operations match the preceding path over the
same 210 score draws, 70 interleaved menus and eight additional clipped,
flipped or degenerate fixtures. Font uploads remain identical. The score draws
avoid 24,824 integer divisions; target compilation and ASan/UBSan checks pass.
This command-word proof does not substitute for target validation or timing.

### Final target verification

The final `menu.mp4` recording runs 133.160 seconds and decodes cleanly with both
video and audio streams. Seven unmodified full-frame screenshots document the
root menus, Setup, both control mappings, two live per-player score panels and
the final **40/40 PASS**. Cumulative RDP validation remains at **0 errors and
0 warnings** through the last captured frame at PTS 133.148333 seconds. The
review samples 32 post-reboot frames; the audio energy check is non-silent.
`menu-result.json` binds these observations to the exact menu ROM and frozen
build inputs. This instrumented capture is functional evidence, not a timing
benchmark or a complete frame-by-frame audiovisual audition.

Separate 75.017-second quiet VI measurements retain the performance boundary:
normal four-player play presents 2,244 fresh poses with no missed two-VI
deadlines. Holding all four score panels open presents 2,243 poses with **one
vehicle-phase deadline miss**, a maximum 66.8 ms presentation interval. The
combat phase has no miss. See `timing-result.json` and
`scores-timing-result.json`; the score stress result does not establish a
steady 30 FPS claim for that condition.
