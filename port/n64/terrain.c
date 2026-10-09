#include "terrain.h"
#include "movement.h"
#include <math.h>
#include <string.h>
static float dot(const float*a,const float*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void sub(float*d,const float*a,const float*b){for(int k=0;k<3;k++)d[k]=a[k]-b[k];}
static void cross(float*d,const float*a,const float*b){d[0]=a[1]*b[2]-a[2]*b[1];d[1]=a[2]*b[0]-a[0]*b[2];d[2]=a[0]*b[1]-a[1]*b[0];}
static float pin(float a,float lo,float hi){return fmaxf(lo,fminf(a,hi));}
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

static void consider(const float a[3],const float b[3],float *best,float pa[3],float pb[3]){
    float d[3];sub(d,a,b);float d2=dot(d,d);if(d2<*best){*best=d2;memcpy(pa,a,12);memcpy(pb,b,12);}
}
float bg_capsule_triangle(const float base[3],float height,float radius,const bg_triangle*t,float pa[3],float pb[3]){
    float a[3]={base[0],base[1]+radius,base[2]},b[3]={base[0],base[1]+height-radius,base[2]},q[3];
    float ab[3],ac[3],n[3],offset[3];sub(ab,t->p[1],t->p[0]);sub(ac,t->p[2],t->p[0]);cross(n,ab,ac);sub(offset,t->p[0],a);
    float nn=dot(n,n),plane=dot(n,offset),axis_len=b[1]-a[1];
    float y=fabsf(n[1])>1e-8f?pin(plane/n[1],0,axis_len):0;
    float point[3]={a[0],a[1]+y,a[2]},delta[3];closest(q,point,t);sub(delta,point,q);
    float best=dot(delta,delta);memcpy(pa,point,12);memcpy(pb,q,12);
    /* If the closest point is on the plane interior, the plane-distance
     * lower bound is attained. Edge tests cannot improve it. This is exact,
     * and avoids four redundant narrow-phase tests on ordinary ground. */
    float separation=plane-y*n[1];
    if(nn>1e-12f&&best<=separation*separation/nn+1e-10f)return best;
    closest(q,a,t);consider(a,q,&best,pa,pb);closest(q,b,t);consider(b,q,&best,pa,pb);
    /* Interior edge/axis pairs, including parallel and degenerate edges.
     * This closes gaps between the old two independent collision spheres. */
    for(unsigned e=0;e<3;e++){
        const float*c=t->p[e],*d=t->p[(e+1)%3];float v[3],w[3];sub(v,d,c);sub(w,a,c);
        float vv=dot(v,v),den=vv-v[1]*v[1];
        float u=den>1e-12f?pin((v[0]*w[0]+v[2]*w[2])/den,0,1):0;
        float y=pin(c[1]+u*v[1]-a[1],0,axis_len);
        if(vv>1e-12f)u=pin((dot(v,w)+v[1]*y)/vv,0,1);
        y=pin(c[1]+u*v[1]-a[1],0,axis_len);
        float point[3]={a[0],a[1]+y,a[2]};for(int k=0;k<3;k++)q[k]=c[k]+u*v[k];
        consider(point,q,&best,pa,pb);
    }
    return best;
}
static bool near_triangle(const bg_triangle*t,const float*p,float h,float r){
    for(int k=0;k<3;k++){
        float lo=t->p[0][k],hi=lo;
        for(unsigned v=1;v<3;v++){float value=t->p[v][k];if(value<lo)lo=value;if(value>hi)hi=value;}
        if(hi<p[k]-(k==1?.02f:r)||lo>p[k]+(k==1?h+.02f:r))return false;
    }
    return true;
}
static void cells(const float*p,float r,int bounds[4]){
    bounds[0]=(int)floorf((p[0]-r-bg_grid_origin[0])/bg_grid_size[0]);
    bounds[1]=(int)floorf((p[0]+r-bg_grid_origin[0])/bg_grid_size[0]);
    bounds[2]=(int)floorf((p[2]-r-bg_grid_origin[1])/bg_grid_size[1]);
    bounds[3]=(int)floorf((p[2]+r-bg_grid_origin[1])/bg_grid_size[1]);
    for(int k=0;k<4;k++)bounds[k]=(int)pin(bounds[k],0,BG_GRID-1);
}
/* Cache candidate IDs, never contact answers. The expanded AABB covers
 * every posture and every query until the anchor moves by 0.25 units.
 * Overflow falls back to the full grid; no collision is silently omitted. */
typedef struct {const bg_player*key;float anchor[3];uint16_t ids[128],count;bool valid;} terrain_candidates;
static terrain_candidates candidates[4];
static unsigned candidate_next;
void bg_terrain_reset(void){memset(candidates,0,sizeof(candidates));candidate_next=0;}
static const terrain_candidates *nearby(const bg_player*p){
    terrain_candidates*c=NULL;
    for(unsigned slot=0;slot<4;slot++)if(candidates[slot].valid&&candidates[slot].key==p){c=&candidates[slot];break;}
    if(!c)c=&candidates[candidate_next++%4];
    if(c->valid&&c->key==p&&fabsf(c->anchor[0]-p->pos[0])<=.25f&&fabsf(c->anchor[1]-p->pos[1])<=.25f&&fabsf(c->anchor[2]-p->pos[2])<=.25f)return c;
    c->key=p;c->valid=true;c->count=0;memcpy(c->anchor,p->pos,12);
    float anchor[3]={p->pos[0],p->pos[1]-.25f,p->pos[2]},radius=bg_movement.radius+.27f;int bounds[4];cells(anchor,radius,bounds);
    for(int z=bounds[2];z<=bounds[3];z++)for(int x=bounds[0];x<=bounds[1];x++){
        bg_cell cell=bg_grid[z*BG_GRID+x];
        for(unsigned j=0;j<cell.count;j++){
            unsigned id=bg_grid_indices[cell.first+j];if(!near_triangle(&bg_collision[id],anchor,bg_movement.height[0]+.5f,radius))continue;
            bool found=false;for(unsigned k=0;k<c->count;k++)if(c->ids[k]==id){found=true;break;}
            if(found)continue;
            if(c->count==128){c->count=UINT16_MAX;return c;}
            c->ids[c->count++]=id;
        }
    }
    return c;
}
bool bg_terrain_clearance(const bg_player*p){
    float r=bg_movement.radius,h=bg_body_height(p);const terrain_candidates*c=nearby(p);
    unsigned count=c->count==UINT16_MAX?bg_collision_count:c->count;
    for(unsigned j=0;j<count;j++){
        const bg_triangle*t=&bg_collision[c->count==UINT16_MAX?j:c->ids[j]];
        if(!near_triangle(t,p->pos,h,r))continue;
        float a[3],b[3];
        if(bg_capsule_triangle(p->pos,h,r,t,a,b)<(r-.003f)*(r-.003f))return false;
    }
    return true;
}
bool bg_can_stand(const bg_player*p){
    float r=bg_movement.radius,h=bg_movement.height[0];const terrain_candidates*c=nearby(p);
    unsigned count=c->count==UINT16_MAX?bg_collision_count:c->count;
    for(unsigned j=0;j<count;j++){
            const bg_triangle*t=&bg_collision[c->count==UINT16_MAX?j:c->ids[j]];
            if(!near_triangle(t,p->pos,h,r))continue;
            float a[3],b[3];float d2=bg_capsule_triangle(p->pos,h,r,t,a,b);
            /* Existing foot/side contact must not forbid standing. Only
             * newly occupied volume above the crouched axis is relevant. */
            if(a[1]>p->pos[1]+bg_body_height(p)-r+.001f&&d2<(r-.002f)*(r-.002f))return false;
    }
    return true;
}
float bg_move_capsule(bg_player*p,float dt){
    float r=bg_movement.radius,h=bg_body_height(p),impact=0;
    float distance=sqrtf(dot(p->velocity,p->velocity))*dt;
    unsigned steps=(unsigned)ceilf(distance/(r*.4f));if(steps<1)steps=1;if(steps>64)steps=64;
    float step=dt/steps;bool supported=false;float support[3]={0,1,0};
    for(unsigned s=0;s<steps;s++){
        for(int k=0;k<3;k++)p->pos[k]+=p->velocity[k]*step;
        supported=false;
        for(unsigned iteration=0;iteration<3;iteration++){
            bool adjusted=false;const terrain_candidates*c=nearby(p);
            unsigned count=c->count==UINT16_MAX?bg_collision_count:c->count;
            for(unsigned j=0;j<count;j++){
                    const bg_triangle*t=&bg_collision[c->count==UINT16_MAX?j:c->ids[j]];
                    if(!near_triangle(t,p->pos,h,r+.02f))continue;
                    float a[3],b[3],n[3];float d2=bg_capsule_triangle(p->pos,h,r,t,a,b);
                    const float skin=.015f;
                    if(d2>(r+skin+.0005f)*(r+skin+.0005f))continue;
                    float d=sqrtf(d2);sub(n,a,b);
                    if(d<1e-6f){float ab[3],ac[3];sub(ab,t->p[1],t->p[0]);sub(ac,t->p[2],t->p[0]);cross(n,ab,ac);float len=sqrtf(dot(n,n));if(len<1e-8f)continue;for(int k=0;k<3;k++)n[k]/=len;if(dot(n,p->velocity)>0)for(int k=0;k<3;k++)n[k]=-n[k];}
                    else for(int k=0;k<3;k++)n[k]/=d;
                    float into=dot(p->velocity,n);
                    if(n[1]>=bg_movement.slope[0]-.0001f&&into<=.01f){
                        if(!supported||n[1]>support[1])memcpy(support,n,12);
                        supported=true;impact=fmaxf(impact,-into);
                    }
                    if(d<r+skin-.00001f){for(int k=0;k<3;k++)p->pos[k]+=n[k]*(r+skin-d);adjusted=true;}
                    if(into<0)for(int k=0;k<3;k++)p->velocity[k]-=n[k]*into;
            }
            if(!adjusted)break;
        }
    }
    p->grounded=supported;if(supported)memcpy(p->ground_normal,support,12);
    p->vy=p->velocity[1];return impact;
}
