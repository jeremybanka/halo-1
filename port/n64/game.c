#include "blam/vehicle_physics.h"
#include "game.h"
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
    unsigned char bytes[BG_MAX_PROJECTILES*(sizeof(bg_projectile)+6*sizeof(void*))+8*sizeof(void*)+32];
} projectile_arena;
bg_projectile *bg_projectile_at(unsigned slot){return blam_object_at(&projectile_store,slot);}
bg_projectile *bg_projectile_create(void){
    /* _object_type_projectile in the original object_types.h is 5. */
    blam_handle handle=blam_object_new(&projectile_store,sizeof(bg_projectile),5);
    bg_projectile *p=blam_object_get(&projectile_store,handle);
    if(p){p->active=true;p->attached=-1;}return p;
}
bg_pickup bg_pickups[BG_MAX_PICKUPS];
bg_event bg_events[BG_MAX_EVENTS];
unsigned bg_vehicle_count,bg_pickup_count,bg_event_count;
static unsigned spawn_cycle,active_players=4;
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
static void cross(float d[3],const float a[3],const float b[3]){
    d[0]=a[1]*b[2]-a[2]*b[1];d[1]=a[2]*b[0]-a[0]*b[2];d[2]=a[0]*b[1]-a[1]*b[0];
}
static float distance2(const float a[3],const float b[3]){float d[3];sub(d,a,b);return dot(d,d);}
static void normalize(float v[3]){float n=sqrtf(dot(v,v));if(n>1e-8f)for(int i=0;i<3;i++)v[i]/=n;}
static float random_signed(void){return blam_real_seed_random_range(&random_state,-1,1);}
void bg_set_players(unsigned count){active_players=count<1?1:count>4?4:count;}
unsigned bg_player_count(void){return active_players;}
void bg_clear_events(void){bg_event_count=0;}
static void event(bg_event_kind kind,int player,int weapon,const float pos[3],float amount){
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
 * weapon tags. AR/pistol/sniper damage is scaled from retail's 75-point
 * body/shield vitality to the 100-point HUD. Plasma/explosion material response
 * and distance falloff remain simplified in this bounded simulation. */
const bg_weapon_def bg_weapon_defs[BG_WEAPON_COUNT]={
    [BG_W_AR]={"ASSAULT RIFLE",60,240,1.f/15,3.4f,10.f*(100.f/75),.0349066f,40,0,0,1,1,true,false,BG_P_PLASMA},
    [BG_W_PISTOL]={"PISTOL",12,60,1.f/3.5f,2.17f,25.f*(100.f/75),.0034907f,40,0,0,2,1,false,false,BG_P_PLASMA},
    [BG_W_PLASMA_PISTOL]={"PLASMA PISTOL",100,0,.2f,0,14,.014f,50,25,.055f,1,1,false,true,BG_P_PLASMA},
    [BG_W_PLASMA_RIFLE]={"PLASMA RIFLE",100,0,.1f,0,15,.02f,45,50,.045f,1,1,true,true,BG_P_PLASMA},
    [BG_W_NEEDLER]={"NEEDLER",20,80,.1f,1.0f,6,.06981317f,20,4,0,1,1,true,false,BG_P_NEEDLE},
    [BG_W_SHOTGUN]={"SHOTGUN",12,24,1.0f,.4f,12,.1745329f,16,0,0,1,15,false,false,BG_P_PLASMA},
    [BG_W_SNIPER]={"SNIPER RIFLE",4,12,.5f,2.5f,101.f*(100.f/75),.0087266f,150,0,0,10,1,false,false,BG_P_PLASMA},
    [BG_W_ROCKET]={"ROCKET LAUNCHER",2,4,2.0f,5.0f,300,.001f,150,12,0,1,1,false,false,BG_P_ROCKET},
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
        const bg_triangle*t=&bg_collision[bg_grid_indices[c.first+i]];
        const float*a=t->p[0],*b=t->p[1],*d=t->p[2];
        float det=(b[2]-d[2])*(a[0]-d[0])+(d[0]-b[0])*(a[2]-d[2]);
        if(fabsf(det)<1e-8f)continue;
        float u=((b[2]-d[2])*(x-d[0])+(d[0]-b[0])*(z-d[2]))/det;
        float v=((d[2]-a[2])*(x-d[0])+(a[0]-d[0])*(z-d[2]))/det;
        if(u<-.0001f||v<-.0001f||u+v>1.0001f)continue;
        float ab[3],ac[3],n[3];sub(ab,b,a);sub(ac,d,a);cross(n,ab,ac);
        if(n[1]*n[1]<.38f*dot(n,n))continue;
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

static void closest(float q[3],const float p[3],const bg_triangle*t){
    const float*a=t->p[0],*b=t->p[1],*c=t->p[2];
    float ab[3],ac[3],ap[3],bp[3],cp[3];sub(ab,b,a);sub(ac,c,a);sub(ap,p,a);
    float d1=dot(ab,ap),d2=dot(ac,ap);
    if(d1<=0&&d2<=0){memcpy(q,a,12);return;}
    sub(bp,p,b);float d3=dot(ab,bp),d4=dot(ac,bp);
    if(d3>=0&&d4<=d3){memcpy(q,b,12);return;}
    float vc=d1*d4-d3*d2;
    if(vc<=0&&d1>=0&&d3<=0){float v=d1/(d1-d3);for(int i=0;i<3;i++)q[i]=a[i]+v*ab[i];return;}
    sub(cp,p,c);float d5=dot(ab,cp),d6=dot(ac,cp);
    if(d6>=0&&d5<=d6){memcpy(q,c,12);return;}
    float vb=d5*d2-d1*d6;
    if(vb<=0&&d2>=0&&d6<=0){float w=d2/(d2-d6);for(int i=0;i<3;i++)q[i]=a[i]+w*ac[i];return;}
    float va=d3*d6-d5*d4;
    if(va<=0&&d4-d3>=0&&d5-d6>=0){float w=(d4-d3)/((d4-d3)+(d5-d6));for(int i=0;i<3;i++)q[i]=b[i]+w*(c[i]-b[i]);return;}
    float denominator=va+vb+vc;
    if(fabsf(denominator)<1e-10f){memcpy(q,a,12);return;}
    float v=vb/denominator,w=vc/denominator;
    for(int i=0;i<3;i++)q[i]=a[i]+ab[i]*v+ac[i]*w;
}

static void walls(bg_player*p){
    const float radius=.14f;
    for(int iteration=0;iteration<2;iteration++){
        int xmin=(int)floorf((p->pos[0]-radius-bg_grid_origin[0])/bg_grid_size[0]);
        int xmax=(int)floorf((p->pos[0]+radius-bg_grid_origin[0])/bg_grid_size[0]);
        int zmin=(int)floorf((p->pos[2]-radius-bg_grid_origin[1])/bg_grid_size[1]);
        int zmax=(int)floorf((p->pos[2]+radius-bg_grid_origin[1])/bg_grid_size[1]);
        for(int z=zmin;z<=zmax;z++)for(int x=xmin;x<=xmax;x++){
            if(x<0||z<0||x>=BG_GRID||z>=BG_GRID)continue;
            bg_cell c=bg_grid[z*BG_GRID+x];
            for(unsigned i=0;i<c.count;i++){
                const bg_triangle*t=&bg_collision[bg_grid_indices[c.first+i]];
                float ab[3],ac[3],n[3];sub(ab,t->p[1],t->p[0]);sub(ac,t->p[2],t->p[0]);cross(n,ab,ac);
                if(n[1]*n[1]>.38f*dot(n,n))continue;
                for(int sample=0;sample<2;sample++){
                    float point[3]={p->pos[0],p->pos[1]+.19f+sample*.32f,p->pos[2]},q[3];closest(q,point,t);
                    float dx=point[0]-q[0],dy=point[1]-q[1],dz=point[2]-q[2];
                    float d2=dx*dx+dy*dy+dz*dz;
                    if(!(d2<radius*radius))continue;
                    float horizontal=sqrtf(dx*dx+dz*dz);
                    if(horizontal>1e-6f){
                        float amount=(radius-sqrtf(d2))/horizontal;
                        p->pos[0]+=dx*amount;p->pos[2]+=dz*amount;
                    }
                }
            }
        }
    }
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
/* Traverse the terrain grid once per ray and test each triangle at most once.
 * This keeps projectiles bounded even when all four players hold fire. */
static uint16_t ray_visits[8192],ray_stamp;
static float ray_triangle(const float origin[3],const float direction[3],const bg_triangle*t,float nearest){
    float e1[3],e2[3],h[3],s[3],q[3];sub(e1,t->p[1],t->p[0]);sub(e2,t->p[2],t->p[0]);cross(h,direction,e2);
    float det=dot(e1,h);if(fabsf(det)<1e-7f)return nearest;
    sub(s,origin,t->p[0]);float u=dot(s,h)/det;if(u<0||u>1)return nearest;
    cross(q,s,e1);float v=dot(direction,q)/det;if(v<0||u+v>1)return nearest;
    float tval=dot(e2,q)/det;return tval>.003f&&tval<nearest?tval:nearest;
}
float bg_raycast(const float origin[3],const float direction[3],float max_distance){
    if(max_distance<=0)return 0;
    float enter=0,leave=max_distance;
    for(int axis=0;axis<2;axis++){
        int a=axis*2;float lo=bg_grid_origin[axis],hi=lo+BG_GRID*bg_grid_size[axis];
        if(fabsf(direction[a])<1e-8f){if(origin[a]<lo||origin[a]>hi)return max_distance;continue;}
        float t0=(lo-origin[a])/direction[a],t1=(hi-origin[a])/direction[a];
        if(t0>t1){float temp=t0;t0=t1;t1=temp;}
        enter=fmaxf(enter,t0);leave=fminf(leave,t1);
    }
    if(enter>leave)return max_distance;
    if(++ray_stamp==0){memset(ray_visits,0,sizeof(ray_visits));ray_stamp=1;}
    int at[2],step[2];float next[2],delta[2];
    for(int axis=0;axis<2;axis++){
        int a=axis*2;float point=origin[a]+direction[a]*(enter+.00001f);
        at[axis]=(int)floorf((point-bg_grid_origin[axis])/bg_grid_size[axis]);
        if(at[axis]<0)at[axis]=0;
        if(at[axis]>=BG_GRID)at[axis]=BG_GRID-1;
        step[axis]=direction[a]>0?1:-1;
        if(fabsf(direction[a])<1e-8f){next[axis]=delta[axis]=FLT_MAX;}
        else{float edge=bg_grid_origin[axis]+(at[axis]+(step[axis]>0))*bg_grid_size[axis];
            next[axis]=(edge-origin[a])/direction[a];delta[axis]=fabsf(bg_grid_size[axis]/direction[a]);}
    }
    float nearest=max_distance;
    for(int iteration=0;iteration<BG_GRID*2+2;iteration++){
        bg_cell c=bg_grid[at[1]*BG_GRID+at[0]];
        for(unsigned i=0;i<c.count;i++){
            unsigned index=bg_grid_indices[c.first+i];
            if(index<8192){if(ray_visits[index]==ray_stamp)continue;ray_visits[index]=ray_stamp;}
            nearest=ray_triangle(origin,direction,&bg_collision[index],nearest);
        }
        int axis=next[0]<next[1]?0:1;
        if(next[axis]>nearest||next[axis]>leave)break;
        at[axis]+=step[axis];next[axis]+=delta[axis];
        if(at[axis]<0||at[axis]>=BG_GRID)break;
    }
    return nearest;
}
#endif

static void store_inventory(bg_player*p){p->magazines[p->slot]=p->ammo;p->reserves[p->slot]=p->reserve;
    p->heats[p->slot]=p->heat;p->overheated_slots[p->slot]=p->overheated;}
static void select_slot(bg_player*p,int slot){
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
    p->inventory[p->slot]=weapon;p->weapon=weapon;p->ammo=w->magazine;p->reserve=w->reserve;
    p->heat=0;p->charge=0;p->overheated=false;p->reload=0;p->zoom=0;p->cooldown=.35f;
    store_inventory(p);event(BG_EVENT_PICKUP,player,weapon,p->pos,1);return true;
}
static void spawn(unsigned player){
    bg_player*p=&bg_players[player];int score=p->score;
    memset(damage_history[player],0,sizeof(damage_history[player]));
    unsigned start=(spawn_cycle*13+player*5)%bg_spawn_count,index=start;
    for(unsigned i=0;i<bg_spawn_count;i++){
        unsigned j=(start+i)%bg_spawn_count;if(bg_spawns[j].team==(int)(player%2)){index=j;break;}
    }
    memset(p,0,sizeof(*p));p->score=score;p->health=100;p->shield=100;
    p->inventory[0]=BG_W_AR;p->inventory[1]=BG_W_PISTOL;
    for(int j=0;j<2;j++){p->magazines[j]=bg_weapon_defs[p->inventory[j]].magazine;p->reserves[j]=bg_weapon_defs[p->inventory[j]].reserve;}
    p->weapon=BG_W_AR;p->ammo=p->magazines[0];p->reserve=p->reserves[0];p->vehicle=-1;p->seat=-1;p->needle_owner=-1;
    p->grenades[0]=2;p->grenades[1]=2;
    memcpy(p->pos,bg_spawns[index].pos,sizeof(p->pos));
    float floor=bg_floor(p->pos[0],p->pos[2],p->pos[1]+.5f);if(floor>-999)p->pos[1]=floor+.015f;
    memcpy(p->last_pos,p->pos,sizeof(p->pos));p->yaw=bg_spawns[index].yaw;p->grounded=true;
    event(BG_EVENT_RESPAWN,player,p->weapon,p->pos,1);
}
int bg_add_pickup(int weapon,const float pos[3]){
    if(bg_pickup_count>=BG_MAX_PICKUPS)return -1;
    int index=bg_pickup_count++;bg_pickup*p=&bg_pickups[index];memset(p,0,sizeof(*p));
    memcpy(p->pos,pos,sizeof(p->pos));p->weapon=weapon;p->active=true;
    float floor=bg_floor(pos[0],pos[2],pos[1]+.4f);if(floor>-999)p->pos[1]=floor+.12f;
    return index;
}
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
    memset(&statistics,0,sizeof(statistics));memset(damage_history,0,sizeof(damage_history));
    memset(bg_players,0,sizeof(bg_players));memset(bg_vehicles,0,sizeof(bg_vehicles));
    blam_objects_init(&projectile_store,projectile_headers,BG_MAX_PROJECTILES,&projectile_arena,sizeof(projectile_arena));
    memset(bg_pickups,0,sizeof(bg_pickups));
    bg_clear_events();bg_vehicle_count=bg_pickup_count=spawn_cycle=0;random_state=0xCE064;
    match_time=0;match_winner=-1;memset(kill_chain,0,sizeof(kill_chain));memset(kill_spree,0,sizeof(kill_spree));
    for(int i=0;i<BG_PLAYERS;i++)last_kill_time[i]=-10;
    for(int i=0;i<BG_PLAYERS;i++)spawn(i);
    load_scenario();
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
static void eject(unsigned player){
    bg_player*p=&bg_players[player];if(p->vehicle<0)return;bg_vehicle*v=&bg_vehicles[p->vehicle];
    const bg_seat_definition*s=bg_player_seat(p);float offset[3],velocity[3],anchor[3];
    seat_vector(v,s,s->exit_offset,offset);seat_vector(v,s,s->exit_velocity,velocity);
    bg_vehicle_seat_position(v,p->seat,false,anchor);
    for(unsigned a=0;a<3;a++){p->pos[a]=anchor[a]+offset[a];p->velocity[a]=v->velocity[a]+velocity[a];}
    v->occupants[p->seat]=-1;p->vehicle=p->seat=-1;p->seat_state=BG_SEAT_STABLE;p->seat_time=p->seat_blend=0;
    p->vy=p->velocity[1];p->grounded=false;p->interact_cooldown=.5f;
    p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;p->animation=BG_ANIM_IDLE;p->anim_time=0;
    event(BG_EVENT_EXIT,player,v->kind,p->pos,1);
}
static void kill(unsigned victim,int owner){
    bg_player*p=&bg_players[victim];if(p->health<=0)return;
    if(p->vehicle>=0)eject(victim);
    p->weapon_ready=p->use_time=0;p->use_latched=false;p->use_target.kind=BG_USE_NONE;
    p->health=0;p->shield=0;p->respawn=3;p->zoom=0;statistics.deaths[victim]++;
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
static void damage_player(unsigned victim,int owner,float damage,bool plasma,bool headshot){
    bg_player*p=&bg_players[victim];if(bg_match_finished()||p->health<=0||damage<=0)return;
    if(owner>=0&&owner<(int)active_players&&owner!=(int)victim)damage_history[victim][owner]+=damage;
    p->shield_delay=6;p->hurt=.65f;p->zoom=0;p->charge=0;
    float shield_damage=damage*(plasma?1.6f:1);
    if(p->shield>0){float absorb=fminf(p->shield,shield_damage);p->shield-=absorb;damage-=absorb/(plasma?1.6f:1);}
    if(p->shield<.0001f)p->shield=0;
    if(headshot&&p->shield==0)damage=200;
    if(damage>0){p->health-= (int)ceilf(damage);}
    event(BG_EVENT_HURT,victim,p->weapon,p->pos,damage);
    if(p->health<=0){p->health=1;kill(victim,owner);}
}
static void damage_vehicle(unsigned index,int owner,float amount){
    bg_vehicle*v=&bg_vehicles[index];if(bg_match_finished()||!v->active)return;v->health-=(int)amount;
    if(v->health>0)return;
    for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=0)kill(v->occupants[seat],owner);
    v->active=false;v->respawn=20;v->wreck_time=BG_WRECK_LIFE;v->speed=0;
    event(BG_EVENT_VEHICLE_DESTROYED,owner,v->kind,v->pos,(float)index);
}
static void explode(const float pos[3],int owner,float damage,float radius,bg_projectile_kind kind){
    event(BG_EVENT_EXPLOSION,owner,kind==BG_P_NEEDLE?BG_EXPLOSION_NEEDLER:
        kind==BG_P_PLASMA_GRENADE?BG_EXPLOSION_PLASMA:BG_EXPLOSION_NORMAL,pos,radius);
    for(unsigned i=0;i<active_players;i++){
        bg_player*p=&bg_players[i];if(p->health<=0)continue;
        float target[3]={p->pos[0],p->pos[1]+.35f,p->pos[2]},d[3];sub(d,target,pos);float length=sqrtf(dot(d,d));
        if(length>=radius)continue;
        if(length>.05f){for(int a=0;a<3;a++)d[a]/=length;
            if(bg_raycast(pos,d,length)<length-.04f)continue;}
        damage_player(i,owner,damage*(1-length/radius),false,false);p->vy+=2*(1-length/radius);
    }
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active){
        float length=sqrtf(distance2(pos,bg_vehicles[i].pos));if(length<radius+1){bg_vehicle_physics_explosion(i,pos,kind);damage_vehicle(i,owner,damage*(1-length/(radius+1)));}
    }
}
static int target_ray(unsigned owner,const float origin[3],const float dir[3],float *nearest,bool *head){
    int victim=-1;
    for(unsigned j=0;j<active_players;j++){
        bg_player*p=&bg_players[j];if(j==owner||p->health<=0)continue;
        for(int sphere=0;sphere<3;sphere++){
            float center[3]={p->pos[0],p->pos[1]+.18f+sphere*.2f,p->pos[2]},d[3];sub(d,center,origin);
            float t=dot(d,dir),r=sphere==2?.12f:.19f,q=dot(d,d)-t*t;
            if(t<=0||q>r*r)continue;
            t-=sqrtf(fmaxf(0,r*r-q));if(t<*nearest&&t>=0){*nearest=t;victim=j;*head=sphere==2;}
        }
    }
    return victim;
}
static float hitscan(unsigned owner,const float origin[3],const float direction[3],float range,float damage,bool headshots){
    float nearest=range;bool head=false;int victim=target_ray(owner,origin,direction,&nearest,&head),vehicle=-1;
    for(unsigned i=0;i<bg_vehicle_count;i++){
        bg_vehicle*v=&bg_vehicles[i];if(!v->active||bg_players[owner].vehicle==(int)i)continue;
        float center[3]={v->pos[0],v->pos[1]+.35f,v->pos[2]},d[3];sub(d,center,origin);
        float t=dot(d,direction),r=v->kind==BG_V_SCORPION?1.05f:.65f,q=dot(d,d)-t*t;
        if(t>0&&q<r*r){t-=sqrtf(r*r-q);if(t>0&&t<nearest){nearest=t;vehicle=i;victim=-1;}}
    }
    if((victim>=0||vehicle>=0)&&bg_raycast(origin,direction,nearest)>=nearest){
        if(victim>=0)damage_player(victim,owner,damage,false,headshots&&head);else damage_vehicle(vehicle,owner,damage);
        return nearest;
    }
    return range;
}
static bg_projectile* projectile(int kind,unsigned owner,const float origin[3],const float direction[3],float speed,float damage,float radius){
    bg_projectile*q=bg_projectile_create();if(q){
        q->kind=kind;q->owner=owner;
        memcpy(q->pos,origin,sizeof(q->pos));for(int a=0;a<3;a++)q->velocity[a]=direction[a]*speed;
        q->damage=damage;q->radius=radius;q->life=kind==BG_P_FLAME?.7f:kind==BG_P_FRAG?2.5f:kind==BG_P_PLASMA_GRENADE?2.5f:8;
        return q;
    }
    return NULL;
}
static void aim(const bg_player*p,float direction[3],float origin[3]){
    float cp=cosf(p->pitch);direction[0]=cosf(p->yaw)*cp;direction[1]=sinf(p->pitch);direction[2]=-sinf(p->yaw)*cp;
    memcpy(origin,p->pos,12);origin[1]+=p->crouched?.4f:.62f;
    if(p->vehicle>=0&&bg_player_personal_weapon(p))bg_vehicle_camera_position(&bg_vehicles[p->vehicle],p->seat,origin);
}
static void fire(unsigned index,bool charged){
    bg_player*p=&bg_players[index];const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
    p->cooldown=w->interval;p->flash=.08f;p->recoil=.06f;p->ammo-=charged?10:1;if(p->ammo<0)p->ammo=0;
    p->heat+=charged?.65f:w->heat;if(p->heat>=1){p->heat=1;p->overheated=true;}
    p->animation=BG_ANIM_FIRE;p->anim_time=0;
    float direction[3],origin[3];aim(p,direction,origin);
    float spread=w->spread*(p->zoom?.3f:1)*(p->grounded?1:1.5f);
    for(int pellet=0;pellet<w->pellets;pellet++){
        float dir[3];for(int a=0;a<3;a++)dir[a]=direction[a]+random_signed()*spread;normalize(dir);
        if(w->speed>0){
            float start[3];for(int a=0;a<3;a++)start[a]=origin[a]+dir[a]*.15f;
            projectile(w->projectile,index,start,dir,charged?18:w->speed,charged?90:w->damage,w->projectile==BG_P_ROCKET?2.2f:0);
        }else{
            float distance=hitscan(index,origin,dir,w->range,w->damage,p->weapon==BG_W_PISTOL||p->weapon==BG_W_SNIPER);
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
    if(q){p->grenades[p->grenade_kind]--;p->grenade_cooldown=.9f;event(BG_EVENT_GRENADE,index,p->grenade_kind,p->pos,1);}
}
static void update_projectiles(float dt){
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q)continue;
        blam_handle handle=blam_object_handle_at(&projectile_store,i);
        if(!q->active){blam_object_delete(&projectile_store,handle);continue;}q->life-=dt;
        if(q->attached==-2){ /* Static sticky grenade keeps its world position. */ }
        else if(q->attached>=0){
            const float*at=NULL;
            if(q->attached<BG_PLAYERS&&bg_players[q->attached].health>0)at=bg_players[q->attached].pos;
            else if(q->attached>=BG_PLAYERS&&bg_vehicles[q->attached-BG_PLAYERS].active)at=bg_vehicles[q->attached-BG_PLAYERS].pos;
            if(at)for(int a=0;a<3;a++)q->pos[a]=at[a]+q->attached_offset[a];
        }else{
            if(q->kind==BG_P_NEEDLE){
                float forward[3];memcpy(forward,q->velocity,sizeof(forward));normalize(forward);
                int target=-1;float best=.965f;
                for(unsigned j=0;j<active_players;j++)if((int)j!=q->owner&&bg_players[j].health>0){
                    float d[3];sub(d,bg_players[j].pos,q->pos);d[1]+=.4f;
                    if(dot(d,d)>35*35)continue;
                    normalize(d);float alignment=dot(d,forward);
                    if(alignment>best){best=alignment;target=j;}
                }
                if(target>=0){float d[3];sub(d,bg_players[target].pos,q->pos);d[1]+=.4f;normalize(d);
                    for(int a=0;a<3;a++)q->velocity[a]+=(d[a]*4-q->velocity[a])*dt*3;}
            }
            bool grenade_kind=q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE;
            if(grenade_kind)q->velocity[1]-=4.8f*dt;
            float speed=sqrtf(dot(q->velocity,q->velocity)),dir[3];memcpy(dir,q->velocity,sizeof(dir));
            if(speed>1e-8f)for(int a=0;a<3;a++)dir[a]/=speed;
            float length=speed*dt,nearest=length;bool head=false;
            int target=target_ray(q->owner,q->pos,dir,&nearest,&head),vehicle=-1;
            for(unsigned j=0;j<bg_vehicle_count;j++){
                bg_vehicle*v=&bg_vehicles[j];if(!v->active||bg_players[q->owner].vehicle==(int)j)continue;
                float center[3]={v->pos[0],v->pos[1]+.4f,v->pos[2]},d[3];sub(d,center,q->pos);
                float t=dot(d,dir),r=v->kind==BG_V_SCORPION?1.05f:.65f,side=dot(d,d)-t*t;
                if(t>0&&side<r*r){t-=sqrtf(r*r-side);if(t>=0&&t<nearest){nearest=t;target=-1;vehicle=j;}}
            }
            float terrain=bg_raycast(q->pos,dir,length);
            if(terrain<nearest){nearest=terrain;target=vehicle=-1;}
            bool impact=nearest<length;
            for(int a=0;a<3;a++)q->pos[a]+=dir[a]*fmaxf(0,nearest-.006f);
            if(impact){
                if(q->kind==BG_P_FRAG){
                    if(fabsf(dir[1])>.25f){q->velocity[1]=fabsf(q->velocity[1])*.45f;q->velocity[0]*=.65f;q->velocity[2]*=.65f;q->pos[1]+=.025f;}
                    else{q->velocity[0]*=-.45f;q->velocity[2]*=-.45f;q->velocity[1]=.6f;}
                    q->life=fminf(q->life,1.4f);
                }else if(q->kind==BG_P_PLASMA_GRENADE){
                    memset(q->velocity,0,sizeof(q->velocity));q->life=fminf(q->life,1.1f);
                    if(target>=0||vehicle>=0){q->attached=target>=0?target:BG_PLAYERS+vehicle;
                        sub(q->attached_offset,q->pos,target>=0?bg_players[target].pos:bg_vehicles[vehicle].pos);}
                    else q->attached=-2; /* Stuck to static terrain. */
                }else if(q->radius>0){explode(q->pos,q->owner,q->damage,q->radius,q->kind);q->active=false;}
                else{
                    if(target>=0){damage_player(target,q->owner,q->damage,q->kind==BG_P_PLASMA,false);
                        if(q->kind==BG_P_NEEDLE&&bg_players[target].health>0){bg_player*p=&bg_players[target];p->needles++;p->needle_timer=1.2f;p->needle_owner=q->owner;
                            event(BG_EVENT_NEEDLE_HIT,q->owner,BG_W_NEEDLER,p->pos,target);
                            if(p->needles>=7){p->needles=0;p->needle_owner=-1;p->needle_timer=0;float center[3]={p->pos[0],p->pos[1]+.4f,p->pos[2]};event(BG_EVENT_SUPERCOMBINE,q->owner,BG_W_NEEDLER,center,target);explode(center,q->owner,300,1.25f,BG_P_NEEDLE);}}}
                    if(vehicle>=0)damage_vehicle(vehicle,q->owner,q->damage);
                    q->active=false;
                }
            }
        }
        if(q->active&&q->life<=0){if(q->radius>0)explode(q->pos,q->owner,q->damage,q->radius,q->kind);q->active=false;}
        if(q->pos[1]<-10||cell(q->pos[0],q->pos[2])<0)q->active=false;
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
        if(p->inventory[0]==q->weapon||p->inventory[1]==q->weapon)continue;
        float d=distance2(p->pos,q->pos);if(d<nearest){result=(bg_use_target){BG_USE_PICKUP,i,-1};nearest=d;}
    }
    if(result.kind)return result;
    nearest=1.f;
    float center[3]={p->pos[0],p->pos[1]+.35f,p->pos[2]};
    for(unsigned i=0;i<bg_vehicle_count;i++){
        const bg_vehicle*v=&bg_vehicles[i];if(!v->active)continue;
        if(v->physics_valid&&v->up[1]<.70710678f){
            if(v->occupants[0]<0&&distance2(p->pos,v->pos)<4.f)return (bg_use_target){BG_USE_FLIP,i,-1};
            continue;
        }
        for(unsigned seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]<0){
            const bg_seat_definition*s=&bg_seat_definitions[v->kind][seat];
            if((s->flags&512)&&v->occupants[0]<0)continue;
            float entry[3],anchor[3];bg_vehicle_seat_position(v,seat,true,entry);bg_vehicle_seat_position(v,seat,false,anchor);
            float d=fminf(distance2(center,entry),distance2(center,anchor));
            float bias=result.kind==BG_USE_ENTER&&result.seat==0&&seat!=0?2.25f:1.f;
            if(d<1.f&&d*bias<nearest){result=(bg_use_target){BG_USE_ENTER,i,seat};nearest=d;}
        }
    }
    return result;
}
static bool same_target(bg_use_target a,bg_use_target b){return a.kind==b.kind&&a.object==b.object&&a.seat==b.seat;}
static void interact(unsigned player,bg_use_target target){
    bg_player*p=&bg_players[player];
    if(!same_target(target,bg_interaction_target(player)))return;
    if(target.kind==BG_USE_PICKUP){
        bg_pickup*q=&bg_pickups[target.object];bg_give_weapon(player,q->weapon);
        p->weapon_ready=bg_ready_times[p->weapon];p->cooldown=p->weapon_ready;
        q->active=false;q->respawn=30;p->interact_cooldown=.5f;
    }else if(target.kind==BG_USE_FLIP){
        bg_vehicle_physics_flip(target.object,p->pos);p->interact_cooldown=.5f;
    }else if(target.kind==BG_USE_EXIT){
        p->seat_state=BG_SEAT_EXITING;p->seat_time=bg_player_seat(p)->exit_time;p->anim_time=0;
        p->reload=p->charge=p->melee_time=p->zoom=0;
    }else if(target.kind==BG_USE_ENTER){
        bg_vehicle*v=&bg_vehicles[target.object];float anchor[3],start[3];
        p->vehicle=target.object;p->seat=target.seat;v->occupants[p->seat]=player;
        const bg_seat_definition*s=bg_player_seat(p);
        bg_vehicle_seat_position(v,p->seat,false,anchor);seat_vector(v,s,s->enter_start,start);
        for(unsigned a=0;a<3;a++)p->seat_offset[a]=p->pos[a]-anchor[a]-start[a];
        p->seat_state=BG_SEAT_ENTERING;p->seat_time=s->enter_time;p->seat_blend=6.f/30;
        p->zoom=p->reload=p->charge=p->melee_time=0;p->animation=BG_ANIM_DRIVE;p->anim_time=0;p->crouched=false;
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
    if(p->use_time+1e-6f>=BG_USE_HOLD_TICKS/30.f){p->use_latched=true;p->use_time=0;interact(player,target);}
}
static void melee(unsigned index){
    bg_player*p=&bg_players[index];if(p->melee_time>0||p->reload>0)return;
    p->melee_time=.7f;p->animation=BG_ANIM_MELEE;p->anim_time=0;p->cooldown=.6f;
    float dir[3],origin[3];aim(p,dir,origin);hitscan(index,origin,dir,.85f,85,false);
    event(BG_EVENT_MELEE,index,p->weapon,p->pos,1);
}
static void update_vehicles(const bg_input inputs[BG_PLAYERS],float dt){
    bg_vehicle_physics_prepare();
    for(unsigned i=0;i<bg_vehicle_count;i++){
        bg_vehicle*v=&bg_vehicles[i];v->cooldown=fmaxf(0,v->cooldown-dt);v->flash=fmaxf(0,v->flash-dt);v->secondary_cooldown=fmaxf(0,v->secondary_cooldown-dt);
        if(!v->active){
            if(v->wreck_time>0){bg_vehicle_physics_wreck(i);v->wreck_time=fmaxf(0,v->wreck_time-dt);}
            v->respawn-=dt;if(v->respawn<=0){v->active=true;v->wreck_time=0;v->health=v->kind==BG_V_SCORPION?800:400;
            memcpy(v->pos,v->home,sizeof(v->pos));v->yaw=v->home_yaw;v->pitch=0;v->physics_valid=false;memset(v->velocity,0,sizeof(v->velocity));memset(v->angular_velocity,0,sizeof(v->angular_velocity));}continue;}
        for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=(int)active_players)eject(v->occupants[seat]);
        int driver=v->occupants[0];const bg_input*in=driver>=0&&bg_players[driver].seat_state==BG_SEAT_STABLE?&inputs[driver]:NULL;
        if(v->kind==BG_V_SCORPION||v->kind==BG_V_BANSHEE){
            const bg_player*p=driver>=0?&bg_players[driver]:NULL;
            float duration=v->kind==BG_V_SCORPION?16.f/30:22.f/30;
            v->hatch_closing=p&&p->seat_state==BG_SEAT_STABLE;
            v->hatch=!p||p->seat_state==BG_SEAT_ENTERING?1:clamp(p->anim_time/duration,0,1);
        }
        float maxspeed=v->kind==BG_V_SCORPION?3.5f:v->kind==BG_V_BANSHEE?9:v->kind==BG_V_GHOST?7:7.65f;
        bg_vehicle_physics_step(i,in);
        if(v->pos[1]<-8||cell(v->pos[0],v->pos[2])<0){damage_vehicle(i,driver,10000);continue;}
        v->engine_phase+=dt*(1+fabsf(v->speed));
        if(v->engine_phase>12){v->engine_phase-=12;if(driver>=0)event(BG_EVENT_ENGINE,driver,v->kind,v->pos,fabsf(v->speed)/maxspeed);}
        for(unsigned j=0;j<active_players;j++)if(bg_players[j].health>0&&bg_players[j].vehicle<0&&fabsf(v->speed)>2){
            if(distance2(bg_players[j].pos,v->pos)<.8f*.8f)damage_player(j,driver,fabsf(v->speed)*40,false,false);}
        for(int seat=0;seat<bg_seat_counts[v->kind];seat++)if(v->occupants[seat]>=0){
            bg_player*p=&bg_players[v->occupants[seat]];
            if(v->kind==BG_V_WARTHOG&&seat==1)v->turret_yaw=p->yaw-v->yaw;
            bg_vehicle_seat_position(v,seat,false,p->pos);
            if((v->kind==BG_V_SCORPION&&seat==0)||(v->kind==BG_V_WARTHOG&&seat==1)){v->turret_yaw=p->yaw-v->yaw;v->turret_pitch=p->pitch;}
            p->vy=0;p->grounded=true;p->animation=BG_ANIM_DRIVE;
            bool mounted=p->seat_state==BG_SEAT_STABLE&&((v->kind==BG_V_WARTHOG&&seat==1)||(v->kind!=BG_V_WARTHOG&&seat==0));
            const bg_input*control=&inputs[v->occupants[seat]];
            if(mounted&&control->fire&&v->cooldown<=0){
                float dir[3],origin[3];aim(p,dir,origin);for(int a=0;a<3;a++)origin[a]+=dir[a]*1.0f;
                if(v->kind==BG_V_WARTHOG){hitscan(v->occupants[seat],origin,dir,100,14,false);v->cooldown=1.f/15;}
                else{int kind=v->kind==BG_V_SCORPION?BG_P_CANNON:BG_P_PLASMA;
                    projectile(kind,v->occupants[seat],origin,dir,kind==BG_P_CANNON?35:25,kind==BG_P_CANNON?400:18,kind==BG_P_CANNON?2.7f:0);
                    v->cooldown=kind==BG_P_CANNON?3:.1f;}
                v->flash=.08f;p->flash=.08f;event(BG_EVENT_FIRE,v->occupants[seat],v->kind==BG_V_WARTHOG?BG_W_AR:v->kind==BG_V_SCORPION?BG_W_ROCKET:BG_W_PLASMA_RIFLE,v->pos,1);
            }
            if(mounted&&(control->grenade||control->secondary_fire)&&v->secondary_cooldown<=0&&v->kind==BG_V_BANSHEE){
                float dir[3],origin[3];aim(p,dir,origin);for(int a=0;a<3;a++)origin[a]+=dir[a]*1.0f;
                projectile(BG_P_CANNON,v->occupants[seat],origin,dir,12,300,2.2f);v->secondary_cooldown=3;
                event(BG_EVENT_FIRE,v->occupants[seat],BG_W_ROCKET,v->pos,1);
            }
            if(mounted&&(control->grenade||control->secondary_fire)&&v->secondary_cooldown<=0&&v->kind==BG_V_SCORPION){
                float dir[3],origin[3];aim(p,dir,origin);for(int a=0;a<3;a++)origin[a]+=dir[a]*1.0f;
                hitscan(v->occupants[seat],origin,dir,100,10.f*(100.f/75),false);
                v->secondary_cooldown=1.f/15;v->flash=p->flash=.06f;
                event(BG_EVENT_FIRE,v->occupants[seat],BG_W_AR,v->pos,1);
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
static void start_reload(unsigned i){
    bg_player*p=&bg_players[i];const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
    if(p->reload>0||w->energy||p->ammo>=w->magazine||p->reserve<=0)return;
    p->reload=w->reload;p->zoom=0;p->animation=BG_ANIM_RELOAD;p->anim_time=0;
    event(BG_EVENT_RELOAD,i,p->weapon,p->pos,1);
}
static void advance_reload(bg_player*p,const bg_input*in,float dt){
    if(p->reload<=0)return;
    if(p->weapon==BG_W_SHOTGUN&&in->fire&&p->ammo>0){p->reload=0;return;}
    p->reload-=dt;if(p->reload>0)return;
    const bg_weapon_def*w=&bg_weapon_defs[p->weapon];int amount=w->magazine-p->ammo;
    if(p->weapon==BG_W_SHOTGUN)amount=1;
    if(amount>p->reserve)amount=p->reserve;
    p->ammo+=amount;p->reserve-=amount;p->reload=0;
    if(p->weapon==BG_W_SHOTGUN&&p->ammo<w->magazine&&p->reserve>0)p->reload=w->reload;
}
void bg_tick(const bg_input inputs[BG_PLAYERS],float dt){
    dt=clamp(dt,0,1.0f/30);if(dt<=0||bg_match_finished())return;
    match_time+=dt;
    for(unsigned i=0;i<bg_pickup_count;i++)if(!bg_pickups[i].active){
        bg_pickups[i].respawn-=dt;if(bg_pickups[i].respawn<=0)bg_pickups[i].active=true;}
    for(unsigned i=0;i<active_players;i++){
        bg_player*p=&bg_players[i];const bg_input*in=&inputs[i];
        p->cooldown=fmaxf(0,p->cooldown-dt);p->flash=fmaxf(0,p->flash-dt);p->hurt=fmaxf(0,p->hurt-dt);
        p->recoil=fmaxf(0,p->recoil-dt*.3f);p->melee_time=fmaxf(0,p->melee_time-dt);
        p->grenade_cooldown=fmaxf(0,p->grenade_cooldown-dt);p->interact_cooldown=fmaxf(0,p->interact_cooldown-dt);
        p->invisibility=fmaxf(0,p->invisibility-dt);p->teleport_cooldown=fmaxf(0,p->teleport_cooldown-dt);p->anim_time+=dt;
        p->weapon_ready=fmaxf(0,p->weapon_ready-dt);p->seat_blend=fmaxf(0,p->seat_blend-dt);
        if(p->seat_state!=BG_SEAT_STABLE){
            p->seat_time=fmaxf(0,p->seat_time-dt);
            if(p->seat_time<=1e-6f){
                if(p->seat_state==BG_SEAT_EXITING)eject(i);
                else {p->seat_state=BG_SEAT_STABLE;p->anim_time=0;}
            }
        }
        if(p->health<=0){p->respawn-=dt;if(p->respawn<=0){spawn_cycle++;spawn(i);}continue;}
        if(p->needles>0){p->needle_timer-=dt;if(p->needle_timer<=0){
            int needles=p->needles,owner=p->needle_owner;p->needles=0;p->needle_owner=-1;p->needle_timer=0;
            damage_player(i,owner,needles*4,false,false);
            if(p->health<=0)continue;
        }}
        if(p->shield_delay>0)p->shield_delay=fmaxf(0,p->shield_delay-dt);
        else if(p->shield<100){if(p->shield<=0)event(BG_EVENT_SHIELD,i,p->weapon,p->pos,1);p->shield=fminf(100,p->shield+25*dt);}
        if(p->shield>100)p->shield=fmaxf(100,p->shield-dt*1.5f);
        p->heat=fmaxf(0,p->heat-dt*.2f);if(p->overheated&&p->heat<.15f)p->overheated=false;
        int stowed=1-p->slot;p->heats[stowed]=fmaxf(0,p->heats[stowed]-dt*.2f);
        if(p->heats[stowed]<.15f)p->overheated_slots[stowed]=false;
        advance_reload(p,in,dt);
        if(in->switch_weapon&&p->weapon_ready<=0&&bg_player_personal_weapon(p))select_slot(p,1-p->slot);
        if(in->switch_grenade)p->grenade_kind=1-p->grenade_kind;
        if(in->zoom){if(bg_weapon_defs[p->weapon].zoom>1)p->zoom=(p->zoom+1)%(p->weapon==BG_W_SNIPER?3:2);else p->zoom=0;}
        float turn_scale=p->zoom?(p->zoom==2?.15f:.35f):1;
        p->yaw+=in->turn*2.25f*dt*turn_scale;p->pitch=clamp(p->pitch+in->look*1.35f*dt*turn_scale,-1.25f,1.25f);
        update_use(i,in->interact,dt);
        if(p->vehicle<0){
            p->crouched=in->crouch;
            float f=in->forward,s=in->strafe,length=sqrtf(f*f+s*s);if(length>1){f/=length;s/=length;}
            float previous[3];memcpy(previous,p->pos,sizeof(previous));bool was_grounded=p->grounded;
            float speed=p->crouched?1.0f:2.25f;
            p->pos[0]+=(cosf(p->yaw)*f+sinf(p->yaw)*s)*speed*dt;
            p->pos[2]+=(-sinf(p->yaw)*f+cosf(p->yaw)*s)*speed*dt;
            if(in->jump&&p->grounded){p->vy=1.9f;p->grounded=false;event(BG_EVENT_JUMP,i,p->weapon,p->pos,1);}
            p->vy-=4.8f*dt;p->pos[1]+=p->vy*dt;walls(p);
            float floor=bg_floor(p->pos[0],p->pos[2],fmaxf(previous[1],p->pos[1])+.18f);
            if(p->vy<=0&&floor>-999&&p->pos[1]<=floor+.025f){
                if(!was_grounded){event(BG_EVENT_LAND,i,p->weapon,p->pos,-p->vy);if(p->vy<-7)damage_player(i,-1,(-p->vy-7)*15,false,false);}
                p->pos[1]=floor+.015f;p->vy=0;p->grounded=true;
            }else p->grounded=false;
            if(p->pos[1]<-6||cell(p->pos[0],p->pos[2])<0){kill(i,i);continue;}
            for(int a=0;a<3;a++)p->velocity[a]=(p->pos[a]-previous[a])/dt;
            float moving=sqrtf(p->velocity[0]*p->velocity[0]+p->velocity[2]*p->velocity[2]);p->gait+=moving*dt*5;
            bg_animation animation=p->melee_time>0?BG_ANIM_MELEE:p->reload>0?BG_ANIM_RELOAD:p->flash>0?BG_ANIM_FIRE:
                !p->grounded?BG_ANIM_JUMP:moving>.15f?(p->crouched?BG_ANIM_WALK:BG_ANIM_RUN):BG_ANIM_IDLE;
            if(animation!=p->animation){p->animation=animation;p->anim_time=0;}
        }
        bool personal=bg_player_personal_weapon(p)&&p->weapon_ready<=0;
        if(personal){
            if(in->reload&&bg_interaction_target(i).kind<=BG_USE_PICKUP)start_reload(i);
            if(in->grenade)grenade(i);
            if(in->melee)melee(i);
            const bg_weapon_def*w=&bg_weapon_defs[p->weapon];
            bool ready=p->cooldown<=0&&p->reload<=0&&!p->overheated&&p->ammo>0&&p->melee_time<=0;
            if(p->weapon==BG_W_PLASMA_PISTOL){
                if(in->fire&&p->ammo>0&&!p->overheated)p->charge=fminf(1.2f,p->charge+dt);
                if(!in->fire&&p->fire_held&&ready){fire(i,p->charge>=.7f&&p->ammo>=10);p->charge=0;}
            }else if(in->fire&&(w->automatic||!p->fire_held)&&ready)fire(i,false);
            if(in->fire&&p->ammo<=0&&p->cooldown<=0){
                if(p->reserve>0)start_reload(i);else{event(BG_EVENT_EMPTY,i,p->weapon,p->pos,1);p->cooldown=.5f;}}
        }
        p->fire_held=in->fire;teleport(i);memcpy(p->last_pos,p->pos,sizeof(p->pos));
        /* Ammunition, health and grenades are collected by walking over them;
         * replacing a carried weapon always requires the interact button. */
        if(p->vehicle<0)for(unsigned j=0;j<bg_pickup_count;j++){
            bg_pickup*q=&bg_pickups[j];if(!q->active||distance2(p->pos,q->pos)>.38f*.38f)continue;
            bool consume=false;
            if(q->weapon==BG_PICK_HEALTH&&p->health<100){p->health=100;consume=true;}
            if(q->weapon==BG_PICK_FRAG&&p->grenades[0]<4){p->grenades[0]=4;consume=true;}
            if(q->weapon==BG_PICK_PLASMA&&p->grenades[1]<4){p->grenades[1]=4;consume=true;}
            if(q->weapon==BG_PICK_OVERSHIELD){p->shield=300;consume=true;}
            if(q->weapon==BG_PICK_CAMO){p->invisibility=30;consume=true;}
            if(q->weapon<BG_WEAPON_COUNT&&(q->weapon==p->inventory[0]||q->weapon==p->inventory[1])){
                int slot=q->weapon==p->inventory[0]?0:1;
                int reserve=slot==p->slot?p->reserve:p->reserves[slot];
                int ammo=slot==p->slot?p->ammo:p->magazines[slot];
                if(reserve<bg_weapon_defs[q->weapon].reserve||ammo<bg_weapon_defs[q->weapon].magazine){bg_give_weapon(i,q->weapon);consume=true;}}
            if(consume){q->active=false;q->respawn=q->weapon>=BG_PICK_OVERSHIELD?60:30;
                if(q->weapon>=BG_WEAPON_COUNT)event(BG_EVENT_PICKUP,i,q->weapon,p->pos,1);}
        }
    }
    if(!bg_match_finished()){update_vehicles(inputs,dt);update_projectiles(dt);}
}
