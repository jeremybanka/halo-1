#ifndef BG_VIEW_CAMERA_H
#define BG_VIEW_CAMERA_H
#include <math.h>
#include <stdbool.h>
typedef struct { const float (*points)[3]; unsigned count; float origin[3]; } bg_camera_track;
#define BG_CAMERA_NORMALIZE_SUM 1024.f
extern const bg_camera_track bg_camera_tracks[4][5];
/* following_camera.c:camera_track_splut + real_math.h:uniform_cubic_spline.
 * Points are still in Xbox forward/left/up coordinates, in world units. */
static inline void bg_camera_track_sample(const bg_camera_track*track,float pitch,float out[3]){
    float t=fmaxf(0,fminf(1,(pitch+1.57079632679f)/3.14159265359f));
    unsigned frame=(unsigned)((track->count-1)*t),index=frame;
    while(index>0&&(index+4>track->count||index>(frame?frame-1:0)))index--;
    float h=1.f/(track->count-1),t0=index*h;
    for(unsigned a=0;a<3;a++){
        float f0=track->points[index][a],f1=track->points[index+1][a],f2=track->points[index+2][a],f3=track->points[index+3][a];
        f3-=f2;f2-=f1;f1-=f0;f3-=f2;f2-=f1;
        out[a]=f0+(t-t0)/h*(f1+(t-(t0+h))*(f2+(t-(t0+2*h))*(f3-f2)/(3*h))/(2*h));
    }
}
static inline void bg_camera_track_offset(const bg_camera_track*track,float yaw,float pitch,float out[3]){
    float offset[3];bg_camera_track_sample(track,pitch,offset);
    float c=cosf(yaw),s=sinf(yaw);
    out[0]=offset[0]*c+offset[1]*s;out[1]=offset[2];out[2]=-offset[0]*s+offset[1]*c;
}
/* Magnification scales focal length, not the angle itself. */
static inline float bg_camera_zoom_fov(float fov,float magnification){
    return 2*atanf(tanf(fov*.5f)/magnification);
}
/* A bounded scope-only distance extension. The camera-space gun has a
 * separate projection, so close sleeves do not constrain world depth. */
static inline void bg_camera_depth(bool scoped,float*near,float*far){
    /* 1/8 Halo unit stays inside the on-foot collision radius, while
     * retaining enough RDP depth precision for wall-attached details.
     * First-person arms keep their separate .125 render-unit projection. */
    *near=4.f;*far=scoped?12400.f:6200.f;
}
#endif
