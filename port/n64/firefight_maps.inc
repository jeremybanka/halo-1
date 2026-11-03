/* Authored encounter entrances. Y selects the intended floor; stage masks
 * restrict Station Sweep's approaches as the team moves through the station. */
typedef struct {const char*name;float x,z,yaw,y,radius;unsigned stages;} ff_zone;
typedef struct {const char*name;float point[3],yaw;} ff_stage;
typedef struct {
    unsigned map;const ff_zone*zones;unsigned zone_count;
    const ff_stage*stages;unsigned stage_count;float enemy_separation;
    bool dropships,vehicles;
} ff_map_definition;
static const ff_zone ff_blood_zones[]={
    {"west rocks",-16,-8,0,0,0,0},{"east rocks",16,9,3.14159265f,0,0,0},
    {"north approach",-5,-23,-1.5707963f,0,0,0},{"south approach",6,24,1.5707963f,0,0,0},
    {"blue base flank",-27,-32,-.7f,0,0,0},{"red base flank",27,32,2.4f,0,0,0}
};
static const ff_zone ff_creek_zones[]={
    {"west wall north",-4,-19,0,-.2f,2,1},
    {"west wall south",-4,-8,0,-.2f,2,1},
    {"west base north",4,-21,1.57f,-.2f,2,1},
    {"west base south",5,-7,-1.57f,-.2f,2,1},
    {"creek west bank",11,-13,3.14f,-.2f,1,1},
    {"east wall north",32,-19,3.14f,-.2f,2,1},
    {"east wall south",32,-8,3.14f,-.2f,2,1},
    {"east base north",24,-21,1.57f,-.2f,2,1},
    {"east base south",24,-6,-1.57f,-.2f,2,1}
};
static const ff_stage ff_creek_stages[]={{"Courtyard",{8,-.20f,-18},3.14159265f}};
static const ff_zone ff_station_zones[]={
    {"cargo west",4,23,0,-3.60f,2,1},
    {"cargo east",21,24,3.14f,-3.61f,2,1},
    {"lower passage",19,15,-1.57f,-3.61f,2,3},
    {"service west",-7,14,0,-2.13f,2,3},
    {"service bend",6,10,0,-2.88f,2,7},
    {"east ramp",19,8,1.57f,-2.20f,2,7},
    {"upper west",-5,0,0,-.59f,2,6},
    {"upper east",6,0,3.14f,-.59f,2,6},
    {"upper passage",20,0,3.14f,-2.13f,2,6}
};
static const ff_stage ff_station_stages[]={
    {"Cargo bay",{13.5f,-3.60f,23},0},
    {"Service hall",{-2,-2.12f,14},0},
    {"Upper station",{2,-.58f,0},0}
};
#define FF_COUNT(a) (sizeof(a)/sizeof(*(a)))
static const ff_map_definition ff_maps[]={
    {BG_MAP_BLOOD_GULCH,ff_blood_zones,FF_COUNT(ff_blood_zones),NULL,0,10,true,true},
    {BG_MAP_BATTLE_CREEK,ff_creek_zones,FF_COUNT(ff_creek_zones),ff_creek_stages,FF_COUNT(ff_creek_stages),3,false,false},
    {BG_MAP_RAT_RACE,ff_station_zones,FF_COUNT(ff_station_zones),ff_station_stages,FF_COUNT(ff_station_stages),3,false,false}
};
static const ff_map_definition*ff_current_map(void){
    for(unsigned n=0;n<FF_COUNT(ff_maps);n++)if(ff_maps[n].map==bg_map_id())return &ff_maps[n];
    return NULL;
}
static unsigned ff_stage_index(void){return bg_ff.fight==BG_FF_STATION_SWEEP?bg_ff.wave/2:0;}
static const ff_stage*ff_current_stage(void){const ff_map_definition*m=ff_current_map();unsigned stage=ff_stage_index();return m&&stage<m->stage_count?&m->stages[stage]:NULL;}
#define ff_zones (ff_current_map()->zones)
#define FF_ZONES (ff_current_map()->zone_count)
