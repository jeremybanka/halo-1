/* Selected-map infantry graph. Blood Gulch keeps its accepted legacy bank.
 * FNV1 records use big-endian 1/256-unit positions and eight reciprocal walk
 * links, baked with the production enemy capsule against the selected map. */
#include <stdlib.h>
#include <stdio.h>
typedef struct {int16_t pos[3];uint16_t next[8];uint8_t edges,pad;} ff_nav_node;
static struct {ff_nav_node *nodes;uint16_t *heads,*chain;unsigned count,map,nx,nz;float step,ox,oz;} ff_nav;
static const unsigned ff_nav_reverse[8]={1,0,3,2,7,6,5,4};
static unsigned ff_nav_read16(FILE*f,bool*ok){int a=fgetc(f),b=fgetc(f);if(a<0||b<0){*ok=false;return 0;}return (unsigned)(a<<8)|b;}
static float ff_nav_read_float(FILE*f,bool*ok){uint32_t bits=ff_nav_read16(f,ok)<<16;bits|=ff_nav_read16(f,ok);float n;memcpy(&n,&bits,4);return n;}
static void ff_nav_release(void){free(ff_nav.nodes);free(ff_nav.heads);free(ff_nav.chain);memset(&ff_nav,0,sizeof(ff_nav));}
static bool ff_nav_load(unsigned map){
    if(ff_nav.nodes&&ff_nav.map==map)return true;
    ff_nav_release();char path[2048];
#ifdef N64
    snprintf(path,sizeof(path),"rom:/firefight-nav-%u.bin",map);
#else
    const char*directory=getenv("BG_FIREFIGHT_NAV_DIRECTORY");
    snprintf(path,sizeof(path),"%s/firefight-nav-%u.bin",directory?directory:"build/n64/frontend-files",map);
#endif
    FILE*f=fopen(path,"rb");if(!f)return false;
    char magic[4];bool ok=fread(magic,1,4,f)==4&&!memcmp(magic,"FNV1",4);
    unsigned id=ff_nav_read16(f,&ok),count=ff_nav_read16(f,&ok);
    float step=ff_nav_read_float(f,&ok),ox=ff_nav_read_float(f,&ok),oz=ff_nav_read_float(f,&ok);
    ok=ok&&id==map&&count>0&&count<=8192&&isfinite(step)&&step>=.1f&&step<=2&&isfinite(ox)&&isfinite(oz)&&fabsf(ox)<128&&fabsf(oz)<128;
    ff_nav_node*nodes=ok?calloc(count,sizeof(*nodes)):NULL;if(!nodes)ok=false;
    for(unsigned n=0;ok&&n<count;n++){
        for(unsigned a=0;a<3;a++)nodes[n].pos[a]=(int16_t)ff_nav_read16(f,&ok);
        for(unsigned k=0;k<8;k++){
            unsigned next=ff_nav_read16(f,&ok);nodes[n].next[k]=next;
            if(next!=UINT16_MAX){if(next>=count||next==n)ok=false;else nodes[n].edges|=1u<<k;}
        }
        if(!nodes[n].edges)ok=false;
    }
    if(fgetc(f)!=EOF)ok=false;
    fclose(f);
    for(unsigned n=0;ok&&n<count;n++)for(unsigned k=0;k<8;k++)if(nodes[n].edges&(1u<<k)){
        const ff_nav_node*next=&nodes[nodes[n].next[k]];
        if(next->next[ff_nav_reverse[k]]!=n)ok=false;
    }
    unsigned nx=0,nz=0;
    for(unsigned n=0;ok&&n<count;n++){
        long x=lroundf((nodes[n].pos[0]/256.f-ox)/step),z=lroundf((nodes[n].pos[2]/256.f-oz)/step);
        if(x<0||z<0||x>=104||z>=104)ok=false;
        else {if((unsigned)x+1>nx)nx=x+1;if((unsigned)z+1>nz)nz=z+1;}
    }
    uint16_t*heads=ok?malloc(nx*nz*sizeof(*heads)):NULL,*chain=ok?malloc(count*sizeof(*chain)):NULL;
    if(!heads||!chain)ok=false;
    if(!ok){free(nodes);free(heads);free(chain);return false;}
    memset(heads,255,nx*nz*sizeof(*heads));
    for(unsigned n=0;n<count;n++){
        unsigned x=lroundf((nodes[n].pos[0]/256.f-ox)/step),z=lroundf((nodes[n].pos[2]/256.f-oz)/step),cell=z*nx+x;
        chain[n]=heads[cell];heads[cell]=n;unsigned layers=0;
        for(unsigned i=heads[cell];i!=UINT16_MAX;i=chain[i])if(++layers>6)ok=false;
    }
    if(!ok){free(nodes);free(heads);free(chain);return false;}
    ff_nav.nodes=nodes;ff_nav.heads=heads;ff_nav.chain=chain;ff_nav.nx=nx;ff_nav.nz=nz;
    ff_nav.count=count;ff_nav.map=map;ff_nav.step=step;ff_nav.ox=ox;ff_nav.oz=oz;return true;
}
