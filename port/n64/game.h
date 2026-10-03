#ifndef HALO_N64_GAME_H
#define HALO_N64_GAME_H
#include <stdbool.h>
#include <stdint.h>
#include "world.h"
#define BG_PLAYERS 4
#define BG_MAX_VEHICLES 12
#define BG_MAX_PROJECTILES 48
#define BG_MAX_PICKUPS 40
#define BG_MAX_EVENTS 64

typedef enum { BG_W_AR, BG_W_PISTOL, BG_W_PLASMA_PISTOL, BG_W_PLASMA_RIFLE,
    BG_W_NEEDLER, BG_W_SHOTGUN, BG_W_SNIPER, BG_W_ROCKET, BG_W_FLAMETHROWER, BG_WEAPON_COUNT } bg_weapon;
enum { BG_PICK_HEALTH=BG_WEAPON_COUNT, BG_PICK_FRAG, BG_PICK_PLASMA, BG_PICK_OVERSHIELD, BG_PICK_CAMO };
typedef enum { BG_V_WARTHOG, BG_V_GHOST, BG_V_SCORPION, BG_V_BANSHEE, BG_VEHICLE_COUNT } bg_vehicle_kind;
typedef enum { BG_ANIM_IDLE, BG_ANIM_WALK, BG_ANIM_RUN, BG_ANIM_JUMP, BG_ANIM_FIRE,
    BG_ANIM_RELOAD, BG_ANIM_MELEE, BG_ANIM_DIE, BG_ANIM_DRIVE } bg_animation;
typedef enum { BG_EVENT_FIRE, BG_EVENT_RELOAD, BG_EVENT_JUMP, BG_EVENT_LAND,
    BG_EVENT_HURT, BG_EVENT_DIE, BG_EVENT_RESPAWN, BG_EVENT_EXPLOSION,
    BG_EVENT_PICKUP, BG_EVENT_EMPTY, BG_EVENT_MELEE, BG_EVENT_ENTER,
    BG_EVENT_EXIT, BG_EVENT_ENGINE, BG_EVENT_SHIELD, BG_EVENT_GRENADE,
    BG_EVENT_GAME_OVER, BG_EVENT_DOUBLE_KILL, BG_EVENT_TRIPLE_KILL, BG_EVENT_KILLING_SPREE, BG_EVENT_TELEPORTER, BG_EVENT_NEEDLE_HIT, BG_EVENT_SUPERCOMBINE } bg_event_kind;
typedef enum { BG_P_PLASMA, BG_P_NEEDLE, BG_P_ROCKET, BG_P_FRAG,
    BG_P_PLASMA_GRENADE, BG_P_CANNON, BG_P_FLAME } bg_projectile_kind;
/* BG_EVENT_EXPLOSION stores this presentation type in event.weapon. */
typedef enum { BG_EXPLOSION_NORMAL, BG_EXPLOSION_PLASMA, BG_EXPLOSION_NEEDLER } bg_explosion_kind;
typedef struct {
    const char *name; int magazine,reserve;
    float interval,reload,damage,spread,range,speed,heat,zoom;
    int pellets; bool automatic,energy; bg_projectile_kind projectile;
} bg_weapon_def;
typedef struct {
    float pos[3],yaw,pitch,vy,cooldown,reload,respawn,hurt,flash;
    int health,ammo,score; bool grounded;
    float shield,shield_delay,heat,charge,recoil,gait,anim_time,melee_time,invisibility;
    float velocity[3],last_pos[3];
    int reserve,weapon,inventory[2],magazines[2],reserves[2],slot,zoom;
    int grenades[2],grenade_kind,vehicle,seat,needles,needle_owner;
    float needle_timer,grenade_cooldown,interact_cooldown,teleport_cooldown;
    bg_animation animation;
    float heats[2];
    bool overheated,overheated_slots[2],fire_held,crouched;
} bg_player;
typedef struct {
    float forward,strafe,turn,look;
    bool jump,fire,reload,switch_weapon,grenade,switch_grenade,interact,melee,zoom,crouch,secondary_fire;
} bg_input;
typedef struct {
    float pos[3],yaw,pitch,velocity[3],speed,cooldown,flash,respawn,engine_phase;
    float home[3],home_yaw,secondary_cooldown,turret_yaw,turret_pitch; int kind,health,occupants[3]; bool active;
} bg_vehicle;
typedef struct {
    float pos[3],velocity[3],life,damage,radius; int kind,owner,attached;
    float attached_offset[3]; bool active;
} bg_projectile;
typedef struct { float pos[3],respawn; int weapon; bool active; } bg_pickup;
typedef struct { float source[3],destination[3],yaw; } bg_teleporter;
typedef struct { bg_event_kind kind; int player,weapon; float pos[3],amount; } bg_event;
extern const bg_teleporter bg_teleporters[2];
extern const unsigned bg_teleporter_count;
extern bg_player bg_players[BG_PLAYERS];
extern bg_vehicle bg_vehicles[BG_MAX_VEHICLES];
/* Live records use original Blam object headers and its movable memory pool.
 * A pointer is valid until a later allocation/tick; reacquire it by slot. */
bg_projectile *bg_projectile_at(unsigned slot);
bg_projectile *bg_projectile_create(void);
extern bg_pickup bg_pickups[BG_MAX_PICKUPS];
extern bg_event bg_events[BG_MAX_EVENTS];
extern unsigned bg_vehicle_count,bg_pickup_count,bg_event_count;
extern const bg_weapon_def bg_weapon_defs[BG_WEAPON_COUNT];
void bg_reset(void);
void bg_set_players(unsigned count);
unsigned bg_player_count(void);
void bg_clear_events(void);
bool bg_match_finished(void);
int bg_match_winner(void);
unsigned bg_score_limit(void);
float bg_match_time(void);
void bg_tick(const bg_input input[BG_PLAYERS],float dt);
float bg_floor(float x,float z,float ceiling);
float bg_raycast(const float origin[3],const float direction[3],float max_distance);
/* Picking up a weapon replaces the current slot; matching weapons replenish it. */
bool bg_give_weapon(unsigned player,bg_weapon weapon);
/* Local map setup may replace default placements with extracted scenario data. */
int bg_add_vehicle(bg_vehicle_kind kind,const float pos[3],float yaw);
/* Original Warthog seat/entry markers, transformed by the current hull pose. */
void bg_vehicle_seat_position(const bg_vehicle *vehicle,unsigned seat,bool entry,float out[3]);
int bg_add_pickup(int weapon,const float pos[3]);
#endif
