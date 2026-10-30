#ifndef BG_FIREFIGHT_FIGHTS_H
#define BG_FIREFIGHT_FIGHTS_H
enum { BG_FF_ONSLAUGHT, BG_FF_GAUNTLET, BG_FF_FIGHTS };
static inline const char *bg_ff_fight_name(unsigned fight) {
    return fight == BG_FF_GAUNTLET ? "Gauntlet" : "Onslaught";
}
static inline int bg_ff_fight_available(unsigned fight) {
    return fight == BG_FF_ONSLAUGHT
#ifdef BG_PVE_ROSTER
        || fight == BG_FF_GAUNTLET
#endif
        ;
}
#endif
