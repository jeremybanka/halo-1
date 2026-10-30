/* Bounded cooperative actor pool. Unit identity is independent of cameras. */
#include <assert.h>
bg_pve_actor bg_pve_actors[BG_PVE_MAX];
unsigned bg_pve_count,bg_pve_tick_number;
uint32_t bg_pve_ai_us,bg_pve_move_us;
static bool pve_active;
static uint32_t pve_random=0x505645;
static const bg_pve_definition*pve_definition_for(unsigned kind,unsigned weapon){return weapon==BG_W_NEEDLER&&kind<2?&bg_pve_needler_definitions[kind]:&bg_pve_definitions[kind];}
static const bg_pve_definition*pve_definition(unsigned i){
#ifdef BG_PVE_ROSTER
    if(bg_pve_actors[i].variant)return &bg_pve_variants[bg_pve_actors[i].variant].def;
#endif
    return pve_definition_for(bg_pve_actors[i].kind,bg_players[BG_PLAYERS+i].weapon);
}
static float pve_range(const float bounds[2]){return blam_real_seed_random_range(&pve_random,bounds[0],bounds[1]);
    }
static float pve_random01(void){return blam_real_seed_random_range(&pve_random,0,1);
    }
bool bg_pve_is_active(void){return pve_active;
    }
float bg_pve_height(const void *player){
    return ((const bg_player*)player)->pve_height;
}
#include "pve_source.inc"
#include "pve_nav.inc"
#include "pve_actions.inc"
#ifdef BG_PVE_ROSTER
#include "pve_roster.inc"
#endif
static bool pve_sees(unsigned i,unsigned target){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=pve_definition(i);
    float origin[3]={p->pos[0],p->pos[1]+d->eye,p->pos[2]},point[3]={bg_players[target].pos[0],bg_players[target].pos[1]+.4f,bg_players[target].pos[2]},dir[3];
    sub(dir,point,origin);float distance=sqrtf(dot(dir,dir));if(distance>d->vision)return false;
    if(distance<.01f)return true;
    for(unsigned k=0;k<3;k++)dir[k]/=distance;
    if(!a->aware&&dir[0]*cosf(p->yaw)-dir[2]*sinf(p->yaw)<cosf(d->vision_angle))return false;
    a->los_tests++;return bg_raycast(origin,dir,distance)>=distance-.02f;
}
static void pve_decide(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=pve_definition(i);
#ifdef BG_PVE_ROSTER
    bool was_aware=a->aware;unsigned old_action=a->action;
#endif
    a->decisions++;a->visible=false;float nearest=1e9f;int target=-1;
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0&&pve_sees(i,h)){
        float distance=distance2(p->pos,bg_players[h].pos);if(distance<nearest){nearest=distance;target=h;}}
    if(target>=0){a->visible=true;a->notice_time+=.2f;if(a->notice_time>=d->notice)a->aware=true;
        if(a->target!=target){
#ifdef BG_ENEMY_VEHICLES
            a->vehicle_target_time=0;
            a->burst_pause=pve_range(p->vehicle>=0?bg_vehicle_ai_defs[bg_vehicles[p->vehicle].kind].first_delay:d->first_delay);
#else
            a->burst_pause=pve_range(d->first_delay);
#endif
        }
        a->target=target;memcpy(a->last_seen,bg_players[target].pos,12);
    }else {
        a->notice_time=0;
        if(a->target>=0&&bg_players[a->target].health<=0){
            a->target=-1;float best=1e9f;
            for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0){float dist=distance2(p->pos,bg_players[h].pos);if(dist<best){best=dist;a->target=h;memcpy(a->last_seen,bg_players[h].pos,12);}}
        }
    }
#ifdef BG_ENEMY_VEHICLES
    if(p->vehicle>=0){a->recent_damage=0;return;}
#endif
    /* These source adapter records belong to actors, not species. A Major's
     * grenade or shield policy must never overwrite a nearby Minor's. */
    pve_source_defs[i].defensive.shield_fraction_emerge_attack=d->emerge_shield;
    pve_source_defs[i].defensive.shield_fraction_emerge_pursue=d->pursue_shield;
    pve_source_variants[i].grenade_combat.grenade_type=1;
    pve_source_variants[i].grenade_combat.stimulus_type=d->grenade_stimulus;
    pve_source_variants[i].grenade_combat.throw_grenade_delay=d->grenade_check;
    pve_source_variants[i].grenade_combat.throw_grenade_chance=d->grenade_chance;
    struct actor_datum*s=actor_get(i);s->meta.definition_index=s->meta.variant_definition_index=i;s->meta.unit_index=BG_PLAYERS+i;
    s->state.combat_status=a->aware?(a->visible?5:3):0;s->input.shield_vitality=d->shield?p->shield/(d->shield*bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1].shield):0;
    s->target.target_type=a->target>=0?5:0;s->target.target_prop_index=a->target;
    s->situation.area_friends_by_type[0]=s->situation.close_friends_by_type[0]=0;
    for(unsigned j=0;j<bg_pve_count;j++)if(j!=i&&bg_pve_actors[j].kind==BG_PVE_ELITE&&bg_players[BG_PLAYERS+j].health>0){
        float dist=distance2(p->pos,bg_players[BG_PLAYERS+j].pos);
        s->situation.area_friends_by_type[0]+=dist<64;s->situation.close_friends_by_type[0]+=dist<16;
    }
    if(a->kind==BG_PVE_GRUNT)grunt_decide_action(i);else if(a->kind==BG_PVE_ELITE)elite_decide_action(i);else if(a->kind==BG_PVE_JACKAL)jackal_decide_action(i);else hunter_decide_action(i);
    a->action=s->state.action;a->recent_damage=0;
#ifdef BG_PVE_ROSTER
    if(!was_aware&&a->aware)pve_say(i,PVE_V_SPOT);
    else if(old_action!=_actor_action_flee&&a->action==_actor_action_flee)pve_say(i,PVE_V_PANIC);
#endif
    if(a->aware&&p->vehicle<0)pve_destination(i);
}
static void pve_killed(unsigned unit,int owner){
    unsigned i=unit-BG_PLAYERS;if(i>=bg_pve_count)return;
    bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[i];
    if(p->health<=0)return;
    if(p->vehicle>=0)eject(unit,true);
    p->health=p->shield=0;a->clip=PVE_DEATH;a->time=0;p->animation=BG_ANIM_DIE;memset(p->velocity,0,12);
    const bg_pve_definition*d=pve_definition(i);
#ifdef BG_PVE_ROSTER
    pve_say(i,PVE_V_DEATH);
    if(a->armament)a->death_weapon_time=pve_range(a->armament==PVE_ARM_FUEL?bg_pve_fuel_drop_delay:bg_pve_sword_drop_delay);
    else
#endif
    if(a->kind!=BG_PVE_HUNTER)drop_item(unit,p->weapon,(int)(bg_ammo_rules[p->weapon].loaded*pve_range(d->drop_loaded)),0,0,false,1,0);
    if(a->grenades&&pve_random01()>=d->no_grenade_drop)drop_item(unit,BG_PICK_PLASMA,0,0,0,false,a->grenades,1);
    event(BG_EVENT_DIE,unit,p->weapon,p->pos,1);
    if(bg_ff.active)bg_ff_enemy_killed(i,owner,a->last_headshot,a->last_profile);
    else if(owner>=0&&owner<(int)active_players){bg_players[owner].score++;statistics.kills[owner]++;}
    if(a->kind==BG_PVE_ELITE)for(unsigned j=0;j<bg_pve_count;j++)if(bg_pve_actors[j].kind==BG_PVE_GRUNT&&bg_players[BG_PLAYERS+j].health>0&&distance2(p->pos,bg_players[BG_PLAYERS+j].pos)<64&&pve_random01()<pve_definition(j)->leader_panic){
        actor_get(j)->stimuli.panic_type=8;actor_get(j)->stimuli.panic_prop_index=1;bg_pve_actors[j].decision_time=0;
    }
}
static void pve_damage(unsigned unit,int owner,float amount,bool headshot,unsigned profile,bool behind,int region){
    unsigned i=unit-BG_PLAYERS;bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[i];const bg_pve_definition*d=pve_definition(i);
    if(!a->occupied||a->arrival==1)return;
    const bg_damage_profile*hit=&bg_damage_profiles[profile];float before=p->health+p->shield;
    const bg_pve_hit_mesh*m=&bg_pve_hits[a->kind];int material=(region>>8)-1;
    const bg_pve_hit_material*r=&m->rules[material>=0&&(unsigned)material<m->material_count?(unsigned)material:d->indirect_material];
    float body_mod=1,shield_mod=1;
#ifdef BG_ENEMY_VEHICLES
    if(profile>=BG_D_WRAITH){
        body_mod=bg_enemy_vehicle_damage[profile-BG_D_WRAITH][r?r->material:d->body_material];
        shield_mod=bg_enemy_vehicle_damage[profile-BG_D_WRAITH][d->shield_material];
    }else
#endif
    if(profile){body_mod=r?r->damage[profile]:d->damage[profile][0];shield_mod=d->damage[profile][1];}
    float body=body_mod*(r?r->body_scale:1);
    float shield=shield_mod*(r?r->shield_scale:1),leak=r?r->leak:0;
    bool backstab=(hit->flags&BG_DAMAGE_BACKSTAB)&&behind;
    if(backstab){p->shield=0;p->health=0;}
    else {
        float remaining=amount;
        if(p->shield>0&&!(hit->flags&BG_DAMAGE_SKIP_SHIELDS)&&shield>0){
            float actual=amount*(1-leak)*shield;
            remaining=amount*leak+fmaxf(0,actual-p->shield);
            if(hit->flags&BG_DAMAGE_EMP)p->shield=0;
            else p->shield=fmaxf(0,p->shield-actual);
        }
        bool uncovered=p->shield<=0||(r&&r->shield_scale==0);
        if(headshot&&uncovered&&remaining>0&&body>0&&(hit->flags&BG_DAMAGE_HEADSHOT))p->health=0;
        else p->health=fmaxf(0,p->health-remaining*body);
    }
    p->hurt=.65f;p->shield_delay=d->shield_delay;a->recent_damage+=(before-p->health-p->shield)/fmaxf(d->health,1);
#ifdef BG_PVE_ROSTER
    pve_say(i,PVE_V_PAIN);
    a->camouflage=fmaxf(0,a->camouflage-bg_pve_camo_damage[profile]);
#endif
    a->last_headshot=headshot;a->last_profile=profile;
    if(owner>=0&&owner<(int)active_players){a->contribution[owner]+=before-p->health-p->shield;a->aware=true;a->target=owner;memcpy(a->last_seen,bg_players[owner].pos,12);}
    if(p->health<=0){p->health=1;pve_killed(unit,owner);}
}
#include "pve_collision.inc"
void bg_pve_stop(void){
    bg_ff_stop();
#ifdef BG_ENEMY_VEHICLES
    pve_routes_release();
#endif
    pve_active=false;bg_pve_count=bg_pve_tick_number=0;
    memset(bg_pve_actors,0,sizeof(bg_pve_actors));
    memset(bg_players+BG_PLAYERS,0,BG_PVE_MAX*sizeof(bg_player));
}
void bg_pve_start(unsigned count){
    pve_active=true;bg_pve_count=count>BG_PVE_MAX?BG_PVE_MAX:count;bg_pve_tick_number=0;pve_random=0x505645;
    mode_enabled=false;bg_set_score_limit(100000);memset(bg_pve_actors,0,sizeof(bg_pve_actors));memset(pve_source_actors,0,sizeof(pve_source_actors));
    bg_vehicle_count=0;pve_nav_init();
    pve_encounter_grenade_time=0;
    for(unsigned k=0;k<BG_PVE_KINDS;k++){
        const bg_pve_definition*d=&bg_pve_definitions[k];pve_source_defs[k].defensive.shield_fraction_emerge_attack=d->emerge_shield;pve_source_defs[k].defensive.shield_fraction_emerge_pursue=d->pursue_shield;
        pve_source_variants[k].grenade_combat.grenade_type=1;
        pve_source_variants[k].grenade_combat.stimulus_type=d->grenade_stimulus;
        pve_source_variants[k].grenade_combat.throw_grenade_delay=d->grenade_check;
        pve_source_variants[k].grenade_combat.throw_grenade_chance=d->grenade_chance;
    }
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];a->kind=i==0?BG_PVE_ELITE:BG_PVE_GRUNT;a->target=-1;a->decision_time=i*.03f;a->occupied=true;a->generation=1;a->grenades=2;
        const bg_pve_definition*d=pve_definition(i);bg_player*p=&bg_players[BG_PLAYERS+i];memset(p,0,sizeof(*p));
        p->pos[0]=3+(i%3)*1.2f;p->pos[2]=1.5f+(i/3)*1.5f;p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
        memcpy(a->destination,p->pos,12);memcpy(a->previous,p->pos,12);p->pve_radius=d->radius;p->pve_height=d->height;p->health=d->health;p->shield=d->shield;p->vehicle=p->exit_vehicle=-1;p->grounded=true;
        p->yaw=3.14159265f;p->weapon=a->kind==BG_PVE_ELITE?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL;p->ammo=100;p->inventory[0]=p->weapon;p->inventory[1]=-1;
        #ifdef BG_ENEMY_VEHICLES
        a->desired_vehicle=-1;
#endif
        a->burst_pause=pve_range(d->first_delay);actor_get(i)->emotions.last_flee_failed_time=NONE;actor_get(i)->control.grenade_last_check_time=NONE;
    }
}
static void pve_place_human(unsigned i){
    if(bg_ff.active){bg_ff_place_human(i);return;}
    bg_player*p=&bg_players[i];p->pos[0]=-2-(i%2)*1.5f;p->pos[2]=1.5f+(i/2)*1.5f;
    p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;p->yaw=0;p->pitch=0;
    bg_give_weapon(i,BG_W_PISTOL);p->ammo=12;p->reserve=120;p->grenades[0]=4;p->grenades[1]=4;
    p->weapon_ready=p->cooldown=0;memcpy(p->last_pos,p->pos,12);
}
void bg_pve_stage(unsigned players){
    bg_pve_stop();bg_configure_mode(BG_MODE_SLAYER,NULL);
    bg_set_players(players);bg_reset();bg_pve_start(5);
    for(unsigned i=0;i<active_players;i++)pve_place_human(i);
}
#ifdef BG_ENEMY_VEHICLES
#include "pve_vehicles.inc"
#endif
#include "pve_tick.inc"
/* Deterministic acceptance input. No hidden invulnerability or direct kills. */
void bg_pve_qa_input(void *data){
    if(bg_ff.active){
#if BG_PVE_QA==4 || BG_PVE_QA==5 || BG_PVE_QA==7 || BG_PVE_QA==8
        if(bg_ff.tick>=600)bg_ff_qa_stage(active_players,BG_PVE_QA);
#endif
        bg_ff_qa_input(data);return;
    }
    bg_input*in=data;memset(in,0,4*sizeof(*in));
    if(bg_pve_tick_number>=450){unsigned players=active_players,count=bg_pve_count;bg_pve_stage(players);if(count!=5)bg_pve_start(count);}
    for(unsigned h=0;h<active_players;h++){
        bg_player*p=&bg_players[h];if(p->health<=0)continue;
        unsigned target=4;while(target<4+bg_pve_count&&bg_players[target].health<=0)target++;
        if(target<4+bg_pve_count){float dx=bg_players[target].pos[0]-p->pos[0],dz=bg_players[target].pos[2]-p->pos[2];
            p->yaw=atan2f(-dz,dx);p->pitch=atan2f(bg_players[target].pos[1]+bg_body_height(&bg_players[target])*.75f-p->pos[1]-bg_eye_height(p),hypotf(dx,dz));
#if defined(BG_PVE_QA) && BG_PVE_QA == 2
            in[h].fire=h==0&&bg_pve_tick_number>=180&&bg_players[4].health>0&&(bg_pve_tick_number%10==0);
#endif
        }
        in[h].reload=p->ammo==0&&p->reload<=0;
    }
}
