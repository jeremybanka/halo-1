#include "frontend.h"
#include <string.h>
const bg_front_entry bg_front_maps[13] = {
    {"Battle Creek", false}, {"Sidewinder", false}, {"Damnation", false},
    {"Rat Race", false},     {"Prisoner", false},   {"Hang 'Em High", false},
    {"Chill Out", false},    {"Derelict", false},   {"Boarding Action", false},
    {"Blood Gulch", true},   {"Wizard", false},     {"Chiron TL34", false},
    {"Longest", false}};
const bg_front_entry bg_front_types[26] = {
    {"Slayer", true},       {"Slayer Pro", false}, {"Elimination", false}, {"Phantoms", false},
    {"Endurance", false},   {"Rockets", false},    {"Snipers", false},     {"Oddball", false},
    {"Reverse Tag", false}, {"Accumulate", false}, {"Juggernaut", false},  {"Stalker", false},
    {"King", false},        {"King Pro", false},   {"Crazy King", false},  {"Race", false},
    {"Rally", false},       {"CTF", false},        {"Invasion", false},    {"Iron CTF", false},
    {"CTF Pro", false},     {"Team Race", false},  {"Team Rally", false},  {"Team Ball", false},
    {"Team King", false},   {"Team Slayer", false}};
bool bg_front_available(bg_front_page p, unsigned i) {
    switch (p) {
    case BG_FRONT_MAIN:
        return i == 1 || i == 2;
    case BG_FRONT_MULTIPLAYER:
        return i == 1;
    case BG_FRONT_MAP:
        return i < 13 && bg_front_maps[i].available;
    case BG_FRONT_TYPE:
        return i < 26 && bg_front_types[i].available;
    case BG_FRONT_PROFILE:
        return i == 1 || i == 4;
    default:
        return true;
    }
}
unsigned bg_front_joined(const bg_frontend *f) {
    unsigned n = 0;
    for (unsigned p = 0; p < 4; p++)
        n += f->joined[p];
    return n;
}
static void page(bg_frontend *f, bg_front_page p) {
    f->page = p;
    f->row = p == BG_FRONT_MAIN || p == BG_FRONT_MULTIPLAYER ? 1 : 0;
    f->deadline = 0;
    f->countdown = -1;
    f->last_beep = -1;
    memset(f->navigation.stick_x_ready, 0, sizeof(f->navigation.stick_x_ready));
    memset(f->navigation.stick_y_ready, 0, sizeof(f->navigation.stick_y_ready));
}
void bg_front_init(bg_frontend *f) {
    memset(f, 0, sizeof(*f));
    bg_menu_init(&f->navigation, 4);
    f->map = 9;
    f->type = 0;
    for (unsigned p = 0; p < 4; p++) {
        f->profile[p] = p;
        f->ports[p] = p;
    }
    page(f, BG_FRONT_MAIN);
    f->winner = -1;
}
static int direction(const bg_menu_input *i, bool horizontal) {
    uint32_t a = horizontal ? BG_BUTTON_D_LEFT : BG_BUTTON_D_UP,
             b = horizontal ? BG_BUTTON_D_RIGHT : BG_BUTTON_D_DOWN;
    if (i->pressed & (a | b))
        return !!(i->pressed & b) - !!(i->pressed & a);
    return horizontal ? i->nav_horizontal : i->nav_vertical;
}
static unsigned cycle(unsigned i, unsigned n, int d) {
    return (i + (d < 0 ? n - 1 : 1)) % n;
}
static bool all_ready(const bg_frontend *f) {
    if (!bg_front_joined(f))
        return false;
    for (unsigned p = 0; p < 4; p++)
        if (f->joined[p] && !f->ready[p])
            return false;
    return true;
}
static void pack_players(bg_frontend *f) {
    f->count = 0;
    if (f->joined[f->host])
        f->ports[f->count++] = f->host;
    for (unsigned p = 0; p < 4; p++)
        if (p != f->host && f->joined[p])
            f->ports[f->count++] = p;
}
void bg_front_results(bg_frontend *f, const int scores[4], int winner) {
    memcpy(f->final_scores, scores, sizeof(f->final_scores));
    f->winner = winner;
    page(f, BG_FRONT_RESULTS);
}
void bg_front_quit(bg_frontend *f) {
    f->return_page = BG_FRONT_PLAY;
    page(f, BG_FRONT_QUIT);
    f->row = 1;
}
bg_front_action bg_front_update(bg_frontend *f, const bg_control_state raw[4], uint64_t now) {
    bg_menu_input in[4];
    bg_menu_inputs(&f->navigation, raw, in);
    f->sound = BG_FRONT_SILENT;
    if (f->page == BG_FRONT_PLAY)
        return BG_FRONT_NONE;
    /* Main-menu ownership follows the controller using it, as on Xbox. */
    if (f->page == BG_FRONT_MAIN)
        for (unsigned p = 0; p < 4; p++)
            if (in[p].pressed || in[p].nav_vertical) {
                f->host = p;
                break;
            }
    const bg_menu_input *i = &in[f->host];
    int v = direction(i, false), h = direction(i, true);
    bool accept = (i->pressed & (BG_BUTTON_A | BG_BUTTON_START)) != 0,
         back = (i->pressed & BG_BUTTON_B) != 0;
    if (f->page == BG_FRONT_JOIN) {
        for (unsigned p = 0; p < 4; p++) {
            uint32_t b = in[p].pressed;
            int d = direction(&in[p], true);
            if (b & BG_BUTTON_B) {
                if (f->ready[p])
                    f->ready[p] = false;
                else if (f->joined[p])
                    f->joined[p] = false;
                else if (p == f->host) {
                    page(f, BG_FRONT_MULTIPLAYER);
                    f->sound = BG_FRONT_BACK;
                    return BG_FRONT_NONE;
                }
                f->sound = BG_FRONT_BACK;
                continue;
            }
            if (d && f->joined[p] && !f->ready[p]) {
                unsigned candidate = f->profile[p];
                for (unsigned attempt = 0; attempt < 4; attempt++) {
                    candidate = cycle(candidate, 4, d);
                    bool used = false;
                    for (unsigned q = 0; q < 4; q++)
                        if (q != p && f->joined[q] && f->profile[q] == candidate)
                            used = true;
                    if (!used) {
                        f->profile[p] = candidate;
                        break;
                    }
                }
                f->sound = BG_FRONT_CURSOR;
                continue;
            }
            if (b & (BG_BUTTON_A | BG_BUTTON_START)) {
                if (!f->joined[p]) {
                    f->joined[p] = true;
                    f->ready[p] = false;
                    for (unsigned k = 0; k < 4; k++) {
                        bool used = false;
                        for (unsigned q = 0; q < 4; q++)
                            if (q != p && f->joined[q] && f->profile[q] == f->profile[p])
                                used = true;
                        if (!used)
                            break;
                        f->profile[p] = (f->profile[p] + 1) % 4;
                    }
                } else if (!f->ready[p])
                    f->ready[p] = true;
                else if (p == f->host && all_ready(f)) {
                    pack_players(f);
                    page(f, BG_FRONT_MAP);
                }
                f->sound = BG_FRONT_ACCEPT;
                /* The accepting poll cannot be reused on the newly opened page. */
                if (f->page != BG_FRONT_JOIN)
                    return BG_FRONT_NONE;
            }
        }
        return BG_FRONT_NONE;
    }
    if (f->page == BG_FRONT_PREGAME) {
        bool changed = false;
        for (unsigned p = 0; p < 4; p++)
            if (f->joined[p]) {
                if (in[p].pressed & BG_BUTTON_B) {
                    page(f, BG_FRONT_TYPE);
                    f->sound = BG_FRONT_BACK;
                    return BG_FRONT_NONE;
                }
                if (in[p].pressed & (BG_BUTTON_A | BG_BUTTON_START)) {
                    f->deadline =
                        f->deadline > now + 5999000 ? f->deadline - 5000000 : now + 999000;
                    changed = true;
                }
                /* Xbox X is represented by C-left on the N64 controller. */
                if (in[p].pressed & BG_BUTTON_C_LEFT) {
                    f->deadline += 5000000;
                    changed = true;
                }
            }
        if (changed)
            f->sound = BG_FRONT_ACCEPT;
        if (now >= f->deadline) {
            /* Check capabilities again at launch, independent of earlier navigation. */
            if (!all_ready(f) || !bg_front_available(BG_FRONT_MAP, f->map) ||
                !bg_front_available(BG_FRONT_TYPE, f->type)) {
                page(f, BG_FRONT_JOIN);
                return BG_FRONT_NONE;
            }
            pack_players(f);
            page(f, BG_FRONT_PLAY);
            return BG_FRONT_START_MATCH;
        }
        f->countdown = (int)((f->deadline - now) / 1000000);
        if (f->countdown != f->last_beep) {
            f->last_beep = f->countdown;
            if (f->countdown <= 10)
                f->sound = BG_FRONT_BEEP;
        }
        return BG_FRONT_NONE;
    }
    if (back) {
        f->sound = BG_FRONT_BACK;
        switch (f->page) {
        case BG_FRONT_MULTIPLAYER:
        case BG_FRONT_SETTINGS:
            page(f, BG_FRONT_MAIN);
            break;
        case BG_FRONT_MAP:
            page(f, BG_FRONT_JOIN);
            break;
        case BG_FRONT_TYPE:
            page(f, BG_FRONT_MAP);
            break;
        case BG_FRONT_CONTROLS:
            page(f, BG_FRONT_PROFILE);
            f->row = 1;
            break;
        case BG_FRONT_PROFILE:
            page(f, BG_FRONT_SETTINGS);
            break;
        case BG_FRONT_RESULTS:
            f->return_page = BG_FRONT_RESULTS;
            page(f, BG_FRONT_QUIT);
            f->row = 1;
            break;
        case BG_FRONT_QUIT:
            page(f, f->return_page);
            if (f->page == BG_FRONT_PLAY)
                return BG_FRONT_RESUME_MATCH;
            break;
        default:
            break;
        }
        return BG_FRONT_NONE;
    }
    if (f->page == BG_FRONT_MAP || f->page == BG_FRONT_TYPE) {
        unsigned *selection = f->page == BG_FRONT_MAP ? &f->map : &f->type,
                 n = f->page == BG_FRONT_MAP ? 13 : 26;
        if (h) {
            *selection = cycle(*selection, n, h);
            if (h < 0 && f->row)
                f->row--;
            else if (h > 0 && f->row < 2)
                f->row++;
            f->sound = BG_FRONT_CURSOR;
            return BG_FRONT_NONE;
        }
        if (accept && bg_front_available(f->page, *selection)) {
            if (f->page == BG_FRONT_MAP)
                page(f, BG_FRONT_TYPE);
            else {
                page(f, BG_FRONT_PREGAME);
                f->deadline = now + 10999000;
                f->countdown = 10;
            }
            f->sound = BG_FRONT_ACCEPT;
        }
        return BG_FRONT_NONE;
    }
    if (f->page == BG_FRONT_CONTROLS) {
        if (h || accept) {
            unsigned profile = f->settings_profile;
            f->styles[profile] = bg_control_style_next(f->styles[profile]);
            f->sound = BG_FRONT_ACCEPT;
        }
        return BG_FRONT_NONE;
    }
    if (f->page == BG_FRONT_SETTINGS) {
        if (h) {
            f->settings_profile = cycle(f->settings_profile, 4, h);
            if (h < 0 && f->row)
                f->row--;
            else if (h > 0 && f->row < 2)
                f->row++;
            f->sound = BG_FRONT_CURSOR;
        } else if (accept) {
            page(f, BG_FRONT_PROFILE);
            f->row = 1;
            f->sound = BG_FRONT_ACCEPT;
        }
        return BG_FRONT_NONE;
    }
    unsigned rows = f->page == BG_FRONT_MAIN || f->page == BG_FRONT_MULTIPLAYER ? 4
                    : f->page == BG_FRONT_PROFILE                               ? 5
                    : f->page == BG_FRONT_QUIT                                  ? 2
                                                                                : 1;
    if (v) {
        f->row = cycle(f->row, rows, v);
        f->sound = BG_FRONT_CURSOR;
        return BG_FRONT_NONE;
    }
    if (!accept || !bg_front_available(f->page, f->row))
        return BG_FRONT_NONE;
    f->sound = BG_FRONT_ACCEPT;
    switch (f->page) {
    case BG_FRONT_MAIN:
        page(f, f->row == 1 ? BG_FRONT_MULTIPLAYER : BG_FRONT_SETTINGS);
        break;
    case BG_FRONT_MULTIPLAYER:
        page(f, BG_FRONT_JOIN);
        break;
    case BG_FRONT_PROFILE:
        page(f, f->row == 1 ? BG_FRONT_CONTROLS : BG_FRONT_SETTINGS);
        break;
    case BG_FRONT_RESULTS:
        page(f, BG_FRONT_MAP);
        break;
    case BG_FRONT_QUIT:
        if (f->row == 0) {
            page(f, BG_FRONT_MAIN);
            return BG_FRONT_LEAVE_MATCH;
        }
        page(f, f->return_page);
        if (f->page == BG_FRONT_PLAY)
            return BG_FRONT_RESUME_MATCH;
        break;
    default:
        break;
    }
    return BG_FRONT_NONE;
}

void bg_front_map_controls(const bg_frontend *f, const bg_control_state physical[4],
                           bg_control_state logical[4]) {
    bg_control_state copy[4];
    memcpy(copy, physical, sizeof(copy));
    memset(logical, 0, sizeof(copy));
    for (unsigned p = 0; p < f->count && p < 4; p++)
        if (f->ports[p] < 4)
            logical[p] = copy[f->ports[p]];
}
