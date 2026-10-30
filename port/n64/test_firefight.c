#include <stdio.h>
#include <stdlib.h>
#include "game.c"
static void advance(unsigned ticks){bg_input in[4]={0};for(unsigned n=0;n<ticks;n++)bg_tick(in,1.f/30);}
static void clear_enemies(void){for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[4+i].health>0&&bg_pve_actors[i].arrival!=1)damage_player_profile(4+i,0,100000,false,false,0,false,false,1);}
#ifdef BG_PVE_ROSTER
#include "test_pve_roster.inc"
#endif
int main(void){
    assert(bg_map_load(9));
    for(unsigned players=1;players<=4;players++){
        bg_ff_start(players);assert(bg_ff.cap==4+players*2&&bg_ff.lives==10&&bg_pve_count==0);
        for(unsigned h=0;h<players;h++){assert(bg_players[h].health==100);assert(bg_terrain_clearance(&bg_players[h]));}
        for(unsigned formation=0;formation<BG_FF_FORMATIONS;formation++){
            unsigned ground=0,ship=0;
            for(unsigned z=0;z<FF_ZONES;z++){
                float points[8][3],landing[3];ground+=ff_zone_points(z,formation,true,points,landing);ship+=ff_zone_points(z,formation,false,points,landing);
            }
            printf("%uP formation %u ground %u ship %u\n",players,formation,ground,ship);assert(ground>0&&ship>0);
        }
        /* Complete the authoritative lifecycle with fixture kills. This is
         * deliberately separate from combat/balance and native benchmarks. */
        unsigned transitions=0,last=99,max_live=0;
        for(unsigned tick=0;tick<60000&&!bg_match_finished();tick++){
            unsigned wave=bg_ff.round*5+bg_ff.wave;if(wave!=last){last=wave;transitions++;}
            for(unsigned h=0;h<players;h++){bg_players[h].health=100;bg_players[h].shield=100;}
            advance(1);unsigned live=ff_alive();if(live>max_live)max_live=live;assert(live<=bg_ff.cap);
            clear_enemies();
            if(bg_ff.phase==BG_FF_READY||bg_ff.phase==BG_FF_RECOVER)bg_ff.timer=fminf(bg_ff.timer,.1f);
            if(bg_ff.phase==BG_FF_BONUS&&bg_ff.packet>=2)bg_ff.timer=0;
        }
        printf("%uP phases %u state %u score %u ticks %u maxlive %u ground %u ships %u failures %u\n",players,transitions,bg_ff.phase,bg_ff.team_score,bg_ff.tick,max_live,bg_ff.ground_arrivals,bg_ff.ship_arrivals,bg_ff.arrival_failures);
        assert(bg_ff.phase==BG_FF_WON&&transitions==15&&bg_ff.team_score>0);unsigned total=0;for(unsigned h=0;h<players;h++)total+=bg_ff.score[h];assert(total==bg_ff.team_score);
        bg_reset();assert(bg_ff.active&&bg_ff.round==0&&bg_ff.lives==10&&bg_ff.team_score==0);
        bg_ff.lives=1;for(unsigned h=0;h<players;h++)kill(h,-1);
        assert(bg_ff.lives==0&&bg_ff.respawn_reserved[0]);for(unsigned h=1;h<players;h++)assert(!bg_ff.respawn_reserved[h]);
        advance(305);assert(bg_players[0].health>0);assert(!bg_ff.respawn_reserved[0]);kill(0,-1);advance(1);assert(bg_ff.phase==BG_FF_LOST);
    }
    bg_ff_start(4);bg_ff.phase=BG_FF_WAVE;bg_ff.wave=4;bg_ff.packet=bg_ff.packets=1;bg_ff.lives=0;
    for(unsigned h=0;h<4;h++)kill(h,-1);bg_ff_after_tick(1.f/30);assert(bg_ff.phase==BG_FF_RECOVER&&bg_ff.round==1&&bg_ff.lives==4);for(unsigned h=0;h<4;h++)assert(bg_players[h].health>0);
    bg_ff_start(1);bg_ff.phase=BG_FF_BONUS;bg_ff.timer=10;kill(0,-1);bg_ff_after_tick(1.f/30);assert(bg_ff.phase==BG_FF_WON&&bg_ff.lives==10);
    bg_ff_start(4);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=999;assert(ff_arrive(BG_FF_HUNTERS,true));advance(750);for(unsigned i=0;i<2;i++)assert(!bg_pve_actors[i].arrival);assert(!bg_ff_dropship.phase);
    /* Execute both delivery paths for every catalog entry. Killing an exiting
     * passenger must preserve its death pose and cannot resurrect the unit. */
    for(unsigned f=0;f<BG_FF_FORMATIONS;f++)for(unsigned ship=0;ship<2;ship++){
        bg_ff_start(4);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
        assert(ff_arrive(f,ship));unsigned packet=bg_ff.packet;
        if(ship){
            for(unsigned t=0;t<300;t++)ff_ship_tick(1.f/30);
            unsigned unit=bg_ff_dropship.actors[0];assert(bg_pve_actors[unit].arrival==2);
            pve_killed(4+unit,0);
            for(unsigned t=0;t<500;t++)ff_ship_tick(1.f/30);
            assert(!bg_ff_dropship.phase&&!bg_pve_actors[unit].arrival);
            assert(bg_players[4+unit].health==0&&bg_pve_actors[unit].clip==PVE_DEATH);
        }else for(unsigned i=0;i<bg_pve_count;i++)assert(ff_hidden(bg_players[4+i].pos,bg_pve_definitions[bg_pve_actors[i].kind].height));
        bg_ff.cap=ff_alive();unsigned count=bg_pve_count;
        assert(!ff_arrive(BG_FF_PATROL,false)&&bg_ff.packet==packet&&bg_pve_count==count);
    }
    /* Material-dependent damage: shield gaps, Hunter weak skin, and armor. */
    bg_ff_start(1);float enemy_pos[3]={4,bg_floor(4,0,12)+.015f,0};
    pve_spawn_actor(0,BG_PVE_JACKAL,BG_W_PLASMA_PISTOL,0,enemy_pos,3.14159265f);
    float shield=bg_players[4].shield,health=bg_players[4].health;
    damage_player_region(4,0,20,false,false,BG_D_PLASMA_PISTOL,false,false,1,(4<<8)|1);
    assert(bg_players[4].shield<shield&&bg_players[4].health==health);shield=bg_players[4].shield;
    damage_player_region(4,0,20,false,false,BG_D_PISTOL,false,false,1,(1<<8)|1);
    assert(bg_players[4].shield==shield&&bg_players[4].health<health);
    pve_spawn_actor(0,BG_PVE_HUNTER,BG_W_PLASMA_RIFLE,0,enemy_pos,3.14159265f);health=bg_players[4].health;
    damage_player_region(4,0,20,false,false,BG_D_PISTOL,false,false,1,(2<<8)|1);assert(bg_players[4].health==health);
    damage_player_region(4,0,20,false,true,BG_D_PISTOL,false,false,1,(3<<8)|2);assert(bg_players[4].health==0);
    unsigned score=bg_ff.team_score;damage_player_region(4,0,20,false,true,BG_D_PISTOL,false,false,1,(3<<8)|2);assert(bg_ff.team_score==score);
    /* Production rays identify actual animated shield and body polygons; a
     * needle reflects from the shield and attaches through a body opening. */
    pve_spawn_actor(0,BG_PVE_JACKAL,BG_W_PLASMA_PISTOL,0,enemy_pos,0);
    int shield_region=0,body_region=0;float shield_origin[3]={0},shield_dir[3]={0};
    for(unsigned side=0;side<4;side++)for(unsigned y=1;y<20;y++)for(int x=-10;x<=10;x++){
        float co=cosf(side*1.5707963f),si=sinf(side*1.5707963f);
        float o[3]={enemy_pos[0]-co*3-si*x*.04f,enemy_pos[1]+y*.04f,enemy_pos[2]+si*3-co*x*.04f},d[3]={co,0,-si};int r=0;
        if(bg_pve_hit_ray(4,o,d,6,&r)<6){unsigned mi=(r>>8)-1;if(bg_pve_hits[BG_PVE_JACKAL].rules[mi].material==16&&dot(pve_hit_normals[0],d)<-.9f){shield_region=r;memcpy(shield_origin,o,12);memcpy(shield_dir,d,12);}else if(bg_pve_hits[BG_PVE_JACKAL].rules[mi].material!=16)body_region=r;}
    }
    assert(shield_region&&body_region);int r=0;bg_pve_hit_ray(4,shield_origin,shield_dir,6,&r);assert(r==shield_region);
    bg_projectile needle={.kind=BG_P_NEEDLE,.tracked=4};for(unsigned k=0;k<3;k++)needle.velocity[k]=shield_dir[k]*10;
    assert(pve_needle_impact(&needle,4,shield_region)&&needle.tracked==-1&&dot(needle.velocity,shield_dir)<0);
    assert(!pve_needle_impact(&needle,4,body_region));
    /* A dying actor's live projectile keeps its identity until expiry. */
    pve_spawn_actor(0,BG_PVE_ELITE,BG_W_PLASMA_RIFLE,0,enemy_pos,0);
    bg_projectile*q=projectile(BG_P_PLASMA,4,enemy_pos,(float[]){1,0,0},1,1,0);assert(q);pve_killed(4,0);bg_pve_actors[0].death_time=10;
    assert(!ff_recyclable(0));q->active=false;assert(ff_recyclable(0));
    /* Grenade checks run through the original CE handler. */
    bg_ff_start(1);pve_spawn_actor(0,BG_PVE_GRUNT,BG_W_PLASMA_PISTOL,0,enemy_pos,3.14159265f);
    bg_pve_actor*a=&bg_pve_actors[0];a->aware=a->visible=true;a->target=0;a->grenades=1;actor_get(0)->meta.variant_definition_index=BG_PVE_GRUNT;actor_get(0)->target.target_type=5;
    actor_get(0)->state.action=_actor_action_flee;actor_get(0)->state.combat_status=5;a->panic_time=10;
    assert(actor_action_test_grenade(0));
    for(unsigned tick=0;tick<300&&!a->throw_pending;tick+=15){bg_pve_tick_number=tick;actor_action_handle_grenade_throwing(0);}
    assert(a->throw_pending&&a->clip==PVE_THROW);
    for(unsigned tick=0;tick<65;tick++)bg_pve_tick(1.f/30);
    assert(a->grenades==0&&!a->throw_pending);bool plasma=false;for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){q=bg_projectile_at(i);plasma|=q&&q->active&&q->kind==BG_P_PLASMA_GRENADE&&q->owner==4;}assert(plasma);
    puts("PASS authored shield/weak-point damage, exactly-once score, ordnance-safe recycling and CE grenade decision/release");
    bg_pve_stop();bg_configure_mode(BG_MODE_CTF,NULL);bg_reset();assert(!bg_ff.active&&!bg_pve_is_active()&&bg_objective_count>0);
    puts("PASS finite sets 1-4P, all formation routes, bounded actor recycling, shared reserves, last-death clear, bonus death, restart and PvP return");
#ifdef BG_PVE_ROSTER
    roster_acceptance();
#endif
    return 0;
}
