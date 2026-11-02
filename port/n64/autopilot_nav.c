#include "autopilot_nav.h"
#include "map.h"
#include "game.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifdef N64
#include <libdragon.h>
#endif
#define PATH 512
#define PORTALS 32
typedef struct {uint16_t from,to;float source[3];} portal;
static struct {unsigned nx,nz,layers,cells,nodes,grid_count,map;float step,ox,oz,oy;int16_t *height;uint8_t *edges,*jumps;uint16_t *g,*parent,*heap,*grid,*cell,*component;uint16_t *at;unsigned used,bytes;portal portals[PORTALS];unsigned portal_count;} graph;
static struct {uint16_t start,goal,path[PATH],count,index;bool pending;} routes[BG_PLAYERS];
static uint16_t neighbor(uint16_t node,unsigned k);
static int owner=-1;static unsigned next_owner,last_work;
static const int dx[8]={1,-1,0,0,1,1,-1,-1},dz[8]={0,0,1,-1,1,-1,1,-1};
static bool read_failed;
static uint16_t read16(FILE *f){int a=fgetc(f),b=fgetc(f);if(a<0||b<0){read_failed=true;return 0;}return (unsigned)(a<<8)|b;}
static float readfloat(FILE *f){uint32_t b=(uint32_t)read16(f)<<16;b|=read16(f);float v;memcpy(&v,&b,4);return v;}
void bg_autonav_reset(void){
    free(graph.height);free(graph.edges);free(graph.jumps);free(graph.g);free(graph.parent);free(graph.heap);free(graph.at);free(graph.grid);free(graph.cell);free(graph.component);memset(&graph,0,sizeof(graph));memset(routes,0,sizeof(routes));owner=-1;next_owner=last_work=0;
}
unsigned bg_autonav_memory(void){return graph.bytes;}
unsigned bg_autonav_work(void){return last_work;}
void bg_autonav_position(uint16_t n,float p[3]){unsigned cell=graph.cell[n]%graph.cells;p[0]=graph.ox+cell%graph.nx*graph.step;p[1]=graph.oy+graph.height[n]/128.f;p[2]=graph.oz+cell/graph.nx*graph.step;}
uint16_t bg_autonav_node(const float p[3]){
    if(!graph.height)return BG_NAV_NONE;
    int x=lroundf((p[0]-graph.ox)/graph.step),z=lroundf((p[2]-graph.oz)/graph.step);uint16_t best=BG_NAV_NONE;float cost=1e9f;
    for(int j=-2;j<=2;j++)for(int i=-2;i<=2;i++){
        int nx=x+i,nz=z+j;if(nx<0||nz<0||nx>=(int)graph.nx||nz>=(int)graph.nz)continue;
        for(unsigned l=0;l<graph.layers;l++){unsigned key=l*graph.cells+nz*graph.nx+nx,n=graph.grid[key];if(n==BG_NAV_NONE)continue;
    float y=graph.oy+graph.height[n]/128.f-p[1];if(fabsf(y)>.75f)continue;
    float a=graph.ox+nx*graph.step-p[0],b=graph.oz+nz*graph.step-p[2],d=a*a+b*b+4*y*y;if(d<cost){best=n;cost=d;}}
    }
    return best;
}
bool bg_autonav_load(void){
    if(graph.height&&graph.map==bg_map_id())return true;
    bg_autonav_reset();char path[2048];
#ifdef N64
    snprintf(path,sizeof(path),"rom:/autonav-%u.bin",bg_map_id());
#else
    const char *directory=getenv("BG_AUTONAV_DIRECTORY");if(!directory)return false;
    snprintf(path,sizeof(path),"%s/autonav-%u.bin",directory,bg_map_id());
#endif
    FILE *f=fopen(path,"rb");if(!f)return false;read_failed=false;
    char magic[4];bool ok=fread(magic,1,4,f)==4&&!memcmp(magic,"GNV3",4);
    graph.nx=read16(f);graph.nz=read16(f);graph.layers=read16(f);(void)read16(f);graph.step=readfloat(f);graph.ox=readfloat(f);graph.oz=readfloat(f);graph.oy=readfloat(f);graph.cells=graph.nx*graph.nz;graph.grid_count=graph.cells*graph.layers;graph.nodes=read16(f);(void)read16(f);
    ok=ok&&graph.nx>=2&&graph.nz>=2&&graph.nx<=104&&graph.nz<=104&&graph.layers<=6&&graph.layers>0&&graph.nodes>0&&graph.nodes<=graph.grid_count&&graph.grid_count<BG_NAV_NONE&&graph.step>=.39f&&isfinite(graph.step)&&isfinite(graph.ox)&&isfinite(graph.oz)&&isfinite(graph.oy);
    if(!ok){fclose(f);bg_autonav_reset();return false;}
    unsigned n=graph.nodes;graph.height=malloc(n*2);graph.edges=calloc(n,1);graph.jumps=calloc(n,1);graph.g=malloc(n*2);graph.parent=malloc(n*2);graph.heap=malloc(n*2);graph.at=malloc(n*2);graph.cell=malloc(n*2);graph.component=malloc(n*2);graph.grid=malloc(graph.grid_count*2);graph.bytes=n*16+graph.grid_count*2;
    if(!graph.height||!graph.edges||!graph.jumps||!graph.g||!graph.parent||!graph.heap||!graph.at||!graph.cell||!graph.component||!graph.grid){fclose(f);bg_autonav_reset();return false;}
    memset(graph.grid,255,graph.grid_count*2);unsigned written=0;
    for(unsigned i=0;i<graph.grid_count&&ok;){unsigned code=read16(f),count=code&32767;if(!count||count>graph.grid_count-i){ok=false;break;}
        if(!(code&32768)){for(unsigned j=i;j<i+count;j++){int16_t height=(int16_t)read16(f);int e=fgetc(f),jump=fgetc(f);if(jump<0||e<=0||height==INT16_MIN||written>=n){ok=false;break;}graph.grid[j]=written;graph.cell[written]=j;graph.height[written]=height;graph.edges[written]=e;graph.jumps[written]=jump;written++;}}
        i+=count;
    }
    ok=ok&&written==n;
    ok=ok&&!read_failed&&!ferror(f)&&fgetc(f)==EOF;fclose(f);if(!ok){bg_autonav_reset();return false;}graph.map=bg_map_id();
    for(unsigned i=0;i<bg_teleporter_count&&graph.portal_count<PORTALS;i++){uint16_t a=bg_autonav_node(bg_teleporters[i].source),b=bg_autonav_node(bg_teleporters[i].destination);if(a!=BG_NAV_NONE&&b!=BG_NAV_NONE){portal *p=&graph.portals[graph.portal_count++];p->from=a;p->to=b;memcpy(p->source,bg_teleporters[i].source,sizeof(p->source));}}
    memset(graph.component,255,n*2);unsigned component=0;
    for(unsigned start=0;start<n;start++)if(graph.component[start]==BG_NAV_NONE){unsigned first=0,last=0;graph.heap[last++]=start;graph.component[start]=component;
        while(first<last){uint16_t current=graph.heap[first++];for(unsigned k=0;k<8;k++)if(graph.edges[current]&(1u<<k)){uint16_t next=neighbor(current,k);if(next!=BG_NAV_NONE&&graph.component[next]==BG_NAV_NONE){graph.component[next]=component;graph.heap[last++]=next;}}}component++;}
    return true;
}
static uint16_t neighbor(uint16_t node,unsigned k){
    int x=graph.cell[node]%graph.cells%graph.nx+dx[k],z=graph.cell[node]%graph.cells/graph.nx+dz[k];if(x<0||z<0||x>=(int)graph.nx||z>=(int)graph.nz)return BG_NAV_NONE;
    int best=-1,delta=INT32_MAX;for(unsigned l=0;l<graph.layers;l++){unsigned key=l*graph.cells+z*graph.nx+x,n=graph.grid[key];if(n==BG_NAV_NONE)continue;
    int dy=graph.height[n]-graph.height[node];if(dy>64||dy< -160)continue;
    int d=abs(dy);if(d<delta){delta=d;best=n;}}
    return best>=0?(uint16_t)best:BG_NAV_NONE;
}
/* Dijkstra is intentional: directed teleporters make the Euclidean heuristic
 * overestimate travel cost. A fixed 256 expansions/tick bounds the service. */
static void swap(unsigned a,unsigned b){uint16_t n=graph.heap[a];graph.heap[a]=graph.heap[b];graph.heap[b]=n;graph.at[graph.heap[a]]=a;graph.at[n]=b;}
static void push(uint16_t n){unsigned i=graph.at[n]==UINT16_MAX?graph.used++:(unsigned)graph.at[n];graph.heap[i]=n;graph.at[n]=i;while(i){unsigned p=(i-1)/2;if(graph.g[graph.heap[p]]<=graph.g[n])break;swap(i,p);i=p;}}
static uint16_t pop(void){uint16_t n=graph.heap[0];graph.at[n]=UINT16_MAX-1;if(--graph.used){graph.heap[0]=graph.heap[graph.used];graph.at[graph.heap[0]]=0;unsigned i=0;for(;;){unsigned a=i*2+1;if(a>=graph.used)break;unsigned b=a+1,c=b<graph.used&&graph.g[graph.heap[b]]<graph.g[graph.heap[a]]?b:a;if(graph.g[graph.heap[i]]<=graph.g[graph.heap[c]])break;swap(i,c);i=c;}}return n;}
static void relax(uint16_t from,uint16_t to,unsigned edge){if(to==BG_NAV_NONE||graph.at[to]==UINT16_MAX-1)return;
    unsigned g=graph.g[from]+edge;if(g<graph.g[to]&&g<UINT16_MAX){graph.g[to]=g;graph.parent[to]=from;push(to);}}
void bg_autonav_request(unsigned p,uint16_t start,uint16_t goal){
    if(p>=BG_PLAYERS||start==BG_NAV_NONE||goal==BG_NAV_NONE)return;
    if(routes[p].goal==goal&&(routes[p].pending||routes[p].index<routes[p].count))return;
    if(owner==(int)p)return;
    routes[p].start=start;routes[p].goal=goal;routes[p].pending=true;
}
void bg_autonav_cancel(unsigned p){if(p<BG_PLAYERS){memset(&routes[p],0,sizeof(routes[p]));if(owner==(int)p)owner=-1;}}
static void finish(bool success){
    unsigned p=owner;if(success){uint16_t reverse[PATH];unsigned count=0;uint16_t n=routes[p].goal;
        while(n!=routes[p].start&&count<PATH){reverse[count++]=n;n=graph.parent[n];if(n==BG_NAV_NONE)break;}
        if(n==routes[p].start){routes[p].count=count;routes[p].index=0;for(unsigned i=0;i<count;i++)routes[p].path[i]=reverse[count-1-i];}
    }
    routes[p].pending=false;owner=-1;
}
void bg_autonav_service(void){
    last_work=0;if(!graph.height)return;
    if(owner<0)for(unsigned i=0;i<BG_PLAYERS;i++){unsigned p=(next_owner+i)%BG_PLAYERS;if(routes[p].pending){owner=p;next_owner=(p+1)%BG_PLAYERS;memset(graph.g,255,graph.nodes*2);memset(graph.parent,255,graph.nodes*2);memset(graph.at,255,graph.nodes*2);graph.used=0;graph.g[routes[p].start]=0;push(routes[p].start);break;}}
    if(owner<0)return;
    while(graph.used&&last_work<256){uint16_t n=pop();last_work++;if(n==routes[owner].goal){finish(true);return;}
        for(unsigned k=0;k<8;k++)if(graph.edges[n]&(1u<<k))relax(n,neighbor(n,k),k<4?10:14);
        for(unsigned i=0;i<graph.portal_count;i++)if(graph.portals[i].from==n)relax(n,graph.portals[i].to,10);
    }
    if(!graph.used)finish(false);
}
bool bg_autonav_waypoint(unsigned p,const float position[3],float out[3],bool *jump){
    if(p>=BG_PLAYERS||!graph.height)return false;
    while(routes[p].index<routes[p].count){bg_autonav_position(routes[p].path[routes[p].index],out);float a=out[0]-position[0],b=out[2]-position[2];
        if(a*a+b*b<.06f*.06f&&fabsf(out[1]-position[1])<.25f){routes[p].index++;continue;}
        /* A portal's remote endpoint becomes a waypoint only after the
         * production trigger has moved the player. Stay on its source pad. */
        {uint16_t previous=routes[p].index?routes[p].path[routes[p].index-1]:routes[p].start,next=routes[p].path[routes[p].index];for(unsigned t=0;t<graph.portal_count;t++)if(graph.portals[t].from==previous&&graph.portals[t].to==next&&a*a+b*b>4*graph.step*graph.step){memcpy(out,graph.portals[t].source,sizeof(graph.portals[t].source));*jump=false;return true;}}
        *jump=out[1]-position[1]>.08f;
        uint16_t from=routes[p].index?routes[p].path[routes[p].index-1]:routes[p].start,to=routes[p].path[routes[p].index];
        for(unsigned k=0;k<8;k++)if((graph.jumps[from]&(1u<<k))&&neighbor(from,k)==to)*jump=true;
        return true;
    }
    return false;
}
uint16_t bg_autonav_goal(const float origin[3],const float direction[3],float distance){
    if(!graph.height)return BG_NAV_NONE;
    uint16_t start=bg_autonav_node(origin),best=start;float score=-1e9f;
    if(start==BG_NAV_NONE)return BG_NAV_NONE;
    for(unsigned n=0;n<graph.nodes;n++)if(graph.component[n]==graph.component[start]){float p[3];bg_autonav_position(n,p);float x=p[0]-origin[0],z=p[2]-origin[2],d=hypotf(x,z);if(d>distance||fabsf(p[1]-origin[1])>1.5f)continue;
    float value=x*direction[0]+z*direction[2]-.20f*d;if(value>score){score=value;best=n;}}
    return best;
}
