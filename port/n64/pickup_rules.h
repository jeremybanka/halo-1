#ifndef BG_PICKUP_RULES_H
#define BG_PICKUP_RULES_H
#include <stdint.h>
typedef struct {int16_t loaded,reserve,maximum_reserve;} bg_ammo_rule;
typedef struct {float pos[3],yaw;uint16_t period;int8_t kind[2];uint8_t first_weight,total_weight;} bg_map_item;
_Static_assert(sizeof(bg_map_item)==24,"HM64 item stride");
/* HM64's final two item bytes were reserved. A nonzero second weight now
 * adds a third choice: byte 22 is its kind, byte 23 the second choice weight.
 * Existing banks have zero tails and retain their original two-choice path. */
static inline unsigned bg_map_item_third(const bg_map_item*m){return ((const uint8_t*)m)[22];}
static inline unsigned bg_map_item_second_weight(const bg_map_item*m){return ((const uint8_t*)m)[23];}
extern const bg_ammo_rule bg_ammo_rules[9];
#ifdef BG_STREAM_MAPS
extern const uint8_t *bg_slayer_spawns;
extern const bg_map_item *bg_map_items;
extern unsigned bg_map_item_count;
extern const int *bg_start_weapons, *bg_start_grenades;
#else
extern const uint8_t bg_slayer_spawns[];
extern const bg_map_item bg_map_items[];
extern const unsigned bg_map_item_count;
extern const int bg_start_weapons[2],bg_start_grenades[2];
#endif
extern const float bg_camo_duration;
float bg_spawn_rating(unsigned player,unsigned index);
int bg_select_spawn(unsigned player);
void bg_pickup_mark_visible(unsigned index);
#endif
