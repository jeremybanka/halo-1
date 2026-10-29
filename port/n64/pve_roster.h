#ifndef BG_PVE_ROSTER_H
#define BG_PVE_ROSTER_H
#include "pve.h"
enum {PVE_R_DEFAULT,PVE_R_GRUNT_MAJOR_PP,PVE_R_GRUNT_MAJOR_ND,PVE_R_ELITE_MAJOR_PR,
 PVE_R_ELITE_MAJOR_ND,PVE_R_JACKAL_MAJOR,PVE_R_GRUNT_SPECOPS_ND,PVE_R_GRUNT_FUEL,
 PVE_R_ELITE_SPECOPS_PR,PVE_R_ELITE_SPECOPS_ND,PVE_R_ZEALOT_PR,PVE_R_ZEALOT_SWORD,
 PVE_R_STEALTH_PR,PVE_R_STEALTH_MAJOR_PR,PVE_R_STEALTH_SWORD,PVE_R_COUNT};
enum {PVE_ARM_NORMAL,PVE_ARM_FUEL,PVE_ARM_SWORD};
enum {PVE_R_CAMO=1,PVE_R_SUPER_CAMO=2,PVE_R_NO_RANGED=4};
enum {PVE_V_SPOT,PVE_V_COMBAT,PVE_V_IDLE,PVE_V_PANIC,PVE_V_PAIN,PVE_V_DEATH,
 PVE_V_GRENADE,PVE_V_KILL,PVE_V_LEADER,PVE_V_FUEL_FIRE,PVE_V_SWORD_SWING,PVE_V_FUEL_EXPLOSION,PVE_V_COUNT};
typedef struct {
 const char *name;bg_pve_definition def;
 uint8_t kind,weapon,rank,armament,flags;
 float tint[3],strike_reach,melee_radius,melee_material[33];
} bg_pve_variant;
extern const bg_pve_variant bg_pve_variants[PVE_R_COUNT];
extern const bg_pve_fuel bg_pve_grunt_fuel,bg_pve_dropped_fuel;
extern const float bg_pve_fuel_drop_delay[2],bg_pve_sword_drop_delay[2];
extern const float bg_pve_camo_damage[26];
extern const bg_pve_animation bg_pve_alt_hit_clips[2][12];
typedef struct {uint32_t offset,bytes;uint8_t kind,event;} bg_pve_voice;
extern const bg_pve_voice bg_pve_voices[];
extern const unsigned bg_pve_voice_count;
void bg_pve_set_variant(unsigned actor,unsigned variant);
#endif
