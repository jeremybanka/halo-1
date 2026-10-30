#ifndef BG_DAMAGE_FLASH_H
#define BG_DAMAGE_FLASH_H
#include "game.h"
#include "combat.h"
typedef struct {
    float duration, maximum, zero_scale;
    uint8_t type,priority,fade,color[4];
} bg_damage_flash_definition;
extern const bg_damage_flash_definition bg_damage_flashes[BG_D_COUNT];
extern const uint8_t bg_damage_fades[6][1024];
static inline float bg_damage_flash_intensity(const bg_player *p) {
    if(p->damage_flash_time<=0)return 0;
    const bg_damage_flash_definition *d=&bg_damage_flashes[p->damage_flash_profile];
    float value=p->damage_flash_strength;
    if(d->duration>0)value*=p->damage_flash_time/d->duration;
    value=fmaxf(0,fminf(1,value));
    if(!d->fade)return value;
    float index=value*1023;unsigned n=(unsigned)index;
    if(n>=1023)return bg_damage_fades[d->fade][1023]/255.f;
    return (bg_damage_fades[d->fade][n]*(1-(index-n))+bg_damage_fades[d->fade][n+1]*(index-n))/255.f;
}
static inline void bg_damage_flash_start(bg_player *p,unsigned profile,float scale) {
    if(profile>=BG_D_COUNT)profile=BG_D_LEGACY;
    const bg_damage_flash_definition *d=&bg_damage_flashes[profile];
    if(!d->type)return;
    const bg_damage_flash_definition *old=&bg_damage_flashes[p->damage_flash_profile];
    if(old->priority>d->priority&&p->damage_flash_time>d->duration)return;
    p->damage_flash_profile=profile;
    /* Zero-duration tags are still displayed once (the source just-started bit). */
    p->damage_flash_time=fmaxf(1.f/30,d->duration);
    p->damage_flash_strength=fminf(d->maximum,fmaxf(0,d->zero_scale+(1-d->zero_scale)*scale));
}
#endif
