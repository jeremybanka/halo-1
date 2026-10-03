#include "game.h"
#include <math.h>
#include <string.h>
#include <float.h>

bg_player bg_players[BG_PLAYERS];
static unsigned spawn_cycle;
static unsigned active_players=2;
void bg_set_players(unsigned count){active_players=count<1?1:count>4?4:count;}
static float clamp(float v,float a,float b){return v<a?a:v>b?b:v;}
static float dot(const float a[3],const float b[3]){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void sub(float d[3],const float a[3],const float b[3]){for(int i=0;i<3;i++)d[i]=a[i]-b[i];}
static void cross(float d[3],const float a[3],const float b[3]){
    d[0]=a[1]*b[2]-a[2]*b[1];d[1]=a[2]*b[0]-a[0]*b[2];d[2]=a[0]*b[1]-a[1]*b[0];
}
static int cell(float x,float z){
    int ix=(int)floorf((x-bg_grid_origin[0])/bg_grid_size[0]);
    int iz=(int)floorf((z-bg_grid_origin[1])/bg_grid_size[1]);
    if(ix<0||iz<0||ix>=BG_GRID||iz>=BG_GRID)return -1;
    return iz*BG_GRID+ix;
}
float bg_floor(float x,float z,float ceiling){
    int index=cell(x,z);float best=-1000;
    if(index<0)return best;
    bg_cell c=bg_grid[index];
    for(unsigned i=0;i<c.count;i++){
        const bg_triangle*t=&bg_collision[bg_grid_indices[c.first+i]];
        const float*a=t->p[0],*b=t->p[1],*d=t->p[2];
        float det=(b[2]-d[2])*(a[0]-d[0])+(d[0]-b[0])*(a[2]-d[2]);
        if(fabsf(det)<1e-8f)continue;
        float u=((b[2]-d[2])*(x-d[0])+(d[0]-b[0])*(z-d[2]))/det;
        float v=((d[2]-a[2])*(x-d[0])+(a[0]-d[0])*(z-d[2]))/det;
        if(u<-.0001f||v<-.0001f||u+v>1.0001f)continue;
        float ab[3],ac[3],n[3];sub(ab,b,a);sub(ac,d,a);cross(n,ab,ac);
        if(n[1]*n[1]<.38f*dot(n,n))continue;
        float y=u*a[1]+v*b[1]+(1-u-v)*d[1];
        if(y<=ceiling&&y>best)best=y;
    }
    return best;
}

static void closest(float q[3],const float p[3],const bg_triangle*t){
    const float*a=t->p[0],*b=t->p[1],*c=t->p[2];
    float ab[3],ac[3],ap[3],bp[3],cp[3];sub(ab,b,a);sub(ac,c,a);sub(ap,p,a);
    float d1=dot(ab,ap),d2=dot(ac,ap);
    if(d1<=0&&d2<=0){memcpy(q,a,12);return;}
    sub(bp,p,b);float d3=dot(ab,bp),d4=dot(ac,bp);
    if(d3>=0&&d4<=d3){memcpy(q,b,12);return;}
    float vc=d1*d4-d3*d2;
    if(vc<=0&&d1>=0&&d3<=0){float v=d1/(d1-d3);for(int i=0;i<3;i++)q[i]=a[i]+v*ab[i];return;}
    sub(cp,p,c);float d5=dot(ab,cp),d6=dot(ac,cp);
    if(d6>=0&&d5<=d6){memcpy(q,c,12);return;}
    float vb=d5*d2-d1*d6;
    if(vb<=0&&d2>=0&&d6<=0){float w=d2/(d2-d6);for(int i=0;i<3;i++)q[i]=a[i]+w*ac[i];return;}
    float va=d3*d6-d5*d4;
    if(va<=0&&d4-d3>=0&&d5-d6>=0){float w=(d4-d3)/((d4-d3)+(d5-d6));for(int i=0;i<3;i++)q[i]=b[i]+w*(c[i]-b[i]);return;}
    float denominator=va+vb+vc;
    if(fabsf(denominator)<1e-10f){memcpy(q,a,12);return;}
    float v=vb/denominator,w=vc/denominator;
    for(int i=0;i<3;i++)q[i]=a[i]+ab[i]*v+ac[i]*w;
}

static void walls(bg_player*p){
    const float radius=.14f;
    for(int iteration=0;iteration<2;iteration++){
        int xmin=(int)floorf((p->pos[0]-radius-bg_grid_origin[0])/bg_grid_size[0]);
        int xmax=(int)floorf((p->pos[0]+radius-bg_grid_origin[0])/bg_grid_size[0]);
        int zmin=(int)floorf((p->pos[2]-radius-bg_grid_origin[1])/bg_grid_size[1]);
        int zmax=(int)floorf((p->pos[2]+radius-bg_grid_origin[1])/bg_grid_size[1]);
        for(int z=zmin;z<=zmax;z++)for(int x=xmin;x<=xmax;x++){
            if(x<0||z<0||x>=BG_GRID||z>=BG_GRID)continue;
            bg_cell c=bg_grid[z*BG_GRID+x];
            for(unsigned i=0;i<c.count;i++){
                const bg_triangle*t=&bg_collision[bg_grid_indices[c.first+i]];
                float ab[3],ac[3],n[3];sub(ab,t->p[1],t->p[0]);sub(ac,t->p[2],t->p[0]);cross(n,ab,ac);
                if(n[1]*n[1]>.38f*dot(n,n))continue;
                for(int sample=0;sample<2;sample++){
                    float point[3]={p->pos[0],p->pos[1]+.19f+sample*.32f,p->pos[2]},q[3];closest(q,point,t);
                    float dx=point[0]-q[0],dy=point[1]-q[1],dz=point[2]-q[2];
                    float d2=dx*dx+dy*dy+dz*dz, horizontal=sqrtf(dx*dx+dz*dz);
                    if(d2<radius*radius&&horizontal>1e-6f){
                        float amount=(radius-sqrtf(d2))/horizontal;
                        p->pos[0]+=dx*amount;p->pos[2]+=dz*amount;
                    }
                }
            }
        }
    }
}

float bg_raycast(const float origin[3],const float direction[3],float max_distance){
    float nearest=max_distance;
    for(unsigned i=0;i<bg_collision_count;i++){
        const bg_triangle*t=&bg_collision[i];
        float e1[3],e2[3],h[3],s[3],q[3];sub(e1,t->p[1],t->p[0]);sub(e2,t->p[2],t->p[0]);cross(h,direction,e2);
        float det=dot(e1,h);if(fabsf(det)<1e-7f)continue;
        sub(s,origin,t->p[0]);float u=dot(s,h)/det;if(u<0||u>1)continue;
        cross(q,s,e1);float v=dot(direction,q)/det;if(v<0||u+v>1)continue;
        float distance=dot(e2,q)/det;if(distance>.015f&&distance<nearest)nearest=distance;
    }
    return nearest;
}

static void spawn(unsigned player){
    bg_player*p=&bg_players[player];int score=p->score;
    unsigned start=(spawn_cycle*13+player*5)%bg_spawn_count,index=start;
    for(unsigned i=0;i<bg_spawn_count;i++){
        unsigned j=(start+i)%bg_spawn_count;
        if(bg_spawns[j].team==(int)(player%2)){index=j;break;}
    }
    memset(p,0,sizeof(*p));p->score=score;p->health=100;p->ammo=32;
    memcpy(p->pos,bg_spawns[index].pos,sizeof(p->pos));
    float floor=bg_floor(p->pos[0],p->pos[2],p->pos[1]+.5f);
    if(floor>-999)p->pos[1]=floor+.015f;
    p->yaw=bg_spawns[index].yaw;p->grounded=true;
}
void bg_reset(void){memset(bg_players,0,sizeof(bg_players));spawn_cycle=0;for(int i=0;i<BG_PLAYERS;i++)spawn(i);}

static void fire(unsigned index){
    bg_player*p=&bg_players[index];p->cooldown=.13f;p->flash=.065f;p->ammo--;
    float cp=cosf(p->pitch),direction[3]={cosf(p->yaw)*cp,sinf(p->pitch),-sinf(p->yaw)*cp};
    float origin[3]={p->pos[0],p->pos[1]+.62f,p->pos[2]};
    float nearest=150;int victim=-1;
    for(unsigned j=0;j<active_players;j++){
        if(j==index||bg_players[j].health<=0)continue;
        for(int sphere=0;sphere<2;sphere++){
            float delta[3]={bg_players[j].pos[0]-origin[0],bg_players[j].pos[1]+.24f+sphere*.28f-origin[1],bg_players[j].pos[2]-origin[2]};
            float t=dot(delta,direction),distance=dot(delta,delta)-t*t;
            if(t>0&&t<nearest&&distance<.055f){nearest=t;victim=j;}
        }
    }
    /* Most shots hit no player. Only cast through the terrain when a target
     * is actually in the reticle, avoiding thousands of needless FP tests. */
    if(victim>=0 && bg_raycast(origin,direction,nearest)>=nearest){bg_player*v=&bg_players[victim];v->health-=25;v->hurt=4;
        if(v->health<=0){v->respawn=2;bg_players[index].score++;}}
}
void bg_tick(const bg_input inputs[BG_PLAYERS],float dt){
    dt=clamp(dt,0,1.0f/30);
    for(unsigned i=0;i<active_players;i++){
        bg_player*p=&bg_players[i];const bg_input*in=&inputs[i];
        p->cooldown=fmaxf(0,p->cooldown-dt);p->flash=fmaxf(0,p->flash-dt);p->hurt=fmaxf(0,p->hurt-dt);
        if(p->health<=0){p->respawn-=dt;if(p->respawn<=0){spawn_cycle++;spawn(i);}continue;}
        if(p->reload>0){p->reload-=dt;if(p->reload<=0)p->ammo=32;}
        if(in->reload&&p->reload<=0&&p->ammo<32)p->reload=1.1f;
        p->yaw+=in->turn*2.25f*dt;p->pitch=clamp(p->pitch+in->look*1.35f*dt,-1.25f,1.25f);
        float f=in->forward,s=in->strafe,length=sqrtf(f*f+s*s);if(length>1){f/=length;s/=length;}
        float previous[3];memcpy(previous,p->pos,12);
        p->pos[0]+=(cosf(p->yaw)*f+sinf(p->yaw)*s)*2.25f*dt;
        p->pos[2]+=(-sinf(p->yaw)*f+cosf(p->yaw)*s)*2.25f*dt;
        if(in->jump&&p->grounded){p->vy=1.9f;p->grounded=false;}
        p->vy-=4.8f*dt;p->pos[1]+=p->vy*dt;
        walls(p);
        float floor=bg_floor(p->pos[0],p->pos[2],fmaxf(previous[1],p->pos[1])+.18f);
        if(p->vy<=0&&floor>-999&&p->pos[1]<=floor+.025f){p->pos[1]=floor+.015f;p->vy=0;p->grounded=true;}
        else p->grounded=false;
        if(p->pos[1]<-6){p->health=0;p->respawn=1;}
        if(in->fire&&p->cooldown<=0&&p->reload<=0&&p->ammo>0&&p->health>0)fire(i);
    }
}
