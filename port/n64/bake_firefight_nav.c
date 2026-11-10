/* Host authoring tool: six floor layers, enemy-sized capsule, walk-only links.
 * No jumps, ladders or teleporters are silently granted to Covenant actors. */
#include "map.h"
#include "game.h"
#include "terrain.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SIDE 104
#define LAYERS 6
#define MAX (SIDE*SIDE*LAYERS)
static float positions[MAX][3];
static uint16_t ids[MAX],links[MAX][8];
static uint8_t edges[MAX];
static unsigned nx,nz,cells;static float step=.5f,ox,oz;
static const int dx[8]={1,-1,0,0,1,1,-1,-1},dz[8]={0,0,1,-1,1,-1,1,-1};
static const unsigned reverse[8]={1,0,3,2,7,6,5,4};
static void u16(FILE*f,unsigned n){fputc(n>>8,f);fputc(n&255,f);}
static void f32(FILE*f,float n){uint32_t bits;memcpy(&bits,&n,4);u16(f,bits>>16);u16(f,bits);}
static bool walk(const float a[3],const float b[3]){
    unsigned samples=(unsigned)ceilf(step*1.42f/.05f);
    for(unsigned i=0;i<=samples;i++){
        float t=(float)i/samples;bg_player p={.vehicle=-1,.pve_radius=.24f,.pve_height=.8f};
        for(unsigned j=0;j<3;j++)p.pos[j]=a[j]+(b[j]-a[j])*t;
        float floor=bg_floor(p.pos[0],p.pos[2],fmaxf(a[1],b[1])+.25f);
        if(floor<bg_map_void_height()+.5f||fabsf(floor+.015f-p.pos[1])>.18f)return false;
        p.pos[1]=floor+.015f;if(!bg_terrain_clearance(&p))return false;
    }
    return true;
}
int main(int argc,char**argv){
    assert(argc==3);unsigned map=(unsigned)strtoul(argv[1],NULL,10);assert(map==0||map==3);assert(bg_map_load(map));
    float lo[3]={1e6,1e6,1e6},hi[3]={-1e6,-1e6,-1e6};
    for(unsigned t=0;t<bg_collision_count;t++)if(bg_collision_flags[t]&BG_SURFACE_FLOOR)for(unsigned v=0;v<3;v++)for(unsigned a=0;a<3;a++){lo[a]=fminf(lo[a],bg_collision[t].p[v][a]);hi[a]=fmaxf(hi[a],bg_collision[t].p[v][a]);}
    float play_lo[3]={1e6,1e6,1e6},play_hi[3]={-1e6,-1e6,-1e6};
    for(unsigned n=0;n<bg_spawn_count;n++)for(unsigned a=0;a<3;a++){play_lo[a]=fminf(play_lo[a],bg_spawns[n].pos[a]);play_hi[a]=fmaxf(play_hi[a],bg_spawns[n].pos[a]);}
    lo[0]=fmaxf(lo[0],play_lo[0]-6);hi[0]=fminf(hi[0],play_hi[0]+6);lo[2]=fmaxf(lo[2],play_lo[2]-6);hi[2]=fminf(hi[2],play_hi[2]+6);
    ox=floorf(lo[0]*2)/2;oz=floorf(lo[2]*2)/2;nx=(unsigned)ceilf((hi[0]-ox)/step)+1;nz=(unsigned)ceilf((hi[2]-oz)/step)+1;
    assert(nx<=SIDE&&nz<=SIDE);cells=nx*nz;unsigned raw=cells*LAYERS;
    for(unsigned n=0;n<raw;n++){positions[n][1]=-1000;ids[n]=UINT16_MAX;for(unsigned k=0;k<8;k++)links[n][k]=UINT16_MAX;}
    for(unsigned c=0;c<cells;c++){
        float ceiling=hi[1]+1;
        for(unsigned l=0;l<LAYERS;l++){
            bg_player p={.vehicle=-1,.pve_radius=.24f,.pve_height=.8f};p.pos[0]=ox+c%nx*step;p.pos[2]=oz+c/nx*step;
            p.pos[1]=bg_floor(p.pos[0],p.pos[2],ceiling)+.015f;if(p.pos[1]<bg_map_void_height()+.5f)break;ceiling=p.pos[1]-.32f;
            for(unsigned a=0;a<3;a++){assert(fabsf(p.pos[a])<127);p.pos[a]=roundf(p.pos[a]*256)/256;}
            if(bg_terrain_clearance(&p))memcpy(positions[l*cells+c],p.pos,12);
        }
    }
    for(unsigned n=0;n<raw;n++)if(positions[n][1]>-999)for(unsigned k=0;k<8;k++){
        int x=n%cells%nx+dx[k],z=n%cells/nx+dz[k];if(x<0||z<0||x>=(int)nx||z>=(int)nz)continue;
        for(unsigned l=0;l<LAYERS;l++){
            unsigned next=l*cells+z*nx+x;
            if(positions[next][1]<-999||fabsf(positions[next][1]-positions[n][1])>.65f)continue;
            if(walk(positions[n],positions[next])){links[n][k]=next;edges[n]|=1u<<k;break;}
        }
    }
    for(unsigned n=0;n<raw;n++)for(unsigned k=0;k<8;k++)if(edges[n]&(1u<<k)){
        unsigned next=links[n][k];if(links[next][reverse[k]]!=n){edges[n]&=~(1u<<k);links[n][k]=UINT16_MAX;}
    }
    unsigned count=0;for(unsigned n=0;n<raw;n++)if(edges[n]){assert(count<8192);ids[n]=count++;}
    char path[2048];snprintf(path,sizeof(path),"%s/firefight-nav-%u.bin",argv[2],map);FILE*f=fopen(path,"wb");assert(f);
    fwrite("FNV1",1,4,f);u16(f,map);u16(f,count);f32(f,step);f32(f,ox);f32(f,oz);
    for(unsigned n=0;n<raw;n++)if(edges[n]){
        for(unsigned a=0;a<3;a++)u16(f,(uint16_t)(int16_t)lroundf(positions[n][a]*256));
        for(unsigned k=0;k<8;k++)u16(f,edges[n]&(1u<<k)?ids[links[n][k]]:UINT16_MAX);
    }
    fclose(f);snprintf(path,sizeof(path),"%s/firefight-nav-%u.json",argv[2],map);f=fopen(path,"w");assert(f);
    fprintf(f,"{\"map\":%u,\"step\":%.3f,\"nodes\":[",map,step);bool first=true;
    for(unsigned n=0;n<raw;n++)if(edges[n]){fprintf(f,"%s[%.4f,%.4f,%.4f]",first?"":",",positions[n][0],positions[n][1],positions[n][2]);first=false;}
    fprintf(f,"],\"spawns\":[");for(unsigned i=0;i<bg_spawn_count;i++)fprintf(f,"%s[%.4f,%.4f,%.4f]",i?",":"",bg_spawns[i].pos[0],bg_spawns[i].pos[1],bg_spawns[i].pos[2]);fprintf(f,"]}\n");fclose(f);
    printf("Firefight map %u: %u nodes, %ux%ux%u at %.2f units; %u-byte bank\n",map,count,nx,nz,LAYERS,step,20+22*count);
}
