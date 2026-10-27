#include "hud_messages.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static bg_notice messages[BG_PLAYERS][BG_NOTICE_SLOTS];
static uint32_t tick, serial;
static const char *const weapon_names[BG_WEAPON_COUNT] = {
    "Assault Rifle", "Pistol", "Plasma Pistol", "Plasma Rifle", "Needler",
    "Shotgun", "Sniper Rifle", "Rocket Launcher", "Flamethrower"
};
const char *bg_hud_weapon_name(unsigned weapon) {
    return weapon < BG_WEAPON_COUNT ? weapon_names[weapon] : "Weapon";
}
int bg_hud_switch_target(const bg_player *p) {
    if (p->health <= 0 || p->weapon_ready > 0 || p->reload > 0 || p->ammo > 0 || p->reserve > 0)
        return -1;
    unsigned other = p->slot ^ 1;
    int weapon = p->inventory[other];
    return weapon >= 0 && weapon < BG_WEAPON_COUNT &&
           p->magazines[other] + p->reserves[other] > 0 ? weapon : -1;
}
void bg_hud_messages_reset(void) {
    memset(messages, 0, sizeof(messages));
    tick = serial = 0;
}
uint8_t bg_hud_message_alpha(const bg_notice *m) {
    unsigned age = tick - m->tick;
    if (!m->serial || age >= BG_NOTICE_UP_TICKS + BG_NOTICE_FADE_TICKS)
        return 0;
    if (age <= BG_NOTICE_UP_TICKS)
        return 255;
    /* Original power-1.9 fade, baked at the fixed 30 Hz message cadence.
     * No powf/exp/log work in the four-player draw path. */
    static const uint8_t fade[61] = {
        255,247,239,231,224,216,209,201,194,187,180,174,167,160,154,148,
        141,135,129,124,118,112,107,102,97,92,87,82,77,73,68,64,
        60,56,52,48,45,41,38,35,32,29,26,23,21,18,16,14,
        12,10,8,7,6,4,3,2,1,1,0,0,0,
    };
    return fade[age - BG_NOTICE_UP_TICKS];
}
static void add(unsigned player, bg_notice m) {
    if (player >= bg_player_count())
        return;
    bg_notice *slot = NULL, *oldest = &messages[player][0];
    for (unsigned i = 0; i < BG_NOTICE_SLOTS; i++) {
        bg_notice *q = &messages[player][i];
        bool live = q->serial && tick - q->tick < BG_NOTICE_UP_TICKS + BG_NOTICE_FADE_TICKS;
        if (live && (m.kind == BG_NOTICE_AMMO || m.kind == BG_NOTICE_ITEM) &&
            q->kind == m.kind && q->item == m.item) {
            unsigned quantity = q->quantity + m.quantity;
            m.quantity = quantity > UINT16_MAX ? UINT16_MAX : quantity;
            slot = q;
            break;
        }
        if (!live && !slot)
            slot = q;
        if (q->serial < oldest->serial)
            oldest = q;
    }
    m.tick = tick;
    m.serial = ++serial;
    *(slot ? slot : oldest) = m;
}
void bg_hud_messages_update(void) {
    uint32_t now = (uint32_t)lroundf(bg_match_time() * 30.f);
    if (now < tick)
        bg_hud_messages_reset();
    tick = now;
    for (unsigned i = 0; i < bg_event_count; i++) {
        const bg_event *e = &bg_events[i];
        bg_notice m = {.item = (uint8_t)e->weapon, .quantity = 1};
        switch (e->kind) {
        case BG_EVENT_OBJECTIVE:
            m.kind = BG_NOTICE_OBJECTIVE;
            m.actor = e->player < 0 ? UINT8_MAX : (uint8_t)e->player;
            m.quantity = (uint16_t)e->amount;
            for(unsigned p=0;p<bg_player_count();p++)add(p,m);
            continue;
        case BG_EVENT_PICKUP:
            m.kind = e->weapon < BG_WEAPON_COUNT ? BG_NOTICE_WEAPON : BG_NOTICE_ITEM;
            m.quantity = (uint16_t)e->amount;
            break;
        case BG_EVENT_AMMO:
            m.kind = BG_NOTICE_AMMO;
            m.quantity = (uint16_t)e->amount;
            break;
        case BG_EVENT_KILL:
            m.kind = BG_NOTICE_KILL;
            m.actor = e->player < 0 ? UINT8_MAX : (uint8_t)e->player;
            m.victim = (uint8_t)e->weapon;
            for (unsigned p = 0; p < bg_player_count(); p++)
                add(p, m);
            continue;
        case BG_EVENT_DOUBLE_KILL: m.kind = BG_NOTICE_DOUBLE; break;
        case BG_EVENT_TRIPLE_KILL:
            m.kind = BG_NOTICE_TRIPLE;
            m.quantity = (uint16_t)e->amount;
            break;
        case BG_EVENT_KILLING_SPREE: m.kind = BG_NOTICE_SPREE; break;
        default: continue;
        }
        if (e->player >= 0 && e->amount > 0)
            add((unsigned)e->player, m);
    }
}
unsigned bg_hud_messages_get(unsigned player, bg_notice out[BG_NOTICE_SLOTS]) {
    unsigned count = 0;
    if (player >= bg_player_count())
        return 0;
    for (unsigned i = 0; i < BG_NOTICE_SLOTS; i++) {
        const bg_notice *m = &messages[player][i];
        if (!m->serial || tick - m->tick >= BG_NOTICE_UP_TICKS + BG_NOTICE_FADE_TICKS)
            continue;
        unsigned at = count++;
        while (at && out[at - 1].serial < m->serial) {
            out[at] = out[at - 1];
            at--;
        }
        out[at] = *m;
    }
    return count;
}
void bg_hud_message_text(unsigned viewer, const bg_notice *m, char *out, size_t size) {
    const char *name = bg_hud_weapon_name(m->item);
    switch (m->kind) {
    case BG_NOTICE_OBJECTIVE: {
        const char *object=m->item==BG_OBJECTIVE_FLAG?"Flag":m->item==BG_OBJECTIVE_BALL?"Ball":
                           m->item==BG_OBJECTIVE_HILL?"Hill":"Checkpoint";
        const char *action=m->quantity==BG_OBJECTIVE_TAKEN?"taken":m->quantity==BG_OBJECTIVE_DROPPED?"dropped":
                           m->quantity==BG_OBJECTIVE_RETURNED?"returned":m->quantity==BG_OBJECTIVE_SCORED?"scored":
                           m->quantity==BG_OBJECTIVE_MOVED?"moved":"reached";
        if(m->actor<bg_player_count())snprintf(out,size,"P%u: %s %s",bg_player_profiles[m->actor]+1,object,action);
        else snprintf(out,size,"%s %s",object,action);
        break;
    }
    case BG_NOTICE_WEAPON: snprintf(out, size, "+ %s", name); break;
    case BG_NOTICE_AMMO: snprintf(out, size, "+%u %s", m->quantity, name); break;
    case BG_NOTICE_ITEM:
        if (m->item == BG_PICK_FRAG || m->item == BG_PICK_PLASMA)
            snprintf(out, size, "+%u %s Grenade%s", m->quantity,
                     m->item == BG_PICK_FRAG ? "Frag" : "Plasma", m->quantity == 1 ? "" : "s");
        else
            snprintf(out, size, "+ %s", m->item == BG_PICK_HEALTH ? "Health Pack" :
                     m->item == BG_PICK_OVERSHIELD ? "Overshield" : "Active Camo");
        break;
    case BG_NOTICE_KILL: {
        unsigned v = m->victim, a = m->actor;
        if (v >= bg_player_count()) { out[0] = 0; break; }
        unsigned victim = bg_player_profiles[v] + 1;
        if (a >= bg_player_count())
            snprintf(out, size, "Player %u died", victim);
        else if (a == v)
            snprintf(out, size, "Player %u committed suicide", victim);
        else if (a == viewer)
            snprintf(out, size, "You killed Player %u", victim);
        else
            snprintf(out, size, "Player %u killed Player %u", bg_player_profiles[a] + 1, victim);
        break;
    }
    case BG_NOTICE_DOUBLE: snprintf(out, size, "Double Kill!"); break;
    case BG_NOTICE_TRIPLE:
        snprintf(out, size, "%s", m->quantity >= 4 ? "Killtacular!" : "Triple Kill!");
        break;
    case BG_NOTICE_SPREE: snprintf(out, size, "Killing Spree!"); break;
    default: out[0] = 0; break;
    }
}
