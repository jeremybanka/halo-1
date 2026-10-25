#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#define BG_HIERARCHY_COUNT(s,member) ((s)->member++)
#include "render_world_hierarchy.h"
#include "render_cull.h"
#include "render_visibility.h"
#include "render_world_cells.h"
#include "render_world_rep.h"
#include "render_pvs.h"
#include <t3d/t3dmath.h>
extern const bg_pvs_data bg_world_pvs;

/* Shared by the exact SDK replay fixture and the offline camera renderer.
 * Compare every bit, including rejected batches, against the flat predicate. */
int hierarchy_check(const float camera[4][4],const float projection[4][4],
        const float matrix[4][4],const float eye[3],int width,int height,
        float near_plane,uint64_t pvs,int scoped,uint32_t *visible,
        uint8_t *levels,bg_hierarchy_stats *stats) {
    const bg_hierarchy_data *d=&bg_world_hierarchy;
    uint8_t chunk_eligible[4096],node_eligible[8192];
    const int16_t *bounds[4096];
    assert(d->chunks<=4096&&d->count<=8192&&d->groups<=128);
    bool room=bg_world_rep_active(&bg_world_rep,d->map_id,eye);
    const uint32_t *cell=room?NULL:bg_world_cells_row_view(&bg_world_cells,d->map_id,eye,scoped);
    for(unsigned b=0;b<d->chunks;b++)chunk_eligible[b]=
        bg_world_cells_keep(&bg_world_cells,cell,b)&&bg_world_rep_keep(&bg_world_rep,room,b)&&
        bg_pvs_keep_chunk(&bg_world_pvs,pvs,b);
    for(unsigned i=0;i<d->count;i++)if(d->nodes[i].code&BG_HIERARCHY_LEAF)
        bounds[d->nodes[i].code&BG_HIERARCHY_VALUE]=d->nodes[i].bounds;
    bg_hierarchy_eligibility(d,chunk_eligible,node_eligible);
    T3DFrustum f;t3d_mat4_to_frustum(&f,(const T3DMat4*)matrix);
    bg_visibility_side_planes((float(*)[4])f.planes,matrix,width,height);
    uint8_t selected[6][3];bg_frustum_prepare(selected,(const float(*)[4])f.planes);
    bg_hierarchy_view v={.planes=(const float(*)[4])f.planes,.selected=selected,
        .camera=camera,.projection=projection,.eye=eye,.width=width,.height=height,
        .near_plane=near_plane,.lod=&bg_world_lod};
    memset(stats,0,sizeof(*stats));bg_hierarchy_visible(d,node_eligible,&v,visible,levels,stats);
    uint8_t reference[128];
    for(unsigned g=0;g<d->groups;g++)reference[g]=bg_world_lod_far(&bg_world_lod.groups[g],camera,projection,width,height,near_plane,eye);
    for(unsigned b=0;b<d->chunks;b++) {
        bool expected=chunk_eligible[b]&&bg_world_lod_keep(&bg_world_lod,reference,b)&&
            bg_frustum_box_cached(v.planes,selected,bounds[b]);
        bool actual=(visible[b/32]>>(b%32))&1;
        if(actual!=expected)return b+1;
        unsigned code=bg_world_lod.chunks[b];
        if(actual&&code&&levels[(code-1)/2]!=reference[(code-1)/2])return -(int)(b+1);
    }
    return 0;
}

#ifdef BG_HIERARCHY_TEST_MAIN
static uint32_t seed=0x2342abcd;
static uint32_t next(void){seed^=seed<<13;seed^=seed>>17;return seed^=seed<<5;}
static float rnd(float min,float max){return min+(max-min)*(next()&65535)/65535.f;}
int main(void) {
    for(unsigned trial=0;trial<200000;trial++) {
        int16_t parent[6],child[6];float planes[6][4];uint8_t selected[6][3];
        for(unsigned a=0;a<3;a++) {
            parent[a]=(int)(next()%60001)-30000;parent[a+3]=parent[a]+next()%2768;
            child[a]=parent[a]+next()%(parent[a+3]-parent[a]+1);
            child[a+3]=child[a]+next()%(parent[a+3]-child[a]+1);
        }
        for(unsigned i=0;i<6;i++)for(unsigned a=0;a<4;a++)planes[i][a]=rnd(-10000,10000)/(a==3?1:4096);
        bg_frustum_prepare(selected,(const float(*)[4])planes);
        bg_hierarchy_view v={.planes=(const float(*)[4])planes,.selected=selected};bg_hierarchy_stats s={0};
        int remaining=bg_hierarchy_clip(&v,parent,63,false,&s);
        bool reference=bg_frustum_box_cached(v.planes,selected,child);
        bool actual=remaining>=0&&bg_hierarchy_clip(&v,child,remaining,true,&s)>=0;
        assert(reference==actual);
    }
    for(unsigned trial=0;trial<10000;trial++) {
        T3DVec3 eye={{rnd(-2600,2600),rnd(-300,900),rnd(-2600,2600)}};
        T3DVec3 target={{eye.x+rnd(-1,1),eye.y+rnd(-.8,.8),eye.z+rnd(-1,1)}};
        T3DMat4 camera,projection,matrix;int w=trial%2?160:320,h=trial%2?120:240;
        float near_plane=trial%3?4:32,fov=trial%3?1.08f:.11f;
        t3d_mat4_look_at(&camera,&eye,&target,&(T3DVec3){{0,1,0}});
        t3d_mat4_perspective(&projection,fov,(float)w/h,near_plane,6200);
        t3d_mat4_mul(&matrix,&projection,&camera);
        uint32_t visible[128];uint8_t levels[128];bg_hierarchy_stats stats;
        uint64_t mask=trial%4?UINT64_MAX:((uint64_t)next()<<32)|next();
        int error=hierarchy_check(camera.m,projection.m,matrix.m,eye.v,w,h,near_plane,mask,trial%3==0,visible,levels,&stats);
        if(error)fprintf(stderr,"Trial %u mismatch %d\n",trial,error);
        assert(!error);
    }
    float p[6][4]={{1,0,0,0},{-1,0,0,10},{0,1,0,10},{0,-1,0,10},{0,0,1,10},{0,0,-1,10}};
    uint8_t sel[6][3];bg_frustum_prepare(sel,(const float(*)[4])p);
    int16_t box[6]={-2,-1,-1,0,1,1};bg_hierarchy_view v={.planes=(const float(*)[4])p,.selected=sel};bg_hierarchy_stats stats={0};
    assert(bg_hierarchy_clip(&v,box,63,false,&stats)==-1);
    puts("200000 inherited-plane certificates, strict contact and 10000 complete tree/flat visibility + visible-LOD comparisons passed");
}
#endif
