/* CE variants feed the existing source selectors and bounded platform services.
 * Speech uses its own counters, never the simulation's combat random stream. */
static void pve_say(unsigned i,unsigned speech){
    if(i>=bg_pve_count||speech>=PVE_V_COUNT)return;
    bg_pve_actor*a=&bg_pve_actors[i];
    if(!a->occupied||a->arrival==1)return;
    if(speech>=PVE_V_FUEL_FIRE){event(BG_EVENT_COVENANT,BG_PLAYERS+i,speech,bg_players[BG_PLAYERS+i].pos,a->generation);return;}
    if(a->speech_delay>0&&speech!=PVE_V_DEATH)return;
    if(bg_players[BG_PLAYERS+i].health<=0&&speech!=PVE_V_DEATH)return;
    a->speech_sequence++;a->speech_delay=speech==PVE_V_PAIN?1.2f:3.f;
    event(BG_EVENT_COVENANT,BG_PLAYERS+i,speech,bg_players[BG_PLAYERS+i].pos,a->generation);
}
void bg_pve_set_variant(unsigned i,unsigned variant){
    assert(i<bg_pve_count&&variant<PVE_R_COUNT);
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
    if(!variant){a->variant=a->armament=a->rank=0;return;}
    const bg_pve_variant*v=&bg_pve_variants[variant];assert(a->kind==v->kind);
    const bg_pve_definition*d=&v->def;const bg_pve_difficulty*s=&bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1];
    a->variant=variant;a->armament=v->armament;a->rank=v->rank;
    p->weapon=p->inventory[0]=v->weapon;p->pve_radius=d->radius;p->pve_height=d->height;
    p->health=d->health*s->vitality;p->shield=d->shield*s->shield;
    a->burst_pause=pve_range(d->first_delay)*s->first_delay;
    a->grenades=d->grenade_count[0]+(unsigned)(pve_random01()*(d->grenade_count[1]-d->grenade_count[0]+1));
    a->camouflage=(v->flags&PVE_R_CAMO)?1:0;a->super_camouflage=(v->flags&PVE_R_SUPER_CAMO)?1:0;
    a->decision_time=0;
}
static void pve_roster_tick(unsigned i,float dt){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
    a->speech_delay=fmaxf(0,a->speech_delay-dt);
    if(p->health<=0){
        if(a->death_weapon_time>0){
            a->death_weapon_time=fmaxf(0,a->death_weapon_time-dt);
            if(a->death_weapon_time==0&&!a->weapon_detonated){
                a->weapon_detonated=true;
                if(a->armament==PVE_ARM_FUEL){float pos[3]={p->pos[0],p->pos[1]+.12f,p->pos[2]};
                    pve_say(i,PVE_V_FUEL_EXPLOSION);
                    explode_profile(pos,BG_PLAYERS+i,bg_pve_dropped_fuel.damage,bg_pve_dropped_fuel.radius,BG_P_DROPPED_FUEL,0);}
            }
        }
        return;
    }
    if(a->variant){
        unsigned flags=bg_pve_variants[a->variant].flags;
        /* units.c: 1/120 per 30 Hz tick, super camouflage 1/90. */
        a->camouflage=clamp(a->camouflage+((flags&PVE_R_CAMO)?dt*.25f:-dt*.25f),0,1);
        a->super_camouflage=clamp(a->super_camouflage+((flags&PVE_R_SUPER_CAMO)?dt/3:-dt/3),0,1);
        p->invisibility=a->camouflage>0?1:0;p->camo_opacity=1-a->camouflage;
    }
    if(a->speech_delay<=0&&a->arrival==0&&(bg_pve_tick_number+i*31)%240==0)pve_say(i,a->aware?PVE_V_COMBAT:PVE_V_IDLE);
}
static float pve_strike_range(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];
    if(a->armament==PVE_ARM_SWORD)return bg_pve_variants[a->variant].strike_reach+(a->target>=0?bg_body_radius(&bg_players[a->target]):.2f);
    return pve_definition(i)->melee_range;
}
