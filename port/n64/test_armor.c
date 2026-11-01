/* Exercise the production damage/reload/destruction paths directly, then
 * advance real simulation ticks for recharge, pickups and respawn. */
#include "game.c"
#include "shield_fixture.h"
#include "visr.h"
#include "shields.h"
#include <assert.h>
#include <stdio.h>
static void close_to(float a,float b){assert(fabsf(a-b)<.005f);}
static void setup(unsigned armor){
    for(unsigned p=0;p<4;p++)bg_set_player_armor(p,p==0?armor:BG_ARMOR_SPARTAN);
    shield_fixture_reset();
}
static void shield_tests(void){
    setup(BG_ARMOR_JORGE);bg_player*p=&bg_players[0];
    assert(p->health==100&&p->shield==200&&bg_players[1].shield==100);
    shield_fixture_ticks(60);assert(p->shield==200); /* Never decays as an overshield. */
    p->shield=0;p->shield_delay=6;shield_fixture_ticks(179);assert(p->shield==0);
    shield_fixture_ticks(245);assert(p->shield==200&&!p->shield_charging);
    bg_add_pickup(BG_PICK_OVERSHIELD,p->pos);shield_fixture_ticks(2);assert(p->shield_overcharging);
    bg_pickup_count=0; /* Do not reacquire the respawning pickup during decay. */
    shield_fixture_ticks(62);assert(p->shield>399&&p->shield<=400);
    shield_fixture_ticks(2800);assert(p->shield==200);
    p->health=1;p->shield=0;damage_player_profile(0,1,100,false,false,BG_D_AR,false,false,1);
    assert(p->health==0);shield_fixture_ticks(95);assert(p->armor==BG_ARMOR_JORGE&&p->health==100&&p->shield==200);
    setup(BG_ARMOR_SPARTAN);assert(bg_players[0].shield==100);
}
static void damage_tests(void){
    const unsigned types[]={BG_D_FRAG,BG_D_ROCKET,BG_D_PLASMA_GRENADE,BG_D_SUPERCOMBINE,BG_D_TANK,BG_D_FUEL_ROD};
    for(unsigned c=0;c<4;c++)for(unsigned k=0;k<sizeof(types)/sizeof(*types);k++)for(unsigned shields=0;shields<3;shields++){
        setup(BG_ARMOR_JORGE);bg_player*p=&bg_players[0];bg_player_profiles[0]=c;
        p->health=71;p->shield=100*shields;float expected=p->shield,health=71;
        bg_combat_apply(&bg_damage_profiles[types[k]],160,false,false,false,&expected,&health);
        damage_player_profile(0,1,160,false,false,types[k],false,false,1);
        close_to(p->shield,expected);assert(p->health==71&&bg_match_stats()->deaths[0]==0);
    }
    for(unsigned armor=0;armor<BG_ARMOR_COUNT;armor++){
        setup(armor);bg_player*p=&bg_players[0];p->shield=0;p->health=71;
        float pos[3]={p->pos[0]-.15f,p->pos[1]+.3f,p->pos[2]};
        explode_profile(pos,1,40,2,BG_P_CANNON,BG_D_LEGACY);
        assert((armor==BG_ARMOR_JORGE)==(p->health==71));
        assert(p->velocity[0]!=0||p->velocity[1]!=0);
    }
    const unsigned ordinary[]={BG_D_AR,BG_D_MELEE,BG_D_FALL,BG_D_COLLISION};
    for(unsigned k=0;k<4;k++){
        setup(BG_ARMOR_JORGE);bg_player*p=&bg_players[0];p->shield=0;
        damage_player_profile(0,1,30,false,false,ordinary[k],false,false,1);assert(p->health<100);
    }
    setup(BG_ARMOR_JORGE);damage_player_profile(0,1,40,false,false,BG_D_MELEE,false,true,1);
    assert(bg_players[0].health==0); /* Backstabs remain lethal. */
}
static void ammo_tests(void){
    setup(BG_ARMOR_JORGE);bg_player*p=&bg_players[0];bg_give_weapon(0,BG_W_ROCKET);
    p->ammo=p->reserve=0;p->weapon_ready=0;
    for(unsigned cycle=0;cycle<8;cycle++){
        start_reload(0);assert(p->reload>0&&p->ammo==0);
        bg_input in[4]={0};for(unsigned t=0;t<180;t++)bg_tick(in,1.f/30);
        assert(p->ammo==2&&p->reserve==0&&p->reload==0);p->ammo=0;
    }
    start_reload(0);stop_reload(p);assert(p->ammo==0); /* Early cancellation stays empty. */
    start_reload(0);p->reload=.001f;stop_reload(p);assert(p->ammo==2&&p->reserve==0);
    store_inventory(p);select_slot(p,1-p->slot);assert(!bg_infinite_reserve(p,p->weapon));
    select_slot(p,1-p->slot);assert(bg_infinite_reserve(p,p->weapon));
    p->ammo=0;shield_fixture_ticks(60); /* Finish the normal weapon-ready animation. */
    bg_input in[4]={0};in[0].fire=true;bg_tick(in,1.f/30);assert(p->reload>0);
    setup(BG_ARMOR_SPARTAN);p=&bg_players[0];bg_give_weapon(0,BG_W_ROCKET);p->ammo=p->reserve=0;
    start_reload(0);assert(p->reload==0&&p->ammo==0);
    setup(BG_ARMOR_JORGE);p=&bg_players[0];p->ammo=p->reserve=0;start_reload(0);assert(p->reload==0);
    bg_give_weapon(0,BG_W_ROCKET);p->reserve=0;store_inventory(p);
    int pickup=bg_add_pickup(BG_W_ROCKET,p->pos);int rounds=bg_pickups[pickup].ammo+bg_pickups[pickup].reserve;
    shield_fixture_ticks(1);assert(bg_pickups[pickup].active&&bg_pickups[pickup].ammo+bg_pickups[pickup].reserve==rounds);
    kill(0,1);for(unsigned i=0;i<bg_pickup_count;i++)assert(bg_pickups[i].reserve>=0&&bg_pickups[i].reserve<1000);
}
static void vehicle_tests(void){
    for(unsigned kind=0;kind<BG_VEHICLE_COUNT;kind++)for(unsigned armor=0;armor<BG_ARMOR_COUNT;armor++){
        setup(armor);bg_player*p=&bg_players[0];int id=bg_add_vehicle(kind,p->pos,0);
        bg_vehicle*v=&bg_vehicles[id];v->occupants[0]=0;p->vehicle=id;p->seat=0;
        p->health=71;p->shield=bg_armor_def(p->armor)->shield;
        damage_vehicle(id,1,1000);
        assert(!v->active&&v->occupants[0]==-1&&p->vehicle==-1);
        assert(p->shield==0&&p->health==(armor==BG_ARMOR_JORGE?71:0));
        assert(bg_match_stats()->deaths[0]==(armor!=BG_ARMOR_JORGE));
    }
}
static void odst_tests(void){
    setup(BG_ARMOR_ODST);bg_player*p=&bg_players[0];
    assert(p->armor==BG_ARMOR_ODST&&p->health==100&&p->shield==0);
    assert(bg_shield_sounds(p)==0);shield_fixture_ticks(400);assert(p->shield==0);
    int id=bg_add_pickup(BG_PICK_OVERSHIELD,p->pos);shield_fixture_ticks(2);
    assert(bg_pickups[id].active&&p->shield==0&&!p->shield_overcharging);
    bg_input in[4]={0};in[0].flashlight=true;bg_tick(in,1.f/30);
    assert(bg_visr_active(p)&&!bg_visr_active(&bg_players[1]));
    bg_players[1].invisibility=10;bg_players[1].camo_opacity=0;
    assert(bg_visr_enemy(0,1)&&!bg_visr_enemy(0,0));
    bg_players[2].health=0;assert(!bg_visr_enemy(0,2));
    uint8_t teams[4]={0,0,1,1};bg_configure_mode(BG_MODE_TEAM_SLAYER,teams);
    assert(!bg_visr_enemy(0,1)&&bg_visr_enemy(0,3));
    bg_tick(in,1.f/30);assert(!bg_visr_active(p));
    damage_player_profile(0,3,1000,false,false,BG_D_ROCKET,false,false,1);
    assert(p->health==0&&!bg_visr_active(p));
    shield_fixture_ticks(400);assert(p->health==100&&p->shield==0&&p->armor==BG_ARMOR_ODST&&!p->flashlight_on);
}
int main(void){shield_tests();damage_tests();ammo_tests();vehicle_tests();odst_tests();puts("PASS: armor identity, 200 shield recharge/overshield/respawn, blast-only health resistance, finite magazines/infinite reserve, pickups, switching and all vehicle rider exits");}
