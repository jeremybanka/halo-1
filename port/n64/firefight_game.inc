/* Limited-style finite survival. Counts/rules below are versioned demake
 * tuning, not an undocumented claim of byte-for-byte Reach variant parity. */
#include <stdio.h>
bg_ff_state bg_ff;
bg_ff_ship bg_ff_dropship;
#define G BG_PVE_GRUNT
#define E BG_PVE_ELITE
#define J BG_PVE_JACKAL
#define H BG_PVE_HUNTER
#define PP BG_W_PLASMA_PISTOL
#define PR BG_W_PLASMA_RIFLE
#define ND BG_W_NEEDLER
const bg_ff_formation bg_ff_formations[BG_FF_FORMATIONS]={
    {"Elite patrol",5,{E,G,G,G,G},{PR,PP,PP,ND,PP},{0}},
    {"Grunt infantry",5,{G,G,G,G,G},{PP,PP,ND,PP,PP},{0}},
    {"Needler patrol",4,{E,G,G,G},{ND,ND,ND,PP},{0}},
    {"Shield line",4,{J,J,G,G},{PP,PP,PP,ND},{0}},
    {"Mixed patrol",5,{E,J,G,G,G},{PR,PP,PP,ND,PP},{0}},
    {"Elite strike team",4,{E,E,G,G},{PR,ND,PP,PP},{0}},
    {"Hunter pair",2,{H,H},{PR,PR},{0}},
    {"Hunter escort",4,{H,E,J,G},{PR,PR,PP,ND},{0}},
#ifdef BG_PVE_ROSTER
    {"Major patrol",4,{E,G,G,J},{PR,PP,ND,PP},{PVE_R_ELITE_MAJOR_PR,PVE_R_GRUNT_MAJOR_PP,PVE_R_GRUNT_MAJOR_ND,PVE_R_JACKAL_MAJOR}},
    {"Fuel rod team",4,{E,G,G,G},{PR,PP,PP,ND},{PVE_R_ELITE_MAJOR_PR,PVE_R_GRUNT_FUEL,0,0}},
    {"Special operations",4,{E,E,G,G},{PR,ND,ND,PP},{PVE_R_ELITE_SPECOPS_PR,PVE_R_ELITE_SPECOPS_ND,PVE_R_GRUNT_SPECOPS_ND,PVE_R_GRUNT_FUEL}},
    {"Zealot guard",4,{E,E,G,G},{PR,ND,PP,ND},{PVE_R_ZEALOT_PR,PVE_R_ELITE_MAJOR_ND,PVE_R_GRUNT_MAJOR_PP,PVE_R_GRUNT_MAJOR_ND}},
    {"Sword assault",3,{E,E,G},{PR,PR,PP},{PVE_R_ZEALOT_SWORD,PVE_R_ELITE_MAJOR_PR,PVE_R_GRUNT_MAJOR_PP}},
    {"Stealth team",3,{E,E,E},{PR,PR,PR},{PVE_R_STEALTH_PR,PVE_R_STEALTH_MAJOR_PR,PVE_R_STEALTH_SWORD}},
#endif
};
#undef G
#undef E
#undef J
#undef H
#undef PP
#undef PR
#undef ND
/* Authoring anchors are refined onto the collision navigation lattice. Each
 * full formation, including its approach, is validated before allocation. */
typedef struct {const char*name;float x,z,yaw;} ff_zone;
static const ff_zone ff_zones[]={
    {"west rocks",-16,-8,0},{"east rocks",16,9,3.14159265f},
    {"north approach",-5,-23,-1.5707963f},{"south approach",6,24,1.5707963f},
    {"blue base flank",-27,-32,-.7f},{"red base flank",27,32,2.4f}
};
#define FF_ZONES (sizeof(ff_zones)/sizeof(ff_zones[0]))
static float ff_landing[3],ff_arrival_points[8][3];
static unsigned ff_last_zone;
static unsigned ff_alive(void){unsigned n=0;for(unsigned i=0;i<bg_pve_count;i++)n+=bg_pve_actors[i].occupied&&bg_players[BG_PLAYERS+i].health>0;return n;}
static void ff_message(const char*message){snprintf(bg_ff.message,sizeof(bg_ff.message),"%s",message);bg_ff.message_time=4;}
static unsigned ff_random(unsigned n){return n?(unsigned)(blam_real_seed_random_range(&bg_ff.random,0,1)*n)%n:0;}
bool bg_ff_cloud(void){return bg_ff.active&&bg_ff.round>=2;}
float bg_ff_grenade_chance(void){return bg_ff.active&&bg_ff.round>=1?2:1;}
void bg_ff_stop(void){memset(&bg_ff,0,sizeof(bg_ff));memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));}
static bool ff_hidden(const float point[3],float height){
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0){
        const bg_player*p=&bg_players[h];if(distance2(point,p->pos)<100)return false;
        float eye[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]};
        for(unsigned sample=0;sample<5;sample++){
            float target[3]={point[0]+(sample==3?.3f:sample==4?-.3f:0),point[1]+height*(sample%3)*.5f,point[2]},dir[3];sub(dir,target,eye);float length=sqrtf(dot(dir,dir));normalize(dir);
            if(bg_raycast(eye,dir,length)>=length-.03f)return false;
        }
    }
    return true;
}
static bool ff_reachable(int node){
    if(node<0)return false;
    for(unsigned p=0;p<active_players;p++)if(bg_players[p].health>0){if(pve_reachable(node,pve_node(bg_players[p].pos)))return true;}
    return false;
}
static bool ff_clear_point(float point[3],unsigned kind,bool concealed){
    const bg_pve_definition*d=&bg_pve_definitions[kind];bg_player capsule={0};capsule.vehicle=-1;capsule.pve_radius=d->radius;capsule.pve_height=d->height;memcpy(capsule.pos,point,12);
    if(!bg_terrain_clearance(&capsule)||!ff_reachable(pve_node(point)))return false;
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0&&distance2(point,bg_players[h].pos)<(concealed?100:16))return false;
    for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[BG_PLAYERS+i].health>0&&distance2(point,bg_players[BG_PLAYERS+i].pos)<1)return false;
    return !concealed||ff_hidden(point,d->height);
}
static bool ff_zone_points(unsigned zone,unsigned formation,bool concealed,float points[8][3],float landing[3]){
    const ff_zone*z=&ff_zones[zone];const bg_ff_formation*f=&bg_ff_formations[formation];
    /* Search only inside the authored entrance, never teleport a packet to
     * an arbitrary convenient part of the arena. */
    for(unsigned attempt=0;attempt<81;attempt++){
        int ax=(int)(attempt%9)-4,az=(int)(attempt/9)-4;
        float center[3]={z->x+ax,0,z->z+az};center[1]=bg_floor(center[0],center[2],12)+.015f;
        int node=pve_node(center);if(node<0||!ff_reachable(node))continue;pve_node_pos(node,center);
        bool valid=true;
        for(unsigned j=0;j<f->count;j++){
            /* Wide, two-file spacing keeps Hunters and their shields clear. */
            float forward=(j/2)*1.6f,lateral=(j&1?1:-1)*1.6f;
            points[j][0]=center[0]+cosf(z->yaw)*forward+sinf(z->yaw)*lateral;
            points[j][2]=center[2]-sinf(z->yaw)*forward+cosf(z->yaw)*lateral;
            points[j][1]=bg_floor(points[j][0],points[j][2],center[1]+1)+.015f;
            if(fabsf(points[j][1]-center[1])>.5f||!ff_clear_point(points[j],f->kind[j],concealed)){valid=false;break;}
        }
        if(!valid)continue;
        memcpy(landing,center,12);landing[1]+=.7f;
        if(!concealed){
            /* Hull clearance over a flat landing footprint. */
            for(int dx=-5;dx<=5;dx+=2)for(int dz=-3;dz<=3;dz+=2){
                float x=center[0]+cosf(z->yaw)*dx+sinf(z->yaw)*dz,zz=center[2]-sinf(z->yaw)*dx+cosf(z->yaw)*dz;
                float ground=bg_floor(x,zz,100);if(ground>landing[1]||ground<-999)valid=false;
            }
        }
        if(valid)return true;
    }
    return false;
}
static bool ff_recyclable(unsigned i){
    if(!bg_pve_actors[i].occupied)return true;
    if(bg_players[BG_PLAYERS+i].health>0||bg_pve_actors[i].death_time<2)return false;
    for(unsigned j=0;j<BG_MAX_PROJECTILES;j++){const bg_projectile*q=bg_projectile_at(j);if(q&&q->active&&q->owner==(int)(BG_PLAYERS+i))return false;}
    return true;
}
static int ff_free_slot(void){
    int oldest=-1;float age=-1;
    for(unsigned i=0;i<BG_PVE_MAX;i++){
        if(!bg_pve_actors[i].occupied)return i;
        if(ff_recyclable(i)&&bg_pve_actors[i].death_time>age){oldest=i;age=bg_pve_actors[i].death_time;}
    }
    return oldest;
}
static void ff_awaken(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];float best=1e9f;
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0){float dist=distance2(p->pos,bg_players[h].pos);if(dist<best){best=dist;a->target=h;memcpy(a->last_seen,bg_players[h].pos,12);}}
    /* A squad is ordered into the arena. It must still acquire a visible
     * target before firing; the director supplies an initial search goal. */
    a->aware=true;a->decision_time=0;a->notice_time=0;pve_destination(i);
}
static void ff_ship_seat(unsigned j,float out[3]){
    /* Original CD passenger positions, staggered across both bays. */
    static const unsigned seat_index[5]={0,4,2,6,3};
    const float*seat=bg_spirit_seats[seat_index[j]];
    const bg_ff_ship*s=&bg_ff_dropship;float c=cosf(s->yaw),sn=sinf(s->yaw);
    out[0]=s->pos[0]+c*seat[0]+sn*seat[2];out[1]=s->pos[1]+seat[1];out[2]=s->pos[2]-sn*seat[0]+c*seat[2];
}
#ifdef BG_ENEMY_VEHICLES
static int ff_vehicle_for_packet(unsigned packet){
    static const int kinds[]={-1,BG_V_GHOST,BG_V_BANSHEE,BG_V_SHADE,BG_V_WRAITH};
    return packet==0&&bg_ff.phase!=BG_FF_BONUS?kinds[bg_ff.wave]:-1;
}
static bool ff_vehicle_spawn_clear(unsigned kind,const float pos[3],float yaw){
    const bg_hit_mesh*m=&bg_vehicle_hit_meshes[kind];float c=cosf(yaw),sn=sinf(yaw);
    float floor=bg_floor(pos[0],pos[2],pos[1]+1);
    for(unsigned n=0;n<8;n++){
        float x=m->bounds[n&1?3:0]/1024.f,z=m->bounds[n&4?5:2]/1024.f;
        float p[3]={pos[0]+c*x+sn*z,pos[1]+m->bounds[n&2?4:1]/1024.f,pos[2]-sn*x+c*z};
        if(!ff_hidden(p,.2f))return false;
        float ground=bg_floor(p[0],p[2],pos[1]+1);if(ground<-999||fabsf(ground-floor)>.7f)return false;
        float o[3]={pos[0],pos[1]+1,pos[2]},d[3];p[1]=fmaxf(p[1],pos[1]+.8f);sub(d,p,o);float len=sqrtf(dot(d,d));normalize(d);if(bg_raycast(o,d,len)<len-.02f)return false;
    }
    for(unsigned n=0;n<bg_vehicle_count;n++)if(bg_vehicle_body_present(&bg_vehicles[n])&&distance2(pos,bg_vehicles[n].pos)<36)return false;
    return true;
}
static bool ff_vehicle_zone_points(unsigned zone,unsigned formation,unsigned kind){
    const ff_zone*z=&ff_zones[zone];const bg_ff_formation*f=&bg_ff_formations[formation];
    const bg_hit_mesh*m=&bg_vehicle_hit_meshes[kind];float c=cosf(z->yaw),sn=sinf(z->yaw);
    float side=fmaxf(fabsf((float)m->bounds[2]),fabsf((float)m->bounds[5]))/1024.f+.8f;
    for(unsigned attempt=0;attempt<81;attempt++){
        float center[3]={z->x+(int)(attempt%9)-4,0,z->z+(int)(attempt/9)-4};
        center[1]=bg_floor(center[0],center[2],12)+.15f;
        if(!ff_reachable(pve_node(center))||!ff_vehicle_spawn_clear(kind,center,z->yaw))continue;
        memcpy(ff_arrival_points[0],center,12);bool valid=true;
        for(unsigned j=1;j<f->count;j++){
            float forward=((int)((j-1)/2)-1)*1.6f,lateral=(j&1?1:-1)*side;
            float*p=ff_arrival_points[j];p[0]=center[0]+c*forward+sn*lateral;p[2]=center[2]-sn*forward+c*lateral;p[1]=bg_floor(p[0],p[2],center[1]+1)+.015f;
            if(fabsf(p[1]-center[1])>.7f||!ff_clear_point(p,f->kind[j],true)){valid=false;break;}
        }
        if(valid){memcpy(ff_landing,center,12);return true;}
    }
    return false;
}
/* Retired empty encounter hulls may be reclaimed only when their complete
 * bounding sphere is concealed. Never remove a human-owned occupied vehicle. */
static void ff_reclaim_vehicles(void){
    for(unsigned n=0;n<bg_vehicle_count;n++){
        bg_vehicle*v=&bg_vehicles[n];if(!v->encounter_owned||!v->active||v->occupants[0]>=0)continue;
        const bg_hit_mesh*m=&bg_vehicle_hit_meshes[v->kind];bool hidden=true;
        for(unsigned j=0;j<8;j++){float local[3]={m->bounds[j&1?3:0]/1024.f,m->bounds[j&2?4:1]/1024.f,m->bounds[j&4?5:2]/1024.f},world[3];bg_vehicle_transform(v,local,world);if(!ff_hidden(world,.2f)){hidden=false;break;}}
        if(!hidden)continue;
        v->active=false;v->wreck_time=0;
    }
}
#endif
/* Gauntlet keeps the solo encounter schedule at every party size. Promote
 * existing roles through real CE variants, without extra actors or invented
 * vitality scaling. Selection is deterministic; sword/camo/fuel roles persist. */
#ifdef BG_PVE_ROSTER
static unsigned ff_member_variant(const bg_ff_formation*f,unsigned member){
    unsigned variant=f->variant[member];
    if(bg_ff.fight!=BG_FF_GAUNTLET||active_players==1||bg_ff.phase==BG_FF_BONUS)return variant;
    unsigned kind=f->kind[member],weapon=f->weapon[member];
    if(!variant){
        if(kind==BG_PVE_ELITE)variant=weapon==BG_W_NEEDLER?PVE_R_ELITE_MAJOR_ND:PVE_R_ELITE_MAJOR_PR;
        else if(kind==BG_PVE_GRUNT)variant=weapon==BG_W_NEEDLER?PVE_R_GRUNT_MAJOR_ND:PVE_R_GRUNT_MAJOR_PP;
        else if(kind==BG_PVE_JACKAL)variant=PVE_R_JACKAL_MAJOR;
    }
    if(active_players>=3){
        switch(variant){
        case PVE_R_ELITE_MAJOR_PR:variant=PVE_R_ELITE_SPECOPS_PR;break;
        case PVE_R_ELITE_MAJOR_ND:variant=PVE_R_ELITE_SPECOPS_ND;break;
        case PVE_R_GRUNT_MAJOR_ND:variant=PVE_R_GRUNT_SPECOPS_ND;break;
        case PVE_R_STEALTH_PR:variant=PVE_R_STEALTH_MAJOR_PR;break;
        default:break;
        }
    }
    if(active_players==4){
        if(member==0&&variant==PVE_R_ELITE_SPECOPS_PR)variant=PVE_R_ZEALOT_PR;
        /* One fuel rod at most per squad. Retain plasma pistols, Needlers,
         * shields and melee specialists around it rather than uniform heavies. */
        if(variant==PVE_R_GRUNT_MAJOR_PP){
            bool fuel=false;unsigned first=f->count;
            for(unsigned j=0;j<f->count;j++){
                fuel|=f->variant[j]==PVE_R_GRUNT_FUEL;
                if(first==f->count&&f->kind[j]==BG_PVE_GRUNT&&
                   (!f->variant[j]||f->variant[j]==PVE_R_GRUNT_MAJOR_PP)&&f->weapon[j]==BG_W_PLASMA_PISTOL)first=j;
            }
            if(!fuel&&member==first)variant=PVE_R_GRUNT_FUEL;
        }
    }
    return variant;
}
#endif
static bool ff_arrive(unsigned formation,bool spirit){
    if(bg_ff_dropship.phase)return false;
#ifdef BG_ENEMY_VEHICLES
    int vehicle_kind=ff_vehicle_for_packet(bg_ff.packet);if(vehicle_kind>=0)spirit=false;
#endif
    const bg_ff_formation*f=&bg_ff_formations[formation];unsigned live=ff_alive(),free=0,hunters=0;
    for(unsigned i=0;i<BG_PVE_MAX;i++){
        free+=ff_recyclable(i);
        hunters+=bg_pve_actors[i].occupied&&bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].kind==BG_PVE_HUNTER;
    }
    for(unsigned j=0;j<f->count;j++)hunters+=f->kind[j]==BG_PVE_HUNTER;
    if(live+f->count>bg_ff.cap||free<f->count||hunters>2)return false;
    unsigned first=(ff_last_zone+1+ff_random(FF_ZONES-1))%FF_ZONES,chosen=FF_ZONES;
    for(unsigned n=0;n<FF_ZONES;n++){unsigned z=(first+n)%FF_ZONES;
#ifdef BG_ENEMY_VEHICLES
        bool valid=vehicle_kind>=0?ff_vehicle_zone_points(z,formation,vehicle_kind):ff_zone_points(z,formation,!spirit,ff_arrival_points,ff_landing);
#else
        bool valid=ff_zone_points(z,formation,!spirit,ff_arrival_points,ff_landing);
#endif
        if(valid){chosen=z;break;}}
    if(chosen==FF_ZONES){bg_ff.arrival_failures++;return false;}
#ifdef BG_ENEMY_VEHICLES
    int vehicle=-1;
    if(vehicle_kind>=0){ff_reclaim_vehicles();vehicle=bg_add_vehicle(vehicle_kind,ff_arrival_points[0],ff_zones[chosen].yaw);if(vehicle<0)return false;bg_vehicles[vehicle].encounter_owned=true;
        if(bg_vehicle_ai_defs[vehicle_kind].health>0)bg_vehicles[vehicle].health=bg_vehicle_ai_defs[vehicle_kind].health*(100.f/bg_combat_body_max);}
#endif
    ff_last_zone=chosen;
    if(spirit){
        memset(&bg_ff_dropship,0,sizeof(bg_ff_dropship));bg_ff_ship*s=&bg_ff_dropship;s->phase=BG_FF_SHIP_APPROACH;s->zone=chosen;s->formation=formation;s->count=f->count;s->yaw=ff_zones[chosen].yaw;
        memcpy(s->pos,ff_landing,12);s->pos[1]+=80;s->pos[0]-=cosf(s->yaw)*90;s->pos[2]+=sinf(s->yaw)*90;
    }
    for(unsigned j=0;j<f->count;j++){
        int slot=ff_free_slot();assert(slot>=0);float point[3];memcpy(point,ff_arrival_points[j],12);if(spirit)ff_ship_seat(j,point);
        pve_spawn_actor(slot,f->kind[j],f->weapon[j],formation,point,ff_zones[chosen].yaw);
#ifdef BG_PVE_ROSTER
        unsigned variant=ff_member_variant(f,j);if(variant)bg_pve_set_variant(slot,variant);
#endif
        bg_pve_actor*a=&bg_pve_actors[slot];memcpy(a->entry_goal,ff_arrival_points[j],12);
        #ifdef BG_ENEMY_VEHICLES
        if(j==0&&vehicle>=0)pve_vehicle_mount(slot,vehicle,true);
#endif
        if(spirit){a->arrival=1;a->clip=PVE_RIDE;bg_players[BG_PLAYERS+slot].yaw+=j&1?-1.5707963f:1.5707963f;bg_ff_dropship.actors[j]=slot;}else ff_awaken(slot);
    }
    bg_ff.spawned+=f->count;bg_ff.packet++;if(spirit)bg_ff.ship_arrivals++;else bg_ff.ground_arrivals++;
    bg_ff.packet_delay=bg_ff.fight==BG_FF_GAUNTLET||active_players==1?6:4;return true;
}
static void ff_ship_tick(float dt){
    bg_ff_ship*s=&bg_ff_dropship;if(!s->phase)return;s->time+=dt;
    switch(s->phase){
    case BG_FF_SHIP_APPROACH:{
        float t=clamp(s->time/8,0,1),horizontal=clamp(t*2,0,1),vertical=clamp(t*2-1,0,1);horizontal=horizontal*horizontal*(3-2*horizontal);vertical=vertical*vertical*(3-2*vertical);memcpy(s->pos,ff_landing,12);
        s->pos[0]-=cosf(s->yaw)*90*(1-horizontal);s->pos[2]+=sinf(s->yaw)*90*(1-horizontal);s->pos[1]+=80*(1-vertical);
        if(t==1){s->phase=BG_FF_SHIP_OPEN;s->time=0;ff_message("Covenant reinforcements");}break;}
    case BG_FF_SHIP_OPEN:s->door=clamp(s->time/1.5f,0,1);if(s->time>=1.5f){s->phase=BG_FF_SHIP_UNLOAD;s->time=0;}break;
    case BG_FF_SHIP_UNLOAD:{bool done=true;
        for(unsigned j=0;j<s->count;j++){
            unsigned i=s->actors[j];bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
            float elapsed=s->time-j*.55f,duration=bg_pve_definitions[a->kind].exit_duration;
            if(elapsed<0){done=false;continue;}
            if(!s->released[j]){s->released[j]=true;a->arrival=2;a->clip=PVE_EXIT;a->time=0;}
            if(elapsed<duration){float seat[3];ff_ship_seat(j,seat);float t=clamp(elapsed/duration,0,1);for(unsigned k=0;k<3;k++)p->pos[k]=seat[k]+(a->entry_goal[k]-seat[k])*t;p->pos[1]+=.2f*sinf(t*3.14159265f);done=false;}
            else if(a->arrival){memcpy(p->pos,a->entry_goal,12);a->arrival=0;if(p->health>0){a->clip=PVE_IDLE;a->time=0;ff_awaken(i);}else {a->clip=PVE_DEATH;a->time=0;}}
        }
        if(done){s->phase=BG_FF_SHIP_CLOSE;s->time=0;}break;}
    case BG_FF_SHIP_CLOSE:s->door=1-clamp(s->time/1.5f,0,1);if(s->time>=1.5f){s->phase=BG_FF_SHIP_LEAVE;s->time=0;}break;
    case BG_FF_SHIP_LEAVE:{float t=clamp(s->time/8,0,1),vertical=clamp(t*2,0,1),horizontal=clamp(t*2-1,0,1);horizontal=horizontal*horizontal*(3-2*horizontal);vertical=vertical*vertical*(3-2*vertical);memcpy(s->pos,ff_landing,12);s->pos[1]+=80*vertical;s->pos[0]+=cosf(s->yaw)*90*horizontal;s->pos[2]-=sinf(s->yaw)*90*horizontal;if(t==1)s->phase=BG_FF_SHIP_NONE;break;}
    default:break;
    }
    for(unsigned j=0;j<s->count;j++){unsigned i=s->actors[j];if(bg_pve_actors[i].arrival==1)ff_ship_seat(j,bg_players[BG_PLAYERS+i].pos);}
}
static void ff_loadout(unsigned h){
    bg_player*p=&bg_players[h];p->inventory[0]=BG_W_AR;p->inventory[1]=BG_W_PISTOL;p->magazines[0]=60;p->magazines[1]=12;p->reserves[0]=180;p->reserves[1]=60;
    p->weapon=BG_W_AR;p->ammo=60;p->reserve=180;p->grenades[0]=2;p->grenades[1]=2;p->weapon_ready=p->cooldown=0;
}
bool bg_ff_place_human(unsigned h){
    if(!bg_ff.active)return false;
    static const float anchors[][2]={{0,0},{-6,5},{7,-4},{-11,-12},{12,14},{-24,-29},{23,29}};
    float best=-1,position[3]={0};
    for(unsigned n=0;n<sizeof(anchors)/sizeof(anchors[0]);n++){
        float point[3]={anchors[n][0]+(h%2)*1.2f,0,anchors[n][1]+(h/2)*1.2f};point[1]=bg_floor(point[0],point[2],12)+.015f;
        bg_player capsule={0};capsule.vehicle=-1;memcpy(capsule.pos,point,12);if(!bg_terrain_clearance(&capsule)||pve_node(point)<0)continue;
        float nearest=10000;
        for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].arrival!=1){float distance=distance2(point,bg_players[BG_PLAYERS+i].pos);nearest=fminf(nearest,distance);}
        for(unsigned j=0;j<active_players;j++)if(j!=h&&bg_players[j].health>0&&distance2(point,bg_players[j].pos)<.5f)nearest=0;
        if(nearest>=16&&nearest>best){best=nearest;memcpy(position,point,12);}
    }
    if(best<0)return false;
    bg_player*p=&bg_players[h];memcpy(p->pos,position,12);memcpy(p->last_pos,position,12);p->yaw=0;p->pitch=0;ff_loadout(h);return true;
}
bool bg_ff_can_respawn(unsigned p){return bg_ff.active&&p<active_players&&bg_ff.respawn_reserved[p]&&bg_ff.phase!=BG_FF_BONUS;}
void bg_ff_player_died(unsigned p){
    if(!bg_ff.active||p>=active_players)return;
    bg_players[p].respawn=10;bg_ff.sprees[p]=bg_ff.multikills[p]=0;
    if(bg_ff.phase!=BG_FF_BONUS&&!bg_ff.respawn_reserved[p]&&bg_ff.lives){bg_ff.lives--;bg_ff.respawn_reserved[p]=true;}
    unsigned living=0;for(unsigned h=0;h<active_players;h++)living+=bg_players[h].health>0;
    if(living==1&&active_players>1)ff_message("Last Spartan standing");
}
static void ff_resupply(void){
    for(unsigned i=0;i<bg_pickup_count;i++)if(!bg_pickups[i].dropped)refill_pickup(&bg_pickups[i]);
    for(unsigned h=0;h<active_players;h++){
        if(bg_players[h].health<=0){bg_ff.respawn_reserved[h]=true;spawn(h);}else {bg_players[h].health=bg_players[h].shield=100;bg_players[h].grenades[0]=bg_players[h].grenades[1]=2;}
    }
}
static unsigned ff_packet_kind(unsigned packet){
#ifdef BG_ENEMY_VEHICLES
    if(ff_vehicle_for_packet(packet)>=0)return BG_FF_PATROL;
#endif
    if(bg_ff.phase==BG_FF_BONUS)return BG_FF_GRUNTS;
    if(bg_ff.wave==0&&packet==0)return BG_FF_PATROL;
#ifdef BG_PVE_ROSTER
    /* Composition changes, not a larger simultaneous population. Late packets
     * retain all source armaments; no invisible on-screen replacement occurs. */
    if(bg_ff.wave==4){
        if(packet==0)return bg_ff.round?BG_FF_HUNTERS:BG_FF_ZEALOTS;
        static const unsigned bosses[]={BG_FF_SWORDS,BG_FF_ZEALOTS,BG_FF_SPECOPS,BG_FF_HUNTER_ESCORT};
        return bosses[(packet+bg_ff.round-1)%4];
    }
    static const unsigned roster[3][8]={
        {BG_FF_PATROL,BG_FF_GRUNTS,BG_FF_NEEDLERS,BG_FF_SHIELDS,BG_FF_MAJORS,BG_FF_GRUNTS,BG_FF_FUEL,BG_FF_MIXED},
        {BG_FF_MAJORS,BG_FF_FUEL,BG_FF_STEALTH,BG_FF_ELITES,BG_FF_SPECOPS,BG_FF_MIXED,BG_FF_SWORDS,BG_FF_SHIELDS},
        {BG_FF_SPECOPS,BG_FF_ZEALOTS,BG_FF_STEALTH,BG_FF_FUEL,BG_FF_HUNTER_ESCORT,BG_FF_MAJORS,BG_FF_SWORDS,BG_FF_SPECOPS}};
    return roster[bg_ff.round][(bg_ff.wave*2+packet)%8];
#else
    if(bg_ff.wave==4){
        if(bg_ff.round==0)return packet%2?BG_FF_MIXED:BG_FF_ELITES;
        if(packet==0)return BG_FF_HUNTERS;
        return packet%3==1?BG_FF_HUNTER_ESCORT:BG_FF_ELITES;
    }
    static const unsigned sequence[3][8]={{BG_FF_PATROL,BG_FF_GRUNTS,BG_FF_NEEDLERS,BG_FF_SHIELDS,BG_FF_MIXED,BG_FF_GRUNTS,BG_FF_NEEDLERS,BG_FF_PATROL},
        {BG_FF_MIXED,BG_FF_SHIELDS,BG_FF_NEEDLERS,BG_FF_ELITES,BG_FF_PATROL,BG_FF_MIXED,BG_FF_GRUNTS,BG_FF_SHIELDS},
        {BG_FF_ELITES,BG_FF_MIXED,BG_FF_SHIELDS,BG_FF_NEEDLERS,BG_FF_HUNTER_ESCORT,BG_FF_MIXED,BG_FF_ELITES,BG_FF_PATROL}};
    return sequence[bg_ff.round][(bg_ff.wave*2+packet)%8];
#endif
}
static void ff_begin_wave(void){
    bg_ff.phase=BG_FF_WAVE;bg_ff.packet=0;bg_ff.packet_delay=1;bg_ff.spawned=bg_ff.killed=bg_ff.total=0;
    unsigned party=bg_ff.fight==BG_FF_GAUNTLET?1:active_players;
    bg_ff.packets=2+party+bg_ff.round+(bg_ff.wave==3||bg_ff.wave==4);
    for(unsigned p=0;p<bg_ff.packets;p++)bg_ff.total+=bg_ff_formations[ff_packet_kind(p)].count;
    snprintf(bg_ff.message,sizeof(bg_ff.message),"Round %u / %s %u",bg_ff.round+1,bg_ff.wave==4?"Boss wave":"Wave",bg_ff.wave+1);bg_ff.message_time=5;
}
void bg_ff_start(unsigned players){
    bg_ff_start_fight(players,BG_FF_ONSLAUGHT);
}
void bg_ff_start_fight(unsigned players,unsigned fight){
    if(!bg_ff_fight_available(fight))fight=BG_FF_ONSLAUGHT;
    bg_pve_stop();bg_configure_mode(BG_MODE_SLAYER,NULL);bg_set_players(players);bg_reset();bg_pve_start(0);
    bg_ff=(bg_ff_state){.active=true,.phase=BG_FF_READY,.difficulty=2,.cap=fight==BG_FF_GAUNTLET?(active_players==1?6:8):4+2*active_players,.fight=fight,.lives=10,.timer=6,.seed=0x46464c31,.random=0x46464c31};
    ff_last_zone=0;match_winner=-1;bg_set_score_limit(100000000);
    /* Supplies are finite within a round. Power weapons return at recovery. */
    for(unsigned i=0;i<bg_pickup_count;i++)if(!bg_pickups[i].dropped)bg_pickups[i].period=bg_pickups[i].respawn=3600;
    for(unsigned h=0;h<active_players;h++){bg_ff.respawn_reserved[h]=true;spawn(h);}
    snprintf(bg_ff.message,sizeof(bg_ff.message),"%s - Heroic / 10 lives",bg_ff_fight_name(fight));bg_ff.message_time=4;
}
void bg_ff_enemy_killed(unsigned i,int owner,bool headshot,unsigned profile){
    if(!bg_ff.active)return;
    bg_ff.killed++;
    if(owner<0||owner>=(int)active_players)return;
    bg_pve_actor*a=&bg_pve_actors[i];static const unsigned value[]={10,50,20,150};
    unsigned base=value[a->kind],points=base*5/4; /* Heroic 1.25, integer ledger. */
    bool stick=profile==BG_D_STICK;
    if(headshot||stick)points=points*5/4;
    unsigned chain=bg_ff.last_kill[owner]&&bg_ff.tick-bg_ff.last_kill[owner]<=45?bg_ff.multikills[owner]+1:1;
    bg_ff.multikills[owner]=chain;bg_ff.last_kill[owner]=bg_ff.tick;bg_ff.sprees[owner]++;
    if(chain>1)points+=25*(chain>4?4:chain-1);
    if(bg_ff.sprees[owner]%10==0)points+=100;
    bg_ff.score[owner]+=points;bg_ff.team_score+=points;statistics.kills[owner]++;
    if(bg_ff.phase==BG_FF_BONUS)bg_ff.bonus_score+=points;
    for(unsigned h=0;h<active_players;h++)if(h!=(unsigned)owner&&a->contribution[h]>a->contribution[owner]*.4f){unsigned assist=base/4;bg_ff.score[h]+=assist;bg_ff.team_score+=assist;statistics.assists[h]++;}
    for(unsigned h=0;h<active_players;h++)bg_players[h].score=bg_ff.score[h];
    if(chain==2)event(BG_EVENT_DOUBLE_KILL,owner,bg_players[owner].weapon,bg_players[owner].pos,2);
    if(chain>=3)event(BG_EVENT_TRIPLE_KILL,owner,bg_players[owner].weapon,bg_players[owner].pos,chain);
    if(bg_ff.sprees[owner]==10&&chain==1)event(BG_EVENT_KILLING_SPREE,owner,bg_players[owner].weapon,bg_players[owner].pos,10);
}
static void ff_finish(bool won){
    bg_ff.phase=won?BG_FF_WON:BG_FF_LOST;mode_finish(won?0:-2);ff_message(won?"Set complete":"Firefight over");
#if defined(N64) && BG_PVE_QA==6
    debugf("FF_QA_%s players=%u round=%u wave=%u tick=%u score=%u ground=%u ships=%u\n",won?"PASS":"FAIL",active_players,bg_ff.round+1,bg_ff.wave+1,(unsigned)bg_ff.tick,(unsigned)bg_ff.team_score,bg_ff.ground_arrivals,bg_ff.ship_arrivals);
#endif
}
void bg_ff_tick(float dt){
    if(!bg_ff.active)return;
    bg_ff.tick++;bg_ff.elapsed+=dt;bg_ff.message_time=fmaxf(0,bg_ff.message_time-dt);bg_ff.packet_delay=fmaxf(0,bg_ff.packet_delay-dt);
    ff_ship_tick(dt);
    if(bg_ff.phase==BG_FF_READY||bg_ff.phase==BG_FF_RECOVER){bg_ff.timer-=dt;if(bg_ff.timer<=0)ff_begin_wave();return;}
    if(bg_ff.phase!=BG_FF_WAVE&&bg_ff.phase!=BG_FF_BONUS)return;
    if(bg_ff.phase==BG_FF_BONUS)bg_ff.timer-=dt;
    if(bg_ff.packet<bg_ff.packets&&bg_ff.packet_delay<=0){
        unsigned formation=ff_packet_kind(bg_ff.packet);bg_ff.next_formation=formation;
        bool ship=bg_ff.packet==0&&(bg_ff.wave==0||bg_ff.wave==4);
        if(!ff_arrive(formation,ship)&&!ship)ff_arrive(formation,true);
        bg_ff.packet_delay=fmaxf(bg_ff.packet_delay,1);
    }
    /* Re-home a genuinely stranded actor only while its old and new location
     * are concealed. The kill ledger is untouched. */
    for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[BG_PLAYERS+i].health>0&&bg_players[BG_PLAYERS+i].vehicle<0&&!bg_pve_actors[i].arrival){
        bg_pve_actor*a=&bg_pve_actors[i];if(a->stuck_time<20||!ff_hidden(bg_players[BG_PLAYERS+i].pos,bg_pve_definitions[a->kind].height))continue;
        float recovery[8][3],landing[3];
        for(unsigned z=0;z<FF_ZONES;z++)if(ff_zone_points(z,BG_FF_HUNTERS,true,recovery,landing)){
            memcpy(bg_players[BG_PLAYERS+i].pos,recovery[0],12);a->stuck_time=0;ff_awaken(i);bg_ff.stuck_recoveries++;break;
        }
    }
}
void bg_ff_after_tick(float dt){
    (void)dt;if(!bg_ff.active)return;
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0)bg_ff.respawn_reserved[h]=false;
    unsigned living=0,returning=0;for(unsigned h=0;h<active_players;h++){living+=bg_players[h].health>0;returning+=bg_ff_can_respawn(h);}
    if(bg_ff.phase==BG_FF_BONUS){if(bg_ff.timer<=0||!living)ff_finish(true);return;}
    unsigned remaining=ff_alive();
    if(bg_ff.phase==BG_FF_WAVE&&bg_ff.packet==bg_ff.packets&&!bg_ff_dropship.phase&&remaining<=(bg_ff.wave==4?0:1)){
        if(bg_ff.wave<4){bg_ff.wave++;bg_ff.phase=BG_FF_READY;bg_ff.timer=5;ff_message("Wave complete");}
        else {
            /* Clear/recovery wins the same-tick last-death race. */
            bg_ff.lives+=active_players;ff_resupply();living=active_players;
            if(bg_ff.round<2){bg_ff.round++;bg_ff.wave=0;bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=15;ff_message(bg_ff.round==1?"Round complete - Catch":"Round complete - Cloud");}
            else {bg_ff.phase=BG_FF_BONUS;bg_ff.timer=60;bg_ff.packet=0;bg_ff.packets=100;bg_ff.packet_delay=1;ff_message("Bonus round - no respawns");}
        }
    }
    if(!living&&!returning)ff_finish(false);
    else if(bg_ff.elapsed>=1800&&bg_ff.phase!=BG_FF_BONUS)ff_finish(false);
}
void bg_ff_qa_input(void*data){
    bg_input*in=data;memset(in,0,sizeof(bg_input)*4);
#if BG_PVE_QA==6
    for(unsigned h=0;h<active_players;h++){bg_players[h].health=bg_players[h].shield=100;}
    if(bg_ff.phase==BG_FF_READY||bg_ff.phase==BG_FF_RECOVER)bg_ff.timer=fminf(bg_ff.timer,.1f);
    if(bg_ff.tick%90==0)for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[4+i].health>0&&!bg_pve_actors[i].arrival)damage_player_profile(4+i,0,100000,false,false,0,false,false,1);
    if(bg_ff.phase==BG_FF_BONUS&&bg_ff.packet>=1)bg_ff.timer=0;
    return;
#elif BG_PVE_QA==5
    return;
#endif
    for(unsigned h=0;h<active_players;h++){
        bg_player*p=&bg_players[h];if(p->health<=0)continue;int target=-1;float best=1e9f;
        for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].arrival!=1){float dist=distance2(p->pos,bg_players[BG_PLAYERS+i].pos);if(dist<best){target=i;best=dist;}}
        if(target>=0){bg_player*q=&bg_players[BG_PLAYERS+target];float dx=q->pos[0]-p->pos[0],dz=q->pos[2]-p->pos[2];p->yaw=atan2f(-dz,dx);p->pitch=atan2f(q->pos[1]+q->pve_height*.7f-p->pos[1]-bg_eye_height(p),hypotf(dx,dz));in[h].fire=bg_trigger_profiles[p->weapon].automatic||(bg_ff.tick%10==0);in[h].forward=best>36?.5f:0;}
        in[h].reload=p->ammo==0&&p->reload<=0;
    }
}

/* Reproducible native load fixtures. Fixture 3 runs the ordinary game; 4 is a
 * deliberately staged cap-sized mixed fight; 5 photographs a Hunter delivery.
 * Fixtures 3–5 retain production combat. Fixture 6 heals and clears actors
 * solely to exercise the complete native allocation/lifecycle path. */
void bg_ff_qa_stage(unsigned players,unsigned fixture){
    bg_ff_start(players);
    if(fixture==3||fixture==6)return;
    bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
#ifdef BG_ENEMY_VEHICLES
    if(fixture==8||fixture==9){
        for(unsigned h=0;h<active_players;h++){bg_player*p=&bg_players[h];p->pos[0]=-8.f-(h%2)*2.f;p->pos[2]=2+(h/2)*3;p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;p->yaw=0;bg_give_weapon(h,BG_W_ROCKET);}
        static const unsigned kinds[]={BG_V_GHOST,BG_V_BANSHEE,BG_V_WRAITH,BG_V_SHADE};
        unsigned vehicles=fixture==9?1:4;
        for(unsigned n=0;n<vehicles;n++){
            float pos[3]={8+(n%2)*12,0,-12.f+(n/2)*16.f};pos[1]=bg_floor(pos[0],pos[2],12)+.05f;
            int vi=bg_add_vehicle(kinds[n],pos,3.14159265f);assert(vi>=0);bg_vehicles[vi].encounter_owned=true;
            if(kinds[n]==BG_V_BANSHEE)bg_vehicles[vi].pos[1]+=5;
            pve_spawn_actor(n,BG_PVE_ELITE,BG_W_PLASMA_RIFLE,BG_FF_PATROL,pos,3.14159265f);pve_vehicle_mount(n,vi,true);ff_awaken(n);
        }
        for(unsigned n=vehicles;n<bg_ff.cap;n++){float pos[3]={4+(n%3)*1.4f,0,2+(n/3)*1.6f};pos[1]=bg_floor(pos[0],pos[2],12)+.015f;pve_spawn_actor(n,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,BG_FF_PATROL,pos,3.14f);ff_awaken(n);}
        return;
    }
#endif
    if(fixture==4||fixture==7){
        for(unsigned h=0;h<active_players;h++){
            bg_player*p=&bg_players[h];p->pos[0]=-2-(h%2)*1.5f;p->pos[2]=1.5f+(h/2)*1.5f;p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;p->yaw=0;bg_give_weapon(h,BG_W_PISTOL);
        }
        for(unsigned i=0;i<bg_ff.cap;i++){
            unsigned kind=i<2?BG_PVE_HUNTER:i%4==2?BG_PVE_JACKAL:i%4==3?BG_PVE_ELITE:BG_PVE_GRUNT;
            float pos[3]={5+(i%3)*1.4f,0,-2+(i/3)*1.5f};pos[1]=bg_floor(pos[0],pos[2],12)+.015f;
            pve_spawn_actor(i,kind,kind==BG_PVE_GRUNT||kind==BG_PVE_JACKAL?BG_W_PLASMA_PISTOL:BG_W_PLASMA_RIFLE,BG_FF_MIXED,pos,3.14159265f);ff_awaken(i);
#ifdef BG_PVE_ROSTER
            if(fixture==7){
                static const unsigned roster[]={PVE_R_GRUNT_FUEL,PVE_R_ZEALOT_SWORD,PVE_R_JACKAL_MAJOR,PVE_R_ELITE_SPECOPS_PR,PVE_R_STEALTH_SWORD,PVE_R_GRUNT_MAJOR_ND,PVE_R_ZEALOT_PR,PVE_R_GRUNT_SPECOPS_ND,PVE_R_ELITE_MAJOR_PR,PVE_R_STEALTH_MAJOR_PR,PVE_R_GRUNT_FUEL,PVE_R_ELITE_SPECOPS_ND};
                unsigned v=roster[i];pve_spawn_actor(i,bg_pve_variants[v].kind,bg_pve_variants[v].weapon,BG_FF_MIXED,pos,3.14159265f);bg_pve_set_variant(i,v);ff_awaken(i);
            }
#endif
        }
    }else {
        bool arrived=ff_arrive(BG_FF_HUNTER_ESCORT,true);assert(arrived);
        for(unsigned h=0;h<active_players;h++){
            bg_player*p=&bg_players[h];p->pos[0]=ff_landing[0]-10-(h%2);p->pos[2]=ff_landing[2]+8+(h/2);p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;
            p->yaw=atan2f(-(ff_landing[2]-p->pos[2]),ff_landing[0]-p->pos[0]);p->pitch=.08f;
        }
    }
}
