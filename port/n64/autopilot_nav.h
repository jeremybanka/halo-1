#ifndef BG_AUTOPILOT_NAV_H
#define BG_AUTOPILOT_NAV_H
#include <stdbool.h>
#include <stdint.h>
#define BG_NAV_NONE UINT16_MAX
/* One selected-map graph; one bounded search service shared fairly by four
 * humans. Published paths remain usable while a new request is pending. */
void bg_autonav_reset(void);
bool bg_autonav_load(void);
void bg_autonav_service(void);
uint16_t bg_autonav_node(const float position[3]);
void bg_autonav_position(uint16_t node,float position[3]);
uint16_t bg_autonav_goal(const float origin[3],const float direction[3],float distance);
void bg_autonav_request(unsigned player,uint16_t start,uint16_t goal);
void bg_autonav_cancel(unsigned player);
bool bg_autonav_waypoint(unsigned player,const float position[3],float out[3],bool *jump);
unsigned bg_autonav_memory(void);
unsigned bg_autonav_work(void);
#endif
