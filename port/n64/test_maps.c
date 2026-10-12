#include "map.h"
#include "game.h"
#include "terrain.h"
#include "movement.h"
#include "pickup_rules.h"
#include "blam/vehicle_physics.h"
#include "replay.h"
#include "frontend_qa.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static bg_input input[4];
#if defined(BG_INITIAL_MAP) && BG_INITIAL_MAP == 10
static void frontend_cycle(void) {
    bg_frontend front;
    bg_menu menu;
    bg_front_init(&front);
    front.map = BG_MAP_WIZARD;
    bg_menu_init(&menu, 4);
    menu.shell_session = true;
    float game_time = 0;
    unsigned matches = 0;
    for (unsigned frame = 1; frame < 15000 && !bg_front_qa_done(); frame++) {
        bg_control_state raw[4];
        bg_front_qa_input(&front, raw, (uint64_t)frame * 33333);
        if (front.page != BG_FRONT_PLAY) {
            bg_front_action action = bg_front_update(&front, raw, (uint64_t)frame * 33333);
            if (action == BG_FRONT_START_MATCH) {
#ifdef BG_MAPS_CYCLE
                const unsigned expected[]={10,9,10,5,6,0};assert(matches<6&&front.map==expected[matches]);
#endif
                bg_map_unload();
                bg_map_load(front.map);
                bg_set_players(front.count);
                bg_set_score_limit(15);
                bg_reset();
                game_time = 0;
                menu.open = false;
                matches++;
            } else if (action == BG_FRONT_RESUME_MATCH) menu.open = false;
            continue;
        }
        bg_menu_input navigation[4];
        bg_menu_inputs(&menu, raw, navigation);
        bg_menu_result result = bg_menu_update(&menu, navigation, bg_player_count());
        if (result.action == BG_MENU_ACTION_QUIT) {
            bg_front_quit(&front);
            continue;
        }
        if (menu.open) continue;
        bg_front_qa_tick(input, game_time);
        bg_clear_events();
        bg_tick(input, 1.f / 30);
        game_time += 1.f / 30;
        if (bg_match_finished()) {
            int scores[4];
            for (unsigned p = 0; p < 4; p++) scores[p] = bg_players[p].score;
            bg_front_results(&front, scores, bg_match_winner());
            bg_map_unload();
        }
    }
    assert(bg_front_qa_done() && matches ==
#ifdef BG_MAPS_CYCLE
 6
#else
 3
#endif
 && front.page == BG_FRONT_MAIN);
    printf("PASS: %u-step menu cycle, %u live matches and quit/resume\n",bg_front_qa_steps(),matches);
}
#endif
static void tick(unsigned count) {
    while (count--) { bg_clear_events(); bg_tick(input, 1.f/30); }
}
static void alone(void) {
    bg_set_score_limit(1000);
    for (unsigned p=1;p<4;p++) { bg_players[p].health=0; bg_players[p].respawn=10000; }
    memset(input,0,sizeof(input));
}
static void wizard_rules(void) {
    unsigned eligible=0;
    for(unsigned i=0;i<bg_spawn_count;i++) if(bg_slayer_spawns[i]) {
        eligible++;
        bg_player probe=bg_players[0];memcpy(probe.pos,bg_spawns[i].pos,12);
        float floor=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f);
        assert(floor>-999);probe.pos[1]=floor+.015f;
        assert(bg_terrain_clearance(&probe));
    }
    assert(eligible==16);
    for (unsigned page = 1; page <= 2; page++) for (unsigned p = 0; p < 4; p++) {
        bg_player probe = bg_players[p];
        float ceiling = -1;
        if (page == 1) {
            probe.pos[0] = p % 2 ? 7 : -7;
            probe.pos[2] = p / 2 ? -5 : 5;
        } else {
            probe.pos[0] = bg_teleporters[p].source[0] * .75f;
            probe.pos[2] = bg_teleporters[p].source[2] * .75f;
            ceiling = bg_teleporters[p].source[1] + .5f;
        }
        float floor = bg_floor(probe.pos[0], probe.pos[2], ceiling);
        assert(floor > -999);
        probe.pos[1] = floor + .015f;
        assert(bg_terrain_clearance(&probe));
    }
    for(unsigned t=0;t<bg_teleporter_count;t++) {
        bg_reset();alone();bg_player*p=&bg_players[0];
        memcpy(p->pos,bg_teleporters[t].source,12);p->teleport_cooldown=0;
        tick(1);assert(p->teleport_cooldown>0);
        float dx=p->pos[0]-bg_teleporters[t].destination[0],dz=p->pos[2]-bg_teleporters[t].destination[2];
        assert(dx*dx+dz*dz<.01f&&p->health==100&&bg_terrain_clearance(p));
    }
    unsigned ladders=0;
    for(unsigned t=0;t<bg_collision_count;t++) if(bg_collision_flags[t]&BG_SURFACE_CLIMBABLE) {
        bg_reset();alone();bg_player*p=&bg_players[0];const bg_triangle*tri=&bg_collision[t];
        float ab[3],ac[3],normal[3];
        for(unsigned a=0;a<3;a++){ab[a]=tri->p[1][a]-tri->p[0][a];ac[a]=tri->p[2][a]-tri->p[0][a];p->pos[a]=(tri->p[0][a]+tri->p[1][a]+tri->p[2][a])/3;}
        normal[0]=ab[1]*ac[2]-ab[2]*ac[1];normal[1]=ab[2]*ac[0]-ab[0]*ac[2];normal[2]=ab[0]*ac[1]-ab[1]*ac[0];
        float len=sqrtf(normal[0]*normal[0]+normal[1]*normal[1]+normal[2]*normal[2]);
        for(unsigned a=0;a<3;a++)normal[a]/=len;
        /* The authored ladder sheets include both faces. Choose the side
         * with a supporting floor rather than staging inside the wall void. */
        float floor=bg_floor(p->pos[0]+normal[0]*(bg_movement.radius+.005f),
                             p->pos[2]+normal[2]*(bg_movement.radius+.005f),
                             fminf(tri->p[0][1],fminf(tri->p[1][1],tri->p[2][1]))+.25f);
        if(floor < -999)for(unsigned a=0;a<3;a++)normal[a]=-normal[a];
        for(unsigned a=0;a<3;a++)p->pos[a]+=normal[a]*(bg_movement.radius+.005f);
        p->pos[1]=fminf(tri->p[0][1],fminf(tri->p[1][1],tri->p[2][1]))+.05f;
        p->yaw=atan2f(normal[2],-normal[0]);p->pitch=.9f;p->teleport_cooldown=10000;
        memset(p->velocity,0,sizeof(p->velocity));p->vy=0;p->grounded=false;
        tick(1);float start=p->pos[1];
        input[0].forward=1;tick(24);
        printf("ladder%u climb%d rise%.3f pos%.3f %.3f %.3f\n",t,p->climbing,p->pos[1]-start,p->pos[0],p->pos[1],p->pos[2]);
        assert(p->health==100&&p->pos[1]>start+.2f);
        float top = p->pos[1];
        p->pitch = -.9f;
        tick(20);
        assert(p->health == 100 && p->pos[1] < top - .2f);
        ladders++;
    }
    assert(ladders==16);
    puts("Wizard: 16 spawn clearances, four teleporter links, sixteen ladder triangles pass");

    /* Completion is produced by live shotgun damage, respawn and scoring;
     * the frontend fixture never assigns a score or winner. */
    bg_reset();
    bg_set_score_limit(15);
    unsigned ticks = 0;
    while (!bg_match_finished() && ticks < 3600) {
        bg_front_qa_tick(input, ticks / 30.f);
        tick(1);
        ticks++;
    }
    assert(bg_match_finished() && bg_players[0].score == 15);
    printf("Wizard staged match: 15 live kills, results after %.2f seconds\n", ticks / 30.f);
}
static void new_maps(void) {
    const unsigned ids[]={BG_MAP_HANG_EM_HIGH,BG_MAP_CHILL_OUT,BG_MAP_BATTLE_CREEK};
    const unsigned starts[]={28,25,22},items[]={43,32,30},portals[]={0,3,2};
    for(unsigned i=0;i<3;i++){
        bg_map_load(ids[i]);bg_set_players(4);bg_reset();memset(input,0,sizeof(input));
        assert(bg_vehicle_count==0&&bg_map_item_count==items[i]&&bg_teleporter_count==portals[i]);
        unsigned count=0;
        for(unsigned j=0;j<bg_spawn_count;j++)if(bg_slayer_spawns[j]){
            bg_player probe=bg_players[0];memcpy(probe.pos,bg_spawns[j].pos,12);
            float floor=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f);
            assert(floor>-999);probe.pos[1]=floor+.015f;
            if(!bg_terrain_clearance(&probe)){
                fprintf(stderr,"map%u start%u clearance fail %.4f %.4f %.4f\n",ids[i],j,probe.pos[0],probe.pos[1],probe.pos[2]);
                for(unsigned f=0;f<bg_collision_count;f++){
                    float axis[3],surface[3];float distance=bg_capsule_triangle(probe.pos,bg_body_height(&probe),bg_movement.radius,&bg_collision[f],axis,surface);
                    if(distance<(bg_movement.radius-.001f)*(bg_movement.radius-.001f))fprintf(stderr,"hit%u flags%u distance%.4f axis%.3f %.3f %.3f surface%.3f %.3f %.3f\n",f,bg_collision_flags[f],sqrtf(distance),axis[0],axis[1],axis[2],surface[0],surface[1],surface[2]);
                }
            }
            assert(bg_terrain_clearance(&probe));count++;
        }
        assert(count==starts[i]);
        for(unsigned p=0;p<4;p++){
            assert(bg_players[p].weapon==bg_start_weapons[0]);
            for(unsigned g=0;g<2;g++)assert(bg_players[p].grenades[g]==bg_start_grenades[g]);
        }
        for(unsigned t=0;t<bg_teleporter_count;t++){
            bg_reset();alone();bg_player*p=&bg_players[0];memcpy(p->pos,bg_teleporters[t].source,12);p->teleport_cooldown=0;
            tick(1);assert(p->teleport_cooldown>0);
            float dx=p->pos[0]-bg_teleporters[t].destination[0],dz=p->pos[2]-bg_teleporters[t].destination[2];
            assert(dx*dx+dz*dz<.01f&&p->health==100&&bg_terrain_clearance(p));
        }
        bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        unsigned shots=0;
        for(unsigned t=0;t<2250;t++){
            bg_replay_input(input,t/30.f);bg_clear_events();bg_tick(input,1.f/30);
            for(unsigned e=0;e<bg_event_count;e++)shots+=bg_events[e].kind==BG_EVENT_FIRE;
            for(unsigned p=0;p<4;p++)for(unsigned a=0;a<3;a++)assert(isfinite(bg_players[p].pos[a]));
            assert(bg_vehicle_count==0&&bg_event_count<=BG_MAX_EVENTS);
        }
        assert(shots>100);printf("PASS map%u: %u source spawn clearances, %u items, %u teleporters, original loadout, 2250 live replay ticks / %u shots\n",ids[i],count,items[i],portals[i],shots);
        bg_map_unload();assert(!bg_map_loaded()&&!bg_map_resident_bytes());
    }
}
static void export_spawn_clearance(void) {
    const unsigned ids[]={BG_MAP_HANG_EM_HIGH,BG_MAP_CHILL_OUT,BG_MAP_BATTLE_CREEK};
    bool first=true;printf("[");
    for(unsigned i=0;i<3;i++){
        bg_map_load(ids[i]);bg_set_players(4);bg_reset();
        for(unsigned j=0;j<bg_spawn_count;j++)if(bg_slayer_spawns[j]){
            bg_player probe=bg_players[0];memcpy(probe.pos,bg_spawns[j].pos,12);
            probe.pos[1]=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f)+.015f;
            if(bg_terrain_clearance(&probe))continue;
            float original[3];memcpy(original,probe.pos,12);memset(probe.velocity,0,12);probe.support_triangle=0;
            for(unsigned pass=0;pass<8&&!bg_terrain_clearance(&probe);pass++)bg_move_capsule(&probe,0);
            assert(bg_terrain_clearance(&probe));float d[3],distance=0;
            for(unsigned a=0;a<3;a++){d[a]=probe.pos[a]-original[a];distance+=d[a]*d[a];}
            assert(distance<.075f*.075f);
            printf("%s{\"id\":%u,\"start\":%u,\"delta\":[%.9g,%.9g,%.9g]}",first?"":",",ids[i],j,d[0],d[1],d[2]);first=false;
        }
        bg_map_unload();
    }
    puts("]");
}
int main(void) {
    if(getenv("BG_EXPORT_SPAWN_CLEARANCE")){export_spawn_clearance();return 0;}
    for(unsigned pass=0;pass<4;pass++) {
        unsigned map=pass%2?10:9;bg_map_load(map);bg_set_players(4);bg_reset();memset(input,0,sizeof(input));
        printf("map%u triangles%u chunks%u spawns%u items%u cars%u portals%u RAM%u\n",map,bg_collision_count,bg_chunk_count,bg_spawn_count,bg_pickup_count,bg_vehicle_count,bg_teleporter_count,bg_map_resident_bytes());
        if(map==10)assert(bg_vehicle_count==0&&bg_pickup_count==30&&bg_teleporter_count==4);
        /* Identical coordinates must not hit a floor cache from the other
         * map. This central Wizard floor is below Blood Gulch's floor. */
        float center_floor = bg_floor(0, 4, 100);
        if (map == BG_MAP_WIZARD) assert(center_floor < -1);
        else assert(center_floor > -1);
        for(unsigned p=0;p<4;p++)assert(bg_players[p].weapon==BG_W_PLASMA_PISTOL&&bg_players[p].grenades[0]==0&&bg_terrain_clearance(&bg_players[p]));
        tick(60);for(unsigned p=0;p<4;p++)assert(bg_players[p].health==100);
        float origin[3]={0,0,0},dir[3]={1,0,0};float hit=bg_world_raycast(origin,dir,100);
        if(map==10)assert(hit<13);else assert(hit>50);
        if(map==10&&pass==1)wizard_rules();
        bg_map_unload();assert(bg_map_resident_bytes()==0&&!bg_map_loaded());
    }
    bg_map_load(10);bg_set_players(4);bg_reset();
    unsigned shots=0,kills=0,warps=0;
    for(unsigned t=0;t<2250;t++){
        bg_replay_input(input,t/30.f);bg_clear_events();bg_tick(input,1.f/30);
        for(unsigned e=0;e<bg_event_count;e++){
            shots+=bg_events[e].kind==BG_EVENT_FIRE;kills+=bg_events[e].kind==BG_EVENT_KILL;
            warps+=bg_events[e].kind==BG_EVENT_TELEPORTER;
        }
        assert(bg_vehicle_count==0&&!bg_match_finished());
        for(unsigned p=0;p<4;p++)for(unsigned a=0;a<3;a++)assert(isfinite(bg_players[p].pos[a]));
    }
    printf("Wizard replay: 2250 real ticks, %u shots / %u kills / %u warps\n",shots,kills,warps);
    assert(shots>100);bg_map_unload();
#if defined(BG_INITIAL_MAP) && BG_INITIAL_MAP == 10
    frontend_cycle();
#endif
    new_maps();
    puts("PASS: original starts/items, clean alternating map residency, source-coordinate rays, Wizard navigation and live replay");
}
