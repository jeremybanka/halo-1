#ifndef BG_MENU_H
#define BG_MENU_H

#include "controls.h"

typedef enum { BG_MENU_ROOT, BG_MENU_SETUP, BG_MENU_CONTROLS } bg_menu_page;
enum { BG_MENU_RESUME, BG_MENU_SETUP_ROW, BG_MENU_CONTROLS_ROW };
enum { BG_MENU_PLAYERS_ROW, BG_MENU_RESTART_ROW };
typedef enum {
    BG_MENU_ACTION_NONE, BG_MENU_ACTION_RESTART, BG_MENU_ACTION_PLAYER_COUNT
} bg_menu_action;

typedef struct {
    /* Optional navigation edges: -1 up/left, +1 down/right. D-pad presses
     * take precedence on the same axis; opposite D-pad presses cancel. */
    uint32_t pressed;
    int8_t nav_vertical,nav_horizontal;
} bg_menu_input;

typedef struct {
    bool open;
    unsigned owner,row,player_count;
    bg_menu_page page;
    bg_control_style styles[BG_PLAYERS];
    /* Analog navigation is edge-triggered, without timed auto-repeat. */
    bool stick_x_ready[BG_PLAYERS],stick_y_ready[BG_PLAYERS];
} bg_menu;

typedef struct {
    /* When true the caller must discard this poll's gameplay inputs and
     * pending gameplay button edges, including on opening/resuming. */
    bool consumed;
    bg_menu_action action;
    unsigned player_count;
} bg_menu_result;

/* Initialize once per application run, not on match reset or view changes. */
void bg_menu_init(bg_menu *menu,unsigned player_count);

/* Call once per input poll, before update, for all four physical ports.
 * Raw +/-40 crosses the navigation threshold; return to +/-20 rearms it.
 * Positive stick Y means up. Opening/transferring the menu disarms all axes,
 * so a held stick cannot move the newly opened root until recentered. */
void bg_menu_inputs(bg_menu *menu,const bg_control_state raw[BG_PLAYERS],
    bg_menu_input out[BG_PLAYERS]);

/* Active ports are [0,active_player_count). Start edges are resolved before
 * all navigation/actions; the lowest active port wins simultaneous Start.
 * Player-count changes apply immediately and keep Setup open. Restart closes
 * the menu. Preferences persist through both actions. No game state is used. */
bg_menu_result bg_menu_update(bg_menu *menu,
    const bg_menu_input input[BG_PLAYERS],unsigned active_player_count);
unsigned bg_menu_row_count(const bg_menu *menu);
bool bg_menu_row_enabled(const bg_menu *menu,unsigned row);

#endif
