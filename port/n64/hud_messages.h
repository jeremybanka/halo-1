#ifndef BG_HUD_MESSAGES_H
#define BG_HUD_MESSAGES_H
#include "game.h"
#include <stddef.h>
#include <stdint.h>
/* Presentation-only bounded receipts: never change inventory, RNG or physics.
 * Feed once immediately after each tick, including catch-up ticks. */
enum { BG_NOTICE_SLOTS = 4, BG_NOTICE_UP_TICKS = 60, BG_NOTICE_FADE_TICKS = 60 };
typedef enum {
    BG_NOTICE_WEAPON, BG_NOTICE_AMMO, BG_NOTICE_ITEM, BG_NOTICE_KILL,
    BG_NOTICE_DOUBLE, BG_NOTICE_TRIPLE, BG_NOTICE_SPREE, BG_NOTICE_OBJECTIVE
} bg_notice_kind;
typedef struct {
    uint32_t tick, serial;
    uint16_t quantity;
    uint8_t kind, item, actor, victim;
} bg_notice;
void bg_hud_messages_reset(void);
void bg_hud_messages_update(void);
unsigned bg_hud_messages_get(unsigned player, bg_notice out[BG_NOTICE_SLOTS]);
uint8_t bg_hud_message_alpha(const bg_notice *message);
void bg_hud_message_text(unsigned viewer, const bg_notice *message, char *out, size_t size);
const char *bg_hud_weapon_name(unsigned weapon);
int bg_hud_switch_target(const bg_player *player);
#endif
