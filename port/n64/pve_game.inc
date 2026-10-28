/* Bounded five-unit PvE experiment. Unit identity is independent of cameras. */
#include <assert.h>
bg_pve_actor bg_pve_actors[BG_PVE_MAX];
unsigned bg_pve_count,bg_pve_tick_number;
uint32_t bg_pve_ai_us,bg_pve_move_us;
static bool pve_active;
static uint32_t pve_random=0x505645;
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
#define PVE_GRID 25
#define PVE_NODES (PVE_GRID*PVE_GRID)
static float pve_nav_height[PVE_NODES];
static uint8_t pve_nav_edges[PVE_NODES];
static uint16_t pve_nav_distance[4][PVE_NODES];
static int pve_nav_goal[4];
#ifndef BG_PVE_NAV_BUILD
extern const float bg_pve_nav_heights[PVE_NODES];
extern const uint8_t bg_pve_nav_links[PVE_NODES];
#endif
static const int pve_dx[4]={1,-1,0,0},pve_dz[4]={0,0,1,-1};
static int pve_node(const float pos[3]){
    int x=(int)floorf(pos[0]+12.5f),z=(int)floorf(pos[2]+12.5f);
    if(x<0||x>=PVE_GRID||z<0||z>=PVE_GRID)return -1;
    return z*PVE_GRID+x;
}
static void pve_node_pos(int node,float out[3]){out[0]=node%PVE_GRID-12;out[1]=pve_nav_height[node];out[2]=node/PVE_GRID-12;}
static void pve_nav_init(void){
#ifdef BG_PVE_NAV_BUILD
    for(int n=0;n<PVE_NODES;n++){
        float x=n%PVE_GRID-12,z=n/PVE_GRID-12;bg_player p={0};p.vehicle=-1;p.pve_radius=.2f;p.pve_height=.8f;p.pos[0]=x;p.pos[2]=z;p.pos[1]=bg_floor(x,z,100)+.015f;
        pve_nav_height[n]=p.pos[1]>-999&&bg_terrain_clearance(&p)?p.pos[1]:-1000;
    }
    for(int n=0;n<PVE_NODES;n++)for(unsigned k=0;k<4;k++){
        int x=n%PVE_GRID+pve_dx[k],z=n/PVE_GRID+pve_dz[k];if(x<0||x>=PVE_GRID||z<0||z>=PVE_GRID)continue;
        int next=z*PVE_GRID+x;if(pve_nav_height[n]<-999||pve_nav_height[next]<-999||fabsf(pve_nav_height[n]-pve_nav_height[next])>.3f)continue;
        bool clear=true;
        for(unsigned step=0;step<=8;step++){
            bg_player p={0};p.vehicle=-1;p.pve_radius=.2f;p.pve_height=.8f;p.pos[0]=n%PVE_GRID-12+pve_dx[k]*(step/8.f);p.pos[2]=n/PVE_GRID-12+pve_dz[k]*(step/8.f);
            p.pos[1]=bg_floor(p.pos[0],p.pos[2],fmaxf(pve_nav_height[n],pve_nav_height[next])+.4f)+.015f;
            if(!bg_terrain_clearance(&p)||p.pos[1]<-999){clear=false;break;}
        }
        if(clear)pve_nav_edges[n]|=1u<<k;
    }
#else
    memcpy(pve_nav_height,bg_pve_nav_heights,sizeof(pve_nav_height));memcpy(pve_nav_edges,bg_pve_nav_links,sizeof(pve_nav_edges));
#endif
    for(unsigned p=0;p<4;p++)pve_nav_goal[p]=-2;
}
static void pve_path(unsigned target,const float pos[3]){
    int goal=pve_node(pos);if(goal==pve_nav_goal[target])return;
    pve_nav_goal[target]=goal;memset(pve_nav_distance[target],255,sizeof(pve_nav_distance[target]));
    if(goal<0||pve_nav_height[goal]<-999)return;
    uint16_t queue[PVE_NODES];unsigned first=0,last=0;queue[last++]=goal;pve_nav_distance[target][goal]=0;
    while(first<last){int node=queue[first++];for(unsigned k=0;k<4;k++)if(pve_nav_edges[node]&(1u<<k)){
        int next=node+pve_dx[k]+PVE_GRID*pve_dz[k];
        if(pve_nav_distance[target][next]==UINT16_MAX){pve_nav_distance[target][next]=pve_nav_distance[target][node]+1;queue[last++]=next;}
    }}
}
static void pve_destination(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
    if(a->target<0)return;
    int node=pve_node(p->pos);if(node<0)return;
    pve_path(a->target,a->last_seen);a->path_queries++;unsigned best=pve_nav_distance[a->target][node];int chosen=node;
    bool retreat=a->action==_actor_action_flee||(a->action==_actor_action_guard&&actor_get(i)->state.action_data.guard.cower);
    for(unsigned k=0;k<4;k++)if(pve_nav_edges[node]&(1u<<k)){
        int next=node+pve_dx[k]+PVE_GRID*pve_dz[k];unsigned cost=pve_nav_distance[a->target][next];
        if(cost==UINT16_MAX)continue;
        if((retreat&&cost>best)||(!retreat&&cost<best)){best=cost;chosen=next;}
    }
    pve_node_pos(chosen,a->destination);
}
static bool pve_sees(unsigned i,unsigned target){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=&bg_pve_definitions[a->kind];
    float origin[3]={p->pos[0],p->pos[1]+d->eye,p->pos[2]},point[3]={bg_players[target].pos[0],bg_players[target].pos[1]+.4f,bg_players[target].pos[2]},dir[3];
    sub(dir,point,origin);float distance=sqrtf(dot(dir,dir));if(distance>d->vision)return false;
    if(distance<.01f)return true;
    for(unsigned k=0;k<3;k++)dir[k]/=distance;
    if(!a->aware&&dir[0]*cosf(p->yaw)-dir[2]*sinf(p->yaw)<cosf(d->vision_angle))return false;
    a->los_tests++;return bg_raycast(origin,dir,distance)>=distance-.02f;
}
static void pve_decide(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=&bg_pve_definitions[a->kind];
    a->decisions++;a->visible=false;float nearest=1e9f;int target=-1;
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0&&pve_sees(i,h)){
        float distance=distance2(p->pos,bg_players[h].pos);if(distance<nearest){nearest=distance;target=h;}}
    if(target>=0){a->visible=true;a->notice_time+=.2f;if(a->notice_time>=d->notice)a->aware=true;
        if(a->target!=target)a->burst_pause=pve_range(d->first_delay);
        a->target=target;memcpy(a->last_seen,bg_players[target].pos,12);
    }else a->notice_time=0;
    struct actor_datum*s=actor_get(i);s->meta.definition_index=a->kind;s->meta.unit_index=BG_PLAYERS+i;
    s->state.combat_status=a->aware?(a->visible?5:3):0;s->input.shield_vitality=d->shield?p->shield/d->shield:0;
    s->situation.area_friends_by_type[0]=s->situation.close_friends_by_type[0]=0;
    for(unsigned j=0;j<bg_pve_count;j++)if(j!=i&&bg_pve_actors[j].kind==BG_PVE_ELITE&&bg_players[BG_PLAYERS+j].health>0){
        float dist=distance2(p->pos,bg_players[BG_PLAYERS+j].pos);
        s->situation.area_friends_by_type[0]+=dist<64;s->situation.close_friends_by_type[0]+=dist<16;
    }
    if(a->kind==BG_PVE_GRUNT)grunt_decide_action(i);else elite_decide_action(i);
    a->action=s->state.action;a->recent_damage=0;
    if(a->aware)pve_destination(i);
}
static void pve_killed(unsigned unit,int owner){
    unsigned i=unit-BG_PLAYERS;if(i>=bg_pve_count)return;
    bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[i];
    if(p->health<=0)return;
    p->health=p->shield=0;a->clip=PVE_DEATH;a->time=0;p->animation=BG_ANIM_DIE;memset(p->velocity,0,12);
    int pickup=bg_add_pickup(p->weapon,p->pos);if(pickup>=0){bg_pickups[pickup].dropped=true;bg_pickups[pickup].ammo=50;bg_pickups[pickup].reserve=0;}
    event(BG_EVENT_DIE,unit,p->weapon,p->pos,1);
    if(owner>=0&&owner<(int)active_players){bg_players[owner].score++;statistics.kills[owner]++;}
    if(a->kind==BG_PVE_ELITE)for(unsigned j=0;j<bg_pve_count;j++)if(bg_pve_actors[j].kind==BG_PVE_GRUNT&&bg_players[BG_PLAYERS+j].health>0&&distance2(p->pos,bg_players[BG_PLAYERS+j].pos)<64&&pve_random01()<bg_pve_definitions[0].leader_panic){
        actor_get(j)->stimuli.panic_type=8;actor_get(j)->stimuli.panic_prop_index=1;bg_pve_actors[j].decision_time=0;
    }
}
static void pve_damage(unsigned unit,int owner,float amount,bool headshot,unsigned profile,bool behind){
    unsigned i=unit-BG_PLAYERS;bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[i];const bg_pve_definition*d=&bg_pve_definitions[a->kind];
    const bg_damage_profile*hit=&bg_damage_profiles[profile];float before=p->health;
    bool backstab=(hit->flags&BG_DAMAGE_BACKSTAB)&&behind;
    if(backstab){p->shield=0;amount=d->health*2;}
    else if(p->shield>0&&!(hit->flags&BG_DAMAGE_SKIP_SHIELDS)){
        float multiplier=profile?d->damage[profile][1]:1;
        if(hit->flags&BG_DAMAGE_EMP)p->shield=0;
        else if(multiplier>0){float absorbed=fminf(p->shield,amount*multiplier);p->shield-=absorbed;amount-=absorbed/multiplier;}
    }
    float multiplier=profile?d->damage[profile][0]:1;
    if(headshot&&p->shield<=0&&amount>0&&(hit->flags&BG_DAMAGE_HEADSHOT))p->health=0;
    else p->health=fmaxf(0,p->health-amount*multiplier);
    p->hurt=.65f;p->shield_delay=d->shield_delay;a->recent_damage+=(before-p->health)/d->health;
    if(owner>=0&&owner<(int)active_players){a->aware=true;a->target=owner;memcpy(a->last_seen,bg_players[owner].pos,12);}
    if(p->health<=0){p->health=1;pve_killed(unit,owner);}
}
static float pve_sphere(const float o[3],const float dir[3],const float c[3],float radius,float nearest){
    float v[3];sub(v,o,c);float b=dot(v,dir),disc=b*b-dot(v,v)+radius*radius;
    if(disc<0)return nearest;
    float t=-b-sqrtf(disc);if(t<0)t=-b+sqrtf(disc);return t>=0&&t<nearest?t:nearest;
}
float bg_pve_hit_ray(unsigned unit,const float o[3],const float dir[3],float nearest,int*region){
    if(unit>=BG_PLAYERS+bg_pve_count)return nearest;
    bg_player*p=&bg_players[unit];const bg_pve_definition*d=&bg_pve_definitions[bg_pve_actors[unit-BG_PLAYERS].kind];
    /* Initial prototype narrow phase: authored capsule dimensions plus a head
     * sphere. Animated source collision regions remain a follow-up. */
    float hit=nearest;int part=1;
    for(unsigned k=0;k<4;k++){float c[3]={p->pos[0],p->pos[1]+d->radius+(d->height-2*d->radius)*k/3,p->pos[2]};float t=pve_sphere(o,dir,c,d->radius,hit);if(t<hit){hit=t;part=k==3?2:1;}}
    if(hit<nearest)*region=part;
    return hit;
}
void bg_pve_stop(void){
    pve_active=false;bg_pve_count=bg_pve_tick_number=0;
    memset(bg_pve_actors,0,sizeof(bg_pve_actors));
    memset(bg_players+BG_PLAYERS,0,BG_PVE_MAX*sizeof(bg_player));
}
void bg_pve_start(unsigned count){
    pve_active=true;bg_pve_count=count>BG_PVE_MAX?BG_PVE_MAX:count;bg_pve_tick_number=0;pve_random=0x505645;
    mode_enabled=false;bg_set_score_limit(100000);memset(bg_pve_actors,0,sizeof(bg_pve_actors));memset(pve_source_actors,0,sizeof(pve_source_actors));
    bg_vehicle_count=0;pve_nav_init();
    for(unsigned k=0;k<2;k++){pve_source_defs[k].defensive.shield_fraction_emerge_attack=bg_pve_definitions[k].emerge_shield;pve_source_defs[k].defensive.shield_fraction_emerge_pursue=.9f;}
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];a->kind=i==0?BG_PVE_ELITE:BG_PVE_GRUNT;a->target=-1;a->decision_time=i*.03f;
        const bg_pve_definition*d=&bg_pve_definitions[a->kind];bg_player*p=&bg_players[BG_PLAYERS+i];memset(p,0,sizeof(*p));
        p->pos[0]=3+(i%3)*1.2f;p->pos[2]=1.5f+(i/3)*1.5f;p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
        memcpy(a->destination,p->pos,12);memcpy(a->previous,p->pos,12);p->pve_radius=d->radius;p->pve_height=d->height;p->health=d->health;p->shield=d->shield;p->vehicle=-1;p->grounded=true;
        p->yaw=3.14159265f;p->weapon=a->kind==BG_PVE_ELITE?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL;p->ammo=100;p->inventory[0]=p->weapon;p->inventory[1]=-1;
        a->burst_pause=pve_range(d->first_delay);actor_get(i)->emotions.last_flee_failed_time=NONE;
    }
}
static void pve_place_human(unsigned i){
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
void bg_pve_tick(float dt){
    if(!pve_active)return;
    bg_pve_tick_number++;
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];const bg_pve_definition*d=&bg_pve_definitions[a->kind];a->time+=dt;
        if(p->health<=0)continue;
        p->hurt=fmaxf(0,p->hurt-dt);p->shield_delay=fmaxf(0,p->shield_delay-dt);if(!p->shield_delay&&d->shield_recharge>0)p->shield=fminf(d->shield,p->shield+d->shield/d->shield_recharge*dt);
        a->panic_time=fmaxf(0,a->panic_time-dt);a->cover_time=fmaxf(0,a->cover_time-dt);a->melee_time=fmaxf(0,a->melee_time-dt);
#ifdef N64
        uint32_t begin=get_ticks_us();
#endif
        a->decision_time-=dt;if(a->decision_time<=0){pve_decide(i);a->decision_time+=.2f;}
#ifdef N64
        bg_pve_ai_us+=get_ticks_us()-begin;begin=get_ticks_us();
#endif
        unsigned clip=PVE_IDLE;float distance=a->target>=0?sqrtf(distance2(p->pos,bg_players[a->target].pos)):100;
        bool retreat=a->action==_actor_action_flee||(a->action==_actor_action_guard&&actor_get(i)->state.action_data.guard.cower);
        bool moving=a->aware&&a->target>=0&&(retreat||!a->visible||distance>d->desired[1]);
        if(moving){float delta[3];sub(delta,a->destination,p->pos);float length=hypotf(delta[0],delta[2]);
            if(length>.08f){float speed=retreat?d->flee_speed:d->move_speed;p->velocity[0]=delta[0]/length*speed;p->velocity[2]=delta[2]/length*speed;clip=retreat?PVE_FLEE:PVE_RUN;}
            else p->velocity[0]=p->velocity[2]=0;
        }else p->velocity[0]=p->velocity[2]=0;
        p->velocity[1]-=bg_movement.gravity*dt;bg_move_capsule(p,dt);if(p->grounded)p->velocity[1]=0;
        if(a->target>=0){const float*target=a->visible?bg_players[a->target].pos:a->last_seen;float dx=target[0]-p->pos[0],dz=target[2]-p->pos[2];
            p->yaw=retreat?atan2f(-p->velocity[2],p->velocity[0]):atan2f(-dz,dx);}
        if(a->aware&&a->visible&&!retreat&&distance<d->range&&bg_players[a->target].health>0){
            a->burst_pause-=dt;a->shot_time-=dt;
            if(a->burst_pause<=0&&a->burst_time<=0)a->burst_time=pve_range(d->burst);
            if(a->burst_time>0){a->burst_time-=dt;
                if(a->shot_time<=0){float origin[3]={p->pos[0]+cosf(p->yaw)*d->gun[0],p->pos[1]+d->gun[2],p->pos[2]-sinf(p->yaw)*d->gun[0]},dir[3],target[3];
                    memcpy(target,bg_players[a->target].pos,12);target[1]+=.35f;sub(dir,target,origin);normalize(dir);
                    float cone[3];bg_combat_cone(dir,0,d->error,pve_random01(),pve_random01(),cone);
                    const bg_weapon_def*w=&bg_weapon_defs[p->weapon];bg_projectile*q=projectile(w->projectile,BG_PLAYERS+i,origin,cone,w->speed,w->damage,0);
                    if(q){q->damage_profile=weapon_damage(p->weapon,false);a->shots++;event(BG_EVENT_FIRE,BG_PLAYERS+i,p->weapon,origin,1);}
                    a->shot_time=1.f/d->rate;clip=PVE_FIRE;
                }
                if(a->burst_time<=0)a->burst_pause=pve_range(d->pause);
            }
        }
        if(a->kind==BG_PVE_ELITE&&a->visible&&distance<d->melee_range&&a->melee_time<=0&&a->target>=0){
            a->melee_time=d->melee_delay;a->melee_pending=true;clip=PVE_MELEE;
        }
        if(a->melee_pending&&a->clip==PVE_MELEE&&a->time>=d->melee_key){
            a->melee_pending=false;
            if(a->target>=0&&a->visible&&distance<d->melee_range)damage_player_profile(a->target,BG_PLAYERS+i,pve_range(d->melee_damage),false,false,0,false,false,1);
        }
        if(a->melee_pending)clip=PVE_MELEE;
        if(clip!=a->clip&&!(a->clip==PVE_FIRE&&a->time<.18f)&&!(a->clip==PVE_MELEE&&a->time<d->melee_duration)){a->clip=clip;a->time=0;}
        memcpy(p->last_pos,p->pos,12);
#ifdef N64
        bg_pve_move_us+=get_ticks_us()-begin;
#endif
    }
}
/* Deterministic acceptance input. No hidden invulnerability or direct kills. */
void bg_pve_qa_input(void *data){
    bg_input*in=data;memset(in,0,4*sizeof(*in));
    if(bg_pve_tick_number>=450){unsigned players=active_players,count=bg_pve_count;bg_pve_stage(players);if(count!=5)bg_pve_start(count);}
    for(unsigned h=0;h<active_players;h++){
        bg_player*p=&bg_players[h];if(p->health<=0)continue;
        unsigned target=4;while(target<4+bg_pve_count&&bg_players[target].health<=0)target++;
        if(target<4+bg_pve_count){float dx=bg_players[target].pos[0]-p->pos[0],dz=bg_players[target].pos[2]-p->pos[2];
            p->yaw=atan2f(-dz,dx);p->pitch=atan2f(bg_players[target].pos[1]+bg_body_height(&bg_players[target])*.75f-p->pos[1]-bg_eye_height(p),hypotf(dx,dz));
#if defined(BG_PVE_QA) && BG_PVE_QA == 2
            in[h].fire=h==0&&bg_pve_tick_number>=180&&bg_players[4].health>0;
#endif
        }
        in[h].reload=p->ammo==0&&p->reload<=0;
    }
}
