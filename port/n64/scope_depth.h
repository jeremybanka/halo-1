#ifndef BG_SCOPE_DEPTH_H
#define BG_SCOPE_DEPTH_H
#include <stdbool.h>
#include <math.h>
#include <string.h>
/* Conservative near-field frustum in world units. The extra margin covers
 * packed projection and exported vertex rounding. No sparse ray sampling. */
typedef struct { float plane[6][4]; } bg_scope_probe;
static inline void bg_scope_probe_init(bg_scope_probe *v,const float eye[3],
        const float forward[3],float tx,float ty,float aim_x,float aim_y) {
    float length=fmaxf(.000001f,hypotf(forward[0],forward[2]));
    float right[3]={-forward[2]/length,0,forward[0]/length};
    float up[3]={-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]};
    float slopes[4]={2*aim_x*tx,2*(1-aim_x)*tx,2*(1-aim_y)*ty,2*aim_y*ty};
    for(unsigned i=0;i<6;i++) {
        float *p=v->plane[i];
        for(unsigned a=0;a<3;a++)p[a]=i<4?(i<2?right[a]:up[a])*(i&1?-1:1)+slopes[i]*forward[a]:forward[a]*(i==4?1:-1);
        p[3]=i==5?1.125f:.03125f;
        for(unsigned a=0;a<3;a++)p[3]-=p[a]*eye[a];
    }
}
static inline float bg_scope_plane_distance(const float p[4],const float v[3]) {
    return p[0]*v[0]+p[1]*v[1]+p[2]*v[2]+p[3];
}
static inline bool bg_scope_probe_box(const bg_scope_probe *v,const float lo[3],const float hi[3]) {
    for(unsigned i=0;i<6;i++) {
        const float *p=v->plane[i];float best=p[3];
        for(unsigned a=0;a<3;a++)best+=p[a]*(p[a]>=0?hi[a]:lo[a]);
        if(best<0)return false;
    }
    return true;
}
/* Clip the entire rendered triangle, including triangles whose vertices all
 * lie outside the near volume. A convex triangle clipped by six planes needs
 * at most nine vertices. Touching or numerically uncertain counts as close. */
static inline bool bg_scope_probe_triangle(const bg_scope_probe *v,const float triangle[3][3]) {
    float polygon[2][10][3];unsigned count=3,src=0;
    memcpy(polygon[0],triangle,9*sizeof(float));
    for(unsigned plane=0;plane<6;plane++) {
        unsigned next=0;
        for(unsigned i=0;i<count;i++) {
            const float *a=polygon[src][i],*b=polygon[src][(i+1)%count];
            float da=bg_scope_plane_distance(v->plane[plane],a),db=bg_scope_plane_distance(v->plane[plane],b);
            if(!isfinite(da)||!isfinite(db))return true;
            if(da>=0) { if(next>=10)return true;memcpy(polygon[1-src][next++],a,3*sizeof(float)); }
            if((da>=0)!=(db>=0)) {
                if(next>=10)return true;
                float t=da/(da-db);
                for(unsigned k=0;k<3;k++)polygon[1-src][next][k]=a[k]+t*(b[k]-a[k]);
                next++;
            }
        }
        if(!next)return false;
        count=next;src=1-src;
    }
    return true;
}
#endif
