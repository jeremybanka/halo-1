/* Exercise production transitions directly, including death and objective
 * events, against the real streamed maps. No graphics or controller mocks. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "game.c"
static const unsigned ids[]={9,10,5,6,0,1,2,3,4,7,8,11,12};
static void start(unsigned mode) {
    const uint8_t teams[]={0,1,0,1};
    bg_set_players(4);bg_configure_mode(mode,teams);bg_reset();
    for(unsigned p=0;p<4;p++)assert(bg_players[p].health>0);
}
static void objective_step(unsigned count) { for(unsigned i=0;i<count;i++)mode_tick(1.f/30); }
static void place(unsigned p,const float pos[3]) {
    memcpy(bg_players[p].pos,pos,12);memset(bg_players[p].velocity,0,12);
    bg_players[p].pos[1]-=.2f;bg_players[p].vehicle=-1;
}
static unsigned events(bg_event_kind kind) {
    unsigned count=0;for(unsigned i=0;i<bg_event_count;i++)count+=bg_events[i].kind==kind;return count;
}
static void reachable_hills(void){
    start(BG_MODE_KING);
    for(unsigned id=0;id<64;id++)if(mode_marker(BG_MARK_HILL,id)){
        hill_id=id;float lo[3]={1e9f,1e9f,1e9f},hi[3]={-1e9f,-1e9f,-1e9f},point[3];unsigned n=0;
        while(bg_mode_hill_point(n++,point))for(unsigned a=0;a<3;a++){lo[a]=fminf(lo[a],point[a]);hi[a]=fmaxf(hi[a],point[a]);}
        bool found=false;
        for(unsigned x=0;x<=32&&!found;x++)for(unsigned z=0;z<=32&&!found;z++){
            bg_player *p=&bg_players[0];p->pos[0]=lo[0]+(hi[0]-lo[0])*x/32;
            p->pos[2]=lo[2]+(hi[2]-lo[2])*z/32;
            p->pos[1]=bg_floor(p->pos[0],p->pos[2],hi[1]+.7f)+.015f;
            found=bg_player_in_hill(0)&&bg_terrain_clearance(p);
        }
        if(!found)fprintf(stderr,"UNREACHABLE HILL map%u id%u\n",bg_map_id(),id);
        assert(found);
    }
}
static void catalog_and_maps(void) {
    for(unsigned map=0;map<13;map++) {
        bg_map_load(ids[map]);assert(bg_current_mode_map());
        for(unsigned j=0;j<bg_spawn_count;j++)if(bg_current_mode_map()->spawn_modes[j]){
            bg_player probe={0};memcpy(probe.pos,bg_current_mode_map()->spawn_positions[j],12);
            float floor=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f);
            assert(floor>-999);
            if(!bg_terrain_clearance(&probe))fprintf(stderr,"UNSAFE map%u start%u %.4f %.4f %.4f\n",ids[map],j,probe.pos[0],probe.pos[1],probe.pos[2]);
            assert(bg_terrain_clearance(&probe));
        }
        for(unsigned mode=0;mode<BG_MODE_COUNT;mode++) {
            start(mode);const bg_mode_rules *r=bg_current_rules();
            assert(bg_score_limit()==r->goal*(bg_mode_timed(r)?60u:1u));
            for(unsigned p=0;p<4;p++) {
                assert(bg_players[p].weapon>=0&&bg_players[p].weapon<BG_WEAPON_COUNT);
                if(r->weapon>=0)assert(bg_players[p].weapon==r->weapon);
                int spawn=bg_select_spawn(p);assert(spawn>=0&&mode_spawn_eligible(p,spawn));
                if(r->engine==BG_ENGINE_CTF)assert(bg_spawns[spawn].team==(int)mode_teams[p]);
            }
            if(!r->vehicles)assert(bg_vehicle_count==0);
            if(mode!=BG_MODE_SLAYER&&r->vehicles)for(unsigned i=0;i<bg_vehicle_count;i++)
                assert(bg_vehicles[i].kind==(r->vehicles==2?BG_V_SCORPION:BG_V_WARTHOG));
            bg_input in[4]={0};for(unsigned tick=0;tick<15;tick++)bg_tick(in,1.f/30);
            assert(bg_objective_count<=BG_MAX_OBJECTIVES);
            assert(!bg_match_finished());
        }
        reachable_hills();
        bg_map_unload();assert(!bg_current_mode_map());
        printf("PASS map%u: all 26 presets, source starts, loadouts, objectives and unload\n",ids[map]);
    }
    bg_map_load(9);
}
static void slayer_and_lives(void) {
    start(BG_MODE_TEAM_SLAYER);damage_history[1][0]=100;damage_history[1][2]=50;damage_history[1][3]=50;
    kill(1,0);assert(statistics.assists[2]==1&&statistics.assists[3]==0);assert(bg_team_score(0)==1&&statistics.kills[0]==1);
    kill(2,0);assert(bg_team_score(0)==0&&statistics.kills[0]==1);
    start(BG_MODE_SLAYER_PRO);assert(bg_players[0].weapon==BG_W_AR&&bg_players[0].inventory[1]==BG_W_PISTOL);
    kill(1,0);assert(bg_players[0].score==1&&bg_mode_speed(0)==1&&bg_mode_speed(1)==1);
    start(BG_MODE_SLAYER);kill(1,0);assert(bg_mode_speed(0)<1&&bg_mode_speed(1)>1);
    start(BG_MODE_PHANTOMS);int target=bg_player_target(0);assert(target>0);
    unsigned wrong=target==1?2:1;kill(wrong,0);assert(bg_players[0].score==0);
    kill(target,0);assert(bg_players[0].score==1&&bg_player_target(0)!=target);
    objective_step(1);assert(bg_players[0].invisibility>0&&!bg_mode_radar());
    start(BG_MODE_ELIMINATION);kill(1,0);assert(bg_player_eliminated(1));
    kill(2,0);assert(!bg_match_finished());kill(3,0);objective_step(1);
    assert(bg_match_finished()&&bg_match_winner()==0);
    unsigned n=events(BG_EVENT_GAME_OVER);objective_step(20);assert(n==1&&events(BG_EVENT_GAME_OVER)==1);
    start(BG_MODE_ENDURANCE);kill(1,0);assert(bg_player_waiting(1)&&!bg_player_eliminated(1));
    match_time++;kill(2,0);assert(!bg_player_waiting(1)&&bg_player_waiting(2));
    assert(mode_penalty[1]==300&&bg_players[1].respawn==3);
    start(BG_MODE_SNIPERS);kill(1,0);spawn(1);kill(1,0);
    assert(bg_players[1].respawn==5&&mode_penalty[1]==300);
    start(BG_MODE_IRON_CTF);assert(mode_damage(1,0)==.5f);
}
static void ctf(void) {
    start(BG_MODE_CTF);bg_set_score_limit(1);bg_clear_events();
    place(0,bg_objectives[1].pos);objective_step(1);assert(bg_player_objective(0)==1);
    assert(events(BG_EVENT_OBJECTIVE)==1);
    place(0,bg_objectives[0].home);objective_step(1);
    assert(bg_match_finished()&&bg_team_score(0)==1&&bg_player_is_winner(2)&&!bg_player_is_winner(1));
    assert(bg_objectives[1].at_home&&bg_player_objective(0)<0);
    start(BG_MODE_CTF_PRO);place(0,bg_objectives[1].pos);objective_step(1);
    place(1,bg_objectives[0].pos);objective_step(1);
    place(0,bg_objectives[0].home);objective_step(1);assert(bg_team_score(0)==0);
    bg_drop_objective(1);place(1,bg_spawns[0].pos);place(2,bg_objectives[0].pos);objective_step(1);
    assert(bg_objectives[0].at_home&&bg_team_score(0)==1);
    start(BG_MODE_IRON_CTF);place(0,bg_objectives[1].pos);objective_step(1);assert(bg_player_objective(0)==1);
    bg_drop_objective(0);place(0,bg_spawns[0].pos);place(1,bg_objectives[1].pos);objective_step(1);
    assert(!bg_objectives[1].at_home);objective_step(510);assert(bg_objectives[1].at_home);
    start(BG_MODE_INVASION);
    const bg_mode_marker *red=mode_marker(BG_MARK_FLAG,0),*blue=mode_marker(BG_MARK_FLAG,1);
    assert(fabsf(bg_objectives[1].home[0]-red->pos[0])<.001f);
    assert(fabsf(bg_objectives[0].home[0]-blue->pos[0])<.001f);
    place(0,bg_objectives[1].pos);objective_step(1);assert(bg_player_objective(0)==1);
    place(0,bg_objectives[0].home);objective_step(1);assert(bg_team_score(0)==1);
}
static void balls(void) {
    start(BG_MODE_ODDBALL);assert(!bg_objectives[0].active);objective_step(451);assert(bg_objectives[0].active);
    place(0,bg_objectives[0].pos);objective_step(1);assert(bg_player_objective(0)==0);
    assert(bg_mode_speed(0)==.75f);objective_step(60);assert(bg_players[0].score==2);
    kill(0,1);assert(bg_player_objective(0)<0&&bg_objectives[0].owner<0);
    start(BG_MODE_REVERSE_TAG);kill(1,0);assert(bg_player_ball_count(0)==1&&bg_player_objective(0)<0);
    objective_step(60);assert(bg_players[0].score==2);
    kill(0,2);assert(bg_player_ball_count(2)==1&&!bg_player_ball_count(0));
    start(BG_MODE_ACCUMULATION);assert(bg_objective_count==16);kill(1,0);spawn(1);kill(1,0);
    assert(bg_player_ball_count(0)==2);objective_step(30);assert(bg_players[0].score==2);
    start(BG_MODE_JUGGERNAUT);kill(1,0);assert(bg_player_ball_count(0)==1&&bg_players[0].score==1);
    assert(mode_damage(2,0)==1.5f);kill(2,0);assert(bg_players[0].score==2);
    kill(0,3);assert(bg_player_ball_count(3)==1&&bg_players[3].score==1);
    start(BG_MODE_STALKER);kill(1,0);objective_step(1);
    assert(bg_players[0].invisibility>0&&bg_mode_speed(0)==1.25f&&mode_damage(2,0)==.5f);
}
static void objective_controls(void) {
    start(BG_MODE_CTF);place(0,bg_objectives[1].pos);objective_step(1);
    assert(bg_player_objective(0)==1);
    bg_player *p=&bg_players[0];p->weapon_ready=0;
    int ammo=p->ammo,grenades=p->grenades[p->grenade_kind];
    bg_input in={.fire=true,.grenade=true,.reload=true};bg_clear_events();
    tick_player_weapons(0,&in,1.f/30);
    assert(p->ammo==ammo&&p->grenades[p->grenade_kind]==grenades&&!p->reload);
    assert(!events(BG_EVENT_FIRE)&&!events(BG_EVENT_GRENADE));
    in=(bg_input){.melee=true};tick_player_weapons(0,&in,1.f/30);
    assert(p->melee_time>0&&p->melee_tick==7&&bg_player_melee_duration(0)==1);
    float nav[3];unsigned kind,team;
    assert(bg_mode_navpoint(0,bg_objective_count,nav,&kind,&team));
    assert(kind==BG_OBJECTIVE_FLAG&&team==0&&distance2(nav,bg_objectives[0].home)<.000001f);
    assert(bg_player_color(0)==bg_player_color(2)&&bg_player_color(0)!=bg_player_color(1));
    for(unsigned v=0;v<bg_vehicle_count;v++)if(bg_vehicles[v].kind==BG_V_WARTHOG){
        bg_vehicle saved=bg_vehicles[v];saved.pos[1]+=2; /* Unsettled source vehicle starts can intersect the floor. */
        /* Only one seat free at a time: carrier may enter passenger seats,
         * while the source's driver/gunner flag bits prohibit those seats. */
        for(unsigned seat=0;seat<bg_seat_counts[saved.kind];seat++){
            bg_vehicle *vehicle=&bg_vehicles[v];*vehicle=saved;
            for(unsigned j=0;j<bg_seat_counts[saved.kind];j++)vehicle->occupants[j]=j==seat?-1:3;
            float entry[3];bg_vehicle_seat_position(vehicle,seat,true,entry);
            memcpy(p->pos,entry,12);p->pos[1]-=.35f;p->interact_cooldown=0;
            bg_use_target use=bg_interaction_target(0);
            if(bg_seat_definitions[saved.kind][seat].flags&12)assert(use.kind!=BG_USE_ENTER||use.object!=(int)v||use.seat!=(int)seat);
            else assert(use.kind==BG_USE_ENTER&&use.object==(int)v&&use.seat==(int)seat);
        }
        bg_vehicles[v]=saved;break;
    }
    in=(bg_input){.switch_weapon=true};int slot=p->slot;
    tick_player_controls(0,&in,1.f/30);
    assert(bg_player_objective(0)<0&&p->slot==slot&&!p->melee_time&&!p->melee_tick);
    assert(events(BG_EVENT_OBJECTIVE)==1);
}
static void hill_and_race(void) {
    start(BG_MODE_TEAM_KING);float center[3]={0},p[3];unsigned count=0;
    while(bg_mode_hill_point(count,p)){for(unsigned a=0;a<3;a++)center[a]+=p[a];count++;}
    assert(count>=3);for(unsigned a=0;a<3;a++)center[a]/=count;
    for(unsigned i=0;i<4;i++)place(i,center);
    objective_step(30);assert(bg_team_score(0)==1&&bg_team_score(1)==1);
    unsigned previous=hill_id;objective_step(1770);assert(hill_id!=previous);
    start(BG_MODE_RACE);
    for(unsigned id=0;id<32;id++)if(race_mask&(1u<<id)) {
        place(0,mode_marker(BG_MARK_RACE,id)->pos);objective_step(1);
    }
    assert(bg_players[0].score==0);place(0,mode_marker(BG_MARK_RACE,race_first)->pos);objective_step(1);
    assert(bg_players[0].score==1);
    start(BG_MODE_TEAM_RACE);mode_race_lap(0);assert(bg_team_score(0)==0);
    mode_race_lap(2);assert(bg_team_score(0)==1);
    start(BG_MODE_RALLY);unsigned old=rally_flag;place(0,mode_marker(BG_MARK_RACE,old)->pos);objective_step(1);
    assert(bg_players[0].score==1&&rally_flag!=old);
}
static void export_clearance(const char *path) {
    FILE *f=fopen(path,"w");assert(f);bool first=true;fprintf(f,"[");
    for(unsigned map=0;map<13;map++){
        bg_map_load(ids[map]);start(BG_MODE_SLAYER);
        for(unsigned j=0;j<bg_spawn_count;j++)if(bg_current_mode_map()->spawn_modes[j]){
            bg_player probe={0};probe.vehicle=-1;memcpy(probe.pos,bg_spawns[j].pos,12);
            probe.pos[1]=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f)+.015f;
            bool needs_correction=!bg_terrain_clearance(&probe);
            float original[3];memcpy(original,probe.pos,12);
            for(unsigned pass=0;pass<40;pass++){
                probe.pos[1]=bg_floor(probe.pos[0],probe.pos[2],probe.pos[1]+.5f)+.015f;
                if(bg_terrain_clearance(&probe))break;
                bg_move_capsule(&probe,0);
            }
            float distance=sqrtf(distance2(probe.pos,original));
            if(needs_correction)fprintf(stderr,"CLEAR map%u start%u displacement %.6f safe%d\n",ids[map],j,distance,bg_terrain_clearance(&probe));
            assert(bg_terrain_clearance(&probe)&&distance<.6f);
            fprintf(f,"%s{\"id\":%u,\"start\":%u,\"position\":[%.9g,%.9g,%.9g]}",first?"":",",ids[map],j,probe.pos[0],probe.pos[1],probe.pos[2]);first=false;
        }
        bg_map_unload();
    }
    fprintf(f,"]\n");fclose(f);
}
int main(void) {
    const char *path=getenv("BG_MODE_CLEARANCE_OUTPUT");if(path){export_clearance(path);return 0;}
    catalog_and_maps();slayer_and_lives();ctf();balls();objective_controls();hill_and_race();bg_map_unload();
    puts("PASS: mode scoring, team penalties, targets, lives, respawn growth, CTF variants, ball transfers/traits, hills and ordered/team races");
}
