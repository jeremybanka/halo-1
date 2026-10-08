#ifndef BG_RENDER_POSE_CACHE_H
#define BG_RENDER_POSE_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "game.h"

/* Raw float representations keep signed zero and every changed input distinct.
 * Two slot bits describe matrix contents, independently of RSP fence ownership. */
#define BG_VEHICLE_POSE_WORDS 27
typedef struct {
    uint32_t key[BG_VEHICLE_POSE_WORDS];
    uint8_t last_slot,slot_mask;
    bool valid;
} bg_vehicle_pose_cache;

static inline void bg_vehicle_pose_key(uint32_t key[BG_VEHICLE_POSE_WORDS],const bg_vehicle*v,const float*wheel){
    _Static_assert(sizeof(float)==4,"Vehicle pose keys require 32-bit floats");
    key[0]=(uint32_t)v->kind|((uint32_t)!v->active<<8);
    memcpy(key+1,v->pos,12);
    memcpy(key+4,&v->yaw,4);memcpy(key+5,&v->pitch,4);
    memcpy(key+6,&v->turret_yaw,4);memcpy(key+7,&v->turret_pitch,4);
    memcpy(key+8,wheel,4);
    key[9]=v->physics_valid;memcpy(key+10,v->forward,12);memcpy(key+13,v->up,12);
    memcpy(key+16,&v->steering,4);memcpy(key+17,v->suspension,32);
    memcpy(key+25,&v->hatch,4);key[26]=v->hatch_closing;
}
#endif
