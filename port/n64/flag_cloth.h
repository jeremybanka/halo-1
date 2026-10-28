#ifndef BG_FLAG_CLOTH_H
#define BG_FLAG_CLOTH_H
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

/* Every third authored grid point: 16x13 -> 6x5, one Tiny3D batch. */
enum { BG_CLOTH_COLS=6,BG_CLOTH_ROWS=5,BG_CLOTH_VERTICES=30,BG_CLOTH_TRIANGLES=40 };
typedef struct {float p[3],v[3];} bg_cloth_point;
typedef struct {
    bg_cloth_point points[BG_CLOTH_VERTICES];
    float attachment[3];
    bool initialized;
} bg_cloth_state;
typedef struct {float width,height,gravity,drag;} bg_cloth_physics;
typedef struct {float plane[4];int16_t back,front;} bg_cloth_weather_node;
typedef struct {
    float speed[2],yaw,pitch,variation[2],magnitude,local_weight,local_rate;
    const bg_cloth_weather_node *nodes;
    int16_t root;
    uint16_t count;
} bg_cloth_weather;
typedef struct {uint32_t seed,tick;float variance[3],wind[3],speed;} bg_cloth_wind_state;

static inline float bg_cloth_dot(const float a[3],const float b[3]) {
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
}
static inline void bg_cloth_cross(float out[3],const float a[3],const float b[3]) {
    out[0]=a[1]*b[2]-a[2]*b[1];out[1]=a[2]*b[0]-a[0]*b[2];out[2]=a[0]*b[1]-a[1]*b[0];
}
static inline float bg_cloth_unit(float v[3]) {
    float length=sqrtf(bg_cloth_dot(v,v));
    if(length>1e-8f)for(unsigned a=0;a<3;a++)v[a]/=length;
    return length;
}
/* -1=no weather, -2=the map's authored wind. Collapsed source BSP selectors
 * retain Carousel's sheltered clusters without carrying its full render BSP. */
static inline bool bg_cloth_has_wind(const bg_cloth_weather *w,const float p[3]) {
    int i=w->root;
    for(unsigned step=0;i>=0&&step<=w->count;step++) {
        if((unsigned)i>=w->count)return false;
        const bg_cloth_weather_node *n=&w->nodes[i];
        i=bg_cloth_dot(n->plane,p)>=n->plane[3]?n->front:n->back;
    }
    return i==-2;
}
static inline void bg_cloth_wind_step(bg_cloth_wind_state *s,const bg_cloth_weather *w) {
    if(!s->seed)s->seed=0x464c4147u;
    s->tick++;
    /* Same bounded 0.01 random walk as source/scenario/wind.c, using a
     * private stream so cosmetics cannot alter gameplay randomness. */
    for(unsigned a=0;a<3;a++) {
        s->seed=s->seed*1664525u+1013904223u;
        s->variance[a]=fminf(1,fmaxf(a? -1.f:0.f,s->variance[a]+((s->seed>>31)? .01f:-.01f)));
    }
    s->speed=w->speed[0]+(w->speed[1]-w->speed[0])*s->variance[0];
    float yaw=w->yaw+w->variation[0]*s->variance[1]*.5f;
    float pitch=w->pitch+w->variation[1]*s->variance[2]*.5f;
    float speed=w->magnitude*s->speed*(1-w->local_weight);
    s->wind[0]=cosf(yaw)*cosf(pitch)*speed;
    s->wind[1]=sinf(pitch)*speed;s->wind[2]=-sinf(yaw)*cosf(pitch)*speed;
}
static inline void bg_cloth_wind_at(float out[3],const bg_cloth_weather *w,
        const bg_cloth_wind_state *s,const float noise[3][64][3],const float source_p[3]) {
    const float axis_scale[3]={.1f,.2f,.07f};
    memcpy(out,s->wind,3*sizeof(float));
    float magnitude=w->local_weight*s->speed/3;
    for(unsigned axis=0;axis<3;axis++) {
        /* Source's 2^23 rounding trick: nearest-even lookup without the
         * libm lrintf call in every particle/axis. memcpy avoids aliasing. */
        float key=fabsf((axis_scale[axis]*s->tick*w->local_rate+source_p[axis])*8)+8388608.f;
        uint32_t bits;memcpy(&bits,&key,sizeof(bits));unsigned index=bits&63;
        for(unsigned a=0;a<3;a++)out[a]+=noise[axis][index][a]*magnitude;
    }
}
static inline void bg_cloth_reset(bg_cloth_state *s,const float corners[3][3]) {
    memset(s,0,sizeof(*s));
    for(unsigned x=0;x<BG_CLOTH_COLS;x++)for(unsigned y=0;y<BG_CLOTH_ROWS;y++) {
        float u=(float)x/(BG_CLOTH_COLS-1),v=(float)y/(BG_CLOTH_ROWS-1);
        for(unsigned a=0;a<3;a++)s->points[x*BG_CLOTH_ROWS+y].p[a]=corners[0][a]+
            u*(corners[2][a]-corners[0][a])+v*(corners[1][a]-corners[0][a]);
    }
    memcpy(s->attachment,corners[0],12);s->initialized=true;
}
/* Reduced form of source/objects/widgets/flags.c::flag_update: integrate
 * point gravity/air drag, then constrain to left/up/down neighbors with the
 * original 4:1 weights. The two marker endpoints stay exactly pinned. */
static inline void bg_cloth_step(bg_cloth_state *s,const bg_cloth_physics *physics,
        const float corners[3][3],const float wind[BG_CLOTH_VERTICES][3],float dt) {
    float delta[3];for(unsigned a=0;a<3;a++)delta[a]=corners[0][a]-s->attachment[a];
    /* Reinitialize on transfer/teleport rather than stretching across a map. */
    if(!s->initialized||bg_cloth_dot(delta,delta)>1.f||dt<=0||dt>.1f) {
        bg_cloth_reset(s,corners);return;
    }
    float distances[3]={physics->width/(BG_CLOTH_COLS-1),physics->height/(BG_CLOTH_ROWS-1),physics->height/(BG_CLOTH_ROWS-1)};
    const int dx[3]={-1,0,0},dy[3]={0,1,-1};
    float drag=fminf(1,physics->drag*dt);
    for(int x=0;x<BG_CLOTH_COLS;x++)for(int y=0;y<BG_CLOTH_ROWS;y++) {
        unsigned at=x*BG_CLOTH_ROWS+y;bg_cloth_point *p=&s->points[at];float candidate[3];
        p->v[1]+=physics->gravity*dt;
        for(unsigned a=0;a<3;a++) {p->v[a]+=(wind[at][a]-p->v[a])*drag;candidate[a]=p->p[a]+p->v[a]*dt;}
        float result[3]={0},total=0;
        if(x==0&&(y==0||y==BG_CLOTH_ROWS-1))memcpy(result,corners[y?1:0],12);
        else {
            for(unsigned n=0;n<3;n++) {
                int nx=x+dx[n],ny=y+dy[n];if(nx<0||ny<0||nx>=BG_CLOTH_COLS||ny>=BG_CLOTH_ROWS)continue;
                const float *neighbor=s->points[nx*BG_CLOTH_ROWS+ny].p;
                float direction[3];for(unsigned a=0;a<3;a++)direction[a]=candidate[a]-neighbor[a];
                if(bg_cloth_unit(direction)<1e-8f) {
                    for(unsigned a=0;a<3;a++)direction[a]=(n==0?corners[2][a]-corners[0][a]:
                        (n==1?-1:1)*(corners[1][a]-corners[0][a]));
                    bg_cloth_unit(direction);
                }
                float weight=x&&n==0?4:1;total+=weight;
                for(unsigned a=0;a<3;a++)result[a]+=weight*(neighbor[a]+direction[a]*distances[n]);
            }
            if(x==0) {
                float v=(float)y/(BG_CLOTH_ROWS-1);total+=4;
                for(unsigned a=0;a<3;a++)result[a]+=4*(corners[0][a]+v*(corners[1][a]-corners[0][a]));
            }
            for(unsigned a=0;a<3;a++)result[a]/=total;
        }
        for(unsigned a=0;a<3;a++){p->v[a]=(result[a]-p->p[a])/dt;p->p[a]=result[a];}
    }
    memcpy(s->attachment,corners[0],12);
}
#endif
