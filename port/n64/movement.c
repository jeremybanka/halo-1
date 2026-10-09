#include "movement.h"
#include "combat.h"
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
float bg_body_height(const bg_player*p){return bg_movement.height[0]+(bg_movement.height[1]-bg_movement.height[0])*p->crouch_amount;}
void bg_start_landing(bg_player*p,float speed){
    const float*l=bg_movement.landing;
    if(speed<l[0])return;
    p->hard_landing=speed>=l[1];
    /* Preserve biped_start_landing's hard branch: its numerator is the full
     * impact speed, not speed minus the hard threshold. Recovery truncates
     * to original 30 Hz ticks. Impact is relative to the contact plane. */
    float range=p->hard_landing?l[2]-l[1]:l[1]-l[0];
    float fraction=range>0?pin((p->hard_landing?speed:speed-l[0])/range,0,1):0;
    p->landing_duration=p->landing_time=(int)((p->hard_landing?l[4]:l[3])*30*fraction)/30.f;
}
void bg_walk_velocity(bg_player*p,float forward,float strafe,float dt){
    float length=hypotf(forward,strafe);if(length>1){forward/=length;strafe/=length;}
    if(p->hard_landing&&p->landing_time>0)forward=strafe=0;
    float stun=1-p->body_stun*bg_stun_config[0];forward*=stun;strafe*=stun;
    float c=p->crouch_amount;
    float f=forward*(bg_movement.run[forward<0]+(bg_movement.sneak[forward<0]-bg_movement.run[forward<0])*c);
    float s=strafe*(bg_movement.run[2]+(bg_movement.sneak[2]-bg_movement.run[2])*c);
    float cy=cosf(p->yaw),sy=sinf(p->yaw),v[3]={cy*f+sy*s,0,-sy*f+cy*s};
    const float*n=p->ground_normal,*k=bg_movement.slope;
    if(p->grounded&&n[1]>0){
        float speed=hypotf(f,s);
        v[1]=-(v[0]*n[0]+v[2]*n[2])/n[1];
        float len=sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
        if(len>0){
            for(unsigned a=0;a<3;a++)v[a]/=len;
            float scale=1;
            if(v[1]<=k[2])scale=k[3];
            else if(v[1]<k[1])scale=1+(v[1]-k[1])*(k[3]-1)/(k[2]-k[1]);
            else if(v[1]>=k[5])scale=k[6];
            else if(v[1]>k[4])scale=1+(v[1]-k[4])*(k[6]-1)/(k[5]-k[4]);
            for(unsigned a=0;a<3;a++)v[a]*=speed*scale;
        }
    }
    float d[3]={v[0]-p->velocity[0],p->grounded?v[1]-p->velocity[1]:0,v[2]-p->velocity[2]};
    float delta=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);
    float limit=dt*(p->grounded?bg_movement.accel[0]+(bg_movement.accel[1]-bg_movement.accel[0])*c:bg_movement.accel[2]);
    if(delta>limit)for(unsigned a=0;a<3;a++)d[a]*=limit/delta;
    for(unsigned a=0;a<3;a++)p->velocity[a]+=d[a];
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
    *yaw*=1-p->body_stun*bg_stun_config[1];*pitch*=1-p->body_stun*bg_stun_config[1];
}
