#ifndef BG_COMBAT_H
#define BG_COMBAT_H
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
/* Compact Xbox damage definitions. Zero keeps legacy/environmental callers
 * explicit while weapon impacts migrate to source-backed profiles. */
typedef enum {BG_D_LEGACY, BG_D_AR, BG_D_PISTOL, BG_D_PLASMA_PISTOL,
    BG_D_PLASMA_RIFLE, BG_D_SHOTGUN, BG_D_SNIPER, BG_D_OVERCHARGE,
    BG_D_MELEE, BG_D_FRAG, BG_D_PLASMA_GRENADE, BG_D_ROCKET, BG_D_NEEDLE, BG_D_SUPERCOMBINE, BG_D_STICK, BG_D_FALL, BG_D_DISTANCE, BG_D_COUNT} bg_damage_kind;
enum {BG_DAMAGE_HEADSHOT=1, BG_DAMAGE_DOUBLE_HEAD=2, BG_DAMAGE_EMP=4, BG_DAMAGE_BACKSTAB=8, BG_DAMAGE_SKIP_SHIELDS=16};
typedef struct {
    float minimum,lower,upper,body,shield,range_start,range_end,speed_start,speed_end,range;
    float falloff,cutoff,core,stun,stun_max,stun_time;
    unsigned flags;
} bg_damage_profile;
typedef struct {
    float rate_min,rate_max,rate_up,rate_down,error_up,error_down;
    float cone_min,cone_max,cone_inner,charge_time;
    uint16_t reload_full,reload_empty,reload_enter,melee_frames,melee_key;
    bool zoom_accurate,automatic;
} bg_trigger_profile;
typedef struct {float arming,fuse,gravity,parallel,perpendicular;} bg_grenade_profile;
extern const bg_grenade_profile bg_grenade_profiles[2];
extern const float bg_needle_fuse,bg_needle_turn,bg_needle_range;
extern const float bg_fall_distances[3],bg_stun_config[5];
extern const bg_trigger_profile bg_trigger_profiles[9];
static inline float bg_trigger_step(float value,float delta){return fminf(1,fmaxf(0,value+delta));}
static inline float bg_melee_duration(unsigned weapon){unsigned n=bg_trigger_profiles[weapon].melee_frames;return (n-(n>>2))/30.f;}
/* Uniform angle around a uniformly distributed azimuth. Unlike a Cartesian
 * cube perturbation this distribution is independent of camera orientation. */
static inline void bg_combat_cone(const float axis[3],float inner,float outer,float azimuth,float radial,float out[3]){
    float right[3]={-axis[2],0,axis[0]},n=hypotf(right[0],right[2]);
    if(n<1e-6f){right[0]=1;right[2]=0;}else{right[0]/=n;right[2]/=n;}
    float up[3]={axis[1]*right[2],axis[2]*right[0]-axis[0]*right[2],-axis[1]*right[0]};
    float angle=inner+(outer-inner)*radial,phi=azimuth*6.283185307f;
    for(unsigned k=0;k<3;k++)out[k]=axis[k]*cosf(angle)+(right[k]*cosf(phi)+up[k]*sinf(phi))*sinf(angle);
}
extern const bg_damage_profile bg_damage_profiles[BG_D_COUNT];
extern const float bg_combat_body_max,bg_combat_shield_max,bg_combat_leg_scale;
static inline float bg_combat_amount(const bg_damage_profile*d,float scale,float random){
    return (1-scale)*d->minimum+(d->lower+(d->upper-d->lower)*random)*scale;
}
/* Constant-deceleration velocity over the source damage range. Hitscan bullets
 * retain the demake's instantaneous travel; this recovers impact energy. */
static inline float bg_combat_range_scale(const bg_damage_profile*d,float distance){
    if(d->speed_start==d->speed_end||d->range_end<=d->range_start)return 1;
    float t=fminf(1,fmaxf(0,(distance-d->range_start)/(d->range_end-d->range_start)));
    float speed=sqrtf(d->speed_start*d->speed_start+(d->speed_end*d->speed_end-d->speed_start*d->speed_start)*t);
    return fminf(1,fmaxf(0,(speed-d->speed_end)/(d->speed_start-d->speed_end)));
}
/* Adapted from object_damage_shield/body in source/objects/damage.c.
 * Keep normalized float subtraction and the original excess-damage units.
 * Headshot handling only runs when damage actually reaches the body. */
static inline float bg_combat_apply(const bg_damage_profile*d,float amount,bool head,bool legs,
        bool behind,float*shield,float*health){
    float body=amount;
    if((d->flags&BG_DAMAGE_BACKSTAB)&&behind){*shield=*health=0;return 100;}
    if(*shield>0&&!(d->flags&BG_DAMAGE_SKIP_SHIELDS)){
        float vitality=*shield/100.f,actual=amount*d->shield;
        float normalized=actual*(1.f/bg_combat_shield_max);
        body=0;
        if(normalized>vitality||(d->flags&BG_DAMAGE_EMP)){
            body=fmaxf(0,actual-bg_combat_shield_max*vitality);*shield=0;
        }else *shield=(vitality-normalized)*100.f;
    }
    float multiplier=legs?bg_combat_leg_scale:1;
    float normalized=body*multiplier*(1.f/bg_combat_body_max)*d->body;
    if(body>0&&head){
        if(d->flags&BG_DAMAGE_HEADSHOT){*health=0;return 100;}
        if(d->flags&BG_DAMAGE_DOUBLE_HEAD)normalized*=2;
    }
    *health=fmaxf(0,(*health/100.f-normalized)*100.f);
    return normalized*100.f;
}
#endif
