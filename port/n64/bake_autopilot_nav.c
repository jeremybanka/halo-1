/* Host-only baker. Its floors and swept capsule clearances are the production
 * selected-map collision, including every upper/lower floor. */
#include "map.h"
#include "game.h"
#include "terrain.h"
#include "movement.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define LAYERS 6
#define SIDE 104
static int16_t heights[SIDE*SIDE*LAYERS];
static uint8_t edges[SIDE*SIDE*LAYERS],jumps[SIDE*SIDE*LAYERS];
static const int dx[8]={1,-1,0,0,1,1,-1,-1},dz[8]={0,0,1,-1,1,-1,1,-1};
static void u16(FILE *f,unsigned n){fputc(n>>8,f);fputc(n&255,f);}
static void f32(FILE *f,float n){uint32_t bits;memcpy(&bits,&n,4);fputc(bits>>24,f);fputc(bits>>16&255,f);fputc(bits>>8&255,f);fputc(bits&255,f);}
static unsigned nx,nz,cells;static float step,ox,oz,oy;
static void pos(unsigned node,float p[3]){unsigned cell=node%cells;p[0]=ox+(cell%nx)*step;p[1]=oy+heights[node]/128.f;p[2]=oz+(cell/nx)*step;}
static int neighbor(unsigned node,unsigned k){
    int x=node%cells%nx+dx[k],z=node%cells/nx+dz[k];if(x<0||z<0||x>=(int)nx||z>=(int)nz)return -1;
    int best=-1,delta=INT32_MAX;for(unsigned l=0;l<LAYERS;l++){unsigned n=l*cells+z*nx+x;if(heights[n]==INT16_MIN)continue;int dy=heights[n]-heights[node];if(dy>64||dy< -160)continue;int d=abs(dy);if(d<delta){delta=d;best=n;}}
    return best;
}
static bool clear(const float a[3],const float b[3]){
    unsigned samples=(unsigned)ceilf(step*1.42f/.07f);float max_y=fmaxf(a[1],b[1]);
    for(unsigned i=0;i<=samples;i++){
        float t=(float)i/samples;bg_player p={.vehicle=-1};for(unsigned j=0;j<3;j++)p.pos[j]=a[j]+(b[j]-a[j])*t;
        float floor=bg_floor(p.pos[0],p.pos[2],max_y+.18f);
        if(floor<bg_map_void_height()+.5f||fabsf(floor+.015f-p.pos[1])>.18f)return false;
        p.pos[1]=floor+.015f;
        if(!bg_terrain_clearance(&p))return false;
    }
    return true;
}
static bool leap(const float a[3],const float b[3]){
    float rise=b[1]-a[1];if(rise>.48f||rise< -1.2f)return false;
    unsigned samples=(unsigned)ceilf(step*1.42f/.04f);
    float peak=rise>-.1f?fminf(.45f,bg_movement.jump*bg_movement.jump/(2*bg_movement.gravity)):.12f;
    for(unsigned i=0;i<=samples;i++){
        float t=(float)i/samples;bg_player p={.vehicle=-1};for(unsigned j=0;j<3;j++)p.pos[j]=a[j]+(b[j]-a[j])*t;p.pos[1]+=4*peak*t*(1-t);
        if(!bg_terrain_clearance(&p))return false;
    }
    return true;
}
int main(int argc,char **argv){
    assert(argc==2);char path[2048];
    for(unsigned map=0;map<13;map++){
        assert(bg_map_load(map));float lo[3]={1e6,1e6,1e6},hi[3]={-1e6,-1e6,-1e6};
        for(unsigned t=0;t<bg_collision_count;t++)if(bg_collision_flags[t]&BG_SURFACE_FLOOR)for(unsigned v=0;v<3;v++)for(unsigned a=0;a<3;a++){lo[a]=fminf(lo[a],bg_collision[t].p[v][a]);hi[a]=fmaxf(hi[a],bg_collision[t].p[v][a]);}
        /* Collision also includes distant decorative ground/death planes.
         * Bound navigation to the authored playable start/portal domain so
         * those surfaces cannot turn a ship corridor into a five-unit cell. */
        float play_lo[3]={1e6,1e6,1e6},play_hi[3]={-1e6,-1e6,-1e6};
        for(unsigned i=0;i<bg_spawn_count;i++)for(unsigned a=0;a<3;a++){play_lo[a]=fminf(play_lo[a],bg_spawns[i].pos[a]);play_hi[a]=fmaxf(play_hi[a],bg_spawns[i].pos[a]);}
        for(unsigned i=0;i<bg_teleporter_count;i++)for(unsigned a=0;a<3;a++){play_lo[a]=fminf(play_lo[a],fminf(bg_teleporters[i].source[a],bg_teleporters[i].destination[a]));play_hi[a]=fmaxf(play_hi[a],fmaxf(bg_teleporters[i].source[a],bg_teleporters[i].destination[a]));}
        float lowest=fmaxf(bg_map_void_height()+.5f,play_lo[1]-4);
        lo[0]=fmaxf(lo[0],play_lo[0]-12);hi[0]=fminf(hi[0],play_hi[0]+12);lo[2]=fmaxf(lo[2],play_lo[2]-12);hi[2]=fminf(hi[2],play_hi[2]+12);
        step=fmaxf(.4f,fmaxf(hi[0]-lo[0],hi[2]-lo[2])/(SIDE-1));ox=lo[0];oz=lo[2];nx=(unsigned)ceilf((hi[0]-lo[0])/step)+1;nz=(unsigned)ceilf((hi[2]-lo[2])/step)+1;if(nx>SIDE)nx=SIDE;if(nz>SIDE)nz=SIDE;cells=nx*nz;
        oy=roundf((hi[1]+fmaxf(lo[1],bg_map_void_height()+.5f))*.5f);
        printf("BOUNDS map%u y%.3f..%.3f offset%.3f void%.3f\n",map,lo[1],hi[1],oy,bg_map_void_height());fflush(stdout);
        unsigned nodes=cells*LAYERS;memset(edges,0,nodes);memset(jumps,0,nodes);for(unsigned n=0;n<nodes;n++)heights[n]=INT16_MIN;
        for(unsigned c=0;c<cells;c++){
            float ceiling=hi[1]+1;
            for(unsigned l=0;l<LAYERS;l++){
                bg_player p={.vehicle=-1};p.pos[0]=ox+(c%nx)*step;p.pos[2]=oz+(c/nx)*step;p.pos[1]=bg_floor(p.pos[0],p.pos[2],ceiling)+.015f;
                if(p.pos[1]<lowest)break;ceiling=p.pos[1]-.32f;
                if(bg_terrain_clearance(&p)){int y=lroundf((p.pos[1]-oy)*128);assert(y>INT16_MIN&&y<INT16_MAX);heights[l*cells+c]=y;}
            }
        }
        unsigned valid=0,links=0;
        for(unsigned n=0;n<nodes;n++)if(heights[n]!=INT16_MIN){
            valid++;float a[3];pos(n,a);
            for(unsigned k=0;k<8;k++){int next=neighbor(n,k);if(next<0)continue;float b[3];pos(next,b);if(clear(a,b)){edges[n]|=1u<<k;links++;}}
        }
        /* Walk edges must be reversible. Authored portals are directed links
         * added separately at load time. No edge cuts across an empty floor. */
        static const unsigned reverse[8]={1,0,3,2,7,6,5,4};
        for(unsigned n=0;n<nodes;n++)for(unsigned k=0;k<8;k++)if(edges[n]&(1u<<k)){int next=neighbor(n,k);if(next<0||!(edges[next]&(1u<<reverse[k]))||neighbor(next,reverse[k])!=(int)n)edges[n]&=~(1u<<k);}
        /* Certified short jump/drop links join crate starts, stairs and
         * floor lips. Ordinary capsule physics executes them at runtime. */
        for(unsigned n=0;n<nodes;n++)if(heights[n]!=INT16_MIN){float a[3];pos(n,a);for(unsigned k=0;k<8;k++)if(!(edges[n]&(1u<<k))){int next=neighbor(n,k);if(next<0)continue;float b[3];pos(next,b);if(leap(a,b)){edges[n]|=1u<<k;jumps[n]|=1u<<k;}}}
        snprintf(path,sizeof(path),"%s/autonav-%u.bin",argv[1],map);FILE *f=fopen(path,"wb");assert(f);fwrite("GNV3",1,4,f);u16(f,nx);u16(f,nz);u16(f,LAYERS);u16(f,0);f32(f,step);f32(f,ox);f32(f,oz);f32(f,oy);unsigned live=0;for(unsigned j=0;j<nodes;j++)live+=edges[j]!=0;u16(f,live);u16(f,0);
        for(unsigned n=0;n<nodes;){bool live=edges[n]!=0;unsigned end=n+1;while(end<nodes&&(edges[end]!=0)==live&&end-n<32767)end++;u16(f,(live?0:32768)|(end-n));if(live)for(unsigned j=n;j<end;j++){u16(f,(uint16_t)heights[j]);fputc(edges[j],f);fputc(jumps[j],f);}n=end;}
        long bytes=ftell(f);fclose(f);printf("map%u %ux%ux%u step%.4f valid%u edges%u bytes%ld\n",map,nx,nz,LAYERS,step,valid,links,bytes);fflush(stdout);bg_map_unload();
    }
}
