#ifndef BG_FIREFIGHT_H
#define BG_FIREFIGHT_H
#include <stdbool.h>
#include <stdint.h>
enum {BG_FF_OFF,BG_FF_READY,BG_FF_WAVE,BG_FF_RECOVER,BG_FF_BONUS,BG_FF_WON,BG_FF_LOST};
enum {BG_FF_GROUND,BG_FF_SPIRIT};
enum {BG_FF_PATROL,BG_FF_GRUNTS,BG_FF_NEEDLERS,BG_FF_SHIELDS,BG_FF_MIXED,BG_FF_ELITES,BG_FF_HUNTERS,BG_FF_HUNTER_ESCORT,BG_FF_FORMATIONS};
enum {BG_FF_SHIP_NONE,BG_FF_SHIP_APPROACH,BG_FF_SHIP_OPEN,BG_FF_SHIP_UNLOAD,BG_FF_SHIP_CLOSE,BG_FF_SHIP_LEAVE};
typedef struct {const char *name;uint8_t count,kind[5],weapon[5];} bg_ff_formation;
extern const bg_ff_formation bg_ff_formations[BG_FF_FORMATIONS];
typedef struct {
    bool active,respawn_reserved[4];uint8_t phase,round,wave,difficulty,cap;
    uint16_t lives,spawned,killed,total,packets,packet,next_formation;
    uint32_t tick,seed,random,score[4],team_score,multikills[4],sprees[4],last_kill[4],bonus_score;
    float timer,elapsed,packet_delay,message_time;unsigned arrival_failures,ground_arrivals,ship_arrivals,stuck_recoveries;
    char message[64];
} bg_ff_state;
typedef struct {uint8_t phase,zone,formation,count;int8_t actors[8];float time,pos[3],yaw,door,unload_time;bool released[8];} bg_ff_ship;
extern bg_ff_state bg_ff;
extern bg_ff_ship bg_ff_dropship;
void bg_ff_start(unsigned players);
void bg_ff_stop(void);
void bg_ff_tick(float dt);
void bg_ff_after_tick(float dt);
void bg_ff_player_died(unsigned player);
bool bg_ff_can_respawn(unsigned player);
bool bg_ff_place_human(unsigned player);
void bg_ff_enemy_killed(unsigned actor,int owner,bool headshot,unsigned profile);
void bg_ff_qa_input(void *inputs);
bool bg_ff_cloud(void);
float bg_ff_grenade_chance(void);
#endif
