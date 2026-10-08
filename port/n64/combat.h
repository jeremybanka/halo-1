#ifndef BG_COMBAT_H
#define BG_COMBAT_H
#include <stdbool.h>
#include <math.h>
/* Compact Xbox damage definitions. Zero keeps legacy/environmental callers
 * explicit while weapon impacts migrate to source-backed profiles. */
typedef enum {BG_D_LEGACY, BG_D_AR, BG_D_PISTOL, BG_D_PLASMA_PISTOL,
    BG_D_PLASMA_RIFLE, BG_D_SHOTGUN, BG_D_SNIPER, BG_D_OVERCHARGE,
    BG_D_MELEE, BG_D_COUNT} bg_damage_kind;
enum {BG_DAMAGE_HEADSHOT=1, BG_DAMAGE_DOUBLE_HEAD=2, BG_DAMAGE_EMP=4, BG_DAMAGE_BACKSTAB=8};
typedef struct {
    float minimum,lower,upper,body,shield,range_start,range_end,speed_start,speed_end,range;
    unsigned flags;
} bg_damage_profile;
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
    if(*shield>0){
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
