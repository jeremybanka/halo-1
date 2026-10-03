/* Host integration tests against the real locally reduced Blood Gulch mesh. */
#include "game.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static bg_input in[BG_PLAYERS];
static void ticks(unsigned n){for(unsigned i=0;i<n;i++){bg_tick(in,1.f/30);bg_clear_events();}}
static float distance(const float a[3],const float b[3]){float x=a[0]-b[0],y=a[1]-b[1],z=a[2]-b[2];return sqrtf(x*x+y*y+z*z);}
static void reset(void){memset(in,0,sizeof(in));bg_set_players(4);bg_reset();bg_pickup_count=bg_vehicle_count=0;bg_clear_events();}
static void duel(void){reset();bg_players[0].yaw=bg_players[0].pitch=0;
    memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.8f;}
static void equip(bg_weapon weapon){assert(bg_give_weapon(0,weapon));if(bg_players[0].weapon!=(int)weapon){in[0].switch_weapon=true;ticks(1);in[0].switch_weapon=false;}ticks(12);}
static unsigned projectiles(int kind){unsigned n=0;for(unsigned i=0;i<BG_MAX_PROJECTILES;i++)if(bg_projectiles[i].active&&(kind<0||bg_projectiles[i].kind==kind))n++;return n;}
static float brute_ray(const float o[3],const float d[3],float result){
    for(unsigned i=0;i<bg_collision_count;i++){
        const bg_triangle*t=&bg_collision[i];float e[3],f[3],s[3];
        for(int a=0;a<3;a++){e[a]=t->p[1][a]-t->p[0][a];f[a]=t->p[2][a]-t->p[0][a];s[a]=o[a]-t->p[0][a];}
        float h[3]={d[1]*f[2]-d[2]*f[1],d[2]*f[0]-d[0]*f[2],d[0]*f[1]-d[1]*f[0]};
        float det=e[0]*h[0]+e[1]*h[1]+e[2]*h[2];if(fabsf(det)<1e-7f)continue;
        float u=(s[0]*h[0]+s[1]*h[1]+s[2]*h[2])/det;if(u<0||u>1)continue;
        float q[3]={s[1]*e[2]-s[2]*e[1],s[2]*e[0]-s[0]*e[2],s[0]*e[1]-s[1]*e[0]};
        float v=(d[0]*q[0]+d[1]*q[1]+d[2]*q[2])/det;if(v<0||u+v>1)continue;
        float hit=(f[0]*q[0]+f[1]*q[1]+f[2]*q[2])/det;if(hit>.003f&&hit<result)result=hit;
    }return result;
}
int main(void){
    reset();ticks(60);assert(bg_player_count()==4);
    for(unsigned i=0;i<4;i++){
        bg_player*p=&bg_players[i];assert(p->health==100&&p->shield==100&&p->grounded);
        assert(fabsf(p->pos[1]-bg_floor(p->pos[0],p->pos[2],p->pos[1]+.1f)-.015f)<.002f);
        float eye[3]={p->pos[0],p->pos[1]+.62f,p->pos[2]};assert(fabsf(bg_raycast(eye,(float[]){0,-1,0},5)-.635f)<.005f);
    }
    assert(bg_floor(10000,10000,100)==-1000);
    for(int i=0;i<200;i++){
        float o[3]={sinf(i*1.31f)*80,2+(i%25),cosf(i*3.11f)*85};
        float d[3]={cosf(i*.773f),sinf(i*.371f),sinf(i*.773f)},n=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);
        for(int a=0;a<3;a++)d[a]/=n;
        assert(fabsf(bg_raycast(o,d,200)-brute_ray(o,d,200))<.004f);
    }
    bg_player others[3];memcpy(others,&bg_players[1],sizeof(others));float start[3];memcpy(start,bg_players[0].pos,12);
    in[0].forward=1;ticks(10);assert(distance(start,bg_players[0].pos)>.3f);
    for(int i=0;i<3;i++)assert(distance(others[i].pos,bg_players[i+1].pos)<.001f);
    reset();float y=bg_players[0].pos[1];in[0].jump=true;ticks(1);in[0].jump=false;ticks(5);
    assert(bg_players[0].pos[1]>y+.1f);ticks(50);assert(bg_players[0].grounded);
    /* Four independent magazines and two-slot switching. */
    reset();for(int i=0;i<4;i++)in[i].fire=true;ticks(1);
    for(int i=0;i<4;i++)assert(bg_players[i].ammo==59);
    memset(in,0,sizeof(in));in[0].switch_weapon=true;ticks(1);in[0].switch_weapon=false;
    assert(bg_players[0].weapon==BG_W_PISTOL&&bg_players[0].ammo==12&&bg_players[1].weapon==BG_W_AR);
    in[0].switch_weapon=true;ticks(1);in[0].switch_weapon=false;assert(bg_players[0].ammo==59);
    /* Rifle rounds drain shields, kill once and preserve score on respawn. */
    duel();in[0].fire=true;ticks(5);assert(bg_players[1].shield<100&&bg_players[1].health==100);
    ticks(65);assert(bg_players[1].health==0&&bg_players[0].score==1);
    in[0].fire=false;ticks(100);assert(bg_players[1].health==100&&bg_players[1].shield==100);
    /* Finite reserve reload; shotgun reloads one shell at a time. */
    reset();bg_players[0].ammo=30;bg_players[0].reserve=5;in[0].reload=true;ticks(1);in[0].reload=false;ticks(105);
    assert(bg_players[0].ammo==35&&bg_players[0].reserve==0);
    equip(BG_W_SHOTGUN);bg_players[0].ammo=0;in[0].reload=true;ticks(1);in[0].reload=false;ticks(13);
    assert(bg_players[0].ammo==1&&bg_players[0].reload>0);
    /* Each weapon has a distinct bounded path and consumes the correct magazine. */
    for(int w=0;w<BG_WEAPON_COUNT;w++){
        reset();equip(w);int ammo=bg_players[0].ammo;in[0].fire=true;ticks(1);
        if(w==BG_W_PLASMA_PISTOL){in[0].fire=false;ticks(1);}
        assert(bg_players[0].ammo==ammo-1);
    }
    duel();equip(BG_W_PLASMA_PISTOL);in[0].fire=true;ticks(30);in[0].fire=false;ticks(5);
    assert(bg_players[0].ammo==90&&bg_players[1].shield==0&&bg_players[1].health<100);
    duel();equip(BG_W_PISTOL);bg_players[1].shield=0;in[0].fire=true;ticks(1);
    assert(bg_players[1].health==0); /* Unshielded precision headshot. */
    duel();equip(BG_W_PISTOL);
    for(int shot=0;shot<3;shot++){in[0].fire=true;ticks(1);in[0].fire=false;ticks(10);}
    assert(bg_players[1].health==0); /* Retail three-shot pistol headshot. */
    duel();equip(BG_W_SNIPER);in[0].fire=true;ticks(1);assert(bg_players[1].health==0);
    reset();equip(BG_W_SNIPER);in[0].zoom=true;ticks(1);assert(bg_players[0].zoom==1);
    ticks(1);assert(bg_players[0].zoom==2);ticks(1);assert(bg_players[0].zoom==0);in[0].zoom=false;
    reset();equip(BG_W_PLASMA_RIFLE);in[0].fire=true;ticks(150);assert(bg_players[0].overheated);
    in[0].fire=false;ticks(150);assert(!bg_players[0].overheated&&bg_players[0].heat==0);
    /* Needles supercombine, rockets apply radial damage, and melee is gated. */
    duel();equip(BG_W_NEEDLER);in[0].fire=true;ticks(40);assert(bg_players[1].health==0);
    /* A needle that kills on its delayed detonation still credits its owner;
     * the victim's retained owner must be cleared by death and respawn. */
    duel();equip(BG_W_NEEDLER);bg_players[1].shield=0;bg_players[1].shield_delay=6;bg_players[1].health=9;
    in[0].fire=true;ticks(1);in[0].fire=false;ticks(6);
    assert(bg_players[1].health==3&&bg_players[1].needles==1&&bg_players[1].needle_owner==0&&bg_players[0].score==0);
    ticks(40);assert(bg_players[1].health==0&&bg_players[0].score==1&&bg_players[1].needle_owner==-1);
    ticks(100);assert(bg_players[1].health==100&&bg_players[1].needles==0&&bg_players[1].needle_owner==-1);
    duel();equip(BG_W_ROCKET);in[0].fire=true;ticks(5);assert(bg_players[1].health==0);
    duel();in[0].melee=true;ticks(1);in[0].melee=false;assert(bg_players[1].shield<100);
    ticks(22);in[0].melee=true;ticks(1);in[0].melee=false;assert(bg_players[1].health<100);
    /* Sticky plasma grenades follow a living target before their fuse expires. */
    duel();bg_projectile *sticky=&bg_projectiles[0];
    *sticky=(bg_projectile){.active=true,.kind=BG_P_PLASMA_GRENADE,.owner=0,.attached=-1,.life=2.5f,.damage=260,.radius=2.2f};
    memcpy(sticky->pos,bg_players[1].pos,12);sticky->pos[0]-=.3f;sticky->pos[1]+=.4f;sticky->velocity[0]=5;
    ticks(1);assert(sticky->attached==1);in[1].strafe=1;ticks(5);
    for(int a=0;a<3;a++)assert(fabsf(sticky->pos[a]-bg_players[1].pos[a]-sticky->attached_offset[a])<.0001f);
    /* Switching away from a hot plasma rifle cannot reset its heat lock. */
    reset();equip(BG_W_PLASMA_RIFLE);bg_players[0].heat=.9f;bg_players[0].overheated=true;
    in[0].switch_weapon=true;ticks(1);ticks(1);in[0].switch_weapon=false;
    assert(bg_players[0].weapon==BG_W_PLASMA_RIFLE&&bg_players[0].overheated&&bg_players[0].heat>.85f);
    /* Recharging shields do not regenerate health. */
    reset();bg_players[0].health=65;bg_players[0].shield=0;bg_players[0].shield_delay=6;ticks(170);assert(bg_players[0].shield==0);
    ticks(140);assert(bg_players[0].shield==100&&bg_players[0].health==65);
    /* Solid base roof occludes hitscan and accelerated ray traversal. */
    duel();bg_players[0].pitch=atan2f(-1.6f,.8f);bg_players[1].pos[1]-=1.5f;
    in[0].fire=true;ticks(1);assert(bg_players[1].health==100&&bg_players[1].shield==100);
    /* Grenades, bounded projectile pool, fuse expiry and alternate type. */
    reset();in[0].grenade=true;ticks(1);in[0].grenade=false;assert(bg_players[0].grenades[0]==1&&projectiles(BG_P_FRAG)==1);
    ticks(28);in[0].switch_grenade=true;ticks(1);in[0].switch_grenade=false;in[0].grenade=true;ticks(1);in[0].grenade=false;
    assert(bg_players[0].grenades[1]==1&&projectiles(BG_P_PLASMA_GRENADE)==1);ticks(120);assert(projectiles(-1)==0);
    /* Fuse events retain grenade audio identity even after the thrower switches
     * weapon; the identical damage radius must not be used to infer the sound. */
    for(int kind=BG_P_FRAG;kind<=BG_P_PLASMA_GRENADE;kind++){
        reset();equip(BG_W_SNIPER);bg_clear_events();bg_projectile*q=&bg_projectiles[0];
        *q=(bg_projectile){.active=true,.kind=kind,.owner=0,.attached=-2,.life=.001f,.damage=260,.radius=2.2f};
        memcpy(q->pos,bg_players[0].pos,12);q->pos[1]+=6;bg_tick(in,1.f/30);
        unsigned explosions=0;
        for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_EXPLOSION){
            const bg_event*event=&bg_events[e];explosions++;
            assert(event->weapon==(kind==BG_P_PLASMA_GRENADE?BG_EXPLOSION_PLASMA:BG_EXPLOSION_NORMAL));
            assert(event->player==0&&event->amount==2.2f&&distance(event->pos,q->pos)==0);
        }
        assert(explosions==1&&!q->active);
    }
    /* Ghost kind is numerically the same as the plasma presentation enum;
     * vehicle destruction must explicitly emit a normal explosion instead. */
    reset();bg_vehicle_count=1;bg_vehicle*ghost=&bg_vehicles[0];
    *ghost=(bg_vehicle){.active=true,.kind=BG_V_GHOST,.health=1,.occupants={-1,-1,-1}};
    memcpy(ghost->pos,bg_players[0].pos,12);ghost->pos[0]+=4;
    bg_projectile*blast=&bg_projectiles[0];
    *blast=(bg_projectile){.active=true,.kind=BG_P_ROCKET,.owner=0,.attached=-2,.life=.001f,.damage=300,.radius=2.2f};
    memcpy(blast->pos,ghost->pos,12);bg_tick(in,1.f/30);unsigned blast_events=0;
    for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_EXPLOSION){
        assert(bg_events[e].weapon==BG_EXPLOSION_NORMAL);blast_events++;
    }
    assert(blast_events==2&&!ghost->active);
    /* Authentic scenario vehicles offer driver, turret and passenger seats. */
    memset(in,0,sizeof(in));bg_reset();bg_pickup_count=0;bg_vehicle*v=&bg_vehicles[0];assert(bg_vehicle_count==10);
    for(int i=0;i<3;i++){
        memcpy(bg_players[i].pos,v->pos,12);bg_players[i].pos[0]+=.9f;
        in[i].interact=true;ticks(1);in[i].interact=false;assert(bg_players[i].vehicle==0&&bg_players[i].seat==i);
    }
    memcpy(start,v->pos,12);in[0].forward=1;in[1].fire=true;ticks(45);
    assert(distance(start,v->pos)>1&&v->speed>2&&bg_players[1].ammo==60);
    assert(bg_players[0].vehicle==bg_players[1].vehicle&&bg_players[2].vehicle==0);
    in[0].interact=true;ticks(1);in[0].interact=false;assert(bg_players[0].vehicle==-1&&v->occupants[0]==-1);
    /* All four vehicle types move; Banshee can gain altitude. */
    for(int kind=BG_V_GHOST;kind<BG_VEHICLE_COUNT;kind++){
        memset(in,0,sizeof(in));bg_reset();bg_pickup_count=0;
        unsigned j=0;while(j<bg_vehicle_count&&bg_vehicles[j].kind!=kind)j++;assert(j<bg_vehicle_count);v=&bg_vehicles[j];
        memcpy(bg_players[0].pos,v->pos,12);bg_players[0].pos[0]+=.8f;in[0].interact=true;ticks(1);in[0].interact=false;
        assert(bg_players[0].vehicle==(int)j);memcpy(start,v->pos,12);in[0].forward=1;in[0].jump=kind==BG_V_BANSHEE;ticks(45);
        assert(distance(start,v->pos)>.5f);if(kind==BG_V_BANSHEE)assert(v->pos[1]>start[1]+1);
        if(kind==BG_V_SCORPION){
            bg_clear_events();in[0].fire=true;in[0].secondary_fire=true;bg_tick(in,1.f/30);
            bool cannon=false,machine_gun=false;
            for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_FIRE){
                cannon|=bg_events[e].weapon==BG_W_ROCKET;machine_gun|=bg_events[e].weapon==BG_W_AR;}
            assert(cannon&&machine_gun&&v->cooldown>2&&v->secondary_cooldown>0);
            in[0]=(bg_input){.turn=1};float hull_yaw=v->yaw;ticks(10);
            assert(fabsf(v->yaw-hull_yaw)<.0001f&&fabsf(v->turret_yaw)>.3f);
            in[0]=(bg_input){.strafe=1};ticks(10);assert(v->yaw>hull_yaw+.1f);
        }
    }
    /* Inactive players cannot take bullets and are ejected from vehicles. */
    duel();bg_set_players(1);in[0].fire=true;ticks(70);assert(bg_players[1].health==100&&bg_players[1].shield==100);
    /* Pickups respect explicit replacement and respawn. */
    reset();int pickup=bg_add_pickup(BG_W_ROCKET,bg_players[0].pos);in[0].interact=true;ticks(1);in[0].interact=false;
    assert(bg_players[0].weapon==BG_W_ROCKET&&!bg_pickups[pickup].active);ticks(905);assert(bg_pickups[pickup].active);
    /* Both original roof-pad teleporters land at their own scenario exit,
     * turn the player toward its exit direction, and enforce a cooldown. */
    for(unsigned portal=0;portal<bg_teleporter_count;portal++){
        reset();const bg_teleporter*t=&bg_teleporters[portal];memcpy(bg_players[0].pos,t->source,12);
        bg_tick(in,1.f/30);assert(fabsf(bg_players[0].pos[0]-t->destination[0])<.001f&&fabsf(bg_players[0].pos[2]-t->destination[2])<.001f);
        assert(fabsf(bg_players[0].yaw-t->yaw)<.001f&&bg_players[0].teleport_cooldown>0);
        unsigned events=0;for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_TELEPORTER)events++;assert(events==1);
        memcpy(bg_players[0].pos,t->source,12);ticks(1);assert(distance(bg_players[0].pos,t->source)<.3f);
        ticks(32);assert(fabsf(bg_players[0].pos[0]-t->destination[0])<.001f);
        float arrival[3];memcpy(arrival,bg_players[0].pos,12);ticks(90);assert(distance(arrival,bg_players[0].pos)<.001f);
    }
    /* Slayer ends exactly at its score limit, emits one winner event and
     * freezes the world until the ordinary restart operation resets it. */
    duel();equip(BG_W_PISTOL);bg_players[0].score=24;bg_players[1].shield=0;
    assert(bg_score_limit()==25&&!bg_match_finished()&&bg_match_winner()==-1);
    bg_clear_events();for(unsigned e=0;e<BG_MAX_EVENTS;e++)bg_give_weapon(1,BG_W_AR);
    in[0].fire=true;bg_tick(in,1.f/30);
    assert(bg_match_finished()&&bg_match_winner()==0&&bg_players[0].score==25);
    unsigned game_over=0;for(unsigned e=0;e<bg_event_count;e++)if(bg_events[e].kind==BG_EVENT_GAME_OVER){game_over++;assert(bg_events[e].player==0);}
    assert(game_over==1);
    bg_player finished[4];memcpy(finished,bg_players,sizeof(finished));float end_time=bg_match_time();
    in[0].forward=1;ticks(120);assert(memcmp(finished,bg_players,sizeof(finished))==0&&bg_match_time()==end_time);
    bg_reset();assert(!bg_match_finished()&&bg_match_time()==0&&bg_players[0].score==0);
    /* Consecutive real kills announce double/triple kills and a five-kill spree. */
    duel();equip(BG_W_PISTOL);unsigned announcement_mask=0;
    for(unsigned kill=0;kill<5;kill++){
        memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.8f;bg_players[1].shield=0;
        bg_clear_events();in[0].fire=true;bg_tick(in,1.f/30);in[0].fire=false;
        assert(bg_players[1].health==0);
        for(unsigned e=0;e<bg_event_count;e++){
            if(bg_events[e].kind==BG_EVENT_DOUBLE_KILL)announcement_mask|=1;
            if(bg_events[e].kind==BG_EVENT_TRIPLE_KILL)announcement_mask|=2;
            if(bg_events[e].kind==BG_EVENT_KILLING_SPREE)announcement_mask|=4;
        }
        ticks(100);assert(bg_players[1].health==100);
    }
    assert(announcement_mask==7&&bg_players[0].score==5);
    /* Sustained four-controller play cannot overflow pools or leak bad state. */
    reset();uint32_t rng=0xA11CE;
    for(unsigned frame=0;frame<1800;frame++){
        for(unsigned p=0;p<4;p++){
            rng=rng*1664525u+1013904223u;
            if(frame%180==0)bg_give_weapon(p,(frame/180+p)%BG_WEAPON_COUNT);
            in[p]=(bg_input){.forward=.75f,.turn=((int)((rng>>8)%101)-50)/50.f,
                .strafe=((int)((rng>>16)%101)-50)/50.f,.fire=true,
                .jump=(rng&63)==0,.grenade=(rng&255)==0,.reload=(rng&127)==0,.switch_weapon=(rng&511)==0};
        }
        ticks(1);
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];assert(q->ammo>=0&&q->ammo<=bg_weapon_defs[q->weapon].magazine);
            assert(q->health>=0&&q->health<=100&&q->shield>=0&&q->shield<=300);
            for(int a=0;a<3;a++)assert(isfinite(q->pos[a]));
        }
        assert(projectiles(-1)<=BG_MAX_PROJECTILES);
    }
    puts("PASS: 4 players, terrain/rays, movement, weapons, reload, shields, charge, zoom, grenades, 4 vehicle types, seats, pickups, respawn, Slayer completion, kill announcements");
    return 0;
}
