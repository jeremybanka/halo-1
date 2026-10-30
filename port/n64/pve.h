#ifndef BG_PVE_H
#define BG_PVE_H
#include <stdint.h>
#include <stdbool.h>
#include "firefight.h"
#define BG_PVE_MAX 12
enum { BG_PVE_GRUNT, BG_PVE_ELITE, BG_PVE_JACKAL, BG_PVE_HUNTER, BG_PVE_KINDS, BG_PVE_SPIRIT=BG_PVE_KINDS, BG_PVE_MODELS };
enum { PVE_IDLE, PVE_RUN, PVE_FIRE, PVE_DEATH, PVE_FLEE, PVE_MELEE, PVE_THROW, PVE_EVADE_LEFT, PVE_EVADE_RIGHT, PVE_RIDE, PVE_EXIT, PVE_CROUCH,
#ifdef BG_PVE_ROSTER
 PVE_CLIPS=24
#else
 PVE_CLIPS=12
#endif
};
typedef struct { const uint16_t *positions,*indices; unsigned frames,vertices,tracks;float duration;int16_t origin[3]; } bg_pve_animation;
typedef struct {uint8_t material,head;float leak,shield_scale,body_scale;float damage[26];} bg_pve_hit_material;
typedef struct {const uint16_t (*triangles)[3];const uint8_t *materials;unsigned triangles_count;const bg_pve_animation *clips;const bg_pve_hit_material *rules;unsigned material_count;} bg_pve_hit_mesh;
extern const bg_pve_hit_mesh bg_pve_hits[BG_PVE_KINDS];
typedef struct {
    unsigned body_material,shield_material,indirect_material;
    float health,shield,height,radius,eye,gun[3],vision,vision_angle,notice;
    float range,rate,error,damage_scale,desired[2],first_delay[2],burst[2],pause[2];
    float panic_damage,leader_panic,cower[2],hide_shield,emerge_shield,hide[2],evade_delay;
    float melee_range,melee_delay,berserk_damage,berserk_threshold,shield_delay,shield_recharge;
    float move_speed,flee_speed,melee_damage[2],melee_key,melee_duration;
    float pursue_shield,grenade_chance,grenade_check,grenade_timeout,grenade_range[2],grenade_speed,grenade_collateral,grenade_radius;
    float throw_key,throw_duration,evade_duration,exit_duration,fire_key,fire_duration,turn_rate;
    uint8_t grenade_stimulus,grenade_minimum;
    float evade_cover_chance,drop_loaded[2],no_grenade_drop;uint8_t grenade_count[2];
    float damage[26][2];
} bg_pve_definition;
extern const bg_pve_definition bg_pve_definitions[BG_PVE_KINDS],bg_pve_needler_definitions[2];
typedef struct {float damage,vitality,shield,recharge,rate,error,first_delay,pause,melee_delay,grenade_chance,grenade_timer;} bg_pve_difficulty;
extern const bg_pve_difficulty bg_pve_difficulties[4];
typedef struct {float speed,gravity,damage,radius,charge,minimum,falloff;float material_damage[33];} bg_pve_fuel;
extern const bg_pve_fuel bg_pve_fuel_rod;
extern const float bg_spirit_seats[8][3];
extern const uint8_t bg_pve_needle_reflect[33];
extern const float bg_pve_needle_noise[33],bg_pve_needle_friction[33];
typedef struct {
    uint8_t kind,clip,action; int8_t target;
#ifdef BG_ENEMY_VEHICLES
    int8_t desired_vehicle;
    uint8_t vehicle_mode,vehicle_special_denials;
    float vehicle_cooldown,vehicle_timer,vehicle_special_delay,vehicle_target_time,oversteer,avoidance[3],vehicle_goal[3];
#endif
    float time,decision_time,notice_time,burst_time,burst_pause,shot_time,panic_time,cover_time;
    float last_seen[3],destination[3],previous[3],stuck_time,melee_time,recent_damage;
    unsigned shots,decisions,los_tests,path_queries,kills;
    bool visible,aware,berserk,melee_pending;
    uint8_t rank,formation,arrival;uint16_t generation;
    float evade_time,evade_cooldown,evade_dir[3],grenade_time,throw_target[3],fire_time,death_time;
    float contribution[4],entry_goal[3];unsigned grenades;
    bool throw_pending,fire_pending,occupied,last_headshot;uint8_t last_profile;
#ifdef BG_PVE_ROSTER
    uint8_t variant,armament;float camouflage,super_camouflage,speech_delay,death_weapon_time;
    uint32_t speech_sequence;bool weapon_detonated;
#endif
} bg_pve_actor;
static inline unsigned bg_pve_render_clip(const bg_pve_actor *a){
#ifdef BG_PVE_ROSTER
 return a->clip+(a->armament?12:0);
#else
 return a->clip;
#endif
}
extern bg_pve_actor bg_pve_actors[BG_PVE_MAX];
extern unsigned bg_pve_count,bg_pve_tick_number;
extern uint32_t bg_pve_ai_us,bg_pve_move_us,bg_pve_nav_us;
typedef struct {unsigned requests,ready,shared,fields,evictions,searches,expanded,committed,work,max_work,completed,wait_ticks,max_wait,service_us,max_us;} bg_pve_navigation_profile;
extern bg_pve_navigation_profile bg_pve_navigation;
extern unsigned bg_pve_animation_us;
void bg_pve_start(unsigned count);
void bg_pve_stop(void);
void bg_pve_tick(float dt);
void bg_pve_stage(unsigned players);
void bg_pve_qa_input(void *inputs);
void bg_ff_qa_stage(unsigned players,unsigned fixture);
float bg_pve_height(const void *player);
float bg_pve_hit_ray(unsigned unit,const float origin[3],const float direction[3],float distance,int *region);
bool bg_pve_is_active(void);
#endif
