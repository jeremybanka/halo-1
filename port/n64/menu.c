#include "menu.h"
#include <string.h>

static void disarm_sticks(bg_menu *m) {
    memset(m->stick_x_ready, 0, sizeof(m->stick_x_ready));
    memset(m->stick_y_ready, 0, sizeof(m->stick_y_ready));
}

void bg_menu_init(bg_menu *m, unsigned count) {
    memset(m, 0, sizeof(*m));
    m->player_count = (count >= 1 && count <= 4) ? count : 4;
    for (unsigned p = 0; p < BG_PLAYERS; p++)
        m->styles[p] = BG_CONTROLS_N64;
}

static int8_t axis_edge(float value, bool *ready) {
    if (value >= -20.0f && value <= 20.0f) {
        *ready = true;
        return 0;
    }
    if (*ready && (value <= -40.0f || value >= 40.0f)) {
        *ready = false;
        return value < 0 ? -1 : 1;
    }
    return 0;
}

void bg_menu_inputs(bg_menu *m, const bg_control_state raw[BG_PLAYERS],
                    bg_menu_input out[BG_PLAYERS]) {
    for (unsigned p = 0; p < BG_PLAYERS; p++) {
        out[p] = (bg_menu_input){.pressed = raw[p].pressed,
                                 .nav_horizontal = axis_edge(raw[p].stick_x, &m->stick_x_ready[p]),
                                 .nav_vertical = -axis_edge(raw[p].stick_y, &m->stick_y_ready[p])};
    }
}

unsigned bg_menu_row_count(const bg_menu *m) {
    return m->page == BG_MENU_ROOT ? 3 : m->page == BG_MENU_SETUP ? 2 : 1;
}

bool bg_menu_row_enabled(const bg_menu *m, unsigned row) {
    if (row >= bg_menu_row_count(m))
        return false;
    if (m->page == BG_MENU_SETUP)
        return m->owner == 0;
    return m->page != BG_MENU_ROOT || row != BG_MENU_SETUP_ROW || m->owner == 0;
}

static int direction(const bg_menu_input *i, uint32_t negative, uint32_t positive, int8_t analog) {
    if (i->pressed & (negative | positive))
        return !!(i->pressed & positive) - !!(i->pressed & negative);
    return (analog > 0) - (analog < 0);
}

static unsigned cycle_count(unsigned value, int direction) {
    static const unsigned counts[] = {1, 2, 4};
    unsigned index = value == 1 ? 0 : value == 2 ? 1 : 2;
    return counts[(index + (direction < 0 ? 2 : 1)) % 3];
}

static void root_page(bg_menu *m, unsigned row) {
    m->page = BG_MENU_ROOT;
    m->row = row;
}

bg_menu_result bg_menu_update(bg_menu *m, const bg_menu_input in[BG_PLAYERS], unsigned active) {
    bg_menu_result result = {.consumed = m->open, .player_count = m->player_count};
    if (active > BG_PLAYERS)
        active = BG_PLAYERS;
    /* An externally removed owner must not leave an inaccessible pause. */
    if (m->open && m->owner >= active) {
        m->open = false;
        root_page(m, BG_MENU_RESUME);
    }
    for (unsigned p = 0; p < active; p++)
        if (in[p].pressed & BG_BUTTON_START) {
            if (m->open && m->owner == p)
                m->open = false;
            else {
                m->open = true;
                m->owner = p;
            }
            root_page(m, BG_MENU_RESUME);
            disarm_sticks(m);
            result.consumed = true;
            return result;
        }
    if (!m->open)
        return result;
    const bg_menu_input *i = &in[m->owner];
    /* Enforce permissions at dispatch as well as navigation. */
    if (m->page == BG_MENU_SETUP && m->owner != 0) {
        root_page(m, BG_MENU_CONTROLS_ROW);
        return result;
    }
    if (i->pressed & BG_BUTTON_B) {
        if (m->page == BG_MENU_ROOT)
            m->open = false;
        else
            root_page(m, m->page == BG_MENU_SETUP ? BG_MENU_SETUP_ROW : BG_MENU_CONTROLS_ROW);
        return result;
    }
    const int vertical = direction(i, BG_BUTTON_D_UP, BG_BUTTON_D_DOWN, i->nav_vertical);
    if (vertical) {
        const unsigned rows = bg_menu_row_count(m);
        do {
            m->row = (m->row + (vertical < 0 ? rows - 1 : 1)) % rows;
        } while (!bg_menu_row_enabled(m, m->row));
        /* Moving the highlight cannot also activate its destination. */
        return result;
    }
    const int horizontal = direction(i, BG_BUTTON_D_LEFT, BG_BUTTON_D_RIGHT, i->nav_horizontal);
    const bool select = (i->pressed & BG_BUTTON_A) != 0;
    if (m->page == BG_MENU_ROOT) {
        if (!select || !bg_menu_row_enabled(m, m->row))
            return result;
        if (m->row == BG_MENU_RESUME)
            m->open = false;
        else {
            m->page = m->row == BG_MENU_SETUP_ROW ? BG_MENU_SETUP : BG_MENU_CONTROLS;
            m->row = 0;
        }
    } else if (m->page == BG_MENU_SETUP) {
        if (m->shell_session) {
            if (select) {
                result.action = m->row == 0 ? BG_MENU_ACTION_RESTART : BG_MENU_ACTION_QUIT;
                m->open = false;
                root_page(m, BG_MENU_RESUME);
            }
        } else if (m->row == BG_MENU_PLAYERS_ROW && (horizontal || select)) {
            m->player_count = cycle_count(m->player_count, horizontal ? horizontal : 1);
            result.action = BG_MENU_ACTION_PLAYER_COUNT;
            result.player_count = m->player_count;
        } else if (m->row == BG_MENU_RESTART_ROW && select) {
            result.action = BG_MENU_ACTION_RESTART;
            m->open = false;
            root_page(m, BG_MENU_RESUME);
        }
    } else if (horizontal || select) {
        unsigned style = (unsigned)m->styles[m->owner];
        if (style >= BG_CONTROLS_COUNT)
            style = BG_CONTROLS_N64;
        m->styles[m->owner] =
            (bg_control_style)((style + (horizontal < 0 ? BG_CONTROLS_COUNT - 1 : 1)) %
                               BG_CONTROLS_COUNT);
    }
    return result;
}
