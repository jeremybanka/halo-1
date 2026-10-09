# Xbox front end on N64

The release boots into the shell. Layouts, bitmap labels, previews, profile
portraits, fonts, descriptions, camera transforms, ring/sky geometry, menu
sounds and title music are extracted from the supplied USA Rev 2 Xbox disc.
Coordinates are retained in the original 640×480 space and rasterized at
320×240. This is the N64 shell implementation, not the original UI interpreter.

The N64 adaptations use blue A / green B button legends and the ModRetro M64
Pro controller in join slots, the pregame roster, and the Split Screen illustration.
See [menu artwork provenance](menu_art/README.md).

## Menu itinerary

Entries marked `(dim)` below are visible and focusable but cannot be activated.
Those annotations are documentation only; they never appear in the game.

```
Main Menu
├─ Campaign (dim)
├─ Multiplayer
│  ├─ Cooperative Play (dim)
│  ├─ Split Screen
│  │  ├─ Select Profile — join/ready 1–4 controllers, choose unique profiles
│  │  ├─ Select Map — Blood Gulch; the other 12 Xbox maps are dim
│  │  ├─ Select Game Type — Slayer; the other 25 Xbox presets are dim
│  │  ├─ Pregame — roster, map/type, 15-kill limit, countdown
│  │  ├─ Match — one, two, three, or four local views
│  │  │  └─ Start → Resume / Setup / Controls
│  │  │     ├─ Setup (P1 only) → Restart Match / Quit Game
│  │  │     └─ Controls → N64 / Xbox style, per player
│  │  └─ Postgame Carnage Report → map selection for another match
│  ├─ System Link Play (dim)
│  └─ Edit Gametypes (dim)
├─ Settings
│  └─ Select Profile
│     ├─ Change Name (dim)
│     ├─ Controller Setup → N64 / Xbox style
│     ├─ Advanced Setup (dim)
│     ├─ Change Color (dim)
│     └─ Save Changes → profile selection
└─ Game Demos (dim)
```

The retail sequence selects **map before game type**. Capability checks are
centralized in `frontend.c` and checked again when launching a match. There
are no fabricated unavailable-content dialogs. The dim opacity is 140/255.

## Interaction

Any controller can navigate the main menu; that controller becomes the host.
In Select Profile, Start or A joins, left/right changes profile, A readies, and
the ready host presses A again when everyone is ready. B unreadies, then leaves
a slot. The host can back out of the join page to Multiplayer and Main Menu.
All controller subsets work, including ports 1, 2 and 4. The host occupies the
first game viewport; remaining joined controllers follow in port order.
Profile names, armor colors and controls follow the selected profile.

The original 10.999-second countdown uses the original countdown sound. A or
Start advances it by five seconds, with a 0.999-second minimum; C-left takes
the original Xbox X function and adds five seconds. B cancels. Menu actions
are consumed before gameplay input, including match launch and quit/resume.

The retail Slayer preset ends at 15 kills. The announcer finishes before the
Postgame Carnage Report appears, with score, kills, assists and deaths. A
continues to map selection; B opens quit confirmation. Quit defaults to No.
The per-player pause menu retains its existing two control styles; Setup is
available to the first local player only.

## Extraction and build

After the map/model/HUD extraction described in README:

```sh
build/n64-python/bin/python port/n64/extract_frontend.py
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The generated `frontend-report.json` records source cache hashes, extractor
and header hashes, every ROM bank hash, original widget definitions, cameras,
font metrics and audio tag paths. `build.py` refuses stale banks. The bank is
embedded through DragonFS; retail pixels/audio are not checked into Git.

Source references:

- `source/interface/ui_widget.c`: widget offsets and bitmap crop/stretch rules.
- `ui.map`: original main, multiplayer, profile, map, type and pregame widgets.
- `source/networking/network_server_manager.c`: countdown duration and adjustment.
- `source/game/game_engine.c`: Postgame Carnage Report tabs and 18-pixel rows.
- `source/game/game_statistics.c`: assist contribution threshold.
- `bloodgulch.map`: countdown sound and postgame background bitmap.

Only the current page's cropped texture rectangles live in RAM. GPU completion
is fenced before those surfaces are replaced. Front-end fonts, geometry and
textures are released before gameplay. The target remains a 4 MiB N64.

## Verification

`test_frontend.c` covers all 15 nonempty controller subsets and every possible
host, physical-to-logical remapping (including in-place remapping), unavailable
presets, launch validation, countdown adjustment/cancel, results, quit/resume,
and control settings. `test_menu.c` includes the shell's restart/quit actions
and P1-only setup. `test_game.c` verifies the 15-kill limit, actual statistics,
assists and respawn/reset behavior. `test_hud_layout.c` checks all ten viewports
across one to four players and 20,000 projected aiming rays. Existing input
adapter tests exercise 70,856 comparisons under both strict and target math.

Separately named `--frontend-qa 3` and `--frontend-qa 4` ROMs navigate the
production state machine with scripted controller edges. They stage shotgun
combat, but use normal health, damage, respawn, scoring and game-over logic;
no winner or final score is assigned by the fixture. They assert 15 kills,
then navigate back through map selection and joining to the main menu.
The extended four-player fixture also opens Settings, changes Player 2 to
Xbox controls, backs out through profile selection, and returns to Main Menu.
Validation builds add RDP diagnostics. Captures of these ROMs are automated
verification demonstrations, not recordings of a human playing.

The three-player lifecycle and extended four-player lifecycle both completed
in Ares with **zero RDP errors and zero warnings**. The recordings are under
`build/n64/frontend-audit/`. The captured audio contains the extracted countdown
tone; waveform matching locates the audible one-second sequence. These checks
verify the emulator runs, not a physical N64 flash cartridge.

The quiet four-player replay retained 2,244 fresh poses, zero missed deadlines,
33.4 ms maximum frame spacing (two retraces), and 617 KiB free heap. The
benchmark displayed 29.9 FPS; Ares wall-clock emulation speed is a separate
measurement. Its input-sample-to-display mean/maximum remained 130/135 ms.

A host-only front-end test can be reproduced with:

```sh
clang -std=c17 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Iport/n64 port/n64/test_frontend.c port/n64/frontend.c \
  port/n64/controls.c port/n64/menu.c -lm -o build/n64/test-frontend
build/n64/test-frontend
```

## Current limits

Four built-in profiles are held in RAM. Save Changes retains settings within
the running session; Controller Pak persistence and profile creation are not
implemented. The original ring/sky meshes and camera paths are retained, but
32×32 texture tiles and a reduced material model approximate the Xbox shaders.
Text and previews are downsampled for 320×240. N64 button help and the existing
control-layout panel necessarily differ from the Xbox controller screen.
Campaign, co-op, System Link, other maps/types, profile editing and demos remain
inaccessible. This change does not complete the remaining Blam engine port.
