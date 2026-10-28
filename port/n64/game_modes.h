#ifndef BG_GAME_MODES_H
#define BG_GAME_MODES_H
#include <stdbool.h>
#include <stdint.h>
enum { BG_ENGINE_SLAYER, BG_ENGINE_CTF, BG_ENGINE_BALL, BG_ENGINE_KING, BG_ENGINE_RACE,
       BG_ENGINE_COUNT };
enum { BG_MODE_INVISIBLE=1, BG_MODE_GENERIC=2, BG_MODE_SENSOR=4, BG_MODE_ODD_MAN=8,
       BG_MODE_NO_DEATH_BONUS=16, BG_MODE_NO_KILL_PENALTY=32, BG_MODE_TARGETS=64,
       BG_MODE_MOVING_HILL=128, BG_MODE_ASSAULT=256, BG_MODE_FLAG_HOME=512,
       BG_MODE_FLAG_RESET=1024 };
enum {
#define BG_MODE(id,key,...) BG_MODE_##key=id,
#include "game_modes.def"
#undef BG_MODE
    BG_MODE_COUNT=26
};
typedef struct {
    const char *name;
    uint8_t engine, teams, radar, vehicles;
    int8_t weapon;
    float health;
    uint16_t goal, lives, respawn_ticks, suicide_ticks, growth_ticks, flags;
    uint8_t ball_type, balls, ball_delay, trait_with_ball, trait_without_ball, ball_speed, race_type;
} bg_mode_rules;
/* Header-only catalog also serves the independently linked menu fixtures.
 * No engine state or source-map payload lives in this table. */
static inline const bg_mode_rules *bg_mode_preset(unsigned id) {
    static const bg_mode_rules rules[BG_MODE_COUNT] = {
#define BG_MODE(id,key,name,...) [id]={name,__VA_ARGS__},
#include "game_modes.def"
#undef BG_MODE
    };
    return &rules[id<BG_MODE_COUNT?id:0];
}
static inline bool bg_mode_timed(const bg_mode_rules *r) {
    return r->engine==BG_ENGINE_KING || (r->engine==BG_ENGINE_BALL && r->ball_type!=2);
}
static inline const char *bg_mode_units(const bg_mode_rules *r) {
    return bg_mode_timed(r)?"Minutes":r->engine==BG_ENGINE_CTF?"Captures":
           r->engine==BG_ENGINE_RACE?(r->race_type==2?"Flags":"Laps"):"Kills";
}
/* The engine keeps objective ownership outside the weapon/ammunition slots. */
enum { BG_OBJECTIVE_FLAG, BG_OBJECTIVE_BALL, BG_OBJECTIVE_HILL, BG_OBJECTIVE_RACE };
typedef struct {
    float pos[3], home[3], yaw, reset_time, pickup_delay, fall_speed;
    int8_t kind, team, owner, ignore_player;
    bool active, at_home;
} bg_objective;
#define BG_MAX_OBJECTIVES 16
extern bg_objective bg_objectives[BG_MAX_OBJECTIVES];
extern unsigned bg_objective_count;
void bg_configure_mode(unsigned mode, const uint8_t teams[4]);
unsigned bg_current_mode(void);
const bg_mode_rules *bg_current_rules(void);
bool bg_mode_has_teams(void);
unsigned bg_player_team(unsigned player);
bool bg_players_allied(unsigned a,unsigned b);
unsigned bg_player_color(unsigned player);
int bg_team_score(unsigned team);
int bg_display_score(unsigned player);
bool bg_player_is_winner(unsigned player);
int bg_player_objective(unsigned player);
unsigned bg_player_ball_count(unsigned player);
int bg_player_target(unsigned player);
bool bg_player_eliminated(unsigned player);
bool bg_player_waiting(unsigned player);
float bg_mode_speed(unsigned player);
float bg_player_melee_duration(unsigned player);
bool bg_mode_radar(void);
bool bg_mode_navpoint(unsigned viewer,unsigned index,float pos[3],unsigned *kind,unsigned *team);
bool bg_mode_hill_point(unsigned index,float out[3]);
bool bg_player_in_hill(unsigned player);
void bg_drop_objective(unsigned player);
#endif
