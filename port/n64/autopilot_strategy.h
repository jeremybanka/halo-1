#ifndef BG_AUTOPILOT_STRATEGY_H
#define BG_AUTOPILOT_STRATEGY_H
#include <stdbool.h>
typedef struct { bool retreat,charge,evade; float near_range,far_range; } bg_autopilot_strategy;
void bg_autopilot_strategy_reset(unsigned player);
bg_autopilot_strategy bg_autopilot_decide(unsigned player,bool panic,bool visible,
    bool aware,bool danger,float recent_damage);
#endif
