#ifndef BG_JACKAL_SHIELD_FLASH_H
#define BG_JACKAL_SHIELD_FLASH_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {float previous;uint32_t tick;uint16_t generation;bool active;} bg_jackal_flash;
static float bg_jackal_flash_step(bg_jackal_flash*s,uint16_t generation,float shield,float hurt,uint32_t tick){
    if(s->generation!=generation){*s=(bg_jackal_flash){.previous=shield,.generation=generation};return 0;}
    if(shield<s->previous&&hurt>0){s->active=true;s->tick=tick-(uint32_t)((.65f-hurt)*30);}
    s->previous=shield;
    unsigned age=tick-s->tick;if(age>=20)s->active=false;
    return s->active?1-(float)age/20:0;
}
#endif
