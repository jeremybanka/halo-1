/* CE source/ai/actors.c:actor_get_timeslice and actor_moving.c:
 * actor_destination_update service path refreshes separately from decisions.
 * source/ai/path.c uses a goal-directed cheapest-node heap, not a map flood.
 * This adapter keeps our authored grid and exact old unit-edge distance rule:
 * bounded A* fills only missing route distances in a shared goal-keyed cache.
 * Each committed suffix is an exact shortest distance. Cached suffixes terminate
 * later searches; perception/last_seen and local retreat/spacing are unchanged. */
#include <stdlib.h>
#define PVE_ROUTE_NODES 8192
#define PVE_ROUTE_FIELDS 16
#define PVE_ROUTE_LANDMARKS 8
#define PVE_ROUTE_WORK 256
#define PVE_ROUTE_NONE UINT16_MAX
static uint16_t pve_route_id[PVE_NODES],pve_route_grid[PVE_ROUTE_NODES];
static uint16_t pve_route_component[PVE_ROUTE_NODES];
static uint8_t pve_route_x[PVE_ROUTE_NODES],pve_route_z[PVE_ROUTE_NODES];
static unsigned pve_route_count,pve_route_clock;
/* Keep one node's eight landmark distances in 16 contiguous bytes. */
static uint16_t pve_route_landmarks[PVE_ROUTE_NODES][PVE_ROUTE_LANDMARKS];
typedef struct {
    uint16_t distance[PVE_ROUTE_NODES],goal;
    unsigned used;
    bool valid;
} pve_route_field;
#ifdef BG_ENEMY_VEHICLES
static pve_route_field *pve_route_fields;
#else
static pve_route_field pve_route_fields[PVE_ROUTE_FIELDS];
#endif
typedef struct {
    uint16_t node,generation;
    int field,target;
    unsigned since;
    bool pending;
} pve_route_request;
static pve_route_request pve_route_requests[BG_PVE_MAX];
static struct {
    uint16_t heap[PVE_ROUTE_NODES+1];
    struct {uint16_t cost,estimate,parent,stamp,position,pad[3];} nodes[PVE_ROUTE_NODES];
    uint16_t epoch,best,best_node,cursor;
    unsigned count,actor,field;
    bool active,committing;
} pve_route_job;
static unsigned pve_route_next_actor;
bg_pve_navigation_profile bg_pve_navigation;
uint32_t bg_pve_nav_us;

static void pve_routes_reset(bool initialize){
#ifdef BG_ENEMY_VEHICLES
    if(!pve_route_fields){
        pve_route_fields=malloc(PVE_ROUTE_FIELDS*sizeof(*pve_route_fields));
        assert(pve_route_fields);
    }
#endif
    if(initialize){
        memset(pve_route_id,255,sizeof(pve_route_id));pve_route_count=0;
        for(unsigned n=0;n<PVE_NODES;n++)if(pve_nav_height[n]>-999&&pve_nav_edges[n]){
            assert(pve_route_count<PVE_ROUTE_NODES);unsigned id=pve_route_count++;
            pve_route_id[n]=id;pve_route_grid[id]=n;
            pve_route_x[id]=n%PVE_CELLS%PVE_GRID;pve_route_z[id]=n%PVE_CELLS/PVE_GRID;
        }
        /* Only at map initialization: immutable connected-region labels answer
         * arrival reachability exactly, without touching any actor's routes. */
        memset(pve_route_component,255,sizeof(pve_route_component));unsigned component=0;
        for(unsigned id=0;id<pve_route_count;id++)if(pve_route_component[id]==PVE_ROUTE_NONE){
            unsigned first=0,last=0;pve_route_job.heap[last++]=id;pve_route_component[id]=component;
            while(first<last){unsigned current=pve_route_job.heap[first++],n=pve_route_grid[current];
                for(unsigned k=0;k<8;k++)if(pve_nav_edges[n]&(1u<<k)){
                    unsigned next=pve_route_id[pve_neighbor(n,k)];assert(next<pve_route_count);
                    if(pve_route_component[next]==PVE_ROUTE_NONE){pve_route_component[next]=component;pve_route_job.heap[last++]=next;}
                }
            }
            component++;
        }
        /* Exact landmark distances strengthen the goal heuristic around canyon
         * detours. Compute once while loading, never in the simulation loop.
         * |d(L,a)-d(L,b)| is a consistent lower bound on d(a,b). Use farthest
         * point sampling in the largest component; small islands keep Chebyshev. */
        uint16_t*sizes=pve_route_fields[0].distance;memset(sizes,0,sizeof(pve_route_fields[0].distance));unsigned largest=0;
        for(unsigned n=0;n<pve_route_count;n++)sizes[pve_route_component[n]]++;
        for(unsigned c=1;c<component;c++)if(sizes[c]>sizes[largest])largest=c;
        unsigned landmark=0;while(pve_route_component[landmark]!=largest)landmark++;
        for(unsigned l=0;l<PVE_ROUTE_LANDMARKS;l++){
            for(unsigned n=0;n<pve_route_count;n++)pve_route_landmarks[n][l]=PVE_ROUTE_NONE;
            unsigned first=0,last=0;pve_route_job.heap[last++]=landmark;pve_route_landmarks[landmark][l]=0;
            while(first<last){unsigned n=pve_route_job.heap[first++],raw=pve_route_grid[n];
                for(unsigned k=0;k<8;k++)if(pve_nav_edges[raw]&(1u<<k)){
                    unsigned next=pve_route_id[pve_neighbor(raw,k)];if(pve_route_landmarks[next][l]==PVE_ROUTE_NONE){pve_route_landmarks[next][l]=pve_route_landmarks[n][l]+1;pve_route_job.heap[last++]=next;}
                }
            }
            unsigned farthest=0;
            for(unsigned n=0;n<pve_route_count;n++)if(pve_route_component[n]==largest){
                unsigned nearest=PVE_ROUTE_NONE;for(unsigned j=0;j<=l;j++)if(pve_route_landmarks[n][j]<nearest)nearest=pve_route_landmarks[n][j];
                if(nearest>farthest){farthest=nearest;landmark=n;}
            }
        }
    }
    for(unsigned i=0;i<PVE_ROUTE_FIELDS;i++)pve_route_fields[i].valid=false;
    memset(pve_route_requests,0,sizeof(pve_route_requests));memset(&pve_route_job,0,sizeof(pve_route_job));
    memset(&bg_pve_navigation,0,sizeof(bg_pve_navigation));bg_pve_nav_us=0;pve_route_clock=pve_route_next_actor=0;
}
#ifdef BG_ENEMY_VEHICLES
static void pve_routes_release(void){
    if(!pve_route_fields)return;
    pve_routes_reset(false);
    free(pve_route_fields);pve_route_fields=NULL;
}
#endif
static bool pve_reachable(int a,int b){
    if(a<0||b<0)return false;
    unsigned x=pve_route_id[a],y=pve_route_id[b];
    return x!=PVE_ROUTE_NONE&&y!=PVE_ROUTE_NONE&&pve_route_component[x]==pve_route_component[y];
}
static bool pve_route_valid(unsigned i){
    const pve_route_request*r=&pve_route_requests[i];const bg_pve_actor*a=&bg_pve_actors[i];
    return r->pending&&i<bg_pve_count&&a->occupied&&a->generation==r->generation&&
        a->target==r->target&&!a->arrival&&bg_players[BG_PLAYERS+i].health>0;
}
static int pve_route_field_for(unsigned goal){
    bool pinned[PVE_ROUTE_FIELDS]={0};
    for(unsigned i=0;i<BG_PVE_MAX;i++)if(pve_route_valid(i))pinned[pve_route_requests[i].field]=true;
    if(pve_route_job.active)pinned[pve_route_job.field]=true;
    int slot=-1;unsigned oldest=UINT32_MAX;
    for(unsigned f=0;f<PVE_ROUTE_FIELDS;f++){
        pve_route_field*c=&pve_route_fields[f];
        if(c->valid&&c->goal==goal){c->used=++pve_route_clock;bg_pve_navigation.shared++;return f;}
        if(!pinned[f]&&(!c->valid||c->used<oldest)){slot=f;oldest=c->valid?c->used:0;}
    }
    assert(slot>=0);pve_route_field*c=&pve_route_fields[slot];
    if(c->valid)bg_pve_navigation.evictions++;
    /* Bounded 16 KiB metadata reset, not a traversal of the map. */
    memset(c->distance,255,sizeof(c->distance));c->goal=goal;c->distance[goal]=0;c->valid=true;c->used=++pve_route_clock;
    bg_pve_navigation.fields++;return slot;
}
static unsigned pve_route_missing(const pve_route_request*r){
    const pve_route_field*c=&pve_route_fields[r->field];unsigned n=pve_route_grid[r->node];
    if(c->distance[r->node]==PVE_ROUTE_NONE)return r->node;
    for(unsigned k=0;k<8;k++)if(pve_nav_edges[n]&(1u<<k)){
        unsigned next=pve_route_id[pve_neighbor(n,k)];if(c->distance[next]==PVE_ROUTE_NONE)return next;
    }
    return PVE_ROUTE_NONE;
}
static void pve_route_apply(unsigned i){
    const pve_route_request*r=&pve_route_requests[i];const pve_route_field*c=&pve_route_fields[r->field];
    bg_pve_actor*a=&bg_pve_actors[i];unsigned node=pve_route_grid[r->node],chosen=node;float best=c->distance[r->node];
    bool retreat=a->action==_actor_action_flee||(a->action==_actor_action_guard&&actor_get(i)->state.action_data.guard.cower);
    /* Same neighbor order, strict comparison and dynamic spacing as the old
     * full flood. Both pursuit and retreat require all neighbor distances. */
    for(unsigned k=0;k<8;k++)if(pve_nav_edges[node]&(1u<<k)){
        unsigned next=pve_neighbor(node,k);float cost=c->distance[pve_route_id[next]],point[3];pve_node_pos(next,point);
        for(unsigned j=0;j<bg_pve_count;j++)if(j!=i&&bg_players[BG_PLAYERS+j].health>0&&distance2(point,bg_players[BG_PLAYERS+j].pos)<.64f)cost+=retreat?-3:3;
        if((retreat&&cost>best)||(!retreat&&cost<best)){best=cost;chosen=next;}
    }
    pve_node_pos(chosen,a->destination);
}
static void pve_destination(unsigned i){
    bg_pve_actor*a=&bg_pve_actors[i];if(a->target<0)return;
    int node=pve_node(bg_players[BG_PLAYERS+i].pos),goal=pve_node(a->last_seen);a->path_queries++;
    pve_route_request*r=&pve_route_requests[i];
    if(!pve_reachable(node,goal)){
        r->pending=false;if(node>=0)pve_node_pos(node,a->destination);return;
    }
    /* Let an already scheduled refresh finish. The actor's perception memory
     * still updates normally; the next refresh uses the new remembered goal.
     * This prevents a moving target from continually cancelling useful work. */
    if(pve_route_valid(i))return;
    r->pending=false;r->field=pve_route_field_for(pve_route_id[goal]);r->node=pve_route_id[node];
    r->generation=a->generation;r->target=a->target;r->since=bg_pve_tick_number;
    if(pve_route_missing(r)==PVE_ROUTE_NONE){bg_pve_navigation.ready++;pve_route_apply(i);return;}
    r->pending=true;bg_pve_navigation.requests++;
    /* Keep the previously certified waypoint while a refresh is pending.
     * New actors begin at their own position. Never move directly through a
     * wall or substitute a living target's position for last_seen. */
}
static unsigned pve_route_heuristic(unsigned n){
    unsigned goal=pve_route_fields[pve_route_job.field].goal;
    int dx=abs((int)pve_route_x[n]-pve_route_x[goal]),dz=abs((int)pve_route_z[n]-pve_route_z[goal]);
    unsigned lower=dx>dz?dx:dz;
    for(unsigned l=0;l<PVE_ROUTE_LANDMARKS;l++){
        unsigned a=pve_route_landmarks[n][l],b=pve_route_landmarks[goal][l];
        if(a==PVE_ROUTE_NONE||b==PVE_ROUTE_NONE)continue;
        unsigned bound=a>b?a-b:b-a;if(bound>lower)lower=bound;
    }
    return lower;
}
static bool pve_route_less(unsigned a,unsigned b){
    if(pve_route_job.nodes[a].estimate!=pve_route_job.nodes[b].estimate)return pve_route_job.nodes[a].estimate<pve_route_job.nodes[b].estimate;
    if(pve_route_job.nodes[a].cost!=pve_route_job.nodes[b].cost)return pve_route_job.nodes[a].cost>pve_route_job.nodes[b].cost;
    return a<b;
}
static void pve_route_up(unsigned at){
    unsigned n=pve_route_job.heap[at];
    while(at>1&&pve_route_less(n,pve_route_job.heap[at/2])){
        pve_route_job.heap[at]=pve_route_job.heap[at/2];pve_route_job.nodes[pve_route_job.heap[at]].position=at;at/=2;
    }
    pve_route_job.heap[at]=n;pve_route_job.nodes[n].position=at;
}
static unsigned pve_route_pop(void){
    unsigned result=pve_route_job.heap[1],n=pve_route_job.heap[pve_route_job.count--],at=1;
    pve_route_job.nodes[result].position=0;
    if(pve_route_job.count){
        while(at*2<=pve_route_job.count){unsigned child=at*2;
            if(child<pve_route_job.count&&pve_route_less(pve_route_job.heap[child+1],pve_route_job.heap[child]))child++;
            if(!pve_route_less(pve_route_job.heap[child],n))break;
            pve_route_job.heap[at]=pve_route_job.heap[child];pve_route_job.nodes[pve_route_job.heap[at]].position=at;at=child;
        }
        pve_route_job.heap[at]=n;pve_route_job.nodes[n].position=at;
    }
    return result;
}
static void pve_route_begin(unsigned actor,unsigned start){
    pve_route_job.active=true;pve_route_job.committing=false;pve_route_job.actor=actor;pve_route_job.field=pve_route_requests[actor].field;
    if(!++pve_route_job.epoch){for(unsigned n=0;n<pve_route_count;n++)pve_route_job.nodes[n].stamp=0;pve_route_job.epoch=1;}
    pve_route_job.count=1;pve_route_job.heap[1]=start;pve_route_job.nodes[start].position=1;
    pve_route_job.nodes[start].stamp=pve_route_job.epoch;pve_route_job.nodes[start].cost=0;pve_route_job.nodes[start].parent=PVE_ROUTE_NONE;
    pve_route_job.nodes[start].estimate=pve_route_heuristic(start);pve_route_job.best=PVE_ROUTE_NONE;bg_pve_navigation.searches++;
}
static void pve_route_step(void){
    pve_route_field*c=&pve_route_fields[pve_route_job.field];
    if(pve_route_job.committing){
        unsigned n=pve_route_job.cursor,distance=pve_route_job.best-pve_route_job.nodes[n].cost;
        assert(c->distance[n]==PVE_ROUTE_NONE||c->distance[n]==distance);c->distance[n]=distance;bg_pve_navigation.committed++;
        pve_route_job.cursor=pve_route_job.nodes[n].parent;
        if(pve_route_job.cursor==PVE_ROUTE_NONE)pve_route_job.active=false;
        return;
    }
    if(!pve_route_job.count||(pve_route_job.best!=PVE_ROUTE_NONE&&pve_route_job.nodes[pve_route_job.heap[1]].estimate>=pve_route_job.best)){
        assert(pve_route_job.best!=PVE_ROUTE_NONE);pve_route_job.committing=true;pve_route_job.cursor=pve_route_job.best_node;return;
    }
    unsigned n=pve_route_pop(),cost=pve_route_job.nodes[n].cost,raw=pve_route_grid[n];bg_pve_navigation.expanded++;
    if(c->distance[n]!=PVE_ROUTE_NONE){
        unsigned total=cost+c->distance[n];if(total<pve_route_job.best){pve_route_job.best=total;pve_route_job.best_node=n;}
        return; /* An exact cached suffix replaces expansion beyond this node. */
    }
    for(unsigned k=0;k<8;k++)if(pve_nav_edges[raw]&(1u<<k)){
        unsigned next=pve_route_id[pve_neighbor(raw,k)],g=cost+1;
        if(pve_route_job.nodes[next].stamp==pve_route_job.epoch&&g>=pve_route_job.nodes[next].cost)continue;
        bool fresh=pve_route_job.nodes[next].stamp!=pve_route_job.epoch;
        /* A consistent heuristic cannot improve a closed node. */
        assert(fresh||pve_route_job.nodes[next].position);
        pve_route_job.nodes[next].stamp=pve_route_job.epoch;pve_route_job.nodes[next].cost=g;pve_route_job.nodes[next].parent=n;
        pve_route_job.nodes[next].estimate=g+pve_route_heuristic(next);
        if(fresh){assert(pve_route_job.count<PVE_ROUTE_NODES);pve_route_job.nodes[next].position=++pve_route_job.count;pve_route_job.heap[pve_route_job.count]=next;}
        pve_route_up(pve_route_job.nodes[next].position);
    }
}
static void pve_routes_service(void){
#ifdef N64
    uint32_t begin=get_ticks_us();
#endif
    /* Update request origins once, before servicing work. Goal/generation remain
     * pinned until completion; teleports/recycled slots cannot inherit a route. */
    for(unsigned i=0;i<BG_PVE_MAX;i++)if(pve_route_requests[i].pending){
        pve_route_request*r=&pve_route_requests[i];int raw=pve_route_valid(i)?pve_node(bg_players[BG_PLAYERS+i].pos):-1;
        if(raw<0||!pve_reachable(raw,pve_route_grid[pve_route_fields[r->field].goal]))r->pending=false;
        else r->node=pve_route_id[raw];
    }
    if(pve_route_job.active&&(!pve_route_valid(pve_route_job.actor)||pve_route_requests[pve_route_job.actor].field!=(int)pve_route_job.field))pve_route_job.active=false;
    unsigned work=0;
    while(work<PVE_ROUTE_WORK){
        if(!pve_route_job.active){
            bool found=false;
            for(unsigned turn=0;turn<BG_PVE_MAX;turn++){
                unsigned i=pve_route_next_actor++%BG_PVE_MAX;pve_route_request*r=&pve_route_requests[i];if(!r->pending)continue;
                unsigned missing=pve_route_missing(r);
                if(missing==PVE_ROUTE_NONE){
                    pve_route_apply(i);r->pending=false;unsigned wait=bg_pve_tick_number-r->since;
                    bg_pve_navigation.completed++;bg_pve_navigation.wait_ticks+=wait;
                    if(wait>bg_pve_navigation.max_wait)bg_pve_navigation.max_wait=wait;
                    continue;
                }
                pve_route_begin(i,missing);found=true;break;
            }
            if(!found)break;
        }
        pve_route_step();work++;
    }
    bg_pve_navigation.work+=work;if(work>bg_pve_navigation.max_work)bg_pve_navigation.max_work=work;
#ifdef N64
    unsigned elapsed=get_ticks_us()-begin;bg_pve_nav_us+=elapsed;bg_pve_navigation.service_us+=elapsed;
    if(elapsed>bg_pve_navigation.max_us)bg_pve_navigation.max_us=elapsed;
#endif
}
