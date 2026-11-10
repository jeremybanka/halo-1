#include <stdio.h>
#include "game.c"

static void player_warthog(unsigned humans,unsigned fight){
    bg_ff_start_fight(humans,fight);
    assert(bg_ff.fight==fight&&bg_vehicle_count==1);
    bg_vehicle*v=&bg_vehicles[0];
    assert(v->active&&v->kind==BG_V_WARTHOG&&!v->encounter_owned&&bg_seat_counts[v->kind]==3);
    for(unsigned seat=0;seat<BG_VEHICLE_SEATS;seat++)assert(v->occupants[seat]==-1);
    for(unsigned h=0;h<humans;h++)assert(!bg_vehicle_contacts_player(v,&bg_players[h])&&distance2(v->pos,bg_players[h].pos)<100);
    bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
    bg_input input[BG_UNITS]={0};
    for(unsigned t=0;t<90;t++)update_vehicles(input,1.f/30);
    assert(v->active&&v->physics_valid&&v->up[1]>.9f&&distance2(v->pos,v->home)<4);
    /* Each source entry is reachable on the actual Blood Gulch terrain. */
    for(unsigned seat=0;seat<3;seat++){
        bg_player*p=&bg_players[0];
        bg_vehicle_seat_position(v,seat,true,p->pos);p->pos[1]=bg_floor(p->pos[0],p->pos[2],12)+.015f;
        assert(bg_terrain_clearance(p));
        bg_use_target target=bg_interaction_target(0);
        if(target.kind!=BG_USE_ENTER||target.object!=0||target.seat!=(int)seat)fprintf(stderr,"%s %uP seat %u prompt %d/%d/%d hull %.2f %.2f %.2f\n",bg_ff_fight_name(fight),humans,seat,target.kind,target.object,target.seat,v->pos[0],v->pos[1],v->pos[2]);
        assert(target.kind==BG_USE_ENTER&&target.object==0&&target.seat==(int)seat);
        interact(0,target);assert(p->vehicle==0&&p->seat==(int)seat&&v->occupants[seat]==0);
        for(unsigned t=0;t<90;t++)bg_tick(input,1.f/30);
        assert(p->seat_state==BG_SEAT_STABLE&&p->vehicle==0);
        if(seat==1){bg_clear_events();input[0].fire=true;bg_tick(input,1.f/30);input[0].fire=false;assert(v->flash>0&&bg_event_count>0);}
        assert(eject(0,false)&&p->vehicle<0&&v->occupants[seat]<0);
        for(unsigned t=0;t<30;t++)bg_tick(input,1.f/30);
    }
    /* Parking on a human anchor must not spawn a player inside the hull. */
    memcpy(v->pos,(float[]){0,bg_floor(0,0,12)+.02f,0},12);v->physics_valid=false;
    bg_vehicle_physics_prepare();
    assert(bg_ff_place_human(0)&&!bg_vehicle_contacts_player(v,&bg_players[0]));
#ifdef BG_ENEMY_VEHICLES
    ff_reclaim_vehicles();assert(v->active);
    /* Enemy allocation must preserve a destroyed player's reserved slot. */
#endif
    damage_vehicle(0,-1,100000);assert(!v->active&&v->respawn==20);
#ifdef BG_ENEMY_VEHICLES
    int enemy=bg_add_vehicle(BG_V_GHOST,(float[]){-16,bg_floor(-16,-8,12),-8},0);
    assert(enemy>0);bg_vehicles[enemy].encounter_owned=true;
    for(unsigned i=0;i<3;i++){bg_vehicles[enemy].active=false;bg_vehicles[enemy].wreck_time=0;enemy=bg_add_vehicle(BG_V_GHOST,(float[]){-16,bg_floor(-16,-8,12),-8},0);assert(enemy>0);bg_vehicles[enemy].encounter_owned=true;}
#endif
    for(unsigned t=0;t<601;t++)update_vehicles(input,1.f/30);
    assert(v->active&&v->health==400&&distance2(v->pos,v->home)<.1f);
    bg_reset();assert(bg_ff.fight==fight&&bg_vehicle_count==1&&bg_vehicles[0].active&&bg_vehicles[0].kind==BG_V_WARTHOG);
    printf("PASS %s %uP Warthog: spawn clearance, stable hull, three seats, turret, respawn, ownership and restart\n",bg_ff_fight_name(fight),humans);
}
int main(void){
    assert(bg_map_load(BG_MAP_BLOOD_GULCH));
    for(unsigned fight=0;fight<BG_FF_FIGHTS;fight++)if(bg_ff_fight_available(fight))
        for(unsigned humans=1;humans<=4;humans++)player_warthog(humans,fight);
    bg_ff_qa_stage(4,3);assert(bg_vehicle_count==1&&bg_vehicles[0].kind==BG_V_WARTHOG);
    bg_ff_qa_stage(4,6);assert(bg_vehicle_count==1&&bg_vehicles[0].kind==BG_V_WARTHOG);
#ifdef BG_ENEMY_VEHICLES
    bg_ff_qa_stage(4,8);assert(bg_vehicle_count==4&&bg_vehicles[0].kind==BG_V_GHOST);
#endif
    bg_pve_stop();bg_configure_mode(BG_MODE_SLAYER,NULL);bg_reset();
    assert(!bg_ff.active&&bg_vehicle_count==bg_map_vehicle_count);
    puts("PASS ordinary Firefight fixtures include transport; isolated enemy fixtures and multiplayer retain their vehicles");
}
