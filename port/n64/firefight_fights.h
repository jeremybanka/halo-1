#ifndef BG_FIREFIGHT_FIGHTS_H
#define BG_FIREFIGHT_FIGHTS_H
#include "map.h"
enum { BG_FF_ONSLAUGHT, BG_FF_GAUNTLET, BG_FF_COURTYARD, BG_FF_STATION_SWEEP, BG_FF_FIGHTS };
static inline const char *bg_ff_fight_name(unsigned fight) {
    static const char*const names[]={"Onslaught","Gauntlet","Courtyard Defense","Station Sweep"};
    return fight<BG_FF_FIGHTS?names[fight]:"Firefight";
}
static inline int bg_ff_casual(unsigned fight){return fight==BG_FF_COURTYARD||fight==BG_FF_STATION_SWEEP;}
static inline unsigned bg_ff_fight_map(unsigned fight){return fight==BG_FF_COURTYARD?BG_MAP_BATTLE_CREEK: fight==BG_FF_STATION_SWEEP?BG_MAP_RAT_RACE:BG_MAP_BLOOD_GULCH;}
static inline unsigned bg_ff_default_fight(unsigned map){return map==BG_MAP_BATTLE_CREEK?BG_FF_COURTYARD:map==BG_MAP_RAT_RACE?BG_FF_STATION_SWEEP:BG_FF_ONSLAUGHT;}
static inline int bg_ff_map_available(unsigned map){return map==BG_MAP_BLOOD_GULCH||map==BG_MAP_BATTLE_CREEK||map==BG_MAP_RAT_RACE;}
static inline int bg_ff_fight_available(unsigned fight) {
    return fight == BG_FF_ONSLAUGHT || bg_ff_casual(fight)
#ifdef BG_PVE_ROSTER
        || fight == BG_FF_GAUNTLET
#endif
        ;
}
static inline int bg_ff_fight_on_map(unsigned map,unsigned fight){return bg_ff_map_available(map)&&bg_ff_fight_available(fight)&&bg_ff_fight_map(fight)==map;}
#endif
