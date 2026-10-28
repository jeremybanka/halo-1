static unsigned pve_spawn_actor(unsigned i,unsigned kind,unsigned weapon,unsigned formation,const float position[3],float yaw){
    assert(i<BG_PVE_MAX&&kind<BG_PVE_KINDS);
    bg_pve_actor*a=&bg_pve_actors[i];uint16_t generation=a->generation+1;
    /* References to a recycled unit slot must not become references to its
     * replacement. Keep flying ordnance, but detach corpse attachments. */
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){
        bg_projectile*q=bg_projectile_at(j);if(!q||!q->active)continue;
        if(q->attached==(int)(BG_PLAYERS+i)){q->attached=-1;q->life=fminf(q->life,.1f);}
        if(q->tracked==(int)(BG_PLAYERS+i))q->tracked=-1;
    }
    memset(a,0,sizeof(*a));memset(actor_get(i),0,sizeof(*actor_get(i)));a->kind=kind;a->formation=formation;a->target=-1;a->occupied=true;a->generation=generation;a->decision_time=(i%5)*.04f;a->grenades=2;
    bg_player*p=&bg_players[BG_PLAYERS+i];memset(p,0,sizeof(*p));const bg_pve_definition*d=pve_definition_for(kind,weapon);const bg_pve_difficulty*scale=&bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1];
    memcpy(p->pos,position,12);memcpy(p->last_pos,position,12);memcpy(a->previous,position,12);memcpy(a->destination,position,12);
    p->yaw=yaw;p->pve_radius=d->radius;p->pve_height=d->height;p->health=d->health*scale->vitality;p->shield=d->shield*scale->shield;p->vehicle=p->seat=p->needle_owner=-1;p->grounded=true;p->ground_normal[1]=1;
    p->weapon=weapon;p->inventory[0]=weapon;p->inventory[1]=-1;p->ammo=100;a->burst_pause=pve_range(d->first_delay)*scale->first_delay;
    a->grenades=d->grenade_count[0]+(unsigned)(pve_random01()*(d->grenade_count[1]-d->grenade_count[0]+1));
    actor_get(i)->emotions.last_flee_failed_time=NONE;actor_get(i)->control.grenade_last_check_time=NONE;
    if(i>=bg_pve_count)bg_pve_count=i+1;
    return i;
}
static void pve_fire(unsigned i,const float origin[3],const float direction[3]){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
    bg_projectile*q=projectile(w->projectile,BG_PLAYERS+i,origin,direction,w->speed,w->damage,0);
    if(q){q->damage_profile=weapon_damage(p->weapon,false);if(q->kind==BG_P_NEEDLE)q->tracked=a->target;a->shots++;event(BG_EVENT_FIRE,BG_PLAYERS+i,p->weapon,origin,1);}
}
void bg_pve_tick(float dt){
    if(!pve_active)return;
    bg_pve_tick_number++;pve_encounter_grenade_time=fmaxf(0,pve_encounter_grenade_time-dt);
    const bg_pve_difficulty*scale=&bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1];
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];if(!a->occupied)continue;
        bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=pve_definition_for(a->kind,bg_players[BG_PLAYERS+i].weapon);a->time+=dt;
        if(p->health<=0){a->death_time+=dt;continue;}
        if(a->arrival==1)continue;
        if(a->arrival==2)continue;
        p->hurt=fmaxf(0,p->hurt-dt);p->shield_delay=fmaxf(0,p->shield_delay-dt);
        if(!p->shield_delay&&d->shield>0)p->shield=d->shield_recharge>0?fminf(d->shield*scale->shield,p->shield+d->shield/d->shield_recharge*scale->recharge*dt):d->shield*scale->shield;
        a->panic_time=fmaxf(0,a->panic_time-dt);a->cover_time=fmaxf(0,a->cover_time-dt);a->melee_time=fmaxf(0,a->melee_time-dt);
        a->grenade_time=fmaxf(0,a->grenade_time-dt);a->evade_cooldown=fmaxf(0,a->evade_cooldown-dt);
#ifdef N64
        uint32_t begin=get_ticks_us();
#endif
        a->decision_time-=dt;if(a->decision_time<=0){pve_decide(i);a->decision_time+=.2f;}
#ifdef N64
        bg_pve_ai_us+=get_ticks_us()-begin;begin=get_ticks_us();
#endif
        unsigned clip=PVE_IDLE;float distance=a->target>=0?sqrtf(distance2(p->pos,bg_players[a->target].pos)):100;
        bool retreat=a->action==_actor_action_flee||(a->action==_actor_action_guard&&actor_get(i)->state.action_data.guard.cower);
        bool moving=a->aware&&a->target>=0&&(retreat||!a->visible||distance>d->desired[1]||(a->berserk&&distance>d->melee_range*.8f));
        if(a->evade_time>0){
            a->evade_time=fmaxf(0,a->evade_time-dt);for(unsigned k=0;k<3;k++)p->velocity[k]=a->evade_dir[k]*fmaxf(d->move_speed,1.5f);clip=a->clip;
        }else if(moving&&!a->melee_pending&&!a->throw_pending&&!a->fire_pending){
            float delta[3];sub(delta,a->destination,p->pos);float length=hypotf(delta[0],delta[2]);
            if(length>.08f){float speed=retreat?d->flee_speed:d->move_speed;p->velocity[0]=delta[0]/length*speed;p->velocity[2]=delta[2]/length*speed;clip=retreat?PVE_FLEE:PVE_RUN;}
            else p->velocity[0]=p->velocity[2]=0;
        }else p->velocity[0]=p->velocity[2]=0;
        p->velocity[1]-=bg_movement.gravity*dt;bg_move_capsule(p,dt);if(p->grounded)p->velocity[1]=0;
        if(a->target>=0&&a->evade_time<=0){
            const float*target=a->visible?bg_players[a->target].pos:a->last_seen;float dx=target[0]-p->pos[0],dz=target[2]-p->pos[2];
            float yaw=retreat?atan2f(-p->velocity[2],p->velocity[0]):atan2f(-dz,dx),delta=remainderf(yaw-p->yaw,6.283185307f);
            p->yaw+=clamp(delta,-d->turn_rate*dt,d->turn_rate*dt);
        }
        float origin[3]={p->pos[0]+cosf(p->yaw)*d->gun[0],p->pos[1]+(d->gun[2]>0?d->gun[2]:d->eye*.8f),p->pos[2]-sinf(p->yaw)*d->gun[0]},target[3],dir[3]={1,0,0};
        bool can_fire=a->aware&&a->visible&&!retreat&&!a->throw_pending&&!a->melee_pending&&a->evade_time<=0&&a->target>=0&&bg_players[a->target].health>0;
        if(can_fire){
            memcpy(target,bg_players[a->target].pos,12);target[1]+=.35f;sub(dir,target,origin);normalize(dir);
            can_fire=distance<d->range&&dir[0]*cosf(p->yaw)-dir[2]*sinf(p->yaw)>.7f&&!pve_friendly_line(i,origin,target);
            if(!can_fire&&distance<d->range&&a->target>=0)pve_destination(i);
        }
        a->burst_pause-=dt;a->shot_time-=dt;
        if(a->kind==BG_PVE_HUNTER){
            if(can_fire&&distance>d->melee_range&&!a->fire_pending&&a->burst_pause<=0){a->fire_pending=true;a->fire_time=bg_pve_fuel_rod.charge;a->clip=PVE_FIRE;a->time=0;}
            if(a->fire_pending){
                clip=PVE_FIRE;a->fire_time-=dt;
                if(a->fire_time<=0){
                    if(can_fire&&pve_ballistic(origin,target,bg_pve_fuel_rod.speed,bg_movement.gravity*bg_pve_fuel_rod.gravity,dir)){
                        bg_projectile*q=projectile(BG_P_FUEL,BG_PLAYERS+i,origin,dir,bg_pve_fuel_rod.speed,bg_pve_fuel_rod.damage,bg_pve_fuel_rod.radius);
                        if(q){a->shots++;event(BG_EVENT_FIRE,BG_PLAYERS+i,BG_W_PLASMA_RIFLE,origin,1);}
                    }
                    a->fire_pending=false;a->burst_pause=pve_range(d->pause)*scale->pause;
                }
            }
        }else if(can_fire){
            if(a->burst_pause<=0&&a->burst_time<=0)a->burst_time=pve_range(d->burst);
            if(a->burst_time>0){
                a->burst_time-=dt;
                if(a->shot_time<=0){float cone[3];bg_combat_cone(dir,0,d->error*scale->error,pve_random01(),pve_random01(),cone);pve_fire(i,origin,cone);a->shot_time=1.f/fmaxf(d->rate*scale->rate,.1f);clip=PVE_FIRE;}
                if(a->burst_time<=0)a->burst_pause=pve_range(d->pause)*scale->pause;
            }
        }
        if((a->kind==BG_PVE_ELITE||a->kind==BG_PVE_HUNTER)&&a->visible&&distance<d->melee_range&&a->melee_time<=0&&a->target>=0&&!a->throw_pending){
            a->melee_time=d->melee_delay*scale->melee_delay;a->melee_pending=true;a->fire_pending=false;clip=PVE_MELEE;
        }
        if(a->melee_pending&&a->clip==PVE_MELEE&&a->time>=d->melee_key){
            a->melee_pending=false;
            if(a->target>=0&&a->visible&&distance<d->melee_range)damage_player_profile(a->target,BG_PLAYERS+i,pve_range(d->melee_damage)*(100.f/bg_combat_body_max),false,false,0,false,false,1);
        }
        if(a->throw_pending){
            clip=PVE_THROW;
            if(a->time>=d->throw_key){
                float velocity=fmaxf(d->grenade_speed,4);
                if(pve_ballistic(origin,a->throw_target,velocity,bg_movement.gravity*bg_grenade_profiles[1].gravity,dir)){
                    bg_projectile*q=projectile(BG_P_PLASMA_GRENADE,BG_PLAYERS+i,origin,dir,velocity,260,2.2f);
                    if(q){q->life=bg_grenade_profiles[1].fuse;q->damage_profile=BG_D_PLASMA_GRENADE;a->grenades--;event(BG_EVENT_GRENADE,BG_PLAYERS+i,1,origin,1);pve_encounter_grenade_time=d->grenade_timeout*scale->grenade_timer/(bg_ff.active&&bg_ff.round>0?2:1);}
                }
                a->throw_pending=false;actor_get(i)->control.grenade_trying_to_throw=false;a->grenade_time=d->throw_duration;
            }
        }
        if(a->melee_pending)clip=PVE_MELEE;
        bool locked=(a->clip==PVE_FIRE&&a->time<.18f)||(a->clip==PVE_MELEE&&a->time<d->melee_duration)||(a->clip==PVE_THROW&&a->time<d->throw_duration)||a->evade_time>0;
        if(clip!=a->clip&&!locked){a->clip=clip;a->time=0;}
        if(distance2(p->pos,a->previous)<.00005f&&moving)a->stuck_time+=dt;else a->stuck_time=0;memcpy(a->previous,p->pos,12);memcpy(p->last_pos,p->pos,12);
#ifdef N64
        bg_pve_move_us+=get_ticks_us()-begin;
#endif
    }
}
