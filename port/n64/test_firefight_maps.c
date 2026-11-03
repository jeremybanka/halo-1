#include <stdio.h>
#include <stdlib.h>
#include "game.c"

static void entrances(void){
    for(unsigned mi=0;mi<2;mi++){
        unsigned map=mi?BG_MAP_RAT_RACE:BG_MAP_BATTLE_CREEK;
        for(unsigned humans=1;humans<=4;humans++){
            assert(bg_map_load(map));bg_ff_start_fight(humans,bg_ff_default_fight(map));
            assert(bg_ff.active&&bg_ff.map==map&&ff_nav.nodes&&ff_nav.map==map);
            printf("MAP %u %uP nodes=%u routes=%u\n",map,humans,ff_nav.count,pve_route_count);
            for(unsigned stage=0;stage<ff_current_map()->stage_count;stage++){
                bg_ff.wave=stage*2;for(unsigned h=0;h<humans;h++){spawn(h);printf("H%u %.2f %.2f %.2f\n",h,bg_players[h].pos[0],bg_players[h].pos[1],bg_players[h].pos[2]);}
                unsigned valid=0;
                for(unsigned z=0;z<FF_ZONES;z++){
                    float points[8][3],landing[3];bool ok=ff_zone_points(z,BG_FF_SCOUTS,true,points,landing);
                    if(ok){valid++;printf("ZONE %u %s %.2f %.2f %.2f\n",z,ff_zones[z].name,points[0][0],points[0][1],points[0][2]);}
                }
                printf("STAGE %u valid %u\n",stage,valid);fflush(stdout);assert(valid>0);
            }
            bg_pve_stop();bg_map_unload();assert(!ff_nav.nodes);
        }
    }
    puts("PASS map-authored human starts and concealed reachable entrances");
}

static void advance(unsigned ticks){bg_input input[4]={0};for(unsigned t=0;t<ticks;t++)bg_tick(input,1.f/30);}
static void navigation(void){
    static uint16_t distance[8192],queue[8192];
    for(unsigned mi=0;mi<2;mi++){
        unsigned map=mi?3:0;assert(bg_map_load(map));bg_ff_start(1);
        for(unsigned sample=0;sample<24;sample++){
            unsigned goal=(sample*83+17)%pve_route_count;
            memset(distance,255,sizeof(distance));unsigned first=0,last=0;queue[last++]=goal;distance[goal]=0;
            while(first<last){unsigned id=queue[first++],raw=pve_route_grid[id];
                for(unsigned k=0;k<8;k++)if(pve_nav_edge_bits(raw)&(1u<<k)){
                    unsigned next=pve_route_id[pve_neighbor(raw,k)];if(distance[next]==UINT16_MAX){distance[next]=distance[id]+1;queue[last++]=next;}
                }
            }
            for(unsigned n=0;n<pve_route_count;n++)assert(pve_reachable(pve_route_grid[n],pve_route_grid[goal])==(distance[n]!=UINT16_MAX));
            unsigned node=goal;for(unsigned n=0;n<pve_route_count;n++)if(distance[n]!=UINT16_MAX&&distance[n]>distance[node])node=n;
            float at[3];pve_node_pos(pve_route_grid[node],at);pve_spawn_actor(0,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,0,at,0);
            bg_pve_actor*a=&bg_pve_actors[0];a->aware=true;a->target=0;pve_node_pos(pve_route_grid[goal],a->last_seen);pve_destination(0);
            unsigned ticks=0;while(pve_route_requests[0].pending){pve_routes_service();assert(++ticks<600);}
            assert(bg_pve_navigation.max_work<=256);
            for(unsigned f=0;f<PVE_ROUTE_FIELDS;f++)if(pve_route_fields[f].valid&&pve_route_fields[f].goal==goal)
                for(unsigned n=0;n<pve_route_count;n++)if(pve_route_fields[f].distance[n]!=UINT16_MAX)assert(pve_route_fields[f].distance[n]==distance[n]);
        }
        bg_pve_stop();bg_map_unload();
    }
    puts("PASS selected-map connectivity and bounded route distances match independent breadth-first searches");
}
static void live_movement(unsigned map){
    assert(bg_map_load(map));bg_ff_start(4);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
    assert(!ff_arrive(BG_FF_DEFENDERS,true)&&!bg_ff_dropship.phase&&!bg_pve_count);
    assert(ff_arrive(BG_FF_DEFENDERS,false));float original[3][3];
    for(unsigned i=0;i<3;i++){memcpy(original[i],bg_players[4+i].pos,12);assert(ff_hidden(original[i],pve_definition(i)->height));}
    for(unsigned tick=0;tick<240;tick++){
        for(unsigned h=0;h<4;h++)bg_players[h].health=bg_players[h].shield=10000;
        advance(1);assert(!bg_ff_dropship.phase&&bg_vehicle_count==0);
    }
    unsigned moved=0;for(unsigned i=0;i<3;i++){
        for(unsigned k=0;k<3;k++)assert(isfinite(bg_players[4+i].pos[k]));
        moved+=distance2(original[i],bg_players[4+i].pos)>.25f;
    }
    assert(moved);printf("PASS map %u: %u/3 live enemies walk from concealed entrances using production AI\n",map,moved);
}
static void full_sets(void){
    for(unsigned map_index=0;map_index<2;map_index++)for(unsigned humans=1;humans<=4;humans++){
        unsigned map=map_index?3:0;assert(bg_map_load(map));bg_ff_start_fight(humans,bg_ff_default_fight(map));
        unsigned seen=0,maximum=0,travel=0;uint8_t cap=bg_ff.cap;
        for(unsigned tick=0;tick<60000&&!bg_match_finished();tick++){
            seen|=1u<<bg_ff.wave;
            for(unsigned h=0;h<humans;h++){bg_players[h].health=bg_armor_def(bg_players[h].armor)->health;bg_players[h].shield=bg_armor_def(bg_players[h].armor)->shield;}
            advance(1);assert(bg_ff.cap==cap&&ff_alive()<=cap&&!bg_ff_dropship.phase&&!bg_vehicle_count);
            if(ff_alive()>maximum)maximum=ff_alive();
            if(tick%90==0)for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[4+i].health>0)damage_player_profile(4+i,0,100000,false,false,0,false,false,1);
            if(bg_ff.phase==BG_FF_READY||bg_ff.phase==BG_FF_RECOVER)bg_ff.timer=fminf(bg_ff.timer,.1f);
            if(bg_ff.phase==BG_FF_RALLY){
                float target[3];assert(bg_ff_rally_point(target));travel++;assert(bg_ff.fight==BG_FF_STATION_SWEEP);
                for(unsigned h=0;h<humans;h++)assert(bg_ff_place_human(h));
            }
        }
        assert(bg_ff.phase==BG_FF_WON&&seen==63&&bg_ff.ground_arrivals>0&&bg_ff.ship_arrivals==0);
        assert(map==0?travel==0:travel==2);unsigned score=0;for(unsigned h=0;h<humans;h++)score+=bg_ff.score[h];assert(score==bg_ff.team_score);
        printf("PASS %s %uP: six waves, %u ground arrivals, max %u enemies, %u sector transitions, score %u\n",bg_ff_fight_name(bg_ff.fight),humans,bg_ff.ground_arrivals,maximum,travel,score);
        bg_reset();assert(bg_ff.active&&bg_ff.map==map&&bg_ff.wave==0&&bg_ff.team_score==0&&bg_vehicle_count==0);
        bg_pve_stop();bg_configure_mode(BG_MODE_SLAYER,NULL);bg_reset();assert(!bg_ff.active&&!ff_nav.nodes);
        bg_map_unload();
    }
}
static void checkpoints(void){
    assert(bg_map_load(3));bg_ff_start(2);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
    kill(0,-1);assert(bg_ff.respawn_reserved[0]&&bg_players[0].respawn==5&&bg_ff.lives==0);
    advance(152);assert(bg_players[0].health>0&&!bg_ff.respawn_reserved[0]&&bg_ff.retries==0);
    bg_ff.wave=2;bg_ff.score[0]=20;bg_ff.score[1]=30;bg_ff.team_score=50;statistics.kills[0]=2;ff_save_checkpoint();
    bg_ff.wave=3;bg_ff.team_score=500;bg_ff.score[0]=470;
    float at[3];bg_ff_rally_point(at);pve_spawn_actor(0,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,0,at,0);
    kill(0,-1);kill(1,-1);bg_ff_after_tick(1.f/30);
    assert(bg_ff.wave==2&&bg_ff.checkpoint==2&&bg_ff.retries==1&&bg_ff.team_score==50&&bg_ff.score[0]==20&&bg_ff.score[1]==30);
    assert(bg_pve_count==0&&bg_ff.phase==BG_FF_RECOVER&&bg_players[0].health>0&&bg_players[1].health>0);
    assert(statistics.kills[0]==2);
    bg_players[0].ammo=bg_players[0].reserve=0;ff_resupply();assert(bg_players[0].ammo==60&&bg_players[0].reserve==bg_weapon_defs[BG_W_AR].reserve);
    bg_ff.phase=BG_FF_WAVE;bg_ff.packet=bg_ff.packets=1;
    kill(0,-1);kill(1,-1);bg_ff_after_tick(1.f/30);
    assert(bg_ff.wave==3&&bg_ff.retries==1&&bg_players[0].health>0&&bg_players[1].health>0);
    bg_map_unload();assert(!ff_nav.nodes&&!bg_ff.active&&!bg_pve_is_active());
    assert(bg_map_load(1));bg_ff_start(1);assert(!bg_ff.active);
    assert(bg_map_load(9));bg_ff_start(1);assert(bg_ff.fight==BG_FF_ONSLAUGHT&&bg_vehicle_count==1&&!ff_nav.nodes);
    assert(bg_map_load(0));bg_ff_start(1);assert(bg_ff.fight==BG_FF_COURTYARD&&ff_nav.map==0&&bg_vehicle_count==0);
    puts("PASS five-second respawn, unlimited lives, sector checkpoint retry/score rollback, ammo resupply and cross-map cleanup");
}
int main(int argc,char**argv){
    if(argc==3){assert(!ff_nav_load((unsigned)strtoul(argv[2],NULL,10)));assert(!ff_nav.nodes);puts("PASS malformed navigation rejected");return 0;}
    entrances();navigation();live_movement(0);live_movement(3);full_sets();checkpoints();
    puts("PASS map-aware Firefight scenarios");
}
