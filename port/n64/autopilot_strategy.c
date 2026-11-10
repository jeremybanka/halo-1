/* Movement-only boundary for the same source selectors as the NPCs. Each
 * human owns its own actor state. No callback fires, reloads, throws, switches
 * a weapon, turns the camera or enters a vehicle. */
#include "game.h"
#include "pve.h"
#include "autopilot_strategy.h"
#include <assert.h>
#include <string.h>
typedef bool boolean;
typedef float real;
#define TRUE true
#define FALSE false
#define NONE (-1)
#define MAX(a,b) ((a)>(b)?(a):(b))
enum { _actor_action_none,_actor_action_sleep,_actor_action_alert,_actor_action_fight,
    _actor_action_flee,_actor_action_uncover,_actor_action_guard,_actor_action_search,
    _actor_action_wait,_actor_action_vehicle,_actor_action_charge,_actor_action_obey,
    _actor_action_converse,_actor_action_avoid,_actor_elite=0,_actor_panic_none=0,
    _ai_communication_attempted_flee=0 };
struct actor_datum {
    struct {int definition_index,unit_index;} meta;
    struct {int area_friends_by_type[1],close_friends_by_type[1];} situation;
    struct {int action,combat_status;struct {
        struct {int panic_type;bool unable_to_flee,done_fleeing;} flee;
        struct {bool cower,cower_panicked,cower_from_retreat;int cower_ticks;} guard;
        struct {bool vehicle_entry_done,vehicle_entry_failed;} vehicle;
        struct {bool initiative,finished;} obey;
        struct {bool failed;} converse;
    } action_data;} state;
    struct {int panic_type,panic_prop_index;} stimuli;
    struct {bool berserk;int last_flee_failed_time;} emotions;
    struct {bool vehicle_passenger;float shield_vitality;} input;
    struct {int conversation_index;} external_orders;
    struct {int danger_type;} danger_zone;
};
struct actor_definition {struct {float shield_fraction_emerge_attack,shield_fraction_emerge_pursue;} defensive;};
static struct actor_datum actors[BG_PLAYERS];
static struct actor_definition definitions[BG_PLAYERS];
static struct {bool visible,aware,danger,evade;float damage;} observations[BG_PLAYERS];
static unsigned strategy_ticks[BG_PLAYERS];
static unsigned deciding;
static struct actor_datum *actor_get(long i){assert(i>=0&&i<BG_PLAYERS);return &actors[i];}
static struct actor_definition *actor_definition_get(int i){return &definitions[i];}
static long game_time_get(void){return strategy_ticks[deciding];}
static void actor_action_handle_initial_action(long i){if(!actors[i].state.action)actors[i].state.action=_actor_action_guard;}
static bool actor_action_deny_transition(long i){(void)i;return false;}
static bool actor_action_handle_combat_status(long i,bool initiative,bool force){
    struct actor_datum *a=&actors[i];
    if(!force&&(a->state.action==_actor_action_flee||a->state.action_data.guard.cower))return false;
    if(!initiative&&!force)return false;
    int next=observations[i].visible?_actor_action_fight:observations[i].aware?_actor_action_search:_actor_action_guard;
    bool changed=a->state.action!=next;a->state.action=next;return changed;
}
static void actor_action_handle_combat_transition(long i){actor_action_handle_combat_status(i,true,false);}
static bool actor_action_try_to_panic(long i,int type,int prop,bool force){
    (void)prop;(void)force;actors[i].state.action=_actor_action_flee;actors[i].state.action_data.flee.panic_type=type;return true;
}
static bool action_flee_blind_panic(int type){return type>=10;}
static bool actor_action_handle_done_fleeing(long i){
    if(actors[i].state.action_data.flee.done_fleeing){actors[i].state.action=_actor_action_fight;actors[i].state.action_data.flee.done_fleeing=false;return true;}return false;
}
static bool actor_action_can_stop_guarding(long i,int action,int reason){(void)action;(void)reason;return !actors[i].state.action_data.guard.cower;}
static void actor_action_handle_active_cover_seeking(long i,bool unused,bool unused2){
    (void)unused;(void)unused2;
    if(actors[i].input.shield_vitality<bg_pve_definitions[BG_PVE_ELITE].hide_shield){actors[i].state.action=_actor_action_guard;actors[i].state.action_data.guard.cower=true;}
}
static void actor_action_handle_berserking_from_damage(long i){
    const bg_pve_definition *d=&bg_pve_definitions[BG_PVE_ELITE];
    if(observations[i].damage>d->berserk_damage&&bg_players[i].health/bg_armor_def(bg_players[i].armor)->health<d->berserk_threshold)actors[i].emotions.berserk=true;
}
static void actor_action_handle_panic_from_attached_projectiles(long i){if(observations[i].danger){actors[i].stimuli.panic_type=10;actors[i].stimuli.panic_prop_index=1;}}
static void actor_action_handle_evasion(long i){observations[i].evade|=observations[i].danger;}
static void actor_action_handle_danger_avoidance(long i){actor_action_handle_evasion(i);}
/* The source selector's combat services cannot take human weapon control. */
#define actor_action_handle_grenade_throwing(...) ((void)0)
#define actor_action_consider_grenade(...) ((void)0)
#define actor_action_handle_pending_command_list(...) ((void)0)
#define actor_action_handle_surprise(...) ((void)0)
#define actor_action_handle_panic_from_surprise(...) ((void)0)
#define actor_action_handle_panic_from_damage(...) ((void)0)
#define actor_action_handle_panic_from_attached_melee_attackers(...) ((void)0)
#define actor_action_handle_panic_from_burning_to_death(...) ((void)0)
#define actor_action_handle_vehicle_entry(...) ((void)0)
#define actor_action_handle_vehicle_exit(...) ((void)0)
#define actor_action_handle_exit_pursuit(...) ((void)0)
#define actor_action_handle_berserking_from_attacking_mode(...) ((void)0)
#define actor_action_handle_berserking_from_proximity(...) ((void)0)
#define actor_action_handle_berserking_from_attached_projectiles(...) ((void)0)
#define actor_action_handle_berserk_transition(...) ((void)0)
#define actor_action_handle_combat_failure(...) false
#define actor_action_can_stop_conversing(...) false
#define ai_communication_event(...) ((void)0)
#define match_assert(file,line,test) assert(test)
#include "gungnir_strategy_source.inc"

void bg_autopilot_strategy_reset(unsigned p){
    if(p>=BG_PLAYERS)return;
    strategy_ticks[p]=0;memset(&actors[p],0,sizeof(actors[p]));memset(&observations[p],0,sizeof(observations[p]));
    actors[p].meta.definition_index=p;actors[p].meta.unit_index=p;actors[p].emotions.last_flee_failed_time=NONE;
}
bg_autopilot_strategy bg_autopilot_decide(unsigned p,bool panic,bool visible,bool aware,bool danger,float recent_damage){
    assert(p<BG_PLAYERS);deciding=p;strategy_ticks[p]+=6;struct actor_datum *a=&actors[p];const bg_pve_definition *d=&bg_pve_definitions[panic?BG_PVE_GRUNT:BG_PVE_ELITE];
    observations[p].visible=visible;observations[p].aware=aware;observations[p].danger=danger;observations[p].damage=recent_damage;observations[p].evade=false;
    float shield=bg_armor_def(bg_players[p].armor)->shield;a->input.shield_vitality=shield>0?bg_players[p].shield/shield:0;a->state.combat_status=visible?5:aware?3:0;
    if(!panic&&!danger&&a->state.action==_actor_action_flee)a->state.action_data.flee.done_fleeing=true;
    definitions[p].defensive.shield_fraction_emerge_attack=d->emerge_shield;definitions[p].defensive.shield_fraction_emerge_pursue=d->pursue_shield;
    if(panic){a->stimuli.panic_type=10;a->stimuli.panic_prop_index=1;grunt_decide_action(p);}else elite_decide_action(p);
    return (bg_autopilot_strategy){.retreat=a->state.action==_actor_action_flee||(a->state.action==_actor_action_guard&&a->state.action_data.guard.cower),.charge=a->emotions.berserk,.evade=observations[p].evade,.near_range=d->desired[0],.far_range=d->desired[1]};
}
