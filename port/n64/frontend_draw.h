#ifndef BG_FRONTEND_DRAW_H
#define BG_FRONTEND_DRAW_H
#include "frontend.h"
void bg_front_draw(const bg_frontend *f,uint64_t now);
/* Call only after the previous display work has completed. */
void bg_front_draw_release(void);
#endif
