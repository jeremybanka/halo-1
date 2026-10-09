#include "blam/vehicle_physics.h"
#include "game.h"
#include "combat.h"
#include "camouflage.h"
#include "pickup_rules.h"
#include "combat_geometry.h"
#include "movement.h"
#include "terrain.h"
#include "blam/runtime.h"
#include "blam/core.h"
#include <math.h>
#include <string.h>
#include <float.h>
#ifdef BG_BLAM_BSP
#include "blam/collision.h"
extern const blam_collision_bsp bg_blam_collision_bsp;
#endif

/* Original netgame teleport_from/to pairs, matched by the scenario channel. */
const bg_teleporter bg_teleporters[2]={
    {{27.583809f,1.806952f,37.451904f},{14.827766f,.702073f,-3.472870f},3.091712f},
    {{-27.943108f,1.814917f,-35.083984f},{-24.204594f,.241005f,8.231079f},-.162618f},
};
const unsigned bg_teleporter_count=2;
bg_player bg_players[BG_PLAYERS];
static bg_shot_trace sniper_traces[BG_PLAYERS];
const bg_shot_trace *bg_sniper_trace(unsigned player){return &sniper_traces[player];}
bg_vehicle bg_vehicles[BG_MAX_VEHICLES];
static blam_object_store projectile_store;
static blam_object_header projectile_headers[BG_MAX_PROJECTILES];
static union {
    uint64_t alignment;
    unsigned char bytes[BG_MAX_PROJECTILES*(((sizeof(bg_projectile)+sizeof(void*)-1)&~(sizeof(void*)-1))+6*sizeof(void*))+8*sizeof(void*)+32];
} projectile_arena;
bg_projectile *bg_projectile_at(unsigned slot){return blam_object_at(&projectile_store,slot);}
bg_projectile *bg_projectile_create(void){
    /* _object_type_projectile in the original object_types.h is 5. */
    blam_handle handle=blam_object_new(&projectile_store,sizeof(bg_projectile),5);
    bg_projectile *p=blam_object_get(&projectile_store,handle);
    if(p){p->active=true;p->attached=-1;p->tracked=-1;}return p;
}
bg_pickup bg_pickups[BG_MAX_PICKUPS];
bg_event bg_events[BG_MAX_EVENTS];
unsigned bg_vehicle_count,bg_pickup_count,bg_event_count;
static unsigned active_players=4;
static uint16_t pickup_generation;
static uint32_t spawn_random=0x53504157,item_random=0x4954454d;
static uint32_t random_state=0xCE064;
static float match_time,last_kill_time[BG_PLAYERS];
static unsigned kill_chain[BG_PLAYERS],kill_spree[BG_PLAYERS];
static int match_winner=-1;
static bg_match_statistics statistics;
unsigned bg_player_profiles[BG_PLAYERS]={0,1,2,3};
static float damage_history[4][4];
const bg_match_statistics *bg_match_stats(void){return &statistics;}
bool bg_match_finished(void){return match_winner>=0;}
int bg_match_winner(void){return match_winner;}
static unsigned score_limit=25;
unsigned bg_score_limit(void){return score_limit;}
void bg_set_score_limit(unsigned value){score_limit=value?value:25;}
float bg_match_time(void){return match_time;}
static float clamp(float v,float a,float b){return v<a?a:v>b?b:v;}
static float dot(const float a[3],const float b[3]){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void sub(float d[3],const float a[3],const float b[3]){for(int i=0;i<3;i++)d[i]=a[i]-b[i];}

static float distance2(const float a[3],const float b[3]){float d[3];sub(d,a,b);return dot(d,d);}
static void normalize(float v[3]){float n=sqrtf(dot(v,v));if(n>1e-8f)for(int i=0;i<3;i++)v[i]/=n;}
static float random_signed(void){return blam_real_seed_random_range(&random_state,-1,1);}
void bg_set_players(unsigned count){active_players=count<1?1:count>4?4:count;}
unsigned bg_player_count(void){return active_players;}
void bg_clear_events(void){bg_event_count=0;}
static void event(bg_event_kind kind,int player,int weapon,const float pos[3],float amount){
    /* Gameplay visibility must update even when the presentation queue is full. */
    if(kind==BG_EVENT_FIRE&&player>=0&&player<BG_PLAYERS)bg_camo_reveal(&bg_players[player]);
    unsigned index=bg_event_count;
    if(index>=BG_MAX_EVENTS){
        if(kind!=BG_EVENT_GAME_OVER&&kind!=BG_EVENT_DIE&&kind!=BG_EVENT_DOUBLE_KILL&&kind!=BG_EVENT_TRIPLE_KILL&&kind!=BG_EVENT_KILLING_SPREE)return;
        for(index=0;index<BG_MAX_EVENTS;index++)if(bg_events[index].kind!=BG_EVENT_GAME_OVER&&bg_events[index].kind!=BG_EVENT_DIE&&bg_events[index].kind!=BG_EVENT_DOUBLE_KILL&&bg_events[index].kind!=BG_EVENT_TRIPLE_KILL&&bg_events[index].kind!=BG_EVENT_KILLING_SPREE)break;
        if(index==BG_MAX_EVENTS)index=BG_MAX_EVENTS-1;
    }else bg_event_count++;
    bg_event *e=&bg_events[index];e->kind=kind;e->player=player;e->weapon=weapon;e->amount=amount;
    memcpy(e->pos,pos,sizeof(e->pos));
}

/* Magazine, initial reserve, rate and reload values come from the supplied Xbox
 * weapon tags. Direct bullet/plasma and melee hits use the extracted combat
 * profiles below; legacy damage fields remain for vehicle/explosive paths
 * awaiting their own audit. The HUD presents vitality on a 100-point scale. */
const bg_weapon_def bg_weapon_defs[BG_WEAPON_COUNT]={
    [BG_W_AR]={"ASSAULT RIFLE",60,240,1.f/15,3.4f,10.f*(100.f/75),.0349066f,40,0,0,1,1,true,false,BG_P_PLASMA},
    [BG_W_PISTOL]={"PISTOL",12,60,1.f/3.5f,2.17f,25.f*(100.f/75),.0034907f,40,0,0,2,1,false,false,BG_P_PLASMA},
    [BG_W_PLASMA_PISTOL]={"PLASMA PISTOL",100,0,.2f,0,14,.014f,50,25,.055f,1,1,false,true,BG_P_PLASMA},
    [BG_W_PLASMA_RIFLE]={"PLASMA RIFLE",100,0,.1f,0,15,.02f,45,50,.045f,1,1,true,true,BG_P_PLASMA},
    [BG_W_NEEDLER]={"NEEDLER",20,80,.1f,1.0f,6,.06981317f,20,4,0,1,1,true,false,BG_P_NEEDLE},
    [BG_W_SHOTGUN]={"SHOTGUN",12,24,1.0f,.4f,12,.1745329f,16,0,0,1,15,false,false,BG_P_PLASMA},
    [BG_W_SNIPER]={"SNIPER RIFLE",4,12,.5f,2.5f,101.f*(100.f/75),.0087266f,150,0,0,10,1,false,false,BG_P_PLASMA},
    [BG_W_ROCKET]={"ROCKET LAUNCHER",2,4,2.0f,5.0f,300,.001f,150,12,0,2,1,false,false,BG_P_ROCKET},
    [BG_W_FLAMETHROWER]={"FLAMETHROWER",100,600,1.f/15,3.4f,8,.0349066f,4,5,.025f,1,1,true,false,BG_P_FLAME},
};
static int cell(float x,float z){
    int ix=(int)floorf((x-bg_grid_origin[0])/bg_grid_size[0]);
    int iz=(int)floorf((z-bg_grid_origin[1])/bg_grid_size[1]);
    if(ix<0||iz<0||ix>=BG_GRID||iz>=BG_GRID)return -1;
    return iz*BG_GRID+ix;
}
static float floor_uncached(float x,float z,float ceiling){
#ifdef BG_BLAM_BSP
    /* Original cache coordinates are Halo XYZ; the presentation coordinates
     * subtract (68,-118,0), use Y up and reverse the original Y axis. */
    if(cell(x,z)<0)return -1000;
    float origin[3]={x+68.f,-z-118.f,ceiling};
    for(unsigned attempt=0;attempt<8;attempt++){
        float displacement[3]={0,0,-1000.f-origin[2]};blam_collision_hit hit;
        if(!blam_collision_segment(&bg_blam_collision_bsp,origin,displacement,true,&hit))break;
        float height=origin[2]+displacement[2]*hit.fraction;
        float length2=dot(hit.normal,hit.normal);
        /* BSP includes the downward-facing sky enclosure and room ceilings.
         * Their normals are steep enough but they cannot support a player. */
        if(hit.normal[2]>0&&hit.normal[2]*hit.normal[2]>=.38f*length2)return height;
        origin[2]=height-.001f;
    }
    return -1000;
#else
    int index=cell(x,z);float best=-1000;
    if(index<0)return best;
    bg_cell c=bg_grid[index];
    for(unsigned i=0;i<c.count;i++){
        unsigned triangle=bg_grid_indices[c.first+i];if(!(bg_collision_flags[triangle]&1))continue;
        const bg_triangle*t=&bg_collision[triangle];
        const float*a=t->p[0],*b=t->p[1],*d=t->p[2];
        float det=(b[2]-d[2])*(a[0]-d[0])+(d[0]-b[0])*(a[2]-d[2]);
        if(fabsf(det)<1e-8f)continue;
        float u=((b[2]-d[2])*(x-d[0])+(d[0]-b[0])*(z-d[2]))/det;
        float v=((d[2]-a[2])*(x-d[0])+(a[0]-d[0])*(z-d[2]))/det;
        if(u<-.0001f||v<-.0001f||u+v>1.0001f)continue;
        float y=u*a[1]+v*b[1]+(1-u-v)*d[1];
        if(y<=ceiling&&y>best)best=y;
    }
    return best;
#endif
}

float bg_floor(float x,float z,float ceiling){
    /* The terrain is immutable. Parked vehicles repeatedly ask for exactly
     * the same body/nose/tail support heights; retain those answers without
     * quantizing coordinates or skipping a moving object's collision query.
     * Bitwise keys also distinguish signed zero and every ceiling value. */
    static struct { uint32_t key[3]; float height; bool valid; } cache[64];
    uint32_t key[3];
    memcpy(&key[0],&x,sizeof(x));memcpy(&key[1],&z,sizeof(z));memcpy(&key[2],&ceiling,sizeof(ceiling));
    uint32_t hash=key[0]^(key[1]*0x9E3779B9u)^(key[2]*0x85EBCA6Bu);
    hash^=hash>>16;hash^=hash>>8;
    unsigned slot=hash&63u;
    if(cache[slot].valid&&cache[slot].key[0]==key[0]&&cache[slot].key[1]==key[1]&&cache[slot].key[2]==key[2])return cache[slot].height;
    float height=floor_uncached(x,z,ceiling);
    memcpy(cache[slot].key,key,sizeof(key));cache[slot].height=height;cache[slot].valid=true;
    return height;
}


#ifdef BG_BLAM_BSP
float bg_raycast(const float origin[3],const float direction[3],float max_distance){
    if(max_distance<=0)return 0;
    if(max_distance<=.003f)return max_distance;
    float skip=.003f,range=max_distance-skip;
    float point[3]={origin[0]+direction[0]*skip+68.f,
                   -origin[2]-direction[2]*skip-118.f,origin[1]+direction[1]*skip};
    float displacement[3]={direction[0]*range,-direction[2]*range,direction[1]*range};
    blam_collision_hit hit;
    return blam_collision_segment(&bg_blam_collision_bsp,point,displacement,true,&hit)
        ?skip+range*hit.fraction:max_distance;
}
#else
float bg_raycast(const float origin[3],const float direction[3],float max_distance){
    if(max_distance<=0)return 0;
    return bg_world_raycast(origin,direction,max_distance);
}
#endif

static void store_inventory(bg_player*p){p->magazines[p->slot]=p->ammo;p->reserves[p->slot]=p->reserve;
    p->heats[p->slot]=p->heat;p->overheated_slots[p->slot]=p->overheated;}
static void stop_reload(bg_player*p);
static void select_slot(bg_player*p,int slot){
    stop_reload(p);p->melee_time=0;p->melee_tick=0;
    store_inventory(p);p->slot=slot;p->weapon=p->inventory[slot];p->ammo=p->magazines[slot];p->reserve=p->reserves[slot];
    p->reload=0;p->charge=0;p->zoom=0;p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;p->heat=p->heats[slot];p->overheated=p->overheated_slots[slot];
}
bool bg_give_weapon(unsigned player,bg_weapon weapon){
    if(player>=BG_PLAYERS||weapon>=BG_WEAPON_COUNT)return false;
    bg_player*p=&bg_players[player];const bg_weapon_def*w=&bg_weapon_defs[weapon];
    store_inventory(p);
    for(int slot=0;slot<2;slot++)if(p->inventory[slot]==(int)weapon){
        p->magazines[slot]=w->magazine;p->reserves[slot]=w->reserve;
        if(slot==p->slot){p->ammo=w->magazine;p->reserve=w->reserve;p->heat=0;p->overheated=false;}
        event(BG_EVENT_PICKUP,player,weapon,p->pos,1);return true;
    }
    p->fire_ticks[p->slot]=65535;p->trigger_error[p->slot]=p->trigger_rate[p->slot]=0;p->melee_tick=0;p->melee_time=0;
    p->inventory[p->slot]=weapon;p->weapon=weapon;p->ammo=w->magazine;p->reserve=w->reserve;
    p->heat=0;p->charge=0;p->overheated=false;p->reload=0;p->zoom=0;p->cooldown=.35f;
    store_inventory(p);event(BG_EVENT_PICKUP,player,weapon,p->pos,1);return true;
}
float bg_spawn_rating(unsigned player,unsigned index){
    if(player>=active_players||index>=bg_spawn_count||!bg_slayer_spawns[index])return 0;
    const float*pos=bg_spawns[index].pos;float rating=1;
    /* Free-for-all: no red/blue partition or friendly bonus. Recovered source
     * rejects enemies within 2 units and ramps the rating to 1 over 2..5. */
    for(unsigned i=0;i<active_players;i++)if(i!=player&&bg_players[i].health>0){
        float d2=distance2(pos,bg_players[i].pos);if(d2<4)return 0;
        if(d2<=25)rating*=(sqrtf(d2)-2)*(1.f/3);
    }
    /* Nearby-vehicle exclusion, using the authored local collision bounds.
     * Expanded by the source .1 query radius plus the player capsule radius. */
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicle_body_present(&bg_vehicles[i])){
        const bg_vehicle*v=&bg_vehicles[i];const bg_hit_mesh*m=&bg_vehicle_hit_meshes[v->kind];
        if(distance2(pos,v->pos)>36)continue;
        float delta[3];sub(delta,pos,v->pos);bool inside=true;
        for(unsigned axis=0;axis<3;axis++){
            float unit[3]={0},basis[3];unit[axis]=1;bg_vehicle_transform(v,unit,basis);sub(basis,basis,v->pos);
            float q=dot(delta,basis),margin=.3f;
            if(q<m->bounds[axis]/1024.f-margin||q>m->bounds[axis+3]/1024.f+margin){inside=false;break;}
        }
        if(inside)return 0;
    }
    return rating;
}
int bg_select_spawn(unsigned player){
    float best=0;int selected=-1;
    for(unsigned i=0;i<bg_spawn_count;i++){
        float rating=bg_spawn_rating(player,i)*sqrtf(blam_real_seed_random_range(&spawn_random,0,1));
        if(rating>best){best=rating;selected=i;}
    }
    return selected;
}
static void spawn(unsigned player){
    int index=bg_select_spawn(player);bg_player*p=&bg_players[player];
    if(index<0){p->respawn=1.f/30;return;} /* retry rather than spawn inside danger */
    int score=p->score;memset(damage_history[player],0,sizeof(damage_history[player]));
    memset(p,0,sizeof(*p));p->fire_ticks[0]=p->fire_ticks[1]=65535;p->score=score;p->health=100;p->shield=100;
    for(int j=0;j<2;j++){
        int w=p->inventory[j]=bg_start_weapons[j];
        if(w>=0){p->magazines[j]=bg_ammo_rules[w].loaded;p->reserves[j]=bg_ammo_rules[w].reserve;}
        p->grenades[j]=bg_start_grenades[j];
    }
    p->weapon=p->inventory[0];p->ammo=p->magazines[0];p->reserve=p->reserves[0];p->vehicle=-1;p->seat=-1;p->needle_owner=-1;
    memcpy(p->pos,bg_spawns[index].pos,sizeof(p->pos));
    float floor=bg_floor(p->pos[0],p->pos[2],p->pos[1]+.5f);if(floor>-999)p->pos[1]=floor+.015f;
    memcpy(p->last_pos,p->pos,sizeof(p->pos));p->yaw=bg_spawns[index].yaw;p->grounded=true;p->ground_normal[1]=1;
    p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;
    event(BG_EVENT_RESPAWN,player,p->weapon,p->pos,1);
}
#include "pickups.inc"
int bg_add_vehicle(bg_vehicle_kind kind,const float pos[3],float yaw){
    if(bg_vehicle_count>=BG_MAX_VEHICLES||kind>=BG_VEHICLE_COUNT)return -1;
    int index=bg_vehicle_count++;bg_vehicle*v=&bg_vehicles[index];memset(v,0,sizeof(*v));
    v->kind=kind;v->yaw=v->home_yaw=yaw;v->active=true;v->health=kind==BG_V_SCORPION?800:400;
    for(int i=0;i<BG_VEHICLE_SEATS;i++)v->occupants[i]=-1;
    memcpy(v->pos,pos,sizeof(v->pos));float floor=bg_floor(pos[0],pos[2],pos[1]+2);
    if(floor>-999)v->pos[1]=floor+(kind==BG_V_GHOST?.15f:.02f);
    memcpy(v->home,v->pos,sizeof(v->home));return index;
}
#include "scenario.inc"
void bg_reset(void){
    bg_terrain_reset();
    memset(&statistics,0,sizeof(statistics));memset(damage_history,0,sizeof(damage_history));
    memset(bg_players,0,sizeof(bg_players));memset(bg_vehicles,0,sizeof(bg_vehicles));
    blam_objects_init(&projectile_store,projectile_headers,BG_MAX_PROJECTILES,&projectile_arena,sizeof(projectile_arena));
    memset(bg_pickups,0,sizeof(bg_pickups));
    bg_clear_events();bg_vehicle_count=bg_pickup_count=0;pickup_generation=0;random_state=0xCE064;spawn_random=0x53504157;item_random=0x4954454d;
    match_time=0;match_winner=-1;memset(kill_chain,0,sizeof(kill_chain));memset(kill_spree,0,sizeof(kill_spree));
    for(int i=0;i<BG_PLAYERS;i++)last_kill_time[i]=-10;
    load_scenario();
    for(unsigned i=0;i<active_players;i++)spawn(i);
}
const bg_seat_definition *bg_player_seat(const bg_player*p){
    return p->vehicle>=0&&(unsigned)p->vehicle<bg_vehicle_count&&p->seat>=0&&p->seat<bg_seat_counts[bg_vehicles[p->vehicle].kind]?&bg_seat_definitions[bg_vehicles[p->vehicle].kind][p->seat]:NULL;
}
bool bg_player_personal_weapon(const bg_player*p){
    const bg_seat_definition*s=bg_player_seat(p);
    return p->seat_state==BG_SEAT_STABLE&&(!s||!(s->flags&12));
}
bool bg_player_third_person(const bg_player*p){
    const bg_seat_definition*s=bg_player_seat(p);
    return s&&((s->flags&16)||p->seat_state!=BG_SEAT_STABLE);
}
static void seat_vector(const bg_vehicle*v,const bg_seat_definition*s,const float local[3],float out[3]){
    float c=cosf(s->yaw),z=sinf(s->yaw);
    float rotated[3]={c*local[0]+z*local[2],local[1],-z*local[0]+c*local[2]},world[3];
    bg_vehicle_transform(v,rotated,world);
    for(unsigned a=0;a<3;a++)out[a]=world[a]-v->pos[a];
}
void bg_vehicle_seat_position(const bg_vehicle*v,unsigned seat,bool entry,float out[3]){
    if(seat>=bg_seat_counts[v->kind])seat=0;
    const bg_seat_definition*s=&bg_seat_definitions[v->kind][seat];
    float local[3];memcpy(local,entry?s->entry:s->anchor,sizeof(local));
    if(!entry&&v->kind==BG_V_WARTHOG&&seat==1){
        float x=local[0]+.5f,z=local[2],c=cosf(v->turret_yaw),sn=sinf(v->turret_yaw);
        local[0]=-.5f+c*x+sn*z;local[2]=-sn*x+c*z;
    }
    bg_vehicle_transform(v,local,out);
}
void bg_vehicle_camera_position(const bg_vehicle*v,unsigned seat,float out[3]){
    bg_vehicle_transform(v,bg_seat_definitions[v->kind][seat].camera,out);
}
bool bg_vehicle_exit_position(unsigned player,float out[3]){
    const bg_player*p=&bg_players[player];if(p->vehicle<0)return false;
    const bg_vehicle*v=&bg_vehicles[p->vehicle];const bg_seat_definition*s=bg_player_seat(p);
    float anchor[3],offset[3];bg_vehicle_seat_position(v,p->seat,false,anchor);seat_vector(v,s,s->exit_offset,offset);
    /* Prefer the authored exit. Try nearby alternatives without crossing a
     * wall; a blocked voluntary exit retains its seat reservation. */
    const float alternatives[7][2]={{0,0},{0,.45f},{0,-.45f},{.5f,0},{-.5f,0},{0,.9f},{0,-.9f}};
    for(unsigned i=0;i<7;i++){
        bg_player probe=*p;probe.crouch_amount=0;
        for(unsigned a=0;a<3;a++)probe.pos[a]=anchor[a]+offset[a];
        probe.pos[0]+=alternatives[i][0]*cosf(v->yaw)+alternatives[i][1]*sinf(v->yaw);
        probe.pos[2]+=-alternatives[i][0]*sinf(v->yaw)+alternatives[i][1]*cosf(v->yaw);
        float floor=bg_floor(probe.pos[0],probe.pos[2],fmaxf(anchor[1],probe.pos[1])+.8f);
        if(floor>-999&&probe.pos[1]<floor+.015f)probe.pos[1]=floor+.015f;
        memset(probe.velocity,0,sizeof(probe.velocity));bg_move_capsule(&probe,0);
        float origin[3]={anchor[0],anchor[1]+.35f,anchor[2]},dir[3];sub(dir,probe.pos,origin);dir[1]+=.35f;
        float distance=sqrtf(dot(dir,dir));normalize(dir);
        if(bg_raycast(origin,dir,distance)<distance-.01f||!bg_terrain_clearance(&probe))continue;
        bool blocked=false;
        for(unsigned other=0;other<bg_vehicle_count;other++)if(bg_vehicle_body_present(&bg_vehicles[other])&&bg_vehicle_contacts_player(&bg_vehicles[other],&probe)){blocked=true;break;}
        for(unsigned other=0;other<active_players&&!blocked;other++)if(other!=player&&bg_players[other].health>0&&bg_players[other].vehicle<0){
            const bg_player*q=&bg_players[other];float dx=q->pos[0]-probe.pos[0],dz=q->pos[2]-probe.pos[2];
            if(dx*dx+dz*dz<4*bg_movement.radius*bg_movement.radius&&fabsf(q->pos[1]-probe.pos[1])<bg_movement.height[0])blocked=true;
        }
        if(!blocked){memcpy(out,probe.pos,12);return true;}
    }
    return false;
}
float bg_camera_clearance(const float origin[3],const float direction[3],float length,int ignore_vehicle){
    /* Probe center and four shoulders so the near plane cannot peek through
     * canyon walls. Ignore the driven hull, but include neighboring vehicles. */
    float right[3]={-direction[2],0,direction[0]};normalize(right);
    const float offsets[5][3]={{0,0,0},{right[0]*.1f,0,right[2]*.1f},{-right[0]*.1f,0,-right[2]*.1f},{0,.1f,0},{0,-.1f,0}};
    float nearest=length,rays[5][3],reaches[5],hits[5];
    for(unsigned i=0;i<5;i++){
        /* Fan outward from the valid pivot: shifted origins can be below ground. */
        for(unsigned a=0;a<3;a++)rays[i][a]=direction[a]*length+offsets[i][a];
        reaches[i]=sqrtf(dot(rays[i],rays[i]));
        for(unsigned a=0;a<3;a++)rays[i][a]/=fmaxf(.001f,reaches[i]);
    }
#ifdef BG_BLAM_BSP
    for(unsigned i=0;i<5;i++)hits[i]=bg_raycast(origin,rays[i],reaches[i]);
#else
    bg_world_camera_rays(origin,rays,reaches,hits);
#endif
    for(unsigned i=0;i<5;i++){
        if(reaches[i]<.001f)continue;
        for(unsigned v=0;v<bg_vehicle_count;v++)if((int)v!=ignore_vehicle&&bg_vehicle_body_present(&bg_vehicles[v]))hits[i]=bg_vehicle_hit_ray(&bg_vehicles[v],origin,rays[i],hits[i]);
        nearest=fminf(nearest,hits[i]*length/reaches[i]);
    }
    return fmaxf(0,nearest-.15f);
}
static bool eject(unsigned player,bool forced){
    bg_player*p=&bg_players[player];if(p->vehicle<0)return true;bg_vehicle*v=&bg_vehicles[p->vehicle];
    float safe[3];bool clear=bg_vehicle_exit_position(player,safe);
    if(!clear&&!forced)return false;
    p->exit_vehicle=p->vehicle;p->exit_grace=.3f;
    const bg_seat_definition*s=bg_player_seat(p);float offset[3],velocity[3],anchor[3];
    seat_vector(v,s,s->exit_offset,offset);seat_vector(v,s,s->exit_velocity,velocity);
    bg_vehicle_seat_position(v,p->seat,false,anchor);
    for(unsigned a=0;a<3;a++){p->pos[a]=anchor[a]+offset[a];p->velocity[a]=v->velocity[a]+velocity[a];}
    if(clear)memcpy(p->pos,safe,12);
    v->occupants[p->seat]=-1;p->vehicle=p->seat=-1;p->seat_state=BG_SEAT_STABLE;p->seat_time=p->seat_blend=0;
    p->vy=p->velocity[1];p->grounded=false;p->interact_cooldown=.5f;
    p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;p->animation=BG_ANIM_IDLE;p->anim_time=0;
    event(BG_EVENT_EXIT,player,v->kind,p->pos,1);return true;
}
static void eject_overturned(unsigned vehicle){
    bg_vehicle*v=&bg_vehicles[vehicle];
    /* vehicles.c vehicle_is_flipped uses up.k < .2. Six consecutive ticks
     * are adapter hysteresis, not a recovered Xbox timing constant. */
    /* A fighter's steep flight attitude is not a grounded rollover. */
    if(v->up[1]>=.2f||(v->kind==BG_V_BANSHEE&&bg_vehicle_airborne(vehicle))){v->overturned_ticks=0;return;}
    if(v->overturned_ticks<6)v->overturned_ticks++;
    if(v->overturned_ticks<6)return;
    for(unsigned seat=0;seat<bg_seat_counts[v->kind];seat++){
        int index=v->occupants[seat];if(index<0)continue;
        eject(index,true);bg_player*p=&bg_players[index];
        /* An inverted exit marker can be below the floor. Recover above
         * that local support and suppress the marker's downward impulse. */
        float floor=bg_floor(p->pos[0],p->pos[2],fmaxf(v->pos[1],p->pos[1])+.8f);
        if(floor>-999&&p->pos[1]<floor+.015f)p->pos[1]=floor+.015f;
        p->vy=p->velocity[1]=fmaxf(0,p->velocity[1]);
        p->use_time=0;p->use_target.kind=BG_USE_NONE;p->use_latched=true;
        memcpy(p->last_pos,p->pos,sizeof(p->pos));
    }
}
static void kill(unsigned victim,int owner){
    bg_player*p=&bg_players[victim];if(p->health<=0)return;
    if(p->vehicle>=0)eject(victim,true);
    drop_inventory(victim);
    p->weapon_ready=p->use_time=0;p->use_latched=false;p->use_target.kind=BG_USE_NONE;
    p->invisibility=p->camo_opacity=p->camo_quiet=0;
    p->shield_overcharging=p->shield_charging=false;
    p->melee_tick=0;p->health=0;p->shield=0;p->respawn=owner<0||owner==(int)victim?10:3;p->zoom=0;statistics.deaths[victim]++;
    p->needles=0;p->needle_timer=0;p->needle_owner=-1;
    p->animation=BG_ANIM_DIE;p->anim_time=0;
    kill_chain[victim]=kill_spree[victim]=0;
    event(BG_EVENT_DIE,victim,p->weapon,p->pos,1);
    if(owner>=0&&owner<(int)active_players){
        bg_player*k=&bg_players[owner];
        if(owner==(int)victim)k->score--;
        else{
            k->score++;kill_spree[owner]++;statistics.kills[owner]++;
            /* Original FFA assist threshold: other attackers contributing
             * more than 40 percent of the credited killer's damage. */
            float threshold=damage_history[victim][owner]*.4f;
            for(unsigned q=0;q<active_players;q++)if(q!=victim&&q!=(unsigned)owner&&threshold>0&&damage_history[victim][q]>threshold)statistics.assists[q]++;
            kill_chain[owner]=match_time-last_kill_time[owner]<=4?kill_chain[owner]+1:1;
            last_kill_time[owner]=match_time;
            if(kill_chain[owner]==2)event(BG_EVENT_DOUBLE_KILL,owner,k->weapon,k->pos,2);
            if(kill_chain[owner]>=3)event(BG_EVENT_TRIPLE_KILL,owner,k->weapon,k->pos,kill_chain[owner]);
            if(kill_spree[owner]==5)event(BG_EVENT_KILLING_SPREE,owner,k->weapon,k->pos,5);
            if(k->score>=(int)bg_score_limit()&&match_winner<0){
                match_winner=owner;event(BG_EVENT_GAME_OVER,owner,k->weapon,k->pos,k->score);
            }
        }
    }
}
static void damage_player_profile(unsigned victim,int owner,float damage,bool plasma,bool headshot,unsigned profile,bool legs,bool behind,float energy){
    bg_player*p=&bg_players[victim];if(bg_match_finished()||p->health<=0||damage<=0)return;
    bg_camo_reveal(p); /* Source damage also depowers camouflage. */
    if(p->shield_overcharging&&!(profile&&(bg_damage_profiles[profile].flags&BG_DAMAGE_BACKSTAB)&&behind)){ /* Original charge protection still flashes. */
        p->shield_hit=1;event(BG_EVENT_SHIELD_HIT,victim,p->weapon,p->pos,0);return;
    }
    if(owner>=0&&owner<(int)active_players&&owner!=(int)victim)damage_history[victim][owner]+=damage*(profile?100.f/bg_combat_body_max:1);
    float old_shield=p->shield;
    p->shield_charging=false;
    if(profile&&bg_damage_profiles[profile].stun>0){const bg_damage_profile*d=&bg_damage_profiles[profile];
        float cap=clamp(d->stun_max*energy,0,1);
        if(p->body_stun<cap)p->body_stun=fminf(cap,p->body_stun+d->stun*fmaxf(0,energy));
        p->stun_time=fminf(bg_stun_config[4],fmaxf(bg_stun_config[3],p->stun_time)+d->stun_time);}
    p->shield_delay=6;p->hurt=.65f;p->zoom=0;p->charge=0;
    if(profile){
        damage=bg_combat_apply(&bg_damage_profiles[profile],damage,headshot,legs,behind,&p->shield,&p->health);
    }else{
        float shield_damage=damage*(plasma?1.6f:1);
        if(p->shield>0){float absorb=fminf(p->shield,shield_damage);p->shield-=absorb;damage-=absorb/(plasma?1.6f:1);}
        if(headshot&&p->shield<=.0001f&&damage>0)damage=200;
        if(damage>0)p->health=fmaxf(0,p->health-damage);
    }
    if(p->shield<.0001f)p->shield=0;
    if(old_shield>p->shield){
        p->shield_hit=p->shield>0?1:0;
        event(BG_EVENT_SHIELD_HIT,victim,p->weapon,p->pos,old_shield-p->shield);
        if(p->shield==0){p->shield_break=2.25f;memcpy(p->shield_break_pos,p->pos,12);event(BG_EVENT_SHIELD_BREAK,victim,p->weapon,p->pos,1);}
    }
    event(BG_EVENT_HURT,victim,p->weapon,p->pos,damage);
    if(p->health<=0){p->health=1;kill(victim,owner);}
}
static unsigned weapon_damage(int weapon,bool charged){
    static const unsigned profiles[BG_WEAPON_COUNT]={BG_D_AR,BG_D_PISTOL,BG_D_PLASMA_PISTOL,
        BG_D_PLASMA_RIFLE,BG_D_LEGACY,BG_D_SHOTGUN,BG_D_SNIPER,BG_D_LEGACY,BG_D_LEGACY};
    return charged?BG_D_OVERCHARGE:profiles[weapon];
}
static void damage_vehicle(unsigned index,int owner,float amount){
    bg_vehicle*v=&bg_vehicles[index];if(bg_match_finished()||!v->active)return;v->health-=amount;
    if(v->health>0)return;
    for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=0)kill(v->occupants[seat],owner);
    v->active=false;v->respawn=20;v->wreck_time=BG_WRECK_LIFE;v->speed=0;
    event(BG_EVENT_VEHICLE_DESTROYED,owner,v->kind,v->pos,(float)index);
}
/* Xbox direct hull damage also reaches riders, before hull resistance is
 * applied. Destructible MP hull vitality remains a deliberate demake choice. */
static void damage_vehicle_profile(unsigned index,int owner,float amount,unsigned profile,unsigned material,bool area){
    if(!profile){damage_vehicle(index,owner,amount);return;}
    bg_vehicle*v=&bg_vehicles[index];const bg_damage_profile*d=&bg_damage_profiles[profile];
    if(!v->active)return;
    if(!area){
        float transfer=bg_vehicle_child_damage[v->kind]*(1-d->passthrough);
        for(unsigned seat=0;seat<bg_seat_counts[v->kind];seat++){
            int child=v->occupants[seat];
            if(child>=0)damage_player_profile(child,owner,amount*transfer,false,false,profile,false,false,1);
        }
    }
    damage_vehicle(index,owner,amount*d->vehicle_material[material<4?material:0]*(100.f/bg_combat_body_max));
}
/* Blast rays use the source four-ray core for broad explosions. Occupants
 * inherit their vehicle's blast exposure, as children_take_area_damage does. */
static float cover_ray(const float origin[3],const float dir[3],float distance,int ignore){
    float nearest=bg_raycast(origin,dir,distance);
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active&&(int)i!=ignore)nearest=bg_vehicle_hit_ray(&bg_vehicles[i],origin,dir,nearest);
    return nearest;
}
static bool blast_clear(const float origin[3],const float target[3],float core,int ignore){
    float d[3];sub(d,target,origin);float length=sqrtf(dot(d,d));if(length<.01f)return true;
    for(unsigned a=0;a<3;a++)d[a]/=length;
    if(core<=0)return cover_ray(origin,d,length,ignore)>=length-.01f;
    float right[3]={-d[2],0,d[0]};if(dot(right,right)<1e-8f)right[0]=1;normalize(right);
    float up[3]={d[1]*right[2],d[2]*right[0]-d[0]*right[2],-d[1]*right[0]};
    for(unsigned ray=0;ray<4;ray++){
        float start[3],offset[3],to[3];const float*v=ray<2?right:up;float sign=ray&1?-1:1;
        for(unsigned a=0;a<3;a++)offset[a]=v[a]*sign;
        float reach=fmaxf(0,cover_ray(origin,offset,core,ignore)-.003f);
        for(unsigned a=0;a<3;a++)start[a]=origin[a]+offset[a]*reach;
        sub(to,target,start);float n=sqrtf(dot(to,to));if(n<.01f)return true;
        for(unsigned a=0;a<3;a++)to[a]/=n;
        if(cover_ray(start,to,n,ignore)>=n-.01f)return true;
    }return false;
}
static unsigned explosion_profile(bg_projectile_kind kind){
    return kind==BG_P_FRAG?BG_D_FRAG:kind==BG_P_PLASMA_GRENADE?BG_D_PLASMA_GRENADE:
        kind==BG_P_ROCKET?BG_D_ROCKET:kind==BG_P_NEEDLE?BG_D_SUPERCOMBINE:BG_D_LEGACY;
}
static void explode_profile(const float pos[3],int owner,float damage,float radius,bg_projectile_kind kind,unsigned profile){
    if(!profile)profile=explosion_profile(kind);
    const bg_damage_profile*d=&bg_damage_profiles[profile];
    if(profile)radius=d->cutoff;
    event(BG_EVENT_EXPLOSION,owner,kind==BG_P_NEEDLE?BG_EXPLOSION_NEEDLER:
        kind==BG_P_PLASMA_GRENADE?BG_EXPLOSION_PLASMA:BG_EXPLOSION_NORMAL,pos,radius);
    for(unsigned i=0;i<active_players;i++){
        bg_player*p=&bg_players[i];if(p->health<=0||((d->flags&BG_DAMAGE_NO_OWNER)&&(int)i==owner))continue;
        float target[3]={p->pos[0],p->pos[1]+bg_body_height(p)*.5f,p->pos[2]};
        float length=sqrtf(distance2(pos,target));if(length>=radius)continue;
        if(p->vehicle>=0){bg_vehicle*v=&bg_vehicles[p->vehicle];target[0]=v->pos[0];target[1]=v->pos[1]+.35f;target[2]=v->pos[2];}
        if(!blast_clear(pos,target,profile?d->core:0,p->vehicle))continue;
        float scale=profile?clamp((radius-length)/fmaxf(.001f,radius-d->falloff),0,1):1-length/radius;
        float amount=profile?bg_combat_amount(d,scale,.5f+.5f*random_signed()):damage*scale;
        damage_player_profile(i,owner,amount,false,false,profile,false,false,scale);
        if(p->vehicle<0){
            float direction[3];sub(direction,target,pos);normalize(direction);direction[1]+=.45f;normalize(direction);
            float acceleration=profile?d->acceleration*bg_player_acceleration_scale*(p->health>0?.5f:1):2*scale;
            for(unsigned a=0;a<3;a++)p->velocity[a]+=direction[a]*acceleration;
            p->vy=p->velocity[1];if(acceleration>0)p->grounded=false;
        }
    }
    /* Destructible multiplayer hulls remain the explicitly requested demake
     * extension. Xbox Warthog/Ghost/Scorpion multiplayer hulls are invulnerable. */
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active){
        bg_vehicle*v=&bg_vehicles[i];float center[3]={v->pos[0],v->pos[1]+.35f,v->pos[2]},length=sqrtf(distance2(pos,center));
        if(length<radius+1&&blast_clear(pos,center,profile?d->core:0,i)){if(profile)bg_vehicle_physics_damage(i,pos,d->acceleration,(d->flags&BG_DAMAGE_EXPLOSIVE)!=0);else bg_vehicle_physics_explosion(i,pos,kind);float scale=profile?clamp((radius-length)/fmaxf(.001f,radius-d->falloff),0,1):1-length/(radius+1);
            damage_vehicle_profile(i,owner,profile?bg_combat_amount(d,scale,.5f+.5f*random_signed()):damage*scale,profile,0,true);}
    }
}
static void explode(const float pos[3],int owner,float damage,float radius,bg_projectile_kind kind){explode_profile(pos,owner,damage,radius,kind,0);}
static int target_ray(unsigned owner,const float origin[3],const float dir[3],float *nearest,int *region){
    int victim=-1;
    for(unsigned j=0;j<active_players;j++){
        bg_player*p=&bg_players[j];if(j==owner||p->health<=0)continue;
        int part=1;float hit=bg_player_hit_ray(j,origin,dir,*nearest,&part);
        if(hit<*nearest){*nearest=hit;victim=j;*region=part;}
    }
    return victim;
}
static float hitscan(unsigned owner,const float origin[3],const float direction[3],float range,float damage,bool headshots,unsigned profile,float scale){
    if(profile&&profile!=BG_D_MELEE)range=bg_damage_profiles[profile].range;
    float nearest=range;int region=1;int victim=target_ray(owner,origin,direction,&nearest,&region),vehicle=-1;unsigned material=0;
    for(unsigned i=0;i<bg_vehicle_count;i++){
        bg_vehicle*v=&bg_vehicles[i];if(!v->active||bg_players[owner].vehicle==(int)i)continue;
        float hit=bg_vehicle_hit_ray_material(v,origin,direction,nearest,&material);
        if(hit<nearest){nearest=hit;vehicle=i;victim=-1;}
    }
    if((victim>=0||vehicle>=0)&&bg_raycast(origin,direction,nearest)>=nearest){
        if(profile){
            const bg_damage_profile*d=&bg_damage_profiles[profile];
            scale=profile==BG_D_MELEE?scale:bg_combat_range_scale(d,nearest);
            damage=bg_combat_amount(d,scale,.5f+.5f*random_signed());
        }
        if(victim>=0){
            bool behind=false;
            if(profile==BG_D_MELEE){
                const bg_player*v=&bg_players[victim];float cp=cosf(v->pitch);
                float facing[3]={cosf(v->yaw)*cp,sinf(v->pitch),-sinf(v->yaw)*cp};
                float offset[3];sub(offset,v->pos,bg_players[owner].pos);behind=dot(offset,facing)>0;
            }
            damage_player_profile(victim,owner,damage,false,(headshots||profile)&&region==2,profile,profile!=BG_D_MELEE&&region==0,behind,scale);
        }else damage_vehicle_profile(vehicle,owner,damage,profile,material,false);
        return nearest;
    }
    return range;
}
static bg_projectile* projectile(int kind,unsigned owner,const float origin[3],const float direction[3],float speed,float damage,float radius){
    bg_projectile*q=bg_projectile_create();if(q){
        q->kind=kind;q->owner=owner;q->tracked=-1;
        memcpy(q->pos,origin,sizeof(q->pos));for(int a=0;a<3;a++)q->velocity[a]=direction[a]*speed;
        q->damage=damage;q->radius=radius;q->life=kind==BG_P_FLAME?.7f:kind==BG_P_FRAG?2.5f:kind==BG_P_PLASMA_GRENADE?2.5f:8;
        return q;
    }
    return NULL;
}
static void aim(const bg_player*p,float direction[3],float origin[3]){
    float cp=cosf(p->pitch);direction[0]=cosf(p->yaw)*cp;direction[1]=sinf(p->pitch);direction[2]=-sinf(p->yaw)*cp;
    memcpy(origin,p->pos,12);origin[1]+=bg_eye_height(p);
    if(p->vehicle>=0&&bg_player_personal_weapon(p))bg_vehicle_camera_position(&bg_vehicles[p->vehicle],p->seat,origin);
}
bg_aim_target bg_aim_query(unsigned owner){
    bg_player*p=&bg_players[owner];bg_aim_target best={.player=-1,.distance=1e9f};
    if(p->vehicle>=0||p->health<=0)return best;
    const bg_aim_config*a=&bg_aim_configs[p->weapon];if(a->zoom_only&&!p->zoom)return best;
    float mag=p->zoom?(p->weapon==BG_W_SNIPER&&p->zoom==1?2:bg_weapon_defs[p->weapon].zoom):1;
    float origin[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]};
    float cp=cosf(p->pitch),dir[3]={cosf(p->yaw)*cp,sinf(p->pitch),-sinf(p->yaw)*cp};
    for(unsigned j=0;j<active_players;j++){
        const bg_player*q=&bg_players[j];if(j==owner||q->health<=0||bg_player_visibility(q)<=0)continue;
        float height=bg_movement.height[0]+(bg_movement.height[1]-bg_movement.height[0])*q->crouch_amount;
        float point[3]={q->pos[0],q->pos[1]+height*.5f,q->pos[2]};
        float dx=point[0]-origin[0],dz=point[2]-origin[2],h2=dir[0]*dir[0]+dir[2]*dir[2];
        if(h2>.00001f)point[1]=clamp(origin[1]+(dx*dir[0]+dz*dir[2])*dir[1]/h2,q->pos[1]+height*.5f,q->pos[1]+height);
        float d[3];sub(d,point,origin);float projection=dot(d,dir);if(projection<=0)continue;
        float perpendicular[3];for(unsigned k=0;k<3;k++)perpendicular[k]=d[k]-dir[k]*projection;
        float width=sqrtf(dot(perpendicular,perpendicular));
        if(width>0){float scale=fminf(1,bg_movement.aim_width/width);for(unsigned k=0;k<3;k++){point[k]-=perpendicular[k]*scale;d[k]=point[k]-origin[k];}}
        float distance=sqrtf(dot(d,d));if(distance<.001f||distance>fmaxf(a->auto_range,a->mag_range)*mag)continue;
        float cosine=clamp(dot(d,dir)/distance,-1,1),max_angle=fmaxf(a->auto_angle,a->mag_angle)/mag;
        if(cosine<cosf(max_angle))continue;
        float angle=acosf(cosine),aut=bg_aim_attenuation(distance,a->auto_range*mag)*bg_aim_attenuation(angle,a->auto_angle/mag);
        float magnet=bg_aim_attenuation(distance,a->mag_range*mag)*bg_aim_attenuation(angle,a->mag_angle/mag);
        if(aut<=0&&magnet<=0)continue;
        if(aut<best.auto_level||(aut==best.auto_level&&(magnet<best.mag_level||(magnet==best.mag_level&&distance>=best.distance))))continue;
        for(unsigned k=0;k<3;k++)d[k]/=distance;
        if(bg_raycast(origin,d,distance)<distance-.015f)continue;
        bool blocked=false;
        for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicles[v].active&&p->vehicle!=(int)v&&bg_vehicle_hit_ray(&bg_vehicles[v],origin,d,distance)<distance){blocked=true;break;}
        if(blocked)continue;
        best=(bg_aim_target){.player=(int)j,.distance=distance,.auto_level=aut,.mag_level=magnet};memcpy(best.point,point,sizeof(point));
    }
    return best;
}
static void player_look(unsigned index,const bg_input*in,float dt){
    bg_player*p=&bg_players[index];
    if(p->vehicle>=0){ /* Vehicle control tuning is deliberately unchanged. */
        float scale=p->zoom?(p->zoom==2?.15f:.35f):1;
        p->yaw+=in->turn*2.25f*dt*scale;p->pitch=clamp(p->pitch+in->look*1.35f*dt*scale,-1.25f,1.25f);p->look_peg_time=0;return;
    }
    float mag=p->zoom?(p->weapon==BG_W_SNIPER&&p->zoom==1?2:bg_weapon_defs[p->weapon].zoom):1,dy,dp;
    bg_look_input(p,in,mag,dt,&dy,&dp);
    if(in->turn!=0||in->look!=0||in->forward!=0||in->strafe!=0){
        bg_aim_target target=bg_aim_query(index);
        if(target.player>=0&&target.mag_level>0){
            bg_player*q=&bg_players[target.player];float d[3]={target.point[0]-p->pos[0],target.point[1]-p->pos[1]-bg_eye_height(p),target.point[2]-p->pos[2]};
            float v[3];sub(v,q->velocity,p->velocity);float h2=d[0]*d[0]+d[2]*d[2],h=sqrtf(h2),r2=h2+d[1]*d[1];
            if(h2>.00001f&&r2>.00001f){
                float ay=(d[2]*v[0]-d[0]*v[2])/h2;
                float ap=(h*v[1]-d[1]/h*(d[0]*v[0]+d[2]*v[2]))/r2;
                float scale=1-target.mag_level*bg_movement.friction,adhesion=target.mag_level*bg_movement.adhesion;
                dy=dy*scale+clamp(ay,-3.14159265f,3.14159265f)*dt*adhesion;
                dp=dp*scale+clamp(ap,-1.57079633f,1.57079633f)*dt*adhesion;
            }
        }
    }
    p->yaw+=dy;p->pitch=clamp(p->pitch+dp,-1.49225651f,1.49225651f);
}
static void assisted_shot(unsigned index,float direction[3],const float origin[3]){
    bg_aim_target target=bg_aim_query(index);if(target.player<0||target.auto_level<=0)return;
    float desired[3];sub(desired,target.point,origin);normalize(desired);
    for(unsigned k=0;k<3;k++)desired[k]=direction[k]+(desired[k]-direction[k])*target.auto_level;
    normalize(desired);
    bg_player*p=&bg_players[index];const bg_aim_config*a=&bg_aim_configs[p->weapon];
    float mag=p->zoom?(p->weapon==BG_W_SNIPER&&p->zoom==1?2:bg_weapon_defs[p->weapon].zoom):1;
    float limit=fmaxf(a->deviation,a->auto_angle)/mag,cosine=clamp(dot(desired,direction),-1,1);
    if(cosine<cosf(limit)){
        float side[3];for(unsigned k=0;k<3;k++)side[k]=desired[k]-direction[k]*cosine;
        normalize(side);for(unsigned k=0;k<3;k++)desired[k]=direction[k]*cosf(limit)+side[k]*sinf(limit);
    }
    memcpy(direction,desired,3*sizeof(float));
}

static void fire(unsigned index,bool charged){
    bg_player*p=&bg_players[index];const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
    const bg_trigger_profile*t=&bg_trigger_profiles[p->weapon];
    p->fire_ticks[p->slot]=0;p->flash=.08f;p->recoil=.06f;p->ammo-=charged?10:1;if(p->ammo<0)p->ammo=0;
    p->heat+=charged?.65f:w->heat;if(p->heat>=1){p->heat=1;p->overheated=true;p->overheat_charged[p->slot]=charged;}
    p->animation=BG_ANIM_FIRE;p->anim_time=0;
    float direction[3],origin[3];aim(p,direction,origin);assisted_shot(index,direction,origin);
    float spread=t->cone_min+(t->cone_max-t->cone_min)*p->trigger_error[p->slot];
    if(p->zoom&&t->zoom_accurate)spread=0;
    for(int pellet=0;pellet<w->pellets;pellet++){
        float dir[3];bg_combat_cone(direction,spread>0?t->cone_inner:0,spread,.5f+.5f*random_signed(),.5f+.5f*random_signed(),dir);
        if(w->speed>0){
            float start[3];for(int a=0;a<3;a++)start[a]=origin[a]+dir[a]*.15f;
            bg_projectile*q=projectile(w->projectile,index,start,dir,charged?18:w->speed,charged?90:w->damage,w->projectile==BG_P_ROCKET?2.2f:0);
            if(q){q->damage_profile=weapon_damage(p->weapon,charged);if(q->kind==BG_P_NEEDLE)q->tracked=bg_aim_query(index).player;}
        }else{
            float distance=hitscan(index,origin,dir,w->range,w->damage,p->weapon==BG_W_PISTOL||p->weapon==BG_W_SNIPER,weapon_damage(p->weapon,false),1);
            if(p->weapon==BG_W_SNIPER){
                distance=fminf(distance,bg_raycast(origin,dir,w->range));
                memcpy(sniper_traces[index].start,origin,sizeof(origin));
                for(unsigned a=0;a<3;a++)sniper_traces[index].end[a]=origin[a]+dir[a]*distance;
            }
        }
    }
    event(BG_EVENT_FIRE,index,p->weapon,p->pos,charged?2:1);
}
static void grenade(unsigned index){
    bg_player*p=&bg_players[index];if(p->grenades[p->grenade_kind]<=0||p->grenade_cooldown>0)return;
    float dir[3],origin[3];aim(p,dir,origin);dir[1]+=.25f;normalize(dir);
    bg_projectile*q=projectile(p->grenade_kind?BG_P_PLASMA_GRENADE:BG_P_FRAG,index,origin,dir,5,260,2.2f);
    if(q){q->life=bg_grenade_profiles[p->grenade_kind].fuse;p->grenades[p->grenade_kind]--;p->grenade_cooldown=.9f;event(BG_EVENT_GRENADE,index,p->grenade_kind,p->pos,1);}
}
static void needle_attach(bg_projectile*q,int target){
    q->attached=target;q->life=bg_needle_fuse;q->countdown=true;
    sub(q->attached_offset,q->pos,bg_players[target].pos);memset(q->velocity,0,sizeof(q->velocity));
    unsigned count=0;
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){bg_projectile*n=bg_projectile_at(j);
        if(n&&n->active&&n->kind==BG_P_NEEDLE&&n->attached==target&&!n->combined){n->life=bg_needle_fuse;count++;}}
    bg_player*p=&bg_players[target];p->needles=count;p->needle_owner=q->owner;p->needle_timer=bg_needle_fuse;
    event(BG_EVENT_NEEDLE_HIT,q->owner,BG_W_NEEDLER,q->pos,target);
}
static void needle_detonate(bg_projectile*q){
    int target=q->attached;if(target<0||target>=BG_PLAYERS||bg_players[target].health<=0)return;
    unsigned count=0;
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){bg_projectile*n=bg_projectile_at(j);
        if(n&&n->active&&n->kind==BG_P_NEEDLE&&n->attached==target&&!n->combined)count++;}
    if(count>=7&&!q->combined){
        /* Source: one super explosion replaces this needle's attached damage;
         * the six siblings keep their own delayed detonation damage. */
        unsigned marked=0;
        for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){bg_projectile*n=bg_projectile_at(j);
            if(n&&n->active&&n!=q&&n->kind==BG_P_NEEDLE&&n->attached==target&&!n->combined){
                if(marked++<6){n->combined=true;n->life*=.5f+.5f*random_signed();}else n->life=0;}}
        float center[3]={bg_players[target].pos[0],bg_players[target].pos[1]+.35f,bg_players[target].pos[2]};
        event(BG_EVENT_SUPERCOMBINE,q->owner,BG_W_NEEDLER,center,target);explode(center,q->owner,300,1,BG_P_NEEDLE);
    }else damage_player_profile(target,q->owner,bg_combat_amount(&bg_damage_profiles[BG_D_NEEDLE],1,.5f),false,false,BG_D_NEEDLE,false,false,1);
    if(bg_players[target].needles>0)bg_players[target].needles--;
    if(!bg_players[target].needles)bg_players[target].needle_owner=-1;
}
static void vehicle_local_point(const bg_vehicle*v,const float world[3],float local[3]){
    float delta[3];sub(delta,world,v->pos);
    for(unsigned axis=0;axis<3;axis++){
        float unit[3]={0},basis[3];unit[axis]=1;bg_vehicle_transform(v,unit,basis);
        for(unsigned a=0;a<3;a++)basis[a]-=v->pos[a];
        local[axis]=dot(delta,basis);
    }
}
static void update_projectiles(float dt){
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q)continue;
        blam_handle handle=blam_object_handle_at(&projectile_store,i);
        if(!q->active){blam_object_delete(&projectile_store,handle);continue;}
        bool grenade_kind=q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE;
        const bg_grenade_profile*g=&bg_grenade_profiles[q->kind==BG_P_PLASMA_GRENADE];
        q->age+=dt;
        if(!grenade_kind||q->countdown||q->attached!=-1)q->life-=dt;
        if(q->attached>=0){
            bool attached=false;
            if(q->attached<BG_PLAYERS&&bg_players[q->attached].health>0){
                for(unsigned a=0;a<3;a++)q->pos[a]=bg_players[q->attached].pos[a]+q->attached_offset[a];
                attached=true;
            }else if(q->attached>=BG_PLAYERS&&(unsigned)(q->attached-BG_PLAYERS)<bg_vehicle_count&&bg_vehicles[q->attached-BG_PLAYERS].active){
                bg_vehicle_transform(&bg_vehicles[q->attached-BG_PLAYERS],q->attached_offset,q->pos);attached=true;
            }
            if(!attached){q->attached=-2;if(q->kind==BG_P_NEEDLE)q->active=false;}
        }else if(q->attached!=-2){
            if(q->tracked>=0&&(q->tracked>=(int)active_players||bg_players[q->tracked].health<=0||bg_player_visibility(&bg_players[q->tracked])<=0))q->tracked=-1;
            if(q->kind==BG_P_NEEDLE&&q->tracked>=0&&q->tracked<(int)active_players&&bg_players[q->tracked].health>0){
                float forward[3],desired[3];memcpy(forward,q->velocity,sizeof(forward));float speed=sqrtf(dot(forward,forward));normalize(forward);
                sub(desired,bg_players[q->tracked].pos,q->pos);desired[1]+=.35f;normalize(desired);
                float cosine=clamp(dot(desired,forward),-1,1);
                if(cosine>0){float angle=fminf(acosf(cosine),bg_needle_turn*dt),side[3];
                    for(unsigned a=0;a<3;a++)side[a]=desired[a]-forward[a]*cosine;
                    if(dot(side,side)>1e-8f){normalize(side);for(unsigned a=0;a<3;a++)q->velocity[a]=speed*(forward[a]*cosf(angle)+side[a]*sinf(angle));}}
            }
            if(q->damage_profile>=BG_D_HOG){
                const bg_damage_profile*d=&bg_damage_profiles[q->damage_profile];
                float speed=sqrtf(dot(q->velocity,q->velocity));
                float energy=clamp((q->distance-d->range_start)/fmaxf(.001f,d->range_end-d->range_start),0,1);
                float desired=30*sqrtf(d->speed_start*d->speed_start+(d->speed_end*d->speed_end-d->speed_start*d->speed_start)*energy);
                if(speed>1e-6f)for(unsigned a=0;a<3;a++)q->velocity[a]*=desired/speed;
                q->velocity[1]-=bg_movement.gravity*d->gravity*dt;
                if(q->distance>=d->range){q->active=false;continue;}
            }
            if(grenade_kind)q->velocity[1]-=bg_movement.gravity*g->gravity*dt;
            float speed=sqrtf(dot(q->velocity,q->velocity)),dir[3];memcpy(dir,q->velocity,sizeof(dir));
            if(speed>1e-8f)for(int a=0;a<3;a++)dir[a]/=speed;
            float length=speed*dt,nearest=length;int region=1;
            int target=target_ray(q->owner,q->pos,dir,&nearest,&region),vehicle=-1;unsigned material=0;
            for(unsigned j=0;j<bg_vehicle_count;j++){
                bg_vehicle*v=&bg_vehicles[j];if(!v->active||bg_players[q->owner].vehicle==(int)j)continue;
                float hit=bg_vehicle_hit_ray_material(v,q->pos,dir,nearest,&material);
                if(hit<nearest){nearest=hit;target=-1;vehicle=j;}
            }
            float normal[3]={-dir[0],-dir[1],-dir[2]};
            float terrain=bg_world_raycast_normal(q->pos,dir,length,normal);
            if(terrain<nearest){nearest=terrain;target=vehicle=-1;}
            else if(target>=0||vehicle>=0)for(unsigned a=0;a<3;a++)normal[a]=-dir[a];
            bool impact=nearest<length;q->distance+=nearest;
            for(int a=0;a<3;a++)q->pos[a]+=dir[a]*(impact?fmaxf(0,nearest-.003f):nearest);
            if(impact){
                if(grenade_kind){
                    if(q->kind==BG_P_PLASMA_GRENADE&&(target>=0||vehicle>=0)){
                        q->attached=target>=0?target:BG_PLAYERS+vehicle;q->countdown=true;q->life=g->fuse;
                        memset(q->velocity,0,sizeof(q->velocity));if(target>=0)sub(q->attached_offset,q->pos,bg_players[target].pos);
                        else vehicle_local_point(&bg_vehicles[vehicle],q->pos,q->attached_offset);
                    }else{
                        if(q->kind==BG_P_FRAG&&!q->countdown){q->countdown=true;q->life=g->fuse;}
                        float along=dot(q->velocity,normal);
                        for(unsigned a=0;a<3;a++)q->velocity[a]=(1-g->perpendicular)*(q->velocity[a]-along*normal[a])-(1-g->parallel)*along*normal[a];
                        /* Quantized rest threshold prevents subpixel contacts
                         * from bouncing forever under the N64 contact bias. */
                        if(normal[1]>.3f&&dot(q->velocity,q->velocity)<.04f){q->attached=-2;memset(q->velocity,0,sizeof(q->velocity));if(!q->countdown){q->countdown=true;q->life=g->fuse;}}
                    }
                }else if(q->kind==BG_P_NEEDLE&&target>=0){needle_attach(q,target);}
                else if(q->radius>0){explode_profile(q->pos,q->owner,q->damage,q->radius,q->kind,q->damage_profile);q->active=false;}
                else{
                    if(target>=0){float amount=q->damage,energy=1;
                        if(q->damage_profile){const bg_damage_profile*d=&bg_damage_profiles[q->damage_profile];energy=bg_combat_range_scale(d,q->distance);amount=bg_combat_amount(d,energy,.5f+.5f*random_signed());}
                        damage_player_profile(target,q->owner,amount,q->kind==BG_P_PLASMA,q->damage_profile&&region==2,q->damage_profile,region==0,false,energy);}
                    if(vehicle>=0){const bg_damage_profile*d=&bg_damage_profiles[q->damage_profile];
                        float amount=q->damage_profile?bg_combat_amount(d,bg_combat_range_scale(d,q->distance),.5f+.5f*random_signed()):q->damage;
                        damage_vehicle_profile(vehicle,q->owner,amount,q->damage_profile,material,false);}
                    q->active=false;
                }
            }
        }
        if(q->active&&q->life<=1e-6f&&(!grenade_kind||q->age+1e-6f>=g->arming)){
            if(q->kind==BG_P_NEEDLE)needle_detonate(q);
            else if(q->radius>0){
                explode_profile(q->pos,q->owner,q->damage,q->radius,q->kind,q->damage_profile);
                if(q->kind==BG_P_PLASMA_GRENADE&&q->attached>=0&&q->attached<BG_PLAYERS)
                    damage_player_profile(q->attached,q->owner,bg_combat_amount(&bg_damage_profiles[BG_D_STICK],1,.5f),false,false,BG_D_STICK,false,false,1);
            }q->active=false;
        }
        if((q->kind==BG_P_NEEDLE&&q->attached==-1&&q->distance>bg_needle_range)||q->age>30||q->pos[1]<-10||cell(q->pos[0],q->pos[2])<0)q->active=false;
        if(!q->active)blam_object_delete(&projectile_store,handle);
    }
}
bg_use_target bg_interaction_target(unsigned player){
    bg_use_target result={BG_USE_NONE,-1,-1};if(player>=active_players)return result;
    const bg_player*p=&bg_players[player];
    if(p->health<=0||p->interact_cooldown>0||p->seat_state!=BG_SEAT_STABLE||p->weapon_ready>0)return result;
    if(p->vehicle>=0)return (bg_use_target){BG_USE_EXIT,p->vehicle,p->seat};
    float nearest=.85f*.85f;
    for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].active&&bg_pickups[i].weapon<BG_WEAPON_COUNT){
        const bg_pickup*q=&bg_pickups[i];
        if(q->ignore_time>0&&q->ignore_player==(int)player)continue;
        if((p->inventory[0]==q->weapon||p->inventory[1]==q->weapon)&&!bg_weapon_defs[q->weapon].energy)continue;
        if(bg_weapon_defs[q->weapon].energy&&q->ammo<=0)continue;
        float d=distance2(p->pos,q->pos);if(d<nearest){result=(bg_use_target){BG_USE_PICKUP,i,q->generation};nearest=d;}
    }
    if(result.kind)return result;
    nearest=1.f;
    float center[3]={p->pos[0],p->pos[1]+.35f,p->pos[2]};
    for(unsigned i=0;i<bg_vehicle_count;i++){
        const bg_vehicle*v=&bg_vehicles[i];if(!v->active)continue;
        if(v->physics_valid&&v->up[1]<BG_VEHICLE_FLIP_MAX_UP){
            if(!v->flipping&&v->occupants[0]<0&&distance2(p->pos,v->pos)<4.f)return (bg_use_target){BG_USE_FLIP,i,-1};
            continue;
        }
        /* Authored seat sphere rejects far hulls before transforming every
         * entry/anchor for both simulation and prompt queries. */
        static float seat_radius2[BG_VEHICLE_COUNT];
        if(!seat_radius2[v->kind]){
            float radius2=0;
            for(unsigned seat=0;seat<bg_seat_counts[v->kind];seat++){
                const bg_seat_definition*s=&bg_seat_definitions[v->kind][seat];
                radius2=fmaxf(radius2,fmaxf(dot(s->entry,s->entry),dot(s->anchor,s->anchor)));
            }
            /* Gunner anchor rotates about a .5-unit offset, so allow another
             * full unit for that orbit plus the one-unit interaction reach. */
            float reach=sqrtf(radius2)+1.01f+(v->kind==BG_V_WARTHOG?1.f:0);
            seat_radius2[v->kind]=reach*reach;
        }
        if(distance2(center,v->pos)>seat_radius2[v->kind])continue;
        for(unsigned seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]<0){
            const bg_seat_definition*s=&bg_seat_definitions[v->kind][seat];
            if((s->flags&512)&&v->occupants[0]<0)continue;
            float entry[3],anchor[3];bg_vehicle_seat_position(v,seat,true,entry);bg_vehicle_seat_position(v,seat,false,anchor);
            float d=fminf(distance2(center,entry),distance2(center,anchor));
            float bias=result.kind==BG_USE_ENTER&&result.seat==0&&seat!=0?2.25f:1.f;
            if(d>=1.f||d*bias>=nearest)continue;
            float entry_chest[3]={entry[0],fmaxf(entry[1],p->pos[1])+.35f,entry[2]};
            float approach[3];sub(approach,entry_chest,center);float reach=sqrtf(dot(approach,approach));normalize(approach);
            if(bg_raycast(center,approach,reach)<reach-.02f)continue;
            bool blocked=false;
            for(unsigned other=0;other<bg_vehicle_count;other++)if(other!=i&&bg_vehicle_body_present(&bg_vehicles[other])&&bg_vehicle_hit_ray(&bg_vehicles[other],center,approach,reach)<reach-.02f){blocked=true;break;}
            if(!blocked){result=(bg_use_target){BG_USE_ENTER,i,seat};nearest=d;}
        }
    }
    return result;
}
static bool same_target(bg_use_target a,bg_use_target b){return a.kind==b.kind&&a.object==b.object&&a.seat==b.seat;}
static void interact(unsigned player,bg_use_target target){
    bg_player*p=&bg_players[player];
    if(!same_target(target,bg_interaction_target(player)))return;
    if(target.kind==BG_USE_PICKUP){
        bg_pickup*q=&bg_pickups[target.object];pickup_weapon(player,q);
        p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;
        p->interact_cooldown=.5f;
    }else if(target.kind==BG_USE_FLIP){
        bg_vehicle_physics_flip(target.object,p->pos);p->interact_cooldown=.5f;
    }else if(target.kind==BG_USE_EXIT){
        float exit[3];if(!bg_vehicle_exit_position(player,exit))return;
        p->seat_state=BG_SEAT_EXITING;p->seat_time=bg_player_seat(p)->exit_time;p->anim_time=0;
        p->melee_tick=0;p->reload=p->charge=p->melee_time=p->zoom=0;
    }else if(target.kind==BG_USE_ENTER){
        bg_vehicle*v=&bg_vehicles[target.object];float anchor[3],start[3];
        p->vehicle=target.object;p->seat=target.seat;v->occupants[p->seat]=player;
        const bg_seat_definition*s=bg_player_seat(p);
        bg_vehicle_seat_position(v,p->seat,false,anchor);seat_vector(v,s,s->enter_start,start);
        for(unsigned a=0;a<3;a++)p->seat_offset[a]=p->pos[a]-anchor[a]-start[a];
        p->seat_state=BG_SEAT_ENTERING;p->seat_time=s->enter_time;p->seat_blend=6.f/30;
        p->melee_tick=0;p->zoom=p->reload=p->charge=p->melee_time=0;p->animation=BG_ANIM_DRIVE;p->anim_time=0;p->crouched=false;p->crouch_amount=0;
        memcpy(p->pos,anchor,sizeof(anchor));event(BG_EVENT_ENTER,player,v->kind,p->pos,p->seat);
    }
}
static void update_use(unsigned player,bool held,float dt){
    bg_player*p=&bg_players[player];
    if(!held){p->use_time=0;p->use_latched=false;p->use_target=(bg_use_target){BG_USE_NONE,-1,-1};return;}
    if(p->use_latched)return;
    bg_use_target target=bg_interaction_target(player);
    if(!same_target(target,p->use_target)){p->use_target=target;p->use_time=0;}
    if(!target.kind){p->use_time=0;return;}
    p->use_time+=dt;
    /* Xbox delays weapon swaps only; vehicle actions start on use. The
     * animation bank is streamed during playback, independently of this hold. */
    if(target.kind!=BG_USE_PICKUP||p->use_time+1e-6f>=BG_USE_HOLD_TICKS/30.f){
        p->use_latched=true;p->use_time=0;interact(player,target);
    }
}
static void melee_impact(unsigned index){
    bg_player*p=&bg_players[index];float dir[3],origin[3];aim(p,dir,origin);
    float right[3]={sinf(p->yaw),0,cosf(p->yaw)};
    float up[3]={-sinf(p->pitch)*cosf(p->yaw),cosf(p->pitch),sinf(p->pitch)*sinf(p->yaw)};
    int victim=-1,vehicle=-1;float best=2;
    /* Source 5x5 rays, 0.8 forward and 0.1 lateral spacing. Select one
     * collision, preferring bipeds, instead of applying 25 damage events. */
    for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++){
        float ray[3];for(unsigned k=0;k<3;k++)ray[k]=dir[k]*.8f+(right[k]*x+up[k]*y)*.1f;
        float length=sqrtf(dot(ray,ray));for(unsigned k=0;k<3;k++)ray[k]/=length;
        float nearest=length;int region,hit=target_ray(index,origin,ray,&nearest,&region),vhit=-1;
        for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicles[v].active){
            float t=bg_vehicle_hit_ray(&bg_vehicles[v],origin,ray,nearest);
            if(t<nearest){nearest=t;hit=-1;vhit=v;}
        }
        if((hit>=0||vhit>=0)&&bg_raycast(origin,ray,nearest)>=nearest){
            if(hit>=0&&(victim<0||nearest/length<best)){victim=hit;vehicle=-1;best=nearest/length;}
            else if(vhit>=0&&victim<0&&vehicle<0)vehicle=vhit;
        }
    }
    float scale=clamp((p->velocity[0]*cosf(p->yaw)-p->velocity[2]*sinf(p->yaw))/bg_movement.run[0],0,1);
    if(p->airborne_time>.5f)scale=1.5f;
    float amount=bg_combat_amount(&bg_damage_profiles[BG_D_MELEE],scale,.5f+.5f*random_signed());
    if(victim>=0){bg_player*v=&bg_players[victim];float cp=cosf(v->pitch),facing[3]={cosf(v->yaw)*cp,sinf(v->pitch),-sinf(v->yaw)*cp},offset[3];sub(offset,v->pos,p->pos);
        damage_player_profile(victim,index,amount,false,false,BG_D_MELEE,false,dot(offset,facing)>0,scale);
    }else if(vehicle>=0)damage_vehicle_profile(vehicle,index,amount,BG_D_MELEE,0,false);
}
static void melee(unsigned index){
    bg_player*p=&bg_players[index];if(p->melee_time>0||p->zoom||p->charge>=bg_trigger_profiles[BG_W_PLASMA_PISTOL].charge_time)return;
    stop_reload(p);p->charge=0;p->melee_tick=bg_trigger_profiles[p->weapon].melee_key+1;
    p->melee_time=bg_melee_duration(p->weapon);p->animation=BG_ANIM_MELEE;p->anim_time=0;p->cooldown=p->melee_time;
    event(BG_EVENT_MELEE,index,p->weapon,p->pos,1);
}
static void mounted_fire(bg_vehicle*v,unsigned player,unsigned gun,unsigned slot,bool down,float dt){
    const bg_mounted_profile*m=&bg_mounted_profiles[gun];const bg_trigger_profile*t=&m->trigger;
    float *cooldown=slot?&v->secondary_cooldown:&v->cooldown;
    if(down&&*cooldown<=1e-6f){
        float axis[3],dir[3],origin[3];aim(&bg_players[player],axis,origin);
        bg_combat_cone(axis,t->cone_inner,t->cone_min+(t->cone_max-t->cone_min)*v->gun_error[slot],.5f+.5f*random_signed(),.5f+.5f*random_signed(),dir);
        for(unsigned a=0;a<3;a++)origin[a]+=axis[a];
        const bg_damage_profile*d=&bg_damage_profiles[m->profile];
        if(gun==0||gun==3)hitscan(player,origin,dir,d->range,0,false,m->profile,1);
        else {bg_projectile*q=projectile(gun==2||gun==5?BG_P_CANNON:BG_P_PLASMA,player,origin,dir,d->speed_start*30,d->upper,d->cutoff);
            if(q)q->damage_profile=m->profile;}
        float rate=t->rate_min+(t->rate_max-t->rate_min)*v->gun_rate[slot];
        *cooldown=m->chamber>0?m->chamber:rate>0?ceilf(30.f/rate)/30.f:1.f/30;
        v->flash=bg_players[player].flash=.08f;
        event(BG_EVENT_FIRE,player,gun==0||gun==3?BG_W_AR:gun==2||gun==5?BG_W_ROCKET:BG_W_PLASMA_RIFLE,v->pos,1);
    }
    v->gun_rate[slot]=bg_trigger_step(v->gun_rate[slot],(down?t->rate_up:-t->rate_down)*dt*30);
    v->gun_error[slot]=bg_trigger_step(v->gun_error[slot],(down?t->error_up:-t->error_down)*dt*30);
}
static void update_vehicles(const bg_input inputs[BG_PLAYERS],float dt){
    bg_vehicle_physics_prepare();
    for(unsigned i=0;i<bg_vehicle_count;i++){
        bg_vehicle*v=&bg_vehicles[i];v->cooldown=fmaxf(0,v->cooldown-dt);v->flash=fmaxf(0,v->flash-dt);v->secondary_cooldown=fmaxf(0,v->secondary_cooldown-dt);
        if(!v->active){
            if(v->wreck_time>0){bg_vehicle_physics_wreck(i);v->wreck_time=fmaxf(0,v->wreck_time-dt);}
            v->respawn-=dt;if(v->respawn<=0){v->active=true;v->wreck_time=0;v->health=v->kind==BG_V_SCORPION?800:400;
            memcpy(v->pos,v->home,sizeof(v->pos));v->yaw=v->home_yaw;v->pitch=0;v->physics_valid=false;memset(v->velocity,0,sizeof(v->velocity));memset(v->angular_velocity,0,sizeof(v->angular_velocity));}continue;}
        for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=(int)active_players)eject(v->occupants[seat],true);
        int driver=v->occupants[0];const bg_input*in=driver>=0&&bg_players[driver].seat_state==BG_SEAT_STABLE?&inputs[driver]:NULL;
        if(v->kind==BG_V_SCORPION||v->kind==BG_V_BANSHEE){
            const bg_player*p=driver>=0?&bg_players[driver]:NULL;
            float duration=v->kind==BG_V_SCORPION?16.f/30:22.f/30;
            v->hatch_closing=p&&p->seat_state==BG_SEAT_STABLE;
            v->hatch=!p||p->seat_state==BG_SEAT_ENTERING?1:clamp(p->anim_time/duration,0,1);
        }
        float maxspeed=v->kind==BG_V_SCORPION?3.5f:v->kind==BG_V_BANSHEE?9:v->kind==BG_V_GHOST?7:7.65f;
        float previous_pos[3];memcpy(previous_pos,v->pos,12);
        bg_vehicle_physics_step(i,in);
        eject_overturned(i);
        for(unsigned p=0;p<active_players;p++)if(bg_players[p].support_vehicle==i+1&&bg_players[p].health>0&&bg_players[p].vehicle<0){
            bg_player*passenger=&bg_players[p];float moved[3];bg_vehicle_transform(v,passenger->support_local,moved);
            bg_player probe=*passenger;memcpy(probe.pos,moved,12);
            if(bg_terrain_clearance(&probe))memcpy(passenger->pos,moved,12);
            else passenger->support_vehicle=0;
        }
        if(v->pos[1]<-8||cell(v->pos[0],v->pos[2])<0){damage_vehicle(i,driver,10000);continue;}
        v->engine_phase+=dt*(1+fabsf(v->speed));
        if(v->engine_phase>12){v->engine_phase-=12;if(driver>=0)event(BG_EVENT_ENGINE,driver,v->kind,v->pos,fabsf(v->speed)/maxspeed);}
        float hull_speed=sqrtf(dot(v->velocity,v->velocity));
        for(unsigned j=0;j<active_players;j++){
            bg_player*p=&bg_players[j];if(p->health<=0||p->vehicle>=0||p->support_vehicle==i+1||(p->exit_grace>0&&p->exit_vehicle==(int)i))continue;
            float relative[3];sub(relative,v->velocity,p->velocity);float speed=sqrtf(dot(relative,relative));if(hull_speed<.05f&&speed<.05f)continue;
            /* Sweep the authored hull, not an origin-centered kill sphere.
             * Up to eight substeps cover fast lateral/falling impacts. */
            unsigned steps=(unsigned)ceilf(hull_speed*dt/(bg_movement.radius*.5f));if(steps<1)steps=1;if(steps>8)steps=8;
            bg_vehicle probe=*v;
            for(unsigned step=0;step<=steps;step++){
                for(unsigned a=0;a<3;a++)probe.pos[a]=previous_pos[a]+(v->pos[a]-previous_pos[a])*step/steps;
                if(bg_vehicle_contacts_player(&probe,p)){
                    /* physics_compute_biped_collision, converted from per-tick
                     * units, including biped_accelerate's live-player halving. */
                    float direction[3];sub(direction,p->pos,v->pos);direction[1]+=bg_body_height(p)*.5f;normalize(direction);direction[1]+=.8f;normalize(direction);
                    float acceleration[3];for(unsigned a=0;a<3;a++){acceleration[a]=(direction[a]*fmaxf(hull_speed,3)+v->velocity[a])*.25f;p->velocity[a]+=acceleration[a];}
                    p->vy=p->velocity[1];p->grounded=false;
                    bg_player displaced=*p;for(unsigned a=0;a<3;a++)displaced.pos[a]+=acceleration[a]*(2.f/30);
                    bool clear=bg_terrain_clearance(&displaced)&&!bg_vehicle_contacts_player(v,&displaced);
                    if(clear)memcpy(p->pos,displaced.pos,12);
                    if(!clear||hull_speed>2||speed>1){
                        damage_player_profile(j,driver,bg_combat_amount(&bg_damage_profiles[BG_D_COLLISION],1,.5f),false,false,BG_D_COLLISION,false,false,1);
                        damage_vehicle_profile(i,j,bg_combat_amount(&bg_damage_profiles[BG_D_VEHICLE_KILL],.25f,.5f),BG_D_VEHICLE_KILL,0,true);
                    }
                    break;
                }
            }
        }
        for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=0){
            bg_player*p=&bg_players[v->occupants[seat]];
            if(v->kind==BG_V_WARTHOG&&seat==1)v->turret_yaw=p->yaw-v->yaw;
            bg_vehicle_seat_position(v,seat,false,p->pos);
            if((v->kind==BG_V_SCORPION&&seat==0)||(v->kind==BG_V_WARTHOG&&seat==1)){v->turret_yaw=p->yaw-v->yaw;v->turret_pitch=p->pitch;}
            p->vy=0;p->grounded=true;p->animation=BG_ANIM_DRIVE;
            bool mounted=p->seat_state==BG_SEAT_STABLE&&((v->kind==BG_V_WARTHOG&&seat==1)||(v->kind!=BG_V_WARTHOG&&seat==0));
            const bg_input*control=&inputs[v->occupants[seat]];
            if(mounted){
                static const unsigned primary[4]={0,1,2,4};
                mounted_fire(v,v->occupants[seat],primary[v->kind],0,control->fire,dt);
                if(v->kind==BG_V_SCORPION||v->kind==BG_V_BANSHEE)
                    mounted_fire(v,v->occupants[seat],v->kind==BG_V_SCORPION?3:5,1,control->grenade||control->secondary_fire,dt);
            }
        }
    }
}
static void teleport(unsigned index){
    bg_player*p=&bg_players[index];if(p->health<=0||p->vehicle>=0||p->teleport_cooldown>0)return;
    for(unsigned i=0;i<bg_teleporter_count;i++){
        const bg_teleporter*t=&bg_teleporters[i];float dx=p->pos[0]-t->source[0],dz=p->pos[2]-t->source[2];
        if(dx*dx+dz*dz>.45f*.45f||fabsf(p->pos[1]-t->source[1])>.55f)continue;
        memcpy(p->pos,t->destination,sizeof(p->pos));float floor=bg_floor(p->pos[0],p->pos[2],p->pos[1]+.5f);
        if(floor>-999)p->pos[1]=floor+.015f;
        p->yaw=t->yaw;p->pitch=0;p->vy=0;p->grounded=true;p->teleport_cooldown=1;
        memset(p->velocity,0,sizeof(p->velocity));memcpy(p->last_pos,p->pos,sizeof(p->pos));
        event(BG_EVENT_TELEPORTER,index,p->weapon,p->pos,i);break;
    }
}
static void load_rounds(bg_player*p){
    int n=bg_weapon_defs[p->weapon].magazine-p->ammo;if(p->weapon==BG_W_SHOTGUN)n=1;
    n=n>p->reserve?p->reserve:n;p->ammo+=n;p->reserve-=n;
}
static void stop_reload(bg_player*p){
    /* Original reset retains a magazine only after passing halfway through
     * the empty-reload timeline; earlier cancellation does not create ammo. */
    if(p->reload>0&&2*p->reload<bg_trigger_profiles[p->weapon].reload_empty/30.f)load_rounds(p);
    p->reload=p->reload_duration=0;
}
static void start_reload(unsigned i){
    bg_player*p=&bg_players[i];const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
    if(p->reload>0||p->melee_time>0||w->energy||p->ammo>=w->magazine||p->reserve<=0)return;
    const bg_trigger_profile*t=&bg_trigger_profiles[p->weapon];
    unsigned frames=t->reload_empty;
    if(p->weapon==BG_W_SHOTGUN&&t->reload_enter)frames=t->reload_enter;
    p->reload=p->reload_duration=frames/30.f;p->zoom=0;p->animation=BG_ANIM_RELOAD;p->anim_time=0;
    event(BG_EVENT_RELOAD,i,p->weapon,p->pos,1);
}
static void advance_reload(bg_player*p,const bg_input*in,float dt){
    if(p->reload<=0)return;
    if(p->weapon==BG_W_SHOTGUN&&in->fire&&p->ammo>0){stop_reload(p);return;}
    p->reload-=dt;if(p->reload>1e-6f)return;
    load_rounds(p);p->reload=0;
    if(p->weapon==BG_W_SHOTGUN&&p->ammo<bg_weapon_defs[p->weapon].magazine&&p->reserve>0&&!in->fire){p->reload=p->reload_duration=bg_trigger_profiles[p->weapon].reload_empty/30.f;p->anim_time=0;}
}
static bool player_can_stand(const bg_player*p){
    if(!bg_can_stand(p))return false;
    bg_player standing=*p;standing.crouch_amount=0;
    for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicles[v].active&&bg_vehicle_contacts_player(&bg_vehicles[v],&standing)&&!bg_vehicle_contacts_player(&bg_vehicles[v],p))return false;
    for(unsigned i=0;i<active_players;i++){
        const bg_player*q=&bg_players[i];if(q==p||q->health<=0||q->vehicle>=0)continue;
        float dx=q->pos[0]-p->pos[0],dz=q->pos[2]-p->pos[2];
        if(dx*dx+dz*dz<4*bg_movement.radius*bg_movement.radius&&q->pos[1]>=p->pos[1]+bg_body_height(p)-.015f&&q->pos[1]<p->pos[1]+bg_movement.height[0])return false;
    }return true;
}
void bg_tick(const bg_input inputs[BG_PLAYERS],float dt){
    dt=clamp(dt,0,1.0f/30);if(dt<=0||bg_match_finished())return;
    match_time+=dt;
    update_pickups(dt);
    for(unsigned i=0;i<active_players;i++){
        bg_player*p=&bg_players[i];const bg_input*in=&inputs[i];
        p->exit_grace=fmaxf(0,p->exit_grace-dt);
        for(unsigned slot=0;slot<2;slot++)if(p->fire_ticks[slot]<65535)p->fire_ticks[slot]++;
        p->stun_time=fmaxf(0,p->stun_time-dt);if(p->stun_time==0)p->body_stun=0;
        p->cooldown=fmaxf(0,p->cooldown-dt);p->flash=fmaxf(0,p->flash-dt);p->hurt=fmaxf(0,p->hurt-dt);
        p->shield_hit=fmaxf(0,p->shield_hit-dt*.5f);p->shield_break=fmaxf(0,p->shield_break-dt);
        p->airborne_time=p->grounded?0:p->airborne_time+dt;
        p->recoil=fmaxf(0,p->recoil-dt*.3f);p->melee_time=fmaxf(0,p->melee_time-dt);
        if(p->melee_tick&&p->health>0&&--p->melee_tick==0)melee_impact(i);
        p->grenade_cooldown=fmaxf(0,p->grenade_cooldown-dt);p->interact_cooldown=fmaxf(0,p->interact_cooldown-dt);
        bg_camo_tick(p,dt);p->teleport_cooldown=fmaxf(0,p->teleport_cooldown-dt);p->anim_time+=dt;
        p->weapon_ready=fmaxf(0,p->weapon_ready-dt);p->seat_blend=fmaxf(0,p->seat_blend-dt);
        if(p->seat_state!=BG_SEAT_STABLE){
            p->seat_time=fmaxf(0,p->seat_time-dt);
            if(p->seat_time<=1e-6f){
                if(p->seat_state==BG_SEAT_EXITING){if(!eject(i,false)){p->seat_state=BG_SEAT_STABLE;p->anim_time=0;}}
                else {p->seat_state=BG_SEAT_STABLE;p->anim_time=0;}
            }
        }
        if(p->health<=0){p->respawn-=dt;if(p->respawn<=0){spawn(i);}continue;}
        bool was_charging=p->shield_charging;p->shield_charging=false;
        if(p->shield_overcharging){
            p->shield=fminf(300,p->shield+100*dt);
            if(p->shield>299.999f)p->shield=300;
            p->shield_overcharging=p->shield<300;
            p->shield_charging=p->shield_overcharging;
        }else if(p->shield>100)p->shield=fmaxf(100,p->shield-dt*(100.f/45));
        else if(p->shield_delay>0)p->shield_delay=fmaxf(0,p->shield_delay-dt);
        else if(p->shield<100){p->shield=fminf(100,p->shield+25*dt);p->shield_charging=p->shield<100;}
        if(p->shield_charging&&!was_charging)event(BG_EVENT_SHIELD,i,p->weapon,p->pos,1);
        p->heat=fmaxf(0,p->heat-dt*.2f);if(p->overheated&&p->heat<.15f)p->overheated=false;
        int stowed=1-p->slot;p->heats[stowed]=fmaxf(0,p->heats[stowed]-dt*.2f);
        if(p->heats[stowed]<.15f)p->overheated_slots[stowed]=false;
        advance_reload(p,in,dt);
        if(in->switch_weapon&&p->inventory[1-p->slot]>=0&&p->weapon_ready<=0&&bg_player_personal_weapon(p))select_slot(p,1-p->slot);
        if(in->switch_grenade)p->grenade_kind=1-p->grenade_kind;
        if(in->zoom){if(bg_weapon_defs[p->weapon].zoom>1)p->zoom=(p->zoom+1)%(p->weapon==BG_W_SNIPER?3:2);else p->zoom=0;}
        player_look(i,in,dt);
        update_use(i,in->interact,dt);
        teleport(i); /* Trigger volumes precede capsule depenetration at the pad. */
        if(p->vehicle<0){
            p->landing_time=fmaxf(0,p->landing_time-dt);
            p->crouched=in->crouch||(p->crouch_amount>0&&!player_can_stand(p));
            float old_crouch=p->crouch_amount;
            p->crouch_amount=clamp(old_crouch+(p->crouched?1:-1)*bg_movement.crouch_rate*dt,0,1);
            /* Original airborne crouch raises the feet while preserving the
             * top of the collision pill; it is not a free vertical impulse. */
            if(!p->grounded)p->pos[1]+=(bg_movement.height[0]-bg_movement.height[1])*(p->crouch_amount-old_crouch);
            bool was_grounded=p->grounded;
            bg_walk_velocity(p,in->forward,in->strafe,dt);
            bool jump=in->jump&&p->grounded&&!(p->hard_landing&&p->landing_time>0);
            if(jump){
                if(p->support_vehicle){const bg_vehicle*v=&bg_vehicles[p->support_vehicle-1];float offset[3],spin[3];sub(offset,p->pos,v->pos);
                    spin[0]=v->angular_velocity[1]*offset[2]-v->angular_velocity[2]*offset[1];spin[1]=v->angular_velocity[2]*offset[0]-v->angular_velocity[0]*offset[2];spin[2]=v->angular_velocity[0]*offset[1]-v->angular_velocity[1]*offset[0];
                    for(unsigned a=0;a<3;a++)p->velocity[a]+=v->velocity[a]+spin[a];
                    p->vy=p->velocity[1];p->support_vehicle=0;}
                p->vy=fmaxf(p->vy,bg_movement.jump*(1-p->body_stun*bg_stun_config[1]));p->velocity[1]=p->vy;p->grounded=false;event(BG_EVENT_JUMP,i,p->weapon,p->pos,1);}
            if(p->grounded){
                /* Original solver presses into the supporting plane by
                 * 1/128 world units per tick. Collision removes only the
                 * inward component, retaining slope-tangent motion. */
                float *n=p->ground_normal;if(n[1]<=0){n[0]=n[2]=0;n[1]=1;}
                for(unsigned axis=0;axis<3;axis++)p->velocity[axis]-=n[axis]*(30.f/128.f);
            }else{p->velocity[1]=p->vy-bg_movement.gravity*dt;}
            float impact=bg_move_capsule(p,dt);
            p->support_vehicle=0;
            for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicles[v].active){
                bool grounded=p->grounded;
                if(bg_vehicle_resolve_player(&bg_vehicles[v],p)&&p->grounded&&!grounded){p->support_vehicle=v+1;vehicle_local_point(&bg_vehicles[v],p->pos,p->support_local);}
            }
            p->vy=p->velocity[1];
            if(!was_grounded&&p->grounded){
                bg_start_landing(p,impact);event(BG_EVENT_LAND,i,p->weapon,p->pos,impact);
                float lo=sqrtf(2*bg_movement.gravity*bg_fall_distances[0]),hi=sqrtf(2*bg_movement.gravity*bg_fall_distances[1]);
                if(impact>lo)damage_player_profile(i,-1,bg_combat_amount(&bg_damage_profiles[BG_D_FALL],clamp((impact-lo)/(hi-lo),0,1),.5f),false,false,BG_D_FALL,false,false,1);
            }
            if(p->vy < -sqrtf(2*bg_movement.gravity*bg_fall_distances[2]))damage_player_profile(i,-1,bg_combat_amount(&bg_damage_profiles[BG_D_DISTANCE],1,.5f),false,false,BG_D_DISTANCE,false,false,1);
            if(p->pos[1]<-6||cell(p->pos[0],p->pos[2])<0){kill(i,i);continue;}
            float moving=sqrtf(p->velocity[0]*p->velocity[0]+p->velocity[2]*p->velocity[2]);p->gait+=moving*dt*5;
            bg_animation animation=p->melee_time>0?BG_ANIM_MELEE:p->reload>0?BG_ANIM_RELOAD:p->flash>0?BG_ANIM_FIRE:
                !p->grounded?BG_ANIM_JUMP:moving>.15f?(p->crouched?BG_ANIM_WALK:BG_ANIM_RUN):BG_ANIM_IDLE;
            if(animation!=p->animation){p->animation=animation;p->anim_time=0;}
        }
        bool personal=bg_player_personal_weapon(p)&&p->weapon_ready<=0;
        if(personal){
            if(in->reload&&bg_interaction_target(i).kind<=BG_USE_PICKUP)start_reload(i);
            if(in->grenade&&p->reload<=0&&p->melee_time<=0)grenade(i);
            if(in->melee)melee(i);
            const bg_trigger_profile*t=&bg_trigger_profiles[p->weapon];
            float rate=t->rate_min+(t->rate_max-t->rate_min)*p->trigger_rate[p->slot];
            bool cadence=rate<=0||p->fire_ticks[p->slot]+1e-5f>=30.f/rate;
            bool ready=cadence&&p->cooldown<=0&&p->reload<=0&&!p->overheated&&p->ammo>0&&p->melee_time<=0;
            if(p->weapon==BG_W_PLASMA_PISTOL){
                if(in->fire&&p->ammo>0&&!p->overheated)p->charge=fminf(1.2f,p->charge+dt);
                if(!in->fire&&p->fire_held&&ready){fire(i,p->charge+1e-6f>=bg_trigger_profiles[p->weapon].charge_time&&p->ammo>=10);p->charge=0;}
            }else if(in->fire&&(bg_trigger_profiles[p->weapon].automatic||!p->fire_held)&&ready)fire(i,false);
            if(in->fire&&p->ammo<=0&&p->cooldown<=0){
                if(p->reserve>0)start_reload(i);else{event(BG_EVENT_EMPTY,i,p->weapon,p->pos,1);p->cooldown=.5f;}}
        }
        for(unsigned slot=0;slot<2;slot++){
            if(p->inventory[slot]<0)continue;
            const bg_trigger_profile*t=&bg_trigger_profiles[p->inventory[slot]];
            bool down=personal&&slot==(unsigned)p->slot&&in->fire;
            float rate=t->rate_min+(t->rate_max-t->rate_min)*p->trigger_rate[slot];
            bool recovering=rate>0&&p->fire_ticks[slot]<ceilf(30.f/rate);
            p->trigger_rate[slot]=bg_trigger_step(p->trigger_rate[slot],down?t->rate_up:-t->rate_down);
            p->trigger_error[slot]=bg_trigger_step(p->trigger_error[slot],(down||recovering)?t->error_up:-t->error_down);
        }
        p->fire_held=in->fire;teleport(i);memcpy(p->last_pos,p->pos,sizeof(p->pos));
        if(p->vehicle<0)collect_nearby(i);

    }
    if(!bg_match_finished()){
        for(unsigned a=0;a<active_players;a++)for(unsigned b=a+1;b<active_players;b++){
            bg_player*p=&bg_players[a],*q=&bg_players[b];if(p->health<=0||q->health<=0||p->vehicle>=0||q->vehicle>=0)continue;
            float r=bg_movement.radius,dx=p->pos[0]-q->pos[0],dz=p->pos[2]-q->pos[2];
            float bottom=fmaxf(p->pos[1]+r,q->pos[1]+r),top=fminf(p->pos[1]+bg_body_height(p)-r,q->pos[1]+bg_body_height(q)-r);
            float dy=fmaxf(0,bottom-top),distance=sqrtf(dx*dx+dy*dy+dz*dz);if(distance>=2*r)continue;
            if(dy>0&&p->pos[1]<q->pos[1])dy=-dy;
            float n[3]={distance>1e-5f?dx/distance:1,distance>1e-5f?dy/distance:0,distance>1e-5f?dz/distance:0};
            float penetration=2*r-distance+.001f;bg_player pp=*p,qq=*q;
            for(unsigned k=0;k<3;k++){pp.pos[k]+=n[k]*penetration*.5f;qq.pos[k]-=n[k]*penetration*.5f;}
            bg_move_capsule(&pp,0);bg_move_capsule(&qq,0);
            bool pc=bg_terrain_clearance(&pp),qc=bg_terrain_clearance(&qq);
            if(pc)memcpy(p->pos,pp.pos,12);
            if(qc)memcpy(q->pos,qq.pos,12);
            if(pc!=qc){bg_player*mobile=pc?p:q;bg_player trial=*mobile;for(unsigned k=0;k<3;k++)trial.pos[k]+=n[k]*penetration*.5f*(pc?1:-1);if(bg_terrain_clearance(&trial))memcpy(mobile->pos,trial.pos,12);}
            float relative[3];sub(relative,p->velocity,q->velocity);float into=dot(relative,n);
            if(into<0)for(unsigned k=0;k<3;k++){p->velocity[k]-=n[k]*into*.5f;q->velocity[k]+=n[k]*into*.5f;}
            if(n[1]>=bg_movement.slope[0]){p->grounded=true;memcpy(p->ground_normal,n,12);}
            if(-n[1]>=bg_movement.slope[0]){q->grounded=true;for(unsigned k=0;k<3;k++)q->ground_normal[k]=-n[k];}
            p->vy=p->velocity[1];q->vy=q->velocity[1];
        }
        update_vehicles(inputs,dt);update_projectiles(dt);
    }
}
