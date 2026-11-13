/* Active combat load, separate from the allocation-only fixture. Scripted
 * supplies, boarding assistance and renewable encounters keep the soak busy.
 * Damage, deaths, projectiles, collisions, AI and vehicle physics stay live.
 * Humans and the player transport are restored during the driving interval;
 * the dismounted interval allows ordinary deaths and vehicle destruction.
 * No direct kills, frozen poses or fabricated explosion events. */
#define bg_tick combat_original_tick
#include "../../game.c"
#undef bg_tick
#ifndef BG_COMBAT_FIGHT
#define BG_COMBAT_FIGHT BG_FF_ONSLAUGHT
#endif
#ifdef N64
#define COMBAT_LOG debugf
#else
#include <stdio.h>
#define COMBAT_LOG printf
#endif
static unsigned combat_fight=BG_COMBAT_FIGHT,combat_ticks,combat_waypoint,combat_spawns;
static struct {
    unsigned human_fire,enemy_fire,frags,plasma_grenades,enemy_grenades,explosions,kills,hurt,enemy_deaths,enemy_hurt;
    unsigned human_deaths,vehicle_destructions,aboard_ticks,moving_aboard_ticks,zoom_edges;
    unsigned peak_projectiles,peak_grenades,peak_events,peak_living,boarding_assists,flips;
    unsigned peak_moving_aboard_projectiles,busy_aboard_ticks,busy_scoped_ticks,explosion_zoom_edges,last_explosion;
    float travel;
} combat_counts;
static int combat_enemy_vehicle[2]={-1,-1};

static void combat_mount(unsigned human){
    bg_player*p=&bg_players[human];bg_vehicle*v=&bg_vehicles[0];
    if(!v->active||v->occupants[human]>=0||p->health<=0||p->vehicle>=0)return;
    if(v->physics_valid&&v->up[1]<BG_VEHICLE_FLIP_MAX_UP){
        p->pos[0]=v->pos[0]+1;p->pos[2]=v->pos[2];p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;
        bg_use_target flip=bg_interaction_target(human);
        if(flip.kind==BG_USE_FLIP&&flip.object==0){interact(human,flip);combat_counts.flips++;}
        return;
    }
    /* Only approach placement is scripted. Validate and enter the actual seat. */
    bg_vehicle_seat_position(v,human,true,p->pos);
    p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;
    p->grounded=true;p->ground_normal[1]=1;memset(p->velocity,0,sizeof(p->velocity));
    bg_use_target t=bg_interaction_target(human);
    if(t.kind==BG_USE_PICKUP){interact(human,t);t=bg_interaction_target(human);}
    if(t.kind==BG_USE_ENTER&&t.object==0&&t.seat==(int)human){
        interact(human,t);combat_counts.boarding_assists++;
    }
}
static void combat_spawn(unsigned i){
    static const float anchors[4][2]={{-6,-5},{16,-5},{16,14},{-6,14}};
    unsigned point=(i+combat_spawns)%4;
    float pos[3]={anchors[point][0]+(i%3)*.9f,0,anchors[point][1]+(i/4)*.9f};
    pos[1]=bg_floor(pos[0],pos[2],12)+.015f;
    unsigned kind=i<2?BG_PVE_ELITE:i%4==2?BG_PVE_HUNTER:i%4==3?BG_PVE_JACKAL:i%4==0?BG_PVE_GRUNT:BG_PVE_ELITE;
    unsigned weapon=kind==BG_PVE_GRUNT||kind==BG_PVE_JACKAL?BG_W_PLASMA_PISTOL:i%2?BG_W_NEEDLER:BG_W_PLASMA_RIFLE;
    pve_spawn_actor(i,kind,weapon,BG_FF_MIXED,pos,3.14159265f);
#ifdef BG_PVE_ROSTER
    if(kind==BG_PVE_GRUNT)bg_pve_set_variant(i,PVE_R_GRUNT_FUEL);
    if(kind==BG_PVE_JACKAL)bg_pve_set_variant(i,PVE_R_JACKAL_MAJOR);
#endif
#ifdef BG_ENEMY_VEHICLES
    if(i<2){
        int vi=combat_enemy_vehicle[i];
        if(vi<0||(!bg_vehicles[vi].active&&bg_vehicles[vi].wreck_time<=0)){
            vi=bg_add_vehicle(i?BG_V_WRAITH:BG_V_GHOST,pos,3.14159265f);
            if(vi>=0){bg_vehicles[vi].encounter_owned=true;combat_enemy_vehicle[i]=vi;}
        }
        if(vi>=0&&bg_vehicles[vi].active&&bg_vehicles[vi].occupants[0]<0)pve_vehicle_mount(i,vi,true);
    }
#endif
    ff_awaken(i);combat_spawns++;
}
static void combat_initialize(void){
    bg_ff_start_fight(3,combat_fight);
    /* A renewable production-cap encounter, with ordinary Heroic combat.
     * Lives and supplies are extended for duration, not damage immunity. */
    bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=99999;bg_ff.lives=60000;
    for(unsigned i=0;i<bg_ff.cap;i++)combat_spawn(i);
    for(unsigned h=0;h<3;h++){
        bg_set_player_armor(h,BG_ARMOR_SPARTAN);
        bg_give_weapon(h,h==0?BG_W_PISTOL:h==1?BG_W_SNIPER:BG_W_AR);
        combat_mount(h);
    }
}
static int combat_target(unsigned h){
    const bg_player*p=&bg_players[h];int best=-1;float score=1e9f;
    for(unsigned i=0;i<bg_pve_count;i++)if(bg_pve_actors[i].occupied&&bg_players[4+i].health>0){
        const bg_player*q=&bg_players[4+i];float d=distance2(p->pos,q->pos);
        float ray[3]={q->pos[0]-p->pos[0],q->pos[1]+q->pve_height*.65f-p->pos[1]-bg_eye_height(p),q->pos[2]-p->pos[2]};
        float length=sqrtf(dot(ray,ray)),origin[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]};
        if(length>.001f){for(unsigned k=0;k<3;k++)ray[k]/=length;if(bg_raycast(origin,ray,length)<length-.05f)d+=10000;}
        if(d<score){score=d;best=i;}
    }
    return best;
}
static void combat_aim(unsigned h,unsigned target,bool throwing){
    bg_player*p=&bg_players[h],*q=&bg_players[4+target];
    float origin[3],unused[3];aim(p,unused,origin);
    float dx=q->pos[0]-origin[0],dz=q->pos[2]-origin[2],range=hypotf(dx,dz);
    p->yaw=atan2f(-dz,dx);
    p->pitch=atan2f(q->pos[1]+q->pve_height*.65f-origin[1],range);
    if(throwing){
        float target_pos[3],dir[3],duration;
        memcpy(target_pos,q->pos,12);target_pos[1]+=.1f;
        if(pve_ballistic_aim(origin,target_pos,bg_grenade_velocity,
            bg_movement.gravity*bg_grenade_profiles[p->grenade_kind].gravity,false,dir,&duration))
            p->pitch=atan2f(dir[1],hypotf(dir[0],dir[2]));
    }
}
static void combat_report(void){
    unsigned free_bytes=0;
#ifdef N64
    heap_stats_t heap;sys_get_heap_stats(&heap);free_bytes=heap.total-heap.used;
#endif
    COMBAT_LOG("COMBAT_SOAK tick=%u seconds=%.2f fight=%u live=%u projectiles=%u grenades=%u events=%u human_fire=%u enemy_fire=%u frags=%u plasma=%u enemy_grenades=%u explosions=%u kills=%u hurt=%u enemy_deaths=%u enemy_hurt=%u human_deaths=%u wrecks=%u aboard=%u moving_aboard=%u travel=%.2f zoom_edges=%u boarding=%u free=%u\n",
        combat_ticks,combat_ticks/30.f,combat_fight,combat_counts.peak_living,combat_counts.peak_projectiles,combat_counts.peak_grenades,combat_counts.peak_events,
        combat_counts.human_fire,combat_counts.enemy_fire,combat_counts.frags,combat_counts.plasma_grenades,combat_counts.enemy_grenades,
        combat_counts.explosions,combat_counts.kills,combat_counts.hurt,combat_counts.enemy_deaths,combat_counts.enemy_hurt,combat_counts.human_deaths,combat_counts.vehicle_destructions,
        combat_counts.aboard_ticks,combat_counts.moving_aboard_ticks,combat_counts.travel,combat_counts.zoom_edges,combat_counts.boarding_assists,free_bytes);
    COMBAT_LOG("COMBAT_HOG pos=%.2f,%.2f,%.2f hp=%.2f up=%.3f speed=%.3f active=%u seats=%d,%d,%d humans=%.0f,%.0f,%.0f flips=%u\n",
        bg_vehicles[0].pos[0],bg_vehicles[0].pos[1],bg_vehicles[0].pos[2],bg_vehicles[0].health,bg_vehicles[0].up[1],bg_vehicles[0].speed,
        bg_vehicles[0].active,bg_vehicles[0].occupants[0],bg_vehicles[0].occupants[1],bg_vehicles[0].occupants[2],bg_players[0].health,bg_players[1].health,bg_players[2].health,combat_counts.flips);
    COMBAT_LOG("COMBAT_OVERLAP tick=%u moving_aboard_projectiles=%u busy_aboard=%u busy_scoped=%u explosion_zoom_edges=%u\n",
        combat_ticks,combat_counts.peak_moving_aboard_projectiles,combat_counts.busy_aboard_ticks,combat_counts.busy_scoped_ticks,combat_counts.explosion_zoom_edges);
}
void bg_tick(const bg_input inputs[4],float dt){
    (void)inputs;if(!combat_ticks)combat_initialize();
    bg_input in[4]={0};unsigned phase=combat_ticks%1800;
    /* Sustain all three views under fire for forty seconds, then leave the
     * normal damage/respawn paths exposed for the rest of each minute. */
    if(phase<1200){
        for(unsigned h=0;h<3;h++)if(bg_players[h].health>0){bg_players[h].health=100;bg_players[h].shield=200;}
        if(bg_vehicles[0].active)bg_vehicles[0].health=400;
    }
    for(unsigned i=0;i<bg_ff.cap;i++)if(!bg_pve_actors[i].occupied||
        (bg_players[4+i].health<=0&&bg_pve_actors[i].death_time>3))combat_spawn(i);
    if(phase<1200&&combat_ticks%90==0)for(unsigned h=0;h<3;h++)combat_mount(h);
    if(phase==1350)for(unsigned h=0;h<3;h++)if(bg_players[h].vehicle>=0)
        interact(h,(bg_use_target){BG_USE_EXIT,bg_players[h].vehicle,bg_players[h].seat});
    bg_vehicle*hog=&bg_vehicles[0];float old_pos[3];memcpy(old_pos,hog->pos,12);
    int old_zoom[3];for(unsigned h=0;h<3;h++)old_zoom[h]=bg_players[h].zoom;
    for(unsigned h=0;h<3;h++){
        bg_player*p=&bg_players[h];if(p->health<=0)continue;
        p->reserve=1000;p->grenades[0]=p->grenades[1]=4;
        if(combat_ticks%300==0){
            static const unsigned passenger_weapons[]={BG_W_AR,BG_W_SNIPER,BG_W_NEEDLER,BG_W_PLASMA_RIFLE};
            unsigned weapon=h==0?(phase>=1500?BG_W_SNIPER:phase>=1200?BG_W_ROCKET:BG_W_PISTOL):h==1?BG_W_SNIPER:passenger_weapons[(combat_ticks/300)%4];
            bg_give_weapon(h,weapon);
        }
        int target=combat_target(h);bool throwing=bg_player_personal_weapon(p)&&(combat_ticks+h*25)%90==0;
        if(target>=0)combat_aim(h,target,throwing);
        in[h].fire=(p->vehicle==0&&p->seat==1)||bg_trigger_profiles[p->weapon].automatic||(combat_ticks+h*2)%10==0;
        in[h].grenade=throwing;in[h].reload=p->ammo==0&&p->reload<=0;
        in[h].zoom=(combat_ticks+h*17)%45==0;in[h].switch_grenade=(combat_ticks+h*20)%300==150;
        if(p->vehicle==0&&p->seat==0){
            static const float route[4][2]={{12,2},{12,11},{0,11},{0,2}};
            float dx=route[combat_waypoint][0]-hog->pos[0],dz=route[combat_waypoint][1]-hog->pos[2];
            if(dx*dx+dz*dz<4)combat_waypoint=(combat_waypoint+1)%4;
            p->yaw=atan2f(-dz,dx);p->pitch=0;in[h].forward=phase<1200?.7f:0;
        }else if(p->vehicle<0){in[h].strafe=sinf(combat_ticks/45.f+h)*.5f;in[h].forward=.1f;in[h].jump=(combat_ticks+h*7)%180==0;}
    }
    unsigned event_start=bg_event_count;combat_original_tick(in,dt);combat_ticks++;
    /* Count newly queued production events without clearing the renderer's
     * queue. At saturation these counters are lower bounds; record its peak. */
    for(unsigned n=event_start;n<bg_event_count;n++){
        const bg_event*e=&bg_events[n];
        if(e->kind==BG_EVENT_FIRE){if(e->player>=4)combat_counts.enemy_fire++;else combat_counts.human_fire++;}
        if(e->kind==BG_EVENT_GRENADE){if(e->player>=4)combat_counts.enemy_grenades++;else if(e->weapon)combat_counts.plasma_grenades++;else combat_counts.frags++;}
        if(e->kind==BG_EVENT_EXPLOSION){combat_counts.explosions++;combat_counts.last_explosion=combat_ticks;}
        if(e->kind==BG_EVENT_KILL)combat_counts.kills++;
        if(e->kind==BG_EVENT_HURT)combat_counts.hurt++;
        if(e->kind==BG_EVENT_HURT&&e->player>=4)combat_counts.enemy_hurt++;
        if(e->kind==BG_EVENT_DIE&&e->player>=4)combat_counts.enemy_deaths++;
        if(e->kind==BG_EVENT_DIE&&e->player<3)combat_counts.human_deaths++;
        if(e->kind==BG_EVENT_VEHICLE_DESTROYED)combat_counts.vehicle_destructions++;
    }
    unsigned projectiles=0,grenades=0,living=0,enemy_ordnance=0;
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){const bg_projectile*q=bg_projectile_at(i);if(q&&q->active){projectiles++;grenades+=q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE;enemy_ordnance+=q->owner>=4;}}
    for(unsigned i=0;i<bg_pve_count;i++)living+=bg_pve_actors[i].occupied&&bg_players[4+i].health>0;
    if(projectiles>combat_counts.peak_projectiles)combat_counts.peak_projectiles=projectiles;
    if(grenades>combat_counts.peak_grenades)combat_counts.peak_grenades=grenades;
    if(bg_event_count>combat_counts.peak_events)combat_counts.peak_events=bg_event_count;
    if(living>combat_counts.peak_living)combat_counts.peak_living=living;
    bool aboard=hog->active,scoped=false;
    for(unsigned h=0;h<3;h++){
        const bg_player*p=&bg_players[h];aboard&=hog->occupants[h]==(int)h;
        bool changed=old_zoom[h]!=p->zoom;combat_counts.zoom_edges+=changed;
        bool zoomed=p->health>0&&p->zoom&&bg_player_personal_weapon(p)&&!bg_player_third_person(p);
        combat_counts.explosion_zoom_edges+=changed&&zoomed&&combat_counts.last_explosion&&combat_ticks-combat_counts.last_explosion<=15;
        scoped|=zoomed;
    }
    float distance=hypotf(hog->pos[0]-old_pos[0],hog->pos[2]-old_pos[2]);
    if(hog->active&&distance<2)combat_counts.travel+=distance;
    if(aboard){
        combat_counts.aboard_ticks++;combat_counts.moving_aboard_ticks+=distance>.005f;
        if(distance>.005f){
            if(projectiles>combat_counts.peak_moving_aboard_projectiles)combat_counts.peak_moving_aboard_projectiles=projectiles;
            combat_counts.busy_aboard_ticks+=enemy_ordnance>=4&&grenades>0;
        }
    }
    combat_counts.busy_scoped_ticks+=scoped&&enemy_ordnance>=4&&grenades>0&&living>=8;
    if(combat_ticks%300==0)combat_report();
}
