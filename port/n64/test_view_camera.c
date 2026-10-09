#include "view_camera.h"
#include <assert.h>
#include <stdio.h>
/* Independent polynomial interpolation checks the source stencil at both
 * boundaries and through every control-point interval, including clamping. */
int main(void){
    float points[9][3];for(unsigned i=0;i<9;i++){
        float t=i/8.f;points[i][0]=t;points[i][1]=t*t;points[i][2]=t*t*t;
    }
    bg_camera_track track={points,9,{0}};
    for(int i=-10;i<=110;i++){
        float t=i/100.f,u=fmaxf(0,fminf(1,t)),out[3];
        bg_camera_track_sample(&track,(t-.5f)*3.14159265359f,out);
        assert(fabsf(out[0]-u)<1e-5f);assert(fabsf(out[1]-u*u)<1e-5f);assert(fabsf(out[2]-u*u*u)<1e-5f);
    }
    for(unsigned v=0;v<4;v++)for(unsigned s=0;s<5;s++){
        const bg_camera_track*t=&bg_camera_tracks[v][s];if(!t->points)continue;
        for(int p=-90;p<=90;p++){
            float offset[3];bg_camera_track_offset(t,.6f,p*3.14159265359f/180,offset);
            for(unsigned a=0;a<3;a++)assert(isfinite(offset[a])&&fabsf(offset[a])<10);
        }
        float a[3],b[3];bg_camera_track_offset(t,0,0,a);bg_camera_track_offset(t,1.57079632679f,0,b);
        assert(fabsf(a[0]+b[2])<1e-5f&&fabsf(a[2]-b[0])<1e-5f&&a[1]==b[1]);
    }
    for(unsigned n=0;n<2;n++)for(unsigned m=1;m<=10;m++){
        float fov=n?.72f:1.08f,z=bg_camera_zoom_fov(fov,m);
        assert(fabsf(tanf(fov*.5f)/tanf(z*.5f)-m)<1e-4f);
    }
    /* Mirror the SDK's integer packing, then recover its actual screen scale.
     * This catches projection/HUD disagreement that float matrix tests miss. */
    float norm=2/BG_CAMERA_NORMALIZE_SUM;
    for(unsigned size=120;size<=320;size+=40){
        float packed=roundf(size*norm*64),w=roundf(65535*norm)/65536.f;
        assert(packed==size*norm*64);assert(fabsf(packed/(64*w)-size)<1e-5f);
    }
    assert(roundf(65535*norm*8)==65536*norm*8);
    float n0,f0,n1,f1;bg_camera_depth(false,&n0,&f0);bg_camera_depth(true,&n1,&f1);
    assert(f1==f0*2&&n1==n0);
    assert(n0/32.f<.2f); /* Remains inside the original on-foot capsule radius. */
    assert(f0/n0<6200.f/1.4f&&f1/n1<12400.f/2.8f);
    puts("PASS: source cubic interpolation, all seat tracks/pitch extremes, yaw basis, exact zoom magnification and world depth precision");
}
