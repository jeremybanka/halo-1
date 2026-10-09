#ifndef BG_PICKUP_RULES_H
#define BG_PICKUP_RULES_H
#include <stdint.h>
typedef struct {int16_t loaded,reserve,maximum_reserve;} bg_ammo_rule;
typedef struct {float pos[3],yaw;uint16_t period;int8_t kind[2];uint8_t first_weight,total_weight;} bg_map_item;
extern const bg_ammo_rule bg_ammo_rules[9];
extern const uint8_t bg_slayer_spawns[];
extern const bg_map_item bg_map_items[];
extern const unsigned bg_map_item_count;
extern const int bg_start_weapons[2],bg_start_grenades[2];
extern const float bg_camo_duration;
float bg_spawn_rating(unsigned player,unsigned index);
int bg_select_spawn(unsigned player);
void bg_pickup_mark_visible(unsigned index);
#endif
