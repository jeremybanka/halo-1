#ifndef BG_CADENCE_TAIL_H
#define BG_CADENCE_TAIL_H
#include "cadence.h"

#define BG_CADENCE_TAIL_COUNT 8
_Static_assert(sizeof(unsigned)==4,"Cadence metadata requires32-bit unsigned");
typedef struct {
    unsigned sim_ms,triangles,vertices,category_triangles[6];
    /* Four bits each: mounted players, zoomed players, dead players. */
    uint16_t vehicle_mask,zoom_mask,dead_mask;
} bg_cadence_frame;
typedef struct {
    unsigned elapsed;
    bg_cadence_frame frame;
} bg_cadence_tail_entry;
typedef struct {
    unsigned count;
    bg_cadence_tail_entry entry[BG_CADENCE_TAIL_COUNT];
} bg_cadence_tail;

static inline void bg_cadence_tail_add(bg_cadence_tail*t,uint32_t elapsed,const bg_cadence_frame*f){
    if(t->count==BG_CADENCE_TAIL_COUNT&&elapsed<=t->entry[t->count-1].elapsed)return;
    unsigned i=t->count<BG_CADENCE_TAIL_COUNT?t->count++:BG_CADENCE_TAIL_COUNT-1;
    while(i&&elapsed>t->entry[i-1].elapsed){t->entry[i]=t->entry[i-1];i--;}
    t->entry[i]=(bg_cadence_tail_entry){elapsed,*f};
}

/* Tail metadata is copied before cadence's release publication. Main-thread
 * readers may inspect both banks only after bg_cadence_complete(). Ordinary
 * measured frames need one threshold comparison once the eight slots fill;
 * a new worst interval moves at most seven fixed-size entries. */
static inline void bg_cadence_record_with_tail(bg_cadence*c,bg_cadence_tail*t,
        uint64_t now,unsigned vehicle,const bg_cadence_frame*f){
    if(!c->complete&&c->started&&c->previous>=c->origin+BG_CADENCE_WARMUP_US)
        bg_cadence_tail_add(t,(uint32_t)(now-c->previous),f);
    bg_cadence_record(c,now,vehicle);
}
#endif
