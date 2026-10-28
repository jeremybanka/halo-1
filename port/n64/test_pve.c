#include <stdio.h>
#include <stdlib.h>
#include "game.c"
int main(void){
    bg_map_load(9);bg_pve_stage(4);
    FILE*f=fopen("halo64-assets/generated/pve/pve_nav.c","w");assert(f);
    fputs("#include <stdint.h>\nconst float bg_pve_nav_heights[625]={",f);
    unsigned nodes=0,links=0;
    for(unsigned i=0;i<PVE_NODES;i++){fprintf(f,"%a%s",(double)pve_nav_height[i],i+1==PVE_NODES?"};\n":",");nodes+=pve_nav_height[i]>-999;}
    fputs("const uint8_t bg_pve_nav_links[625]={",f);
    for(unsigned i=0;i<PVE_NODES;i++){fprintf(f,"%u%s",pve_nav_edges[i],i+1==PVE_NODES?"};\n":",");links+=!!pve_nav_edges[i];}fclose(f);
    printf("navigation nodes %u linked %u\n",nodes,links);
    for(unsigned i=0;i<bg_unit_count();i++)if(i<active_players||i>=4){bg_player*p=&bg_players[i];printf("unit %u %.3f %.3f %.3f clearance %u\n",i,p->pos[0],p->pos[1],p->pos[2],bg_terrain_clearance(p));assert(bg_terrain_clearance(p));}
    bg_input inputs[4]={0};for(unsigned tick=0;tick<90;tick++)bg_tick(inputs,1.f/30);
    for(unsigned i=0;i<5;i++)printf("actor%u action%u aware%u shots%u\n",i,bg_pve_actors[i].action,bg_pve_actors[i].aware,bg_pve_actors[i].shots);
    assert(bg_pve_actors[0].shots>0);
    for(unsigned i=0;i<5;i++)assert(bg_pve_actors[i].aware);
    actor_get(1)->stimuli.panic_type=1;actor_get(1)->stimuli.panic_prop_index=1;pve_decide(1);assert(bg_pve_actors[1].action!=_actor_action_flee);
    damage_player_profile(4,0,10000,false,false,0,false,false,1);for(unsigned i=0;i<10;i++)bg_tick(inputs,1.f/30);
    for(unsigned i=1;i<5;i++){assert(bg_pve_actors[i].action==_actor_action_flee);assert(bg_pve_actors[i].panic_time>0);}
    for(unsigned players=1;players<=4;players++){bg_pve_stage(players);for(unsigned tick=0;tick<3600;tick++)bg_tick(inputs,1.f/30);printf("PASS %u-player 120s ticks %u\n",players,bg_pve_tick_number);}
    bg_pve_stage(2);
    for(unsigned tick=0;tick<390;tick++){bg_pve_qa_input(inputs);bg_tick(inputs,1.f/30);}
    printf("QA leader health %.1f kills %d\n",bg_players[4].health,bg_players[0].score);assert(bg_players[4].health==0);
    bg_pve_stage(1);bg_pve_start(1);
    bg_player*elite=&bg_players[4];elite->pos[0]=bg_players[0].pos[0]+.8f;elite->pos[2]=bg_players[0].pos[2];elite->pos[1]=bg_floor(elite->pos[0],elite->pos[2],100)+.015f;
    bg_pve_actor*actor=&bg_pve_actors[0];actor->clip=PVE_FIRE;actor->time=0;actor->burst_pause=999;actor->shot_time=999;actor->aware=true;actor->target=0;
    float vitality=bg_players[0].health+bg_players[0].shield;
    for(unsigned tick=0;tick<18;tick++)bg_pve_tick(1.f/30);
    assert(bg_players[0].health+bg_players[0].shield==vitality);
    for(unsigned tick=0;tick<40;tick++)bg_pve_tick(1.f/30);
    assert(bg_players[0].health+bg_players[0].shield<vitality);assert(!actor->melee_pending);
    puts("PASS timed Elite melee after a fire animation");
    bg_pve_stage(4);bg_pve_start(8);
    unsigned last=BG_PLAYERS+7;float origin[3];memcpy(origin,bg_players[last].pos,12);origin[1]+=.3f;
    bg_projectile*needle=projectile(BG_P_NEEDLE,0,origin,(float[]){1,0,0},1,1,0);assert(needle);
    needle_attach(needle,last);assert(needle->attached==(int)last);float previous=bg_players[last].health;needle_detonate(needle);assert(bg_players[last].health<previous);
    bg_pve_stage(4);float blast[3];memcpy(blast,bg_players[5].pos,12);blast[1]+=.4f;
    explode_profile(blast,0,1000,3,BG_P_FRAG,BG_D_FRAG);assert(bg_players[5].health==0);assert(bg_pve_actors[1].clip==PVE_DEATH);
    bool dropped=false;for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].dropped&&bg_pickups[i].weapon==BG_W_PLASMA_PISTOL)dropped=true;assert(dropped);
    puts("PASS highest NPC-slot needle damage, grenade kills and weapon drops");
    bg_pve_stage(3);float start[3];memcpy(start,bg_players[0].pos,sizeof(start));
    bg_players[0].pos[0]+=2;bg_players[4].health=0;bg_reset();
    assert(bg_pve_is_active()&&bg_pve_count==5&&bg_players[4].health>0);
    assert(!memcmp(start,bg_players[0].pos,sizeof(start)));
    bg_pve_stop();assert(!bg_pve_is_active()&&bg_pve_count==0&&bg_unit_count()==3);
    bg_configure_mode(BG_MODE_CTF,NULL);bg_reset();assert(bg_objective_count>0);
    for(unsigned tick=0;tick<90;tick++)bg_tick(inputs,1.f/30);
    assert(!bg_pve_is_active()&&bg_pve_tick_number==0);
    bg_pve_stage(3);assert(bg_pve_is_active()&&bg_pve_count==5&&bg_objective_count==0);
    puts("PASS Firefight restart, three-player staging, leave to CTF and return to squad");
    puts("PASS squad source selectors, leader-death panic, navigation and split-screen simulation");return 0;
}
