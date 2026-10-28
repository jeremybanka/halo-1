#ifndef BG_PVE_H
#define BG_PVE_H
#include <stdint.h>
#include <stdbool.h>
#define BG_PVE_MAX 8
enum { BG_PVE_GRUNT, BG_PVE_ELITE };
enum { PVE_IDLE, PVE_RUN, PVE_FIRE, PVE_DEATH, PVE_FLEE, PVE_MELEE, PVE_CLIPS };
typedef struct {
    unsigned body_material,shield_material;
    float health,shield,height,radius,eye,gun[3],vision,vision_angle,notice;
    float range,rate,error,damage_scale,desired[2],first_delay[2],burst[2],pause[2];
    float panic_damage,leader_panic,cower[2],hide_shield,emerge_shield,hide[2],evade_delay;
    float melee_range,melee_delay,berserk_damage,berserk_threshold,shield_delay,shield_recharge;
    float move_speed,flee_speed,melee_damage[2],melee_key,melee_duration;
    float damage[26][2];
} bg_pve_definition;
extern const bg_pve_definition bg_pve_definitions[2];
typedef struct {
    uint8_t kind,clip,action; int8_t target;
    float time,decision_time,notice_time,burst_time,burst_pause,shot_time,panic_time,cover_time;
    float last_seen[3],destination[3],previous[3],stuck_time,melee_time,recent_damage;
    unsigned shots,decisions,los_tests,path_queries,kills;
    bool visible,aware,berserk,melee_pending;
} bg_pve_actor;
extern bg_pve_actor bg_pve_actors[BG_PVE_MAX];
extern unsigned bg_pve_count,bg_pve_tick_number;
extern uint32_t bg_pve_ai_us,bg_pve_move_us;
extern unsigned bg_pve_animation_us;
void bg_pve_start(unsigned count);
void bg_pve_stop(void);
void bg_pve_tick(float dt);
void bg_pve_stage(unsigned players);
void bg_pve_qa_input(void *inputs);
float bg_pve_height(const void *player);
float bg_pve_hit_ray(unsigned unit,const float origin[3],const float direction[3],float distance,int *region);
bool bg_pve_is_active(void);
#endif
