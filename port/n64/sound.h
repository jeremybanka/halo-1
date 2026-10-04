#ifndef BG_SOUND_H
#define BG_SOUND_H
#include <stdbool.h>
void bg_sound_frontend(bool active);
void bg_sound_front_effect(unsigned effect);
void bg_sound_init(void);
void bg_sound_update(void);
void bg_sound_pump(void);
void bg_sound_announce(unsigned sound);
#endif
