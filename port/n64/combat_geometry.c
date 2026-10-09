#include "combat_geometry.h"
#include "blam/vehicle_physics.h"
#include <math.h>
#include <assert.h>
static float dot3(const float*a,const float*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void cross3(const float*a,const float*b,float*out){out[0]=a[1]*b[2]-a[2]*b[1];out[1]=a[2]*b[0]-a[0]*b[2];out[2]=a[0]*b[1]-a[1]*b[0];}
float bg_vehicle_hit_ray(const bg_vehicle*v,const float origin[3],const float direction[3],float distance){
    const bg_hit_mesh*m=&bg_vehicle_hit_meshes[v->kind];float o[3],d[3],offset[3];
    for(unsigned a=0;a<3;a++)offset[a]=origin[a]-v->pos[a];
    /* Most queries are nowhere near this hull. Reject in world space before
     * transforming the ray or traversing its authored collision geometry. */
    static float radius2[4];float radius=radius2[v->kind];
    if(!radius){for(unsigned a=0;a<3;a++){float extent=fmaxf(fabsf((float)m->bounds[a]),fabsf((float)m->bounds[a+3]))/1024.f;radius+=extent*extent;}radius2[v->kind]=radius;}
    float along=fminf(distance,fmaxf(0,-dot3(offset,direction))),closest[3];
    for(unsigned a=0;a<3;a++)closest[a]=offset[a]+along*direction[a];
    if(dot3(closest,closest)>radius+.0001f)return distance;
    float basis[3][3];
    if(v->physics_valid){
        for(unsigned a=0;a<3;a++){basis[0][a]=v->forward[a];basis[1][a]=v->up[a];}
        cross3(basis[0],basis[1],basis[2]);
    }else for(unsigned axis=0;axis<3;axis++){
        float unit[3]={0};unit[axis]=1;bg_vehicle_transform(v,unit,basis[axis]);
        for(unsigned a=0;a<3;a++)basis[axis][a]-=v->pos[a];
    }
    float inverse[3];bool parallel[3];
    for(unsigned axis=0;axis<3;axis++){
        o[axis]=dot3(offset,basis[axis]);d[axis]=dot3(direction,basis[axis]);
        parallel[axis]=fabsf(d[axis])<1e-8f;inverse[axis]=parallel[axis]?0:1/d[axis];
    }
    uint16_t stack[16]={0};unsigned pending=1;
    while(pending){
      const bg_hit_node*node=&m->nodes[stack[--pending]];
      float lo=0,hi=distance;bool overlap=true;
      for(unsigned a=0;a<3;a++){
        float lower=node->bounds[a]/1024.f,upper=node->bounds[a+3]/1024.f;
        if(parallel[a]){if(o[a]<lower||o[a]>upper){overlap=false;break;}}
        else{float x=(lower-o[a])*inverse[a],y=(upper-o[a])*inverse[a];lo=fmaxf(lo,fminf(x,y));hi=fminf(hi,fmaxf(x,y));if(lo>hi){overlap=false;break;}}
      }
      if(!overlap)continue;
      if(!node->count){assert(pending+2<=16);stack[pending++]=node->right;stack[pending++]=node->first;continue;}
      for(unsigned i=node->first;i<node->first+node->count;i++){
        const int16_t*a=m->vertices[m->triangles[i][0]],*b=m->vertices[m->triangles[i][1]],*c=m->vertices[m->triangles[i][2]];
        float e1[3],e2[3],tvec[3],p[3],q[3];
        for(unsigned k=0;k<3;k++){e1[k]=(b[k]-a[k])/1024.f;e2[k]=(c[k]-a[k])/1024.f;tvec[k]=o[k]-a[k]/1024.f;}
        cross3(d,e2,p);float det=dot3(e1,p);if(fabsf(det)<1e-8f)continue;
        float inverse=1/det,u=dot3(tvec,p)*inverse;if(u<0||u>1)continue;
        cross3(tvec,e1,q);float w=dot3(d,q)*inverse;if(w<0||u+w>1)continue;
        float t=dot3(e2,q)*inverse;if(t>=0&&t<distance)distance=t;
      }
    }return distance;
}
