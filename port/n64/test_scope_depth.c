#include "scope_depth.h"
#include "view_camera.h"
#include "hud_layout.h"
#include "view_layout.h"
#include <assert.h>
#include <stdio.h>
static unsigned random_state=512;
static float random_float(void){random_state=random_state*1664525u+1013904223u;return (random_state>>8)/16777216.f;}
int main(void) {
    bg_scope_probe probe;
    float eye[3]={0,.62f,0},forward[3]={1,0,0};
    float tangent=tanf(bg_camera_zoom_fov(1.08f,2)*.5f);
    bg_scope_probe_init(&probe,eye,forward,tangent*4/3,tangent,.5f,.5f);
    const float floor[3][3]={{-30,0,-30},{-30,0,30},{30,0,0}};
    assert(!bg_scope_probe_triangle(&probe,floor));
    forward[0]=cosf(-.6f);forward[1]=sinf(-.6f);
    bg_scope_probe_init(&probe,eye,forward,tangent*4/3,tangent,.5f,.5f);
    assert(bg_scope_probe_triangle(&probe,floor));
    eye[1]=.32f;
    bg_scope_probe_init(&probe,eye,forward,tangent*4/3,tangent,.5f,.5f);
    assert(bg_scope_probe_triangle(&probe,floor));
    forward[0]=1;forward[1]=0;
    bg_scope_probe_init(&probe,eye,forward,tangent*4/3,tangent,.5f,.5f);
    const float wall[3][3]={{.2f,-10,-10},{.2f,10,-10},{.2f,0,10}};
    const float far[3][3]={{20,-10,-10},{20,10,-10},{20,0,10}};
    assert(bg_scope_probe_triangle(&probe,wall));assert(!bg_scope_probe_triangle(&probe,far));
    const float touching[3][3]={{1.125f,.32f,-.1f},{1.125f,.32f,.1f},{1.125f,.42f,0}};
    assert(bg_scope_probe_triangle(&probe,touching));
    /* Independent sampled-point oracle: any point in the near volume must
     * keep its parent triangle, including long off-screen crossing faces. */
    unsigned witnessed=0;
    for(unsigned n=0;n<6000;n++) {
        float triangle[3][3];for(unsigned v=0;v<3;v++)for(unsigned a=0;a<3;a++)triangle[v][a]=random_float()*8-4;
        bool intersects=bg_scope_probe_triangle(&probe,(const float (*)[3])triangle);
        for(unsigned i=0;i<=10;i++)for(unsigned j=0;j<=10-i;j++) {
            float point[3];for(unsigned a=0;a<3;a++)point[a]=(triangle[0][a]*i+triangle[1][a]*j+triangle[2][a]*(10-i-j))*.1f;
            bool inside=true;for(unsigned p=0;p<6;p++)if(bg_scope_plane_distance(probe.plane[p],point)<0)inside=false;
            if(inside){assert(intersects);witnessed++;}
        }
    }
    assert(witnessed>500);
    /* Every supported scoped viewport's padded near volume fits inside the
     * candidate cache radius (2 units minus its .5-unit reuse tolerance). */
    for(unsigned views=1;views<=4;views++)for(unsigned p=0;p<views;p++)for(unsigned mag=2;mag<=10;mag+=8) {
        bg_view_rect area=bg_view_area(views,p);float ax,ay;
        bg_hud_aim_point(views,p,0,0,1,1,&ax,&ay);
        float fov=area.w==320&&area.h==120?.72f:1.08f;
        float ty=tanf(bg_camera_zoom_fov(fov,mag)*.5f),tx=ty*area.w/area.h;
        float x=2*fmaxf(ax,1-ax)*tx*1.125f+.03125f;
        float y=2*fmaxf(ay,1-ay)*ty*1.125f+.03125f;
        assert(sqrtf(1.125f*1.125f+x*x+y*y)<1.5f);
    }
    printf("PASS: close ground/walls, open distant view, touching triangles, %u independent interior witnesses and all viewport cache bounds\n",witnessed);
}
