/* Platform boundary for the original Grunt/Elite action selectors. Source
 * bodies below are generated verbatim. This prototype supplies bounded local
 * perception/navigation/action services, not the entire campaign AI engine. */
typedef bool boolean;
#ifndef TRUE
#define TRUE true
#define FALSE false
#endif
#ifndef NONE
#define NONE (-1)
#endif
#ifndef MAX
#define MAX(a,b) ((a)>(b)?(a):(b))
#endif
enum { _actor_action_none,_actor_action_sleep,_actor_action_alert,_actor_action_fight,
    _actor_action_flee,_actor_action_uncover,_actor_action_guard,_actor_action_search,
    _actor_action_wait,_actor_action_vehicle,_actor_action_charge,_actor_action_obey,
    _actor_action_converse,_actor_action_avoid,_actor_elite=0,_actor_panic_none=0,
    _ai_communication_attempted_flee=0 };
struct actor_datum {
    struct {int definition_index,variant_definition_index,unit_index,team_index;} meta;
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
    struct {bool grenade_trying_to_throw;int grenade_last_check_time;} control;
    struct {int target_type,target_prop_index;} target;
};
struct actor_definition {struct {float shield_fraction_emerge_attack,shield_fraction_emerge_pursue;} defensive;};
typedef float real;
static struct actor_datum pve_source_actors[BG_PVE_MAX];
static struct actor_definition pve_source_defs[BG_PVE_KINDS];
typedef unsigned short word;
struct actor_variant_definition {struct {int grenade_type,trajectory_type,stimulus_type;float throw_grenade_delay,throw_grenade_chance;} grenade_combat;};
static struct actor_variant_definition pve_source_variants[BG_PVE_KINDS];
static struct actor_variant_definition*actor_variant_definition_get(int i){return &pve_source_variants[i];}
struct prop_datum {bool swarm;};
static struct prop_datum *prop_get(int i){(void)i;static struct prop_datum p;return &p;}
static struct {bool grenades_enabled;} pve_source_globals={true};
#define ai_globals (&pve_source_globals)
#define ACTOR_GRENADE_TICKS_PER_SECOND 30.f
enum {_actor_grenade_stimulus_visible_target=1,_actor_grenade_stimulus_seek_cover=2,_game_difficulty_value_grenade_chance_scale};
static float game_difficulty_get_team_value(int value,word team){(void)value;(void)team;return bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1].grenade_chance*bg_ff_grenade_chance();}
static uint32_t *get_global_random_seed_address(void){return &pve_random;}
static float real_seed_random(uint32_t*seed){return blam_real_seed_random_range(seed,0,1);}
static bool actor_action_test_grenade(long i);
static bool actor_action_try_to_throw_grenade(long i,bool first);
static bool actor_action_consider_grenade(long actor_index);
static bool actor_action_handle_grenade_throwing(long actor_index);
static bool pve_try_evade(unsigned i);
static struct actor_datum *actor_get(long i){return &pve_source_actors[i];}
static struct actor_definition *actor_definition_get(int i){return &pve_source_defs[i];}
static long game_time_get(void){return bg_pve_tick_number;}
static bool actor_action_deny_transition(long i){bg_pve_actor*a=&bg_pve_actors[i];return a->melee_pending||a->throw_pending||a->evade_time>0||a->arrival;}
static void actor_action_handle_initial_action(long i){if(!actor_get(i)->state.action)actor_get(i)->state.action=_actor_action_guard;}
static void actor_action_handle_panic_from_damage(long i){
    bg_pve_actor *a=&bg_pve_actors[i];const bg_pve_definition*d=pve_definition_for(a->kind,bg_players[BG_PLAYERS+i].weapon);
    if(a->recent_damage>d->panic_damage){actor_get(i)->stimuli.panic_type=MAX(actor_get(i)->stimuli.panic_type,1);actor_get(i)->stimuli.panic_prop_index=1;}
}
static void actor_action_handle_panic_from_attached_projectiles(long i){
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){bg_projectile*q=bg_projectile_at(j);
        if(q&&q->active&&q->kind==BG_P_PLASMA_GRENADE&&q->attached==(int)(BG_PLAYERS+i)){
            actor_get(i)->stimuli.panic_type=10;actor_get(i)->stimuli.panic_prop_index=1;}}
}
static bool actor_action_try_to_panic(long i,int type,int prop,bool force){
    (void)prop;(void)force;bg_pve_actor*a=&bg_pve_actors[i];
    actor_get(i)->state.action=_actor_action_flee;actor_get(i)->state.action_data.flee.panic_type=type;
    a->panic_time=pve_range(bg_pve_definitions[a->kind].cower);if(a->panic_time<1)a->panic_time=1;
    return true;
}
static bool action_flee_blind_panic(int type){return type>=10;}
static bool actor_action_handle_done_fleeing(long i){
    if(bg_pve_actors[i].panic_time<=0||actor_get(i)->state.action_data.flee.done_fleeing){
        actor_get(i)->state.action=_actor_action_fight;actor_get(i)->state.action_data.flee.done_fleeing=false;return true;}
    return false;
}
static bool actor_action_handle_combat_status(long i,bool initiative,bool force){
    struct actor_datum*s=actor_get(i);bg_pve_actor*a=&bg_pve_actors[i];
    if(s->state.action==_actor_action_flee&&a->panic_time>0&&!force)return false;
    if(s->state.action==_actor_action_guard&&s->state.action_data.guard.cower)return false;
    if(!initiative&&!force)return false;
    int action=a->visible?_actor_action_fight:(a->aware?_actor_action_search:_actor_action_guard);
    bool changed=action!=s->state.action;s->state.action=action;return changed;
}
static void actor_action_handle_combat_transition(long i){actor_action_handle_combat_status(i,true,false);}
static bool actor_action_can_stop_guarding(long i,int action,int reason){(void)action;(void)reason;return !actor_get(i)->state.action_data.guard.cower;}
static void actor_action_handle_active_cover_seeking(long i,bool unused,bool unused2){
    (void)unused;(void)unused2;bg_pve_actor*a=&bg_pve_actors[i];struct actor_datum*s=actor_get(i);
    if(s->input.shield_vitality<bg_pve_definitions[a->kind].hide_shield){
        s->state.action=_actor_action_guard;s->state.action_data.guard.cower=true;
        a->cover_time=fmaxf(a->cover_time,pve_range(bg_pve_definitions[a->kind].hide));}
}
static void actor_action_handle_berserking_from_damage(long i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=pve_definition_for(a->kind,bg_players[BG_PLAYERS+i].weapon);
    if(a->recent_damage>d->berserk_damage&&p->health/(d->health*bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1].vitality)<d->berserk_threshold)a->berserk=true;
}
static void actor_action_handle_berserk_transition(long i,int level){(void)level;actor_get(i)->emotions.berserk=bg_pve_actors[i].berserk;}
/* Campaign commands/conversations and boarding are outside this survival mode. */
#define actor_action_handle_pending_command_list(...) ((void)0)
#define actor_action_handle_surprise(...) ((void)0)
#define actor_action_handle_panic_from_surprise(...) ((void)0)
#define actor_action_handle_panic_from_attached_melee_attackers(...) ((void)0)
#define actor_action_handle_panic_from_burning_to_death(...) ((void)0)
#define actor_action_handle_vehicle_entry(...) ((void)0)
#define actor_action_handle_vehicle_exit(...) ((void)0)
#define actor_action_handle_danger_avoidance(i) pve_try_evade(i)
#define actor_action_handle_evasion(i) pve_try_evade(i)
#define actor_action_handle_exit_pursuit(...) ((void)0)
#define actor_action_handle_berserking_from_attacking_mode(...) ((void)0)
#define actor_action_handle_berserking_from_proximity(...) ((void)0)
#define actor_action_handle_berserking_from_attached_projectiles(...) ((void)0)
#define actor_action_handle_combat_failure(...) false
#define actor_action_can_stop_conversing(...) false
#define ai_communication_event(...) ((void)0)
#define match_assert(file,line,test) assert(test)
#include "pve_source_decisions.inc"
#undef match_assert
