/* Bounded surface light: source cyborg radius 6, falloff 20°, cutoff 45°.
 * Shared by all cameras. No searches or allocations per split viewport.
 * Cells crossing a corner/discontinuity are rejected rather than bridging
 * unrelated walls. Opaque scene depth still occludes the resulting patch. */
static T3DVertPacked flashlight_vertices[BG_FRAME_SLOTS][4][17] __attribute__((aligned(16)));
static T3DMat4FP flashlight_matrices[BG_FRAME_SLOTS][4];
static float flashlight_points[4][33][3],flashlight_normals[4][33][3];
static bool flashlight_hits[4][33],flashlight_active[4];
#include "flashlight_surface.h"
static void prepare_flashlights(void) {
    for(unsigned p=0;p<views;p++) {
        const bg_player *q=&bg_players[p];
        flashlight_active[p]=q->health>0&&q->flashlight_on&&q->vehicle<0;
        if(!flashlight_active[p])continue;
        float eye[3]={q->pos[0],q->pos[1]+bg_eye_height(q),q->pos[2]};
        flashlight_gather(eye);
        float cy=cosf(q->yaw),sy=sinf(q->yaw),cp=cosf(q->pitch),sp=sinf(q->pitch);
        float f[3]={cy*cp,sp,-sy*cp},r[3]={sy,0,cy},u[3]={-cy*sp,cp,sy*sp};
        T3DVertPacked *v=flashlight_vertices[slot][p];memset(v,0,17*sizeof(*v));
        matrix(&flashlight_matrices[slot][p],BG_SCALE/1024.f,0,0,eye);
        for(unsigned n=0;n<33;n++) {
            float radius=n?(n<=16?.36397023f:1.f):0;
            float angle=(n?((n-1)%16):0)*.3926990817f;
            float d[3],length=sqrtf(1+radius*radius),normal[3]={0};
            for(unsigned a=0;a<3;a++)d[a]=(f[a]+radius*(r[a]*cosf(angle)+u[a]*sinf(angle)))/length;
            float distance=flashlight_raycast(eye,d,normal);
            /* The outer ring is a zero-alpha boundary. If its ray leaves the
             * surface/range, clip it to the center hit plane and recast. This
             * closes the fade at the six-unit limit instead of cutting a
             * bright wedge out of the footprint. The recast still occludes. */
            if(n>16 && distance>=5.999f && flashlight_hits[p][0]) {
                float target[3],plane=0;
                for(unsigned a=0;a<3;a++) {
                    target[a]=eye[a]+d[a]*6;
                    plane+=(target[a]-flashlight_points[p][0][a])*flashlight_normals[p][0][a];
                }
                float length2=0;
                for(unsigned a=0;a<3;a++) {
                    d[a]=target[a]-plane*flashlight_normals[p][0][a]-eye[a];
                    length2+=d[a]*d[a];
                }
                if(length2>.0001f) {
                    for(unsigned a=0;a<3;a++)d[a]/=sqrtf(length2);
                    distance=flashlight_raycast(eye,d,normal);
                }
            }
            flashlight_hits[p][n]=distance<5.999f;
            for(unsigned a=0;a<3;a++) {
                flashlight_points[p][n][a]=eye[a]+d[a]*distance;
                flashlight_normals[p][n][a]=normal[a];
                t3d_vertbuffer_get_pos(v,n)[a]=lrintf((d[a]*distance+normal[a]*.009f)*1024.f);
            }
            unsigned alpha=n>16?0:(unsigned)(65*fmaxf(0,1-distance/6));
            *t3d_vertbuffer_get_color(v,n)=0xffffff00u|alpha;
        }
        data_cache_hit_writeback(v,17*sizeof(*v));
        data_cache_hit_writeback(&flashlight_matrices[slot][p],sizeof(T3DMat4FP));
    }
}
static bool flashlight_triangle(unsigned p,unsigned a,unsigned b,unsigned c) {
    if(!flashlight_hits[p][a]||!flashlight_hits[p][b]||!flashlight_hits[p][c])return false;
    unsigned ids[2]={b,c};
    for(unsigned j=0;j<2;j++) {
        float dot=0,plane=0;
        for(unsigned k=0;k<3;k++) {
            dot+=flashlight_normals[p][a][k]*flashlight_normals[p][ids[j]][k];
            plane+=(flashlight_points[p][ids[j]][k]-flashlight_points[p][a][k])*flashlight_normals[p][a][k];
        }
        if(dot<.8f||fabsf(plane)>.25f)return false;
    }
    t3d_tri_draw(a,b,c);return true;
}
static unsigned draw_flashlights(void) {
    unsigned total=0;
    if(!(flashlight_active[0]||flashlight_active[1]||flashlight_active[2]||flashlight_active[3]))return 0;
    rdpq_sync_pipe();
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH);
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);rdpq_mode_zbuf(true,false);
    for(unsigned p=0;p<views;p++)if(flashlight_active[p]) {
        t3d_matrix_set(&flashlight_matrices[slot][p],true);
        t3d_vert_load(flashlight_vertices[slot][p],0,34);
        for(unsigned i=0;i<16;i++) {
            unsigned a=1+i,b=1+(i+1)%16;
            total+=flashlight_triangle(p,0,a,b);
            total+=flashlight_triangle(p,a,a+16,b+16);
            total+=flashlight_triangle(p,a,b+16,b);
        }
        t3d_tri_sync();
    }
    rdpq_sync_pipe();rdpq_mode_blender(0);rdpq_mode_zbuf(true,true);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
    return total;
}
