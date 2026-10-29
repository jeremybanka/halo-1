#include <stdio.h>
#include <stdlib.h>
#include "game.c"
static void advance(unsigned ticks){bg_input input[4]={0};for(unsigned i=0;i<ticks;i++)bg_tick(input,1.f/30);}
static void threshold_tests(void){
    float still[3]={0};unsigned checked=0;
    for(unsigned axis=0;axis<3;axis++)for(int side=-1;side<=1;side+=2){
        float threshold=.06666667f*30;
        for(int n=-3;n<=3;n++){
            float v=threshold;for(int s=0;s<abs(n);s++)v=nextafterf(v,n<0?0:INFINITY);
            float velocity[3]={0},body[3]={0};velocity[axis]=body[axis]=side*v;
            bool original=fabsf(velocity[axis]/30.f)>.06666667f;
            assert(bg_vehicle_contact_damage(velocity,body,false,0)==original);
            assert(!bg_vehicle_contact_damage(velocity,body,true,90));
            assert(bg_vehicle_contact_damage(velocity,body,true,91)==original);checked++;
        }
        float threshold_relative=sqrtf(.0011111111f)*30;
        for(int n=-3;n<=3;n++){
            float speed=threshold_relative;for(int s=0;s<abs(n);s++)speed=nextafterf(speed,n<0?0:INFINITY);
            float body[3]={0};body[axis]=side*speed;float r=body[axis]/30.f;
            assert(bg_vehicle_contact_damage(still,body,false,0)==(r*r>.0011111111f));checked++;
        }
    }
    printf("native contact thresholds/grace: %u boundaries passed\n",checked);
}
static bool entry_position(unsigned vehicle){
    bg_vehicle*v=&bg_vehicles[vehicle];bg_player*p=&bg_players[0];
    for(int y=0;y<24;y++)for(int x=-20;x<=20;x++)for(int z=-20;z<=20;z++){
        p->pos[0]=v->pos[0]+x*.2f;p->pos[1]=v->pos[1]+y*.15f;p->pos[2]=v->pos[2]+z*.2f;
        if(!bg_terrain_clearance(p)||bg_vehicle_contacts_player(v,p))continue;
        bg_use_target t=bg_interaction_target(0);if(t.kind==BG_USE_ENTER&&t.object==(int)vehicle)return true;
    }
    return false;
}
static void available_seat_tests(void){
    for(unsigned kind_index=0;kind_index<4;kind_index++){
        bg_ff_qa_stage(2,8);bg_pickup_count=0;
        bg_player*p=&bg_players[0];bg_vehicle*v=&bg_vehicles[kind_index];unsigned pilot=v->occupants[0];
        assert(eject(pilot,true));assert(entry_position(kind_index));
        bg_use_target vacant=bg_interaction_target(0);float approach[3];memcpy(approach,p->pos,12);
        /* A seat claimed after the prompt was selected cannot be stolen. */
        pve_vehicle_mount(pilot-BG_PLAYERS,kind_index,true);
        interact(0,vacant);assert(p->vehicle<0&&v->occupants[0]==(int)pilot);
        float health=bg_players[pilot].health;
        for(unsigned t=0;t<60;t++)update_use(0,true,1.f/30);
        assert(p->vehicle<0&&v->occupants[0]==(int)pilot&&bg_players[pilot].health==health);
        assert(bg_interaction_target(0).kind==BG_USE_NONE);
        /* Killing the pilot frees the seat; Use starts source entry immediately. */
        kill(pilot,0);assert(v->active&&v->occupants[0]<0);
        bg_pickup_count=0; /* Isolate the seat from the dropped weapon prompt. */
        assert(same_target(vacant,bg_interaction_target(0)));
        update_use(0,false,1.f/30);update_use(0,true,1.f/30);
        assert(p->vehicle==(int)kind_index&&v->occupants[0]==0&&p->seat_state==BG_SEAT_ENTERING);
        assert(p->seat_time==bg_player_seat(p)->enter_time);
        memcpy(bg_players[1].pos,approach,12);
        for(unsigned t=0;t<60;t++)update_use(1,true,1.f/30);
        assert(bg_players[1].vehicle<0&&v->occupants[0]==0);
        assert(eject(0,false));assert(v->occupants[0]<0);
        assert(!bg_vehicle_contacts_player(v,p));
        printf("available-seat kind=%d: NPC/human occupancy respected, stale target rejected, pilot-death entry and safe exit passed\n",v->kind);
    }
}
static void autonomous_entry_tests(void){
    for(unsigned n=0;n<4;n++){
        bg_ff_qa_stage(1,8);assert(eject(4+n,true));bg_pve_actor*a=&bg_pve_actors[n];bg_player*p=&bg_players[4+n];bg_vehicle*v=&bg_vehicles[n];
        a->desired_vehicle=n;a->vehicle_cooldown=0;a->vehicle_timer=0;
        bg_vehicle_transform(v,bg_enemy_vehicle_seats[v->kind].entry,p->pos);
        assert(pve_vehicle_approach(n,1.f/30));assert(p->vehicle==(int)n&&p->seat_state==BG_SEAT_ENTERING);
        unsigned ticks=(unsigned)ceilf(bg_player_seat(p)->enter_time*30)+2;
        for(unsigned t=0;t<ticks;t++)bg_pve_tick(1.f/30);
        assert(p->seat_state==BG_SEAT_STABLE&&v->occupants[0]==(int)(4+n));
    }
    puts("autonomous empty-seat entry/source durations passed");
}
static void contact_integration_tests(void){
    for(unsigned victim_kind=0;victim_kind<5;victim_kind++)for(unsigned fast=0;fast<2;fast++){
        bg_ff_start(2);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=999;bg_vehicle_count=0;bg_pickup_count=0;
        float at[3]={0,bg_floor(0,0,12)+.15f,0};int v=bg_add_vehicle(BG_V_GHOST,at,0);assert(v==0);
        bg_vehicle*h=&bg_vehicles[v];bg_input in[BG_UNITS]={0};
        unsigned victim=victim_kind==4?1:4;
        if(victim_kind<4)pve_spawn_actor(0,victim_kind,BG_W_PLASMA_PISTOL,0,at,0);
        bg_player*p=&bg_players[victim];p->pos[0]=h->pos[0]+.6f;p->pos[1]=h->pos[1];p->pos[2]=h->pos[2];p->shield=0;p->exit_vehicle=-1;
        bg_players[0].pos[0]=-20;bg_players[0].pos[2]=20;
        if(victim!=1){bg_players[1].pos[0]=-20;bg_players[1].pos[2]=22;}
        assert(bg_vehicle_contacts_player(h,p));float health=p->health;
        h->velocity[0]=fast?4:.05f;update_vehicles(in,1.f/30);
        assert((p->health<health)==(fast!=0));
        printf("actual hull contact kind=%u speed=%s health %.2f -> %.2f\n",victim_kind,fast?"fast":"slow",health,p->health);
    }
}
static void pilot_weapon_tests(void){
    for(unsigned n=0;n<4;n++){
        bg_ff_qa_stage(1,8);bg_pve_actor*a=&bg_pve_actors[n];bg_player*p=&bg_players[4+n];bg_vehicle*v=&bg_vehicles[n];
        a->aware=a->visible=true;a->target=0;a->burst_pause=a->shot_time=a->burst_time=0;
        v->forward[0]=-1;v->forward[1]=v->forward[2]=0;v->up[0]=v->up[2]=0;v->up[1]=1;v->physics_valid=true;
        bg_players[0].pos[0]=v->pos[0]-10;bg_players[0].pos[1]=v->pos[1]-.35f;bg_players[0].pos[2]=v->pos[2];
        /* Call the production weapon directly: source trigger cooldown,
         * projectile speed/gravity and attribution must survive mounting. */
        unsigned gun=(unsigned[]){1,4,6,7}[n];bg_clear_events();p->yaw=3.14159265f;p->pitch=.3f;
        mounted_fire(v,4+n,gun,0,true,1.f/30);unsigned found=0;
        for(unsigned q=0;q<BG_MAX_PROJECTILES;q++){bg_projectile*shot=bg_projectile_at(q);if(!shot||!shot->active)continue;
            if(shot->owner==(int)(4+n)&&shot->damage_profile==bg_mounted_profiles[gun].profile){found++;float speed=sqrtf(dot(shot->velocity,shot->velocity));assert(fabsf(speed-bg_damage_profiles[shot->damage_profile].speed_start*30)<.001f);}}
        assert(found==1&&v->cooldown>0);mounted_fire(v,4+n,gun,0,true,1.f/30);assert(bg_event_count==1);
    }
    puts("mounted source profiles/speed/cooldown/attribution passed");
}
static void banshee_special_tests(void){
    bg_ff_qa_stage(1,8);bg_pve_count=2;
    bg_players[4].health=0;bg_pve_actor*a=&bg_pve_actors[1];bg_vehicle*v=&bg_vehicles[1];
    a->target=0;a->aware=a->visible=true;a->burst_time=a->burst_pause=a->vehicle_special_delay=0;a->vehicle_special_denials=0;
    v->pos[0]=0;v->pos[1]=15;v->pos[2]=0;v->forward[0]=1;v->forward[1]=v->forward[2]=0;v->up[1]=1;v->up[0]=v->up[2]=0;v->physics_valid=true;
    bg_players[0].pos[0]=20;bg_players[0].pos[1]=14.65f;bg_players[0].pos[2]=0;
    bg_input inputs[BG_UNITS]={0};pve_vehicle_inputs(inputs,1.f/30);
    assert(!inputs[5].secondary_fire); /* Source forbids bombing players on foot. */
    a->burst_time=a->burst_pause=a->vehicle_special_delay=0;bg_players[0].vehicle=0;
    memset(inputs,0,sizeof(inputs));pve_vehicle_inputs(inputs,1.f/30);
    assert(inputs[5].secondary_fire&&a->vehicle_special_denials==3&&a->vehicle_special_delay>=10&&a->vehicle_special_delay<=11.5f);
    a->vehicle_special_delay=0;memset(inputs,0,sizeof(inputs));pve_vehicle_inputs(inputs,1.f/30);assert(!inputs[5].secondary_fire);
    puts("CE Banshee secondary: vehicle target only, source delay and three-strafe exclusion passed");
}
int main(void){
    setvbuf(stdout,NULL,_IONBF,0);threshold_tests();assert(bg_map_load(9));available_seat_tests();autonomous_entry_tests();contact_integration_tests();pilot_weapon_tests();banshee_special_tests();
    for(unsigned players=1;players<=4;players++){
        bg_ff_qa_stage(players,8);assert(bg_vehicle_count==4&&bg_pve_count==bg_ff.cap);
        for(unsigned i=0;i<4;i++){assert(bg_players[4+i].vehicle==(int)i);assert(bg_vehicles[i].occupants[0]==(int)(4+i));}
        float original[4][3];for(unsigned i=0;i<4;i++)memcpy(original[i],bg_vehicles[i].pos,12);
        for(unsigned tick=0;tick<150;tick++){
            advance(1);
            for(unsigned n=0;n<4;n++)assert(fabsf(bg_vehicles[n].pos[0])<100&&fabsf(bg_vehicles[n].pos[2])<100&&fabsf(bg_vehicles[n].pos[1])<150);
        }
        for(unsigned i=0;i<4;i++){
            bg_vehicle*v=&bg_vehicles[i];for(unsigned k=0;k<3;k++)assert(isfinite(v->pos[k])&&isfinite(v->velocity[k]));
            printf("%uP kind=%d moved=%.3f health=%.1f pilot=%d\n",players,v->kind,sqrtf(distance2(v->pos,original[i])),v->health,v->occupants[0]);
        }
        /* An ordinary pilot death releases its seat and preserves scoring. */
        bg_ff_qa_stage(players,8);unsigned killed=bg_ff.killed;kill(4,0);assert(bg_vehicles[0].occupants[0]<0&&bg_players[4].vehicle<0&&bg_ff.killed==killed+1);
        /* Hull destruction kills its pilot once and wave hulls never respawn. */
        damage_vehicle(2,0,100000);assert(!bg_vehicles[2].active&&bg_players[6].health<=0&&bg_players[6].vehicle<0);
        unsigned after=bg_ff.killed;damage_vehicle(2,0,100000);assert(bg_ff.killed==after);
        bg_vehicles[2].wreck_time=0;bg_vehicles[2].respawn=0;bg_input inputs[BG_UNITS]={0};update_vehicles(inputs,1.f/30);assert(!bg_vehicles[2].active);
    }
    puts("enemy vehicle ownership/contact checks passed");return 0;
}
