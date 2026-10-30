/* Vehicle combat services for CE movement and vehicle firing variants. The
 * encounter owns goals/arrivals; the retained controller owns steering/throttle
 * and the existing original rigid-body solver owns movement/collisions. */
static bool pve_vehicle_kind(unsigned kind){return kind==BG_V_GHOST||kind==BG_V_BANSHEE||kind==BG_V_WRAITH||kind==BG_V_SHADE;}
static float pve_vehicle_damage_scale(unsigned profile){
    unsigned kind=profile==BG_D_GHOST?BG_V_GHOST:profile==BG_D_BANSHEE||profile==BG_D_FUEL_ROD?BG_V_BANSHEE:profile==BG_D_WRAITH?BG_V_WRAITH:profile==BG_D_SHADE?BG_V_SHADE:BG_VEHICLE_COUNT;
    return kind<BG_VEHICLE_COUNT?bg_vehicle_ai_defs[kind].damage:1;
}
static void pve_vehicle_mount(unsigned i,unsigned vehicle,bool immediate){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];bg_vehicle*v=&bg_vehicles[vehicle];
    assert(a->kind==BG_PVE_ELITE&&p->vehicle<0&&v->active&&v->occupants[0]<0&&pve_vehicle_kind(v->kind));
    p->vehicle=vehicle;p->seat=0;v->occupants[0]=BG_PLAYERS+i;
    const bg_seat_definition*s=bg_player_seat(p);p->seat_state=immediate?BG_SEAT_STABLE:BG_SEAT_ENTERING;
    p->seat_time=immediate?0:s->enter_time;p->anim_time=0;p->yaw=v->yaw;p->pitch=v->pitch;p->grounded=true;p->crouched=false;
    memset(p->velocity,0,12);p->support_vehicle=0;p->reload=p->charge=p->melee_time=0;
    bg_vehicle_seat_position(v,0,false,p->pos);a->desired_vehicle=-1;a->time=0;a->clip=PVE_IDLE;
    a->fire_pending=a->throw_pending=a->melee_pending=false;actor_get(i)->control.grenade_trying_to_throw=false;
    a->burst_time=a->shot_time=0;a->burst_pause=pve_range(bg_vehicle_ai_defs[v->kind].first_delay);
    a->vehicle_timer=a->vehicle_target_time=a->vehicle_special_delay=0;a->vehicle_special_denials=0;a->vehicle_mode=0;a->oversteer=0;memcpy(a->previous,p->pos,12);
    event(BG_EVENT_ENTER,BG_PLAYERS+i,v->kind,p->pos,0);
}
static bool pve_vehicle_approach(unsigned i,float dt){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
    a->vehicle_cooldown=fmaxf(0,a->vehicle_cooldown-dt);
    if(a->kind!=BG_PVE_ELITE||a->vehicle_cooldown>0||a->arrival||a->berserk||a->armament==PVE_ARM_SWORD)return false;
    int selected=a->desired_vehicle;
    if(selected<0){
        /* Match action_vehicle's eligibility before investing in an approach.
         * Each actor checks at 5 Hz; never perform a whole-grid vehicle search. */
        if((bg_pve_tick_number+i)%6)return false;
        float nearest=64;
        for(unsigned n=0;n<bg_vehicle_count;n++){
            bg_vehicle*v=&bg_vehicles[n];if(!v->active||!pve_vehicle_kind(v->kind)||v->occupants[0]>=0||(v->physics_valid&&v->up[1]<BG_VEHICLE_FLIP_MAX_UP))continue;
            if(v->kind==BG_V_BANSHEE&&fabsf(v->pos[1]-p->pos[1])>1.5f)continue;
            float d=distance2(v->pos,p->pos);if(d<nearest){nearest=d;selected=n;}
        }
        a->desired_vehicle=selected;a->vehicle_timer=0;
    }
    if(selected<0)return false;
    bg_vehicle*v=&bg_vehicles[selected];
    if(!v->active||v->occupants[0]>=0){a->desired_vehicle=-1;return false;}
    float entry[3],delta[3];bg_vehicle_transform(v,bg_enemy_vehicle_seats[v->kind].entry,entry);sub(delta,entry,p->pos);float reach=hypotf(delta[0],delta[2]);
    float eye[3]={p->pos[0],p->pos[1]+p->pve_height*.5f,p->pos[2]},target[3]={entry[0],fmaxf(p->pos[1],entry[1])+.4f,entry[2]},direction[3];sub(direction,target,eye);float length=sqrtf(dot(direction,direction));normalize(direction);
    if(bg_raycast(eye,direction,length)<length-.03f){a->desired_vehicle=-1;a->vehicle_cooldown=1;return false;}
    for(unsigned n=0;n<bg_vehicle_count;n++)if(n!=(unsigned)selected&&bg_vehicle_body_present(&bg_vehicles[n])&&bg_vehicle_hit_ray(&bg_vehicles[n],eye,direction,length)<length-.03f){a->desired_vehicle=-1;return false;}
    if(reach<1&&fabsf(entry[1]-p->pos[1])<1.5f){pve_vehicle_mount(i,selected,false);return true;}
    a->vehicle_timer+=dt;
    if(reach>8||a->vehicle_timer>6){a->vehicle_timer=0;a->vehicle_cooldown=2;a->desired_vehicle=-1;return false;}
    float speed=pve_definition(i)->move_speed;p->velocity[0]=delta[0]/fmaxf(reach,.01f)*speed;p->velocity[2]=delta[2]/fmaxf(reach,.01f)*speed;p->velocity[1]-=bg_movement.gravity*dt;
    bg_move_capsule(p,dt);if(p->grounded)p->velocity[1]=0;p->yaw=atan2f(-delta[2],delta[0]);if(a->clip!=PVE_RUN){a->clip=PVE_RUN;a->time=0;}
    memcpy(p->last_pos,p->pos,12);return true;
}
/* Five rays cover the tag pathfinding radius. Terrain support probes reject
 * cliff routes before the original hull solver reaches them. */
static float pve_vehicle_clearance(const bg_vehicle*v,const float direction[3],float reach){
    const bg_vehicle_ai_definition*d=&bg_vehicle_ai_defs[v->kind];float best=reach;
    float right[3]={direction[2],0,-direction[0]};normalize(right);
    float origins[5][3],hits[5];
    for(int side=-2;side<=2;side++){
        float *o=origins[side+2];for(unsigned k=0;k<3;k++)o[k]=v->pos[k]+right[k]*d->radius*side*.5f;o[1]+=.6f;
    }
#if defined(BG_VEHICLE_QUERY_BASELINE) || defined(BG_BLAM_BSP)
    /* The optional source-BSP service retains its own collision semantics. */
    for(unsigned lane=0;lane<5;lane++)hits[lane]=bg_raycast(origins[lane],direction,reach);
#else
    bg_world_clearance_rays(origins,direction,reach,hits);
#endif
    for(unsigned lane=0;lane<5;lane++)best=fminf(best,hits[lane]);
    if(v->kind!=BG_V_BANSHEE){
        float ground=bg_floor(v->pos[0],v->pos[2],v->pos[1]+1),end=bg_floor(v->pos[0]+direction[0]*reach,v->pos[2]+direction[2]*reach,v->pos[1]+1);
        if(end<ground-.7f||end>ground+.7f)best=0;
    }
    return best;
}
static void pve_vehicle_inputs(bg_input inputs[BG_UNITS],float dt){
    if(!pve_active)return;
    const bg_pve_difficulty*scale=&bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1];
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];if(!a->occupied||p->health<=0||p->vehicle<0)continue;
        bg_vehicle*v=&bg_vehicles[p->vehicle];if(!pve_vehicle_kind(v->kind)||p->seat_state!=BG_SEAT_STABLE)continue;
        bg_input*in=&inputs[BG_PLAYERS+i];const bg_vehicle_ai_definition*d=&bg_vehicle_ai_defs[v->kind];
        a->vehicle_timer+=dt;a->vehicle_target_time+=dt;a->vehicle_special_delay=fmaxf(0,a->vehicle_special_delay-dt);a->burst_pause-=dt;a->shot_time-=dt;
        if(a->target<0||bg_players[a->target].health<=0)continue;
        float target[3];memcpy(target,a->visible?bg_players[a->target].pos:a->last_seen,12);target[1]+=.35f;
        float delta[3];sub(delta,target,v->pos);float distance=sqrtf(dot(delta,delta));if(distance<.01f)continue;
        float goal[3];memcpy(goal,target,12);
        bool flying=v->kind==BG_V_BANSHEE;
        if(flying){
            /* Keep moving through a strafe, then reacquire on the source's
             * repeat timer. The arena goal provider replaces campaign orders. */
            if(distance<d->abort_range&&!a->vehicle_mode){
                a->vehicle_mode=1;a->vehicle_timer=0;
                for(unsigned k=0;k<3;k++)a->vehicle_goal[k]=v->pos[k]+v->forward[k]*12;
                a->vehicle_goal[1]=fmaxf(a->vehicle_goal[1],bg_floor(v->pos[0],v->pos[2],v->pos[1])+6);
            }
            if(a->vehicle_mode&&a->vehicle_timer<d->repeat)memcpy(goal,a->vehicle_goal,12);
            else{if(a->vehicle_mode&&a->vehicle_special_denials)a->vehicle_special_denials--;a->vehicle_mode=0;goal[1]+=3;}
            float floor=bg_floor(goal[0],goal[2],v->pos[1]+20);goal[1]=fmaxf(goal[1],floor+3);
        }else if(v->kind!=BG_V_SHADE){
            if(!a->visible){pve_destination(i);memcpy(goal,a->destination,12);}
            else{
                float desired=(d->desired[0]+d->desired[1])*.5f;
                for(unsigned k=0;k<3;k++)goal[k]=target[k]-delta[k]/distance*desired;
                goal[1]=v->pos[1];
                if(distance>=d->desired[0]&&distance<=d->desired[1])memcpy(goal,v->pos,12);
            }
        }else memcpy(goal,v->pos,12);
        float movement[3];sub(movement,goal,v->pos);if(!flying)movement[1]=0;
        float move_length=sqrtf(dot(movement,movement));
        if(move_length>.1f&&v->kind!=BG_V_SHADE){
            float direction[3];memcpy(direction,movement,12);normalize(direction);float reach=flying?d->avoidance:fmaxf(1.5f,d->radius*2);
            float clear=pve_vehicle_clearance(v,direction,reach),correction[3]={0};
            if(clear<reach*.8f){
                if(flying){correction[1]=reach-clear;correction[0]=-direction[2]*2;correction[2]=direction[0]*2;}
                else{
                    float left[3]={-direction[2],0,direction[0]},right[3]={direction[2],0,-direction[0]};
                    float l=pve_vehicle_clearance(v,left,reach),r=pve_vehicle_clearance(v,right,reach);
                    const float*safe=l>r?left:right;
                    for(unsigned k=0;k<3;k++)movement[k]=fmaxf(l,r)>reach*.8f?safe[k]*reach:0;
                }
            }
            /* actor_move_update's asymmetric avoidance filter. */
            float smoothing=dot(correction,correction)>dot(a->avoidance,a->avoidance)?.3f:.05f;
            for(unsigned k=0;k<3;k++){a->avoidance[k]+=(correction[k]-a->avoidance[k])*smoothing;movement[k]+=a->avoidance[k];}
        }
        float aim_dir[3];memcpy(aim_dir,delta,12);normalize(aim_dir);
        float facing[3]={v->forward[0],-v->forward[2],v->forward[1]},aim_ce[3]={aim_dir[0],-aim_dir[2],aim_dir[1]},desired[3]={movement[0],-movement[2],movement[1]},outface[3],throttle[3];
        if(!v->physics_valid){facing[0]=cosf(v->yaw);facing[1]=sinf(v->yaw);facing[2]=0;}
        bg_vehicle_ai_movement(v->kind,facing,aim_ce,desired,v->speed,flying,&a->oversteer,outface,throttle);
        p->yaw=atan2f(outface[1],outface[0]);p->pitch=flying?atan2f(outface[2],hypotf(outface[0],outface[1])):0;
        in->forward=v->kind==BG_V_SHADE?0:throttle[0];in->strafe=v->kind==BG_V_SHADE?0:-throttle[1];
        if(!flying&&move_length<.1f)in->forward=in->strafe=0;
        float origin[3];vehicle_weapon_origin(v,origin);
        unsigned gun=v->kind==BG_V_GHOST?1:v->kind==BG_V_BANSHEE?4:v->kind==BG_V_WRAITH?6:7;
        const bg_damage_profile*weapon=&bg_damage_profiles[bg_mounted_profiles[gun].profile];
        if(a->visible){float lead=d->leading*distance/fmaxf(weapon->speed_start*30,.01f);for(unsigned k=0;k<3;k++)target[k]+=bg_players[a->target].velocity[k]*lead;}
        sub(aim_dir,target,origin);normalize(aim_dir);
        bool can_fire=a->aware&&a->visible&&distance<d->range&&!pve_friendly_line(i,origin,target);
        if(v->kind==BG_V_WRAITH){
            bool check_path=a->burst_pause<=0||d->special_mode==2;
#ifdef BG_VEHICLE_QUERY_BASELINE
            check_path=true;
#endif
            can_fire=can_fire&&pve_ballistic_arc_checked(origin,target,weapon->speed_start*30,bg_movement.gravity*weapon->gravity,d->superballistic>0&&distance>d->superballistic,aim_dir,check_path);
        }
        if(!(d->flags&256)){p->yaw=atan2f(-aim_dir[2],aim_dir[0]);p->pitch=atan2f(aim_dir[1],hypotf(aim_dir[0],aim_dir[2]));}
        else can_fire=can_fire&&dot(aim_dir,v->forward)>.97f;
        /* CE strafe bombs allow vehicle targets, but explicitly reject players
         * on foot. Delay is 10..11.5 seconds and three intervening strafes. */
        if(can_fire&&d->special_mode==2&&a->burst_time<=0&&a->vehicle_special_delay<=0&&!a->vehicle_special_denials){
            a->vehicle_special_delay=d->special_delay+pve_range((float[]){0,1.5f});
            if(bg_players[a->target].vehicle>=0&&pve_range((float[]){0,1})<d->special_chance){
                in->secondary_fire=true;a->vehicle_special_denials=3;a->burst_pause=pve_range(d->pause)*scale->pause;continue;
            }
        }
        bool new_target=a->vehicle_target_time<d->new_target_time;
        float duration_scale=new_target&&d->new_target[0]>0?d->new_target[0]:1;
        float pause_scale=new_target&&d->new_target[1]>0?d->new_target[1]:1;
        float rate_scale=new_target&&d->new_target[2]>0?d->new_target[2]:1;
        if(can_fire&&a->burst_pause<=0){
            if(a->burst_time<=0)a->burst_time=pve_range(d->burst)*duration_scale;
            a->burst_time-=dt;
            if(a->shot_time<=0){in->fire=true;a->shot_time=d->rate>0?fmaxf(2,floorf(30/(d->rate*scale->rate*rate_scale)))/30.f:dt;}
            if(a->burst_time<=0)a->burst_pause=pve_range(d->pause)*scale->pause*pause_scale;
        }
    }
}
