/* Source-rule and encounter assertions, compiled into the real simulation. */
#include "test_jackal_shield.inc"
static void roster_acceptance(void){
    jackal_shield_acceptance();
    unsigned appeared=0;
    for(unsigned humans=1;humans<=4;humans++){
        bg_ff_start(humans);
        for(unsigned round=0;round<3;round++)for(unsigned wave=0;wave<5;wave++){
            bg_ff.round=round;bg_ff.wave=wave;ff_begin_wave();
            for(unsigned packet=0;packet<bg_ff.packets;packet++){
                const bg_ff_formation*f=&bg_ff_formations[ff_packet_kind(packet)];assert(f->count<=bg_ff.cap);
                for(unsigned n=0;n<f->count;n++)if(f->variant[n]){assert(bg_pve_variants[f->variant[n]].kind==f->kind[n]);appeared|=1u<<f->variant[n];}
            }
        }
    }
    assert(appeared==((1u<<PVE_R_COUNT)-2));
    bg_ff_start(1);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
    float pos[3]={4,bg_floor(4,0,12)+.015f,0};
    for(unsigned v=1;v<PVE_R_COUNT;v++){
        const bg_pve_variant*r=&bg_pve_variants[v];pve_spawn_actor(0,r->kind,r->weapon,0,pos,3.14159265f);bg_pve_set_variant(0,v);
        bg_player*p=&bg_players[4];bg_pve_actor*a=&bg_pve_actors[0];
        assert(pve_definition(0)==&r->def&&p->health==r->def.health*bg_pve_difficulties[2].vitality);
        assert(p->shield==r->def.shield*bg_pve_difficulties[2].shield);
        assert(a->rank==r->rank&&a->armament==r->armament&&p->weapon==r->weapon);
        a->target=0;a->aware=true;pve_decide(0);
        assert(actor_get(0)->meta.variant_definition_index==0);
        assert(pve_source_variants[0].grenade_combat.throw_grenade_chance==r->def.grenade_chance);
        if(r->flags&PVE_R_CAMO){
            assert(p->shield==0&&a->camouflage==1);
            pve_damage(4,0,1,false,BG_D_AR,false,0);
            float expected=fmaxf(0,1-bg_pve_camo_damage[BG_D_AR]);assert(a->camouflage==expected);
            pve_roster_tick(0,1.f/30);assert(fabsf(a->camouflage-fminf(1,expected+1.f/120))<1e-6f);
        }
        for(unsigned c=0;c<12;c++)if(a->armament){
            const bg_pve_animation*clip=&bg_pve_alt_hit_clips[a->kind][c];assert(clip->frames&&clip->vertices&&clip->duration>0);
        }
    }
    /* A weapon must retain its own projectile and charge, and may not leave a
     * pickable plasma-pistol stand-in when its source says detonate on drop. */
    pve_spawn_actor(0,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,0,pos,3.14159265f);bg_pve_set_variant(0,PVE_R_GRUNT_FUEL);
    bg_pve_actors[0].grenades=0;unsigned pickups=bg_pickup_count;pve_killed(4,0);assert(bg_pickup_count==pickups);
    float delay=bg_pve_actors[0].death_weapon_time;assert(delay>=bg_pve_fuel_drop_delay[0]&&delay<=bg_pve_fuel_drop_delay[1]);
    bg_clear_events();pve_roster_tick(0,delay+.01f);assert(bg_pve_actors[0].weapon_detonated);
    unsigned explosions=0;for(unsigned n=0;n<bg_event_count;n++)explosions+=bg_events[n].kind==BG_EVENT_EXPLOSION;assert(explosions==1);
    pve_roster_tick(0,1);unsigned again=0;for(unsigned n=0;n<bg_event_count;n++)again+=bg_events[n].kind==BG_EVENT_EXPLOSION;assert(again==1);
    /* Exercise discharge, not just extracted constants: one source charge,
     * the distinct projectile, then the held-trigger/release pause. */
    bg_ff_start(1);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
    memset(bg_pve_actors,0,sizeof(bg_pve_actors));bg_pve_count=0;
    bg_players[0].pos[0]=bg_players[0].pos[2]=0;bg_players[0].pos[1]=bg_floor(0,0,12)+.015f;
    pve_spawn_actor(0,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,0,pos,3.14159265f);bg_pve_set_variant(0,PVE_R_GRUNT_FUEL);
    bg_pve_actor*f=&bg_pve_actors[0];f->aware=f->visible=true;f->target=0;f->decision_time=9999;f->burst_pause=0;f->grenades=0;
    for(unsigned tick=0;tick<30;tick++)bg_pve_tick(1.f/30);
    assert(f->fire_pending&&f->shots==0);
    for(unsigned tick=0;tick<10;tick++)bg_pve_tick(1.f/30);
    assert(!f->fire_pending&&f->shots==1);
    unsigned fuel_projectiles=0;for(unsigned n=0;n<BG_MAX_PROJECTILES;n++){bg_projectile*q=bg_projectile_at(n);if(q&&q->active&&q->kind==BG_P_GRUNT_FUEL){fuel_projectiles++;assert(q->damage==bg_pve_grunt_fuel.damage&&q->radius==bg_pve_grunt_fuel.radius);}}
    assert(fuel_projectiles==1);
    for(unsigned tick=0;tick<60;tick++)bg_pve_tick(1.f/30);
    assert(f->shots==1&&!f->fire_pending);
    /* Sword pursuit covers the tactical charge distance but damage stays local
     * and waits for the source animation key. It never emits rifle projectiles. */
    bg_ff_start(1);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;bg_players[0].pos[0]=0;bg_players[0].pos[2]=0;bg_players[0].pos[1]=bg_floor(0,0,12)+.015f;bg_players[0].health=10000;bg_players[0].shield=100;bg_players[0].shield_delay=9999;
    pve_spawn_actor(0,BG_PVE_ELITE,BG_W_PLASMA_RIFLE,0,pos,3.14159265f);bg_pve_set_variant(0,PVE_R_ZEALOT_SWORD);ff_awaken(0);bg_pve_actors[0].grenades=0;
    float distance=distance2(bg_players[4].pos,bg_players[0].pos),health=bg_players[0].health+bg_players[0].shield;advance(30);
    assert(bg_pve_actors[0].shots==0&&distance2(bg_players[4].pos,bg_players[0].pos)<distance);
    assert(bg_players[0].health+bg_players[0].shield==health);
    bg_players[4].pos[0]=.6f;bg_players[4].pos[2]=0;bg_players[4].pos[1]=bg_floor(.6f,0,12)+.015f;
    bg_pve_actors[0].melee_time=0;bg_pve_actors[0].decision_time=0;advance(45);
    assert(bg_pve_actors[0].shots==0&&bg_players[0].health+bg_players[0].shield<health);
    /* Speech neither consumes combat randomness nor duplicates death messages
     * on a later tick. Actor-generation tags reject recycled-speaker events. */
    uint32_t random=pve_random;bg_pve_actors[0].speech_delay=0;bg_clear_events();pve_say(0,PVE_V_SPOT);pve_say(0,PVE_V_SPOT);assert(pve_random==random);
    assert(bg_event_count==1&&bg_events[0].kind==BG_EVENT_COVENANT);
    assert(bg_events[0].amount==bg_pve_actors[0].generation);
    puts("PASS 14 CE variants, all wave schedules, actor-specific rules, source camouflage, sword pursuit/keyframe/reach, fuel-rod death detonation and isolated speech RNG");
}
