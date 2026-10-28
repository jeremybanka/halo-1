/* Bounded services for the original action selectors. Grenade desire/check
 * cadence runs through the verbatim CE handlers; trajectory and movement use
 * this port's collision queries and source tag distances/timings. */
static float pve_encounter_grenade_time;
static bool pve_friendly_line(unsigned i,const float origin[3],const float target[3]){
    float d[3];sub(d,target,origin);float length2=dot(d,d);if(length2<.001f)return false;
    for(unsigned j=0;j<bg_pve_count;j++)if(i!=j&&bg_players[BG_PLAYERS+j].health>0&&bg_pve_actors[j].arrival!=1){
        bg_player*q=&bg_players[BG_PLAYERS+j];float center[3]={q->pos[0],q->pos[1]+q->pve_height*.5f,q->pos[2]},v[3];sub(v,center,origin);
        float t=dot(v,d)/length2;if(t<=0||t>=1)continue;float distance=0;for(unsigned k=0;k<3;k++){float x=v[k]-t*d[k];distance+=x*x;}
        float radius=q->pve_radius+.15f;if(distance<radius*radius)return true;
    }
    return false;
}
static bool pve_ballistic(const float origin[3],const float target[3],float speed,float gravity,float direction[3]){
    float dx=target[0]-origin[0],dz=target[2]-origin[2],height=target[1]-origin[1],range=hypotf(dx,dz),v2=speed*speed;
    float disc=v2*v2-gravity*(gravity*range*range+2*height*v2);if(range<.1f||disc<0||speed<.1f)return false;
    float tangent=(v2-sqrtf(disc))/(gravity*range),co=1/sqrtf(1+tangent*tangent);
    direction[0]=dx/range*co;direction[1]=tangent*co;direction[2]=dz/range*co;
    float previous[3];memcpy(previous,origin,12);float duration=range/(speed*co);
    for(unsigned step=1;step<=12;step++){
        float t=duration*step/12,point[3],d[3];for(unsigned k=0;k<3;k++)point[k]=origin[k]+direction[k]*speed*t;point[1]-=.5f*gravity*t*t;
        sub(d,point,previous);float distance=sqrtf(dot(d,d));if(distance>.0001f){for(unsigned k=0;k<3;k++)d[k]/=distance;if(bg_raycast(previous,d,distance)<distance-.03f)return false;}memcpy(previous,point,12);
    }
    return true;
}
static bool actor_action_test_grenade(long i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=pve_definition_for(a->kind,bg_players[BG_PLAYERS+i].weapon);
    if(!a->grenades||a->target<0||!a->visible||a->arrival||a->evade_time>0||a->melee_pending||a->grenade_time>0||pve_encounter_grenade_time>0)return false;
    float distance=sqrtf(distance2(p->pos,bg_players[a->target].pos));if(distance<d->grenade_range[0]||distance>d->grenade_range[1])return false;
    unsigned enemies=0;for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0&&distance2(bg_players[h].pos,bg_players[a->target].pos)<=d->grenade_radius*d->grenade_radius+.01f)enemies++;
    if(enemies<d->grenade_minimum)return false;
    for(unsigned j=0;j<bg_pve_count;j++)if(bg_players[BG_PLAYERS+j].health>0&&distance2(bg_players[BG_PLAYERS+j].pos,bg_players[a->target].pos)<d->grenade_collateral*d->grenade_collateral)return false;
    float origin[3]={p->pos[0],p->pos[1]+d->eye,p->pos[2]},direction[3];memcpy(a->throw_target,bg_players[a->target].pos,12);a->throw_target[1]+=.15f;
    return pve_ballistic(origin,a->throw_target,fmaxf(d->grenade_speed,4),bg_movement.gravity*bg_grenade_profiles[1].gravity,direction);
}
static bool actor_action_try_to_throw_grenade(long i,bool first){
    (void)first;bg_pve_actor*a=&bg_pve_actors[i];if(a->throw_pending)return true;
    if(!actor_action_test_grenade(i)){actor_get(i)->control.grenade_trying_to_throw=false;return false;}
    a->throw_pending=true;a->clip=PVE_THROW;a->time=0;return true;
}
static bool pve_try_evade(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];const bg_pve_definition*d=pve_definition_for(a->kind,bg_players[BG_PLAYERS+i].weapon);bg_player*p=&bg_players[BG_PLAYERS+i];
    if(a->arrival||a->evade_time>0||a->melee_pending||a->throw_pending||a->evade_cooldown>0||a->kind==BG_PVE_HUNTER)return false;
    float threat[3];bool danger=false;
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){
        bg_projectile*q=bg_projectile_at(j);if(!q||!q->active||q->attached==(int)(BG_PLAYERS+i))continue;
        if(q->kind!=BG_P_FRAG&&q->kind!=BG_P_PLASMA_GRENADE&&q->kind!=BG_P_ROCKET)continue;
        if(distance2(q->pos,p->pos)>9)continue;
        float ray[3];sub(ray,q->pos,p->pos);float length=sqrtf(dot(ray,ray));if(length>.01f){for(unsigned k=0;k<3;k++)ray[k]/=length;if(bg_raycast(p->pos,ray,length)<length-.02f)continue;}
        memcpy(threat,q->pos,12);danger=true;break;
    }
    if(!danger)return false;
    int node=pve_node(p->pos),chosen=-1;if(node<0)return false;
    float best=distance2(p->pos,threat);
    for(unsigned k=0;k<8;k++)if(pve_nav_edges[node]&(1u<<k)){
        int next=pve_neighbor(node,k);float position[3];pve_node_pos(next,position);float score=distance2(position,threat);
        if(score>best){best=score;chosen=next;}
    }
    if(chosen<0)return false;
    float point[3];pve_node_pos(chosen,point);sub(a->evade_dir,point,p->pos);a->evade_dir[1]=0;normalize(a->evade_dir);
    a->clip=(a->evade_dir[0]*sinf(p->yaw)+a->evade_dir[2]*cosf(p->yaw))>0?PVE_EVADE_RIGHT:PVE_EVADE_LEFT;a->time=0;a->evade_time=d->evade_duration;
    a->evade_cooldown=d->evade_delay/(bg_ff.active?1.25f:1);
    if(pve_random01()<d->evade_cover_chance){actor_get(i)->state.action=_actor_action_flee;actor_get(i)->state.action_data.flee.panic_type=0;a->panic_time=pve_range(d->hide);}
    return true;
}
