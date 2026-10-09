#include "game.h"
#include "blam/vehicle_physics.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static bg_input input[4];
static void tick(unsigned n){while(n--){bg_clear_events();bg_tick(input,1.f/30);}}
static void reset(void){bg_set_players(4);bg_reset();bg_pickup_count=bg_vehicle_count=0;memset(input,0,sizeof(input));
    for(unsigned i=0;i<4;i++){bg_players[i].pos[0]=i*4;bg_players[i].pos[2]=4;bg_players[i].pos[1]=bg_floor(i*4,4,100)+.015f;}}
static void pickup(void){
    reset();bg_player*p=&bg_players[0];float pos[3]={p->pos[0]+.5f,p->pos[1],p->pos[2]};
    int q=bg_add_pickup(BG_W_SHOTGUN,pos);assert(bg_interaction_target(0).kind==BG_USE_PICKUP);
    input[0].interact=true;tick(6);assert(p->weapon==BG_W_AR&&bg_pickups[q].active);
    input[0].interact=false;tick(1);assert(p->use_time==0);
    input[0].interact=true;tick(6);assert(p->weapon==BG_W_AR);tick(1);
    assert(p->weapon==BG_W_SHOTGUN&&!bg_pickups[q].active&&p->weapon_ready>0);
    int ammo=p->ammo;input[0].fire=input[0].melee=input[0].grenade=input[0].switch_weapon=true;
    tick(1);assert(p->ammo==ammo&&p->weapon==BG_W_SHOTGUN&&p->melee_time==0&&p->grenade_cooldown==0);
    input[0].fire=input[0].melee=input[0].grenade=input[0].switch_weapon=false;
    tick(60);assert(p->weapon_ready==0&&p->use_latched);
    input[0].interact=false;tick(1);assert(!p->use_latched);
    input[0].switch_weapon=true;tick(1);input[0].switch_weapon=false;assert(p->weapon_ready>0);
    tick(60);assert(p->weapon_ready==0);
    /* Two players holding on one gun cannot both acquire it. */
    reset();p=&bg_players[0];memcpy(bg_players[1].pos,p->pos,12);pos[0]=p->pos[0]+.5f;pos[1]=p->pos[1];pos[2]=p->pos[2];
    bg_add_pickup(BG_W_ROCKET,pos);input[0].interact=input[1].interact=true;tick(7);
    assert(p->weapon==BG_W_ROCKET&&bg_players[1].weapon!=BG_W_ROCKET);
    /* Losing the target cancels elapsed use time. */
    reset();p=&bg_players[0];pos[0]=p->pos[0]+.5f;pos[1]=p->pos[1];pos[2]=p->pos[2];q=bg_add_pickup(BG_W_ROCKET,pos);
    input[0].interact=true;tick(6);bg_pickups[q].active=false;bg_pickups[q].respawn=30;tick(1);assert(p->weapon==BG_W_AR&&p->use_time==0);
}
static void seats(void){
    for(unsigned kind=0;kind<4;kind++)for(unsigned seat=0;seat<bg_seat_counts[kind];seat++){
        reset();float pos[3]={0,bg_floor(0,4,100),4};int vi=bg_add_vehicle(kind,pos,0);bg_vehicle*v=&bg_vehicles[vi];
        bg_players[0].pos[2]+=5;tick(45);
        if(kind==BG_V_SCORPION&&seat){v->occupants[0]=1;bg_players[1].vehicle=vi;bg_players[1].seat=0;}
        bg_player*p=&bg_players[0];bg_vehicle_seat_position(v,seat,true,p->pos);p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
        bg_use_target target=bg_interaction_target(0);
        printf("kind %u seat %u -> target %d/%d\n",kind,seat,target.kind,target.seat);
        assert(target.kind==BG_USE_ENTER&&target.seat==(int)seat);
        p->crouched=true;p->crouch_amount=1;
        input[0].interact=true;tick(1);
        assert(p->vehicle==vi&&p->seat==(int)seat&&p->seat_state==BG_SEAT_ENTERING&&v->occupants[seat]==0);
        assert(!p->crouched&&p->crouch_amount==0);
        input[0].fire=input[0].secondary_fire=true;input[0].forward=1;tick(1);assert(v->flash==0&&v->cooldown==0);
        input[0].fire=input[0].secondary_fire=false;input[0].forward=0;
        tick(90);assert(p->seat_state==BG_SEAT_STABLE&&p->vehicle==vi&&p->use_latched);
        assert(bg_interaction_target(0).kind==BG_USE_EXIT);
        bool passenger=!(bg_seat_definitions[kind][seat].flags&12);
        assert(bg_player_personal_weapon(p)==passenger);
        if(passenger){
            int ammo=p->ammo;input[0].fire=true;tick(1);input[0].fire=false;
            assert(p->ammo==ammo-1);
        }
        input[0].interact=false;tick(1);input[0].interact=true;tick(1);
        assert(p->seat_state==BG_SEAT_EXITING&&v->occupants[seat]==0);
        unsigned frames=(unsigned)lroundf(bg_seat_definitions[kind][seat].exit_time*30);
        tick(frames-1);assert(p->vehicle==vi);tick(1);
        assert(p->vehicle==-1&&v->occupants[seat]==-1&&p->weapon_ready>0);
        for(unsigned a=0;a<3;a++)assert(isfinite(p->pos[a]));
    }
    /* A contested single-seat vehicle reserves its occupant before animation. */
    reset();float ghost_pos[3]={0,bg_floor(0,4,100),4};int ghost=bg_add_vehicle(BG_V_GHOST,ghost_pos,0);
    bg_vehicle_seat_position(&bg_vehicles[ghost],0,true,bg_players[0].pos);
    memcpy(bg_players[1].pos,bg_players[0].pos,12);input[0].interact=input[1].interact=true;tick(1);
    assert(bg_players[0].vehicle==ghost&&bg_players[1].vehicle<0&&bg_vehicles[ghost].occupants[0]==0);
    /* Destruction during entry frees the reservation and cannot leave a busy corpse. */
    bg_vehicles[ghost].health=1;bg_projectile*blast=bg_projectile_create();assert(blast);
    *blast=(bg_projectile){.active=true,.kind=BG_P_ROCKET,.owner=3,.attached=-2,.life=.001f,.damage=300,.radius=2.2f};
    memcpy(blast->pos,bg_vehicles[ghost].pos,12);tick(1);
    assert(bg_players[0].health<=0&&bg_players[0].vehicle<0&&bg_players[0].seat_state==BG_SEAT_STABLE&&bg_players[0].weapon_ready==0);
    assert(bg_vehicles[ghost].occupants[0]<0);
    /* Original Scorpion benches require a driver. */
    reset();float pos[3]={0,bg_floor(0,4,100),4};int vi=bg_add_vehicle(BG_V_SCORPION,pos,0);
    bg_vehicle_seat_position(&bg_vehicles[vi],4,true,bg_players[0].pos);
    assert(bg_interaction_target(0).kind!=BG_USE_ENTER);
}
static void flips(void){
    for(unsigned kind=0;kind<4;kind++){
        if(kind==BG_V_SCORPION)continue;
        /* Use an open original-terrain patch. The old decimated patch at
         * (0,4) hid a slope that tips the unpowered Banshee back onto a wing. */
        reset();bg_player*p=&bg_players[0];float pos[3]={-12,bg_floor(-12,5,100)+.5f,5};
        int vi=bg_add_vehicle(kind,pos,0);bg_vehicle*v=&bg_vehicles[vi];
        v->pitch=3.14159265f;bg_vehicle_physics_prepare();
        memcpy(p->pos,v->pos,12);p->pos[2]+=1.2f;
        assert(bg_interaction_target(0).kind==BG_USE_FLIP);
        v->occupants[0]=1;assert(bg_interaction_target(0).kind!=BG_USE_FLIP);v->occupants[0]=-1;
        v->active=false;assert(bg_interaction_target(0).kind!=BG_USE_FLIP);v->active=true;
        input[0].interact=true;tick(1);assert(p->use_latched&&p->vehicle<0);
        assert(bg_interaction_target(0).kind!=BG_USE_FLIP); /* No restart mid-roll. */
        p->pos[0]=-4;p->pos[2]=4;p->pos[1]=bg_floor(-4,4,100)+.015f;p->vy=0;
        float peak=v->up[1];for(unsigned t=1;t<120;t++){tick(1);peak=fmaxf(peak,v->up[1]);}
        assert(p->health>0&&p->use_latched&&p->vehicle<0);
        input[0].interact=false;tick(1);assert(!p->use_latched);
        printf("Flip kind %u: upright peak %.3f, settled up %.3f\n",kind,peak,v->up[1]);
        assert(peak>.9f&&v->up[1]>BG_VEHICLE_FLIP_MAX_UP&&!v->flipping);
        bg_vehicle_seat_position(v,0,true,p->pos);assert(bg_interaction_target(0).kind==BG_USE_ENTER);
        /* A tilted but not flipped chassis must not offer an ineffective flip. */
        v->up[1]=.71f;assert(bg_interaction_target(0).kind!=BG_USE_FLIP);
        memcpy(p->pos,v->pos,12);v->up[1]=.5f;assert(bg_interaction_target(0).kind==BG_USE_FLIP);
        p->pos[0]+=10;assert(bg_interaction_target(0).kind!=BG_USE_FLIP);
    }
}
static void rollover(void){
    reset();float pos[3]={-12,bg_floor(-12,5,100)+1,5};
    int vi=bg_add_vehicle(BG_V_WARTHOG,pos,0);bg_vehicle*v=&bg_vehicles[vi];
    for(unsigned seat=0;seat<3;seat++){
        v->occupants[seat]=seat;bg_players[seat].vehicle=vi;bg_players[seat].seat=seat;
        bg_players[seat].seat_state=BG_SEAT_STABLE;
    }
    /* A momentary tilt recovers without ejecting anyone. */
    for(unsigned t=0;t<4;t++){v->pitch=3.14159265f;v->physics_valid=false;tick(1);}
    assert(v->overturned_ticks==4&&bg_players[0].vehicle==vi);
    v->pitch=0;v->physics_valid=false;tick(1);
    assert(v->overturned_ticks==0&&bg_players[0].vehicle==vi);
    /* Sustained rollover releases driver, gunner and passenger together. */
    for(unsigned t=0;t<6;t++){v->pitch=3.14159265f;v->physics_valid=false;tick(1);}
    unsigned exits=0;for(unsigned e=0;e<bg_event_count;e++)exits+=bg_events[e].kind==BG_EVENT_EXIT;
    assert(exits==3);
    for(unsigned seat=0;seat<3;seat++){
        bg_player*p=&bg_players[seat];assert(p->vehicle<0&&v->occupants[seat]<0);
        assert(p->health>0&&p->seat_state==BG_SEAT_STABLE&&p->weapon_ready>0);
        float floor=bg_floor(p->pos[0],p->pos[2],p->pos[1]+.8f);
        assert(p->pos[1]>=floor&&p->vy>=0&&p->interact_cooldown>0);
        assert(p->exit_grace>0&&p->exit_vehicle==vi);
    }
}
int main(void){pickup();seats();flips();rollover();puts("PASS: weapon holds, immediate seat use, Warthog/Ghost/Banshee flips, contention, ready locks and reservations");}
