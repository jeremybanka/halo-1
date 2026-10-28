#include <stdio.h>
#include <stdlib.h>
#include "game.c"
static uint16_t reference[PVE_ROUTE_NODES],queue[PVE_ROUTE_NODES];
static uint32_t navigation_test_seed=0x4e4156;
static unsigned random_node(void){navigation_test_seed=navigation_test_seed*1664525u+1013904223u;return navigation_test_seed%pve_route_count;}
static void reference_flood(unsigned goal){
    memset(reference,255,sizeof(reference));unsigned first=0,last=0;queue[last++]=goal;reference[goal]=0;
    while(first<last){unsigned n=queue[first++],raw=pve_route_grid[n];for(unsigned k=0;k<8;k++)if(pve_nav_edges[raw]&(1u<<k)){
        unsigned next=pve_route_id[pve_neighbor(raw,k)];if(reference[next]==UINT16_MAX){reference[next]=reference[n]+1;queue[last++]=next;}
    }}
}
static unsigned reference_choice(unsigned i,unsigned node){
    unsigned raw=pve_route_grid[node],chosen=raw;float best=reference[node];
    bool retreat=bg_pve_actors[i].action==_actor_action_flee||(bg_pve_actors[i].action==_actor_action_guard&&actor_get(i)->state.action_data.guard.cower);
    for(unsigned k=0;k<8;k++)if(pve_nav_edges[raw]&(1u<<k)){
        unsigned next=pve_neighbor(raw,k),steps=reference[pve_route_id[next]];if(steps==UINT16_MAX)continue;
        float point[3];pve_node_pos(next,point);float cost=steps;
        for(unsigned j=0;j<bg_pve_count;j++)if(j!=i&&bg_players[4+j].health>0&&distance2(point,bg_players[4+j].pos)<.64f)cost+=retreat?-3:3;
        if((retreat&&cost>best)||(!retreat&&cost<best)){best=cost;chosen=next;}
    }
    return chosen;
}
static void position_actor(unsigned i,unsigned node,unsigned goal){
    bg_pve_actor*a=&bg_pve_actors[i];a->occupied=a->aware=true;a->arrival=0;a->target=i%4;a->action=_actor_action_fight;
    a->generation++;bg_players[4+i].health=100;pve_node_pos(pve_route_grid[node],bg_players[4+i].pos);
    memcpy(a->destination,bg_players[4+i].pos,12);pve_node_pos(pve_route_grid[goal],a->last_seen);
}
static unsigned settle(unsigned i){
    unsigned ticks=0;while(pve_route_requests[i].pending){bg_pve_tick_number++;pve_routes_service();assert(++ticks<600);assert(bg_pve_navigation.max_work<=PVE_ROUTE_WORK);}
    return ticks;
}
int main(void){
    assert(bg_map_load(9));bg_pve_stage(4);bg_pve_start(2);
    unsigned maximum=0,comparisons=0,exact=0;
    for(unsigned sample=0;sample<240;sample++){
        unsigned goal=random_node(),node=random_node();reference_flood(goal);
        for(unsigned n=0;n<pve_route_count;n++)assert(pve_reachable(pve_route_grid[n],pve_route_grid[goal])==(reference[n]!=UINT16_MAX));
        position_actor(0,node,goal);
        if(sample%3==1)bg_pve_actors[0].action=_actor_action_flee;
        if(sample%3==2)bg_pve_actors[0].action=_actor_action_guard;
        actor_get(0)->state.action_data.guard.cower=sample%3==2;
        unsigned raw=pve_route_grid[node],friend_node=node;
        for(unsigned k=0;k<8;k++)if(pve_nav_edges[raw]&(1u<<k)){friend_node=pve_route_id[pve_neighbor(raw,k)];break;}
        position_actor(1,friend_node,goal); /* Exercise dynamic crowd penalties. */
        float memory[3];memcpy(memory,bg_pve_actors[0].last_seen,12);unsigned before=bg_pve_actors[0].decisions;
        pve_destination(0);unsigned ticks=settle(0);if(ticks>maximum)maximum=ticks;
        assert(!memcmp(memory,bg_pve_actors[0].last_seen,12)&&bg_pve_actors[0].decisions==before);
        float expected[3];pve_node_pos(reference_choice(0,node),expected);if(memcmp(expected,bg_pve_actors[0].destination,12))fprintf(stderr,"choice sample=%u node=%u goal=%u expected=%d actual=%d dist=%u ticks=%u\n",sample,node,goal,pve_node(expected),pve_node(bg_pve_actors[0].destination),reference[node],ticks);assert(!memcmp(expected,bg_pve_actors[0].destination,12));comparisons++;
        for(unsigned f=0;f<PVE_ROUTE_FIELDS;f++)if(pve_route_fields[f].valid&&pve_route_fields[f].goal==goal)
            for(unsigned n=0;n<pve_route_count;n++)if(pve_route_fields[f].distance[n]!=UINT16_MAX){assert(pve_route_fields[f].distance[n]==reference[n]);exact++;}
        if(reference[node]!=UINT16_MAX){unsigned fields=bg_pve_navigation.fields,searches=bg_pve_navigation.searches;
            pve_destination(0);assert(!pve_route_requests[0].pending&&bg_pve_navigation.fields==fields&&bg_pve_navigation.searches==searches);
        }
    }
    printf("PASS %u pursuit/retreat/cower choices, %u exact cached distances; max completion %u ticks\n",comparisons,exact,maximum);
    /* Several actors can share one endpoint without sharing perception state. */
    bg_pve_start(12);unsigned goal=0;while(pve_route_component[goal]!=0)goal++;
    for(unsigned i=0;i<12;i++){unsigned node;do node=random_node();while(pve_route_component[node]!=pve_route_component[goal]);position_actor(i,node,goal);pve_destination(i);}
    for(unsigned i=0;i<12;i++)settle(i);
    assert(bg_pve_navigation.fields==1);printf("PASS 12 actors/4 targets share one goal; max wait %u ticks\n",bg_pve_navigation.max_wait);
    /* Distinct remembered goals must coexist, even for the same human target. */
    bg_pve_start(12);
    for(unsigned i=0;i<12;i++){unsigned n=random_node(),g=n;for(unsigned k=0;k<8;k++)if(pve_nav_edges[pve_route_grid[n]]&(1u<<k)){g=pve_route_id[pve_neighbor(pve_route_grid[n],k)];break;}
        position_actor(i,n,g);bg_pve_actors[i].target=0;pve_destination(i);}
    for(unsigned i=0;i<12;i++)settle(i);
    unsigned fields=bg_pve_navigation.fields;assert(fields==12);for(unsigned i=0;i<12;i++)pve_destination(i);assert(bg_pve_navigation.fields==fields);
    bg_pve_start(12);
    for(unsigned i=0;i<12;i++){
        unsigned node,goal;do node=random_node();while(pve_route_component[node]!=0);do goal=random_node();while(pve_route_component[goal]!=0);
        position_actor(i,node,goal);pve_destination(i);
    }
    for(unsigned i=0;i<12;i++)settle(i);
    printf("PASS 12 simultaneous distinct long routes; max wait %u ticks, work limit %u\n",bg_pve_navigation.max_wait,bg_pve_navigation.max_work);
    /* In-flight jobs survive remembered-goal movement without starving, but
     * recycled slots, target changes, death and disconnected moves cancel. */
    bg_pve_start(1);unsigned n=0,g=0;for(unsigned i=0;i<pve_route_count;i++)if(pve_route_component[i]==pve_route_component[n])g=i;
    position_actor(0,n,g);pve_destination(0);pve_routes_service();unsigned original_field=pve_route_requests[0].field;bool was_pending=pve_route_requests[0].pending;
    pve_node_pos(pve_route_grid[n],bg_pve_actors[0].last_seen);pve_destination(0);
    if(was_pending)assert(pve_route_requests[0].field==(int)original_field);
    settle(0);pve_destination(0);settle(0);assert(pve_route_fields[pve_route_requests[0].field].goal==n);
    position_actor(0,n,g);pve_destination(0);bg_pve_actors[0].generation++;pve_routes_service();assert(!pve_route_requests[0].pending&&!pve_route_job.active);
    position_actor(0,n,g);pve_destination(0);bg_pve_actors[0].target=-1;pve_routes_service();assert(!pve_route_requests[0].pending&&!pve_route_job.active);
    position_actor(0,n,g);pve_destination(0);bg_players[4].health=0;pve_routes_service();assert(!pve_route_requests[0].pending&&!pve_route_job.active);
    bg_pve_start(1);assert(!pve_route_job.active&&!bg_pve_navigation.requests);for(unsigned i=0;i<PVE_ROUTE_FIELDS;i++)assert(!pve_route_fields[i].valid);
    puts("PASS goal sharing/isolation, moving-memory refresh, generation/target/death cancellation and restart; bounded work per tick");
    return 0;
}
