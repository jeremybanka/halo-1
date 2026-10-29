#ifndef BG_VEHICLE_KINDS_H
#define BG_VEHICLE_KINDS_H
typedef enum { BG_V_WARTHOG, BG_V_GHOST, BG_V_SCORPION, BG_V_BANSHEE,
#ifdef BG_ENEMY_VEHICLES
 BG_V_WRAITH, BG_V_SHADE,
#endif
 BG_VEHICLE_COUNT } bg_vehicle_kind;

static inline unsigned bg_vehicle_hatch_index(unsigned kind){
#ifdef BG_ENEMY_VEHICLES
if(kind==BG_V_WRAITH)return 2;
#endif
return kind==BG_V_BANSHEE;
}

#endif
