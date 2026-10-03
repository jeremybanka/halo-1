#ifndef BG_RENDER_POSE_CACHE_H
#define BG_RENDER_POSE_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "game.h"

/* Raw float representations keep signed zero and every changed input distinct.
 * Two slot bits describe matrix contents, independently of RSP fence ownership. */
typedef struct {
    uint32_t key[9];
    uint8_t last_slot,slot_mask;
    bool valid;
} bg_vehicle_pose_cache;

static inline void bg_vehicle_pose_key(uint32_t key[9],const bg_vehicle*v,const float*wheel){
    _Static_assert(sizeof(float)==4,"Vehicle pose keys require 32-bit floats");
    key[0]=(uint32_t)v->kind;
    memcpy(key+1,v->pos,12);
    memcpy(key+4,&v->yaw,4);memcpy(key+5,&v->pitch,4);
    memcpy(key+6,&v->turret_yaw,4);memcpy(key+7,&v->turret_pitch,4);
    memcpy(key+8,wheel,4);
}
#endif
