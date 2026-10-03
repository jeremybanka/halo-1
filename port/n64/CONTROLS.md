# Controls and pause menu

All players start with the original **N64** layout. To choose **Xbox** style,
press Start on your active controller, select **Controls**, and change
**Control Style** with left/right or A. The choice affects only your player.
This is an alternate layout on the N64 controller; the stick aims and the
D-pad moves. Controller and keyboard bindings in ares remain separate.

## Pause menu

Start from any active player pauses the match and opens the root menu for
that player. The upper-right label identifies the owner. Only that controller
can navigate or select. If another active player presses Start, ownership
transfers to them and the root menu returns to **Resume**. Start from the
current owner resumes play. If several players press Start in one poll, the
lowest active controller port takes precedence.

| Page / option | Behavior |
| --- | --- |
| Resume | Continue the match. |
| Setup → Players | Player 1 changes the active player count between 1, 2 and 4; the change applies immediately and Setup stays open. |
| Setup → Restart Match | Player 1 resets the match and resumes play. |
| Controls → Control Style | Change the menu owner's layout between N64 and Xbox. |

**Setup is disabled for Players 2–4.** Their navigation skips it. Inactive
controller ports cannot open or take over the menu. Player 1 can restore
additional players through Setup; their previously selected styles return.

Use D-pad or stick up/down to move the highlight. A selects an option; B
returns to the root, or resumes when already at the root. D-pad or stick
left/right changes Players or Control Style; A also cycles those values.
Menu navigation is the same under both gameplay layouts. A stick tilt moves
once: return it to center before tilting again. Opening or transferring the
menu requires recentering a held stick before it can navigate.

Each player's preference persists through match restart and player-count
changes. Preferences are held in memory and **are not saved after power-off
or restarting the emulator's game system**. Opening, navigating, transferring
and closing the menu consume gameplay input, so the selecting A/B/R presses
do not also jump, melee, reload or interact with the world.

## Gameplay layouts

The N64 column preserves the existing mapping. Directions refer to the named
buttons on the N64 controller, including when Xbox style is selected.

| Action | N64 | Xbox style | Input behavior |
| --- | --- | --- | --- |
| Forward / backward | Stick up/down | D-up/down | Continuous while held |
| Turn / horizontal aim | Stick left/right | Stick left/right | Analog |
| Strafe | C-left/right | D-left/right | Continuous while held |
| Look up/down | C-up/down | Stick up/down | Held in N64; analog in Xbox style |
| Jump | A | A | New press on foot |
| Fire | Z | Z | Held; weapon rules determine repeat fire |
| Reload / contextual use | B | R | New press |
| Switch carried weapon | R | C-left | New press |
| Throw grenade | L | L | New press |
| Select grenade type | D-left | C-right | New press |
| Melee | D-down | B | New press |
| Cycle zoom | D-up | C-up | New press; supported weapons only |
| Crouch | D-right | C-down | Held |
| Pause / take menu ownership / resume | Start | Start | New press |

Contextual use picks up a nearby weapon, enters an available vehicle seat, or
exits the current vehicle. The same button requests reload, retaining the
existing contextual gameplay rules. On-screen pickup, enter and exit prompts
say **B** for N64 and **R** for Xbox style.

Both layouts retain the same stick scaling and deadzone: raw stick values are
divided by 80, and each normalized axis below 0.12 in magnitude becomes zero.
Positive stick Y means forward in N64 and look up in Xbox style. Neither
layout adds aim inversion or a different sensitivity.

## Vehicles

Forward/backward input drives the vehicle. Turn input steers the Warthog,
Ghost and Banshee; the Scorpion instead uses it to aim its turret, with look
input raising or lowering the cannon and strafe input steering the hull.
That hull control is C-left/right in N64 and D-left/right in Xbox style.

Hold A to raise the Banshee and hold crouch to descend: D-right in N64 or
C-down in Xbox style. Z fires the mounted primary weapon. Hold L for mounted
secondary fire where available: the Scorpion's machine gun and the Banshee's
secondary projectile. The Warthog gunner aims independently of the driver.

For the Warthog, approach the left side to drive, the right side to ride in
the front passenger seat, or the rear to use the gunner seat, then press your
contextual-use button. The nearest available entry marker selects the seat.

## Implementation and tests

`controls.c` maps one hardware-neutral controller sample to one `bg_input`;
it stores no player preferences. `menu.c` owns four separate choices and the
menu's ownership/permission rules. `main.c` adapts the libdragon buttons,
updates the menu once per poll, and clears queued gameplay edges when the
menu consumes a poll. HUD interaction labels use cached paragraphs for both
layouts, without rebuilding text during each draw.

Host tests cover all 16,384 N64 held-button masks with multiple edge masks
and mounted/on-foot states, bit-identical legacy axes, Xbox action isolation,
button holds versus edges, stick signs/deadzone, and independent players.
Menu tests cover ownership transfer, Player 1 Setup permission, simultaneous
Start, analog recentering, input consumption and preference persistence.

```sh
mkdir -p build/n64/controls-qa
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 \
  port/n64/test_controls.c port/n64/controls.c -lm \
  -o build/n64/controls-qa/test-controls
build/n64/controls-qa/test-controls
clang -std=c17 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -Iport/n64 \
  port/n64/test_menu.c port/n64/menu.c \
  -o build/n64/controls-qa/test-menu
build/n64/controls-qa/test-menu
python3 port/n64/test_hud_controls.py
python3 port/n64/test_hud_cache.py
python3 port/n64/test_input_menu.py
python3 port/n64/test_paced_acquire.py
```

These tests establish input and menu behavior. They are not evidence of
physical-controller latency or a new presentation-timing result.

The final Ares test ROM uses `--menu-qa --validate --paced30 --paced30-buffers 5`.
It passes 40 checkpoints through the production input/menu path, including
all four owners, Setup permissions, 1/2/4 player counts, style isolation,
mixed-layout gameplay and restart persistence. Cumulative RDP validation ends
at zero errors and warnings. Actual screenshots and the scripted recording
are in `build/n64/controls-menu-qa/index.html`; the normal release contains
neither the test inputs nor the diagnostic banners. Its separate five-surface
timing regression also retains nominal 30 Hz with zero missed deadlines;
see [PACING.md](PACING.md) for the measured latency and memory cost.
