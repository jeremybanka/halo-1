#include "movement.h"
#include <math.h>
static float pin(float x,float lo,float hi){return fmaxf(lo,fminf(hi,x));}
float bg_aim_attenuation(float value,float maximum){
    if(maximum<=0||value>=maximum)return 0;
    return value<=maximum*.5f?1:(maximum-value)/(maximum*.5f);
}
float bg_look_curve(float value){
    float x=pin(fabsf(value)*5,0,5);unsigned lo=(unsigned)x,hi=lo<5?lo+1:lo;
    float y=bg_movement.curve[lo]+(bg_movement.curve[hi]-bg_movement.curve[lo])*(x-lo);
    return copysignf(y,value);
}
void bg_walk_velocity(bg_player*p,float forward,float strafe,float dt){
    float length=hypotf(forward,strafe);if(length>1){forward/=length;strafe/=length;}
    float c=p->crouch_amount;
    float f=forward*(bg_movement.run[forward<0]+(bg_movement.sneak[forward<0]-bg_movement.run[forward<0])*c);
    float s=strafe*(bg_movement.run[2]+(bg_movement.sneak[2]-bg_movement.run[2])*c);
    float cy=cosf(p->yaw),sy=sinf(p->yaw);
    float dx=cy*f+sy*s-p->velocity[0],dz=-sy*f+cy*s-p->velocity[2];
    float delta=hypotf(dx,dz),limit=dt*(p->grounded?bg_movement.accel[0]+(bg_movement.accel[1]-bg_movement.accel[0])*c:bg_movement.accel[2]);
    if(delta>limit){dx*=limit/delta;dz*=limit/delta;}
    p->velocity[0]+=dx;p->velocity[2]+=dz;
}
void bg_look_input(bg_player*p,const bg_input*in,float magnification,float dt,float*yaw,float*pitch){
    float x=in->turn,y=in->look,ax=fabsf(x),ay=fabsf(y);
    /* Original diagonal-look expansion before the nonlinear response. */
    if(ax>.1f&&ay>.1f){float small=fminf(ax,ay)/fmaxf(ax,ay),scale=sqrtf(1+small*small);x*=scale;y*=scale;}
    x=pin(x,-1,1);y=pin(y,-1,1);
    *yaw=bg_look_curve(x)*bg_movement.yaw_rate*(3.14159265358979323846f/180.f)*dt/magnification;
    *pitch=bg_look_curve(y)*bg_movement.pitch_rate*(3.14159265358979323846f/180.f)*dt/magnification;
    if(fabsf(x)>=bg_movement.peg_threshold){
        *yaw*=1+(bg_movement.peg_scale-1)*pin(p->look_peg_time/bg_movement.peg_time,0,1);
        p->look_peg_time=fminf(bg_movement.peg_time,p->look_peg_time+dt);
    }else p->look_peg_time=0;
}
