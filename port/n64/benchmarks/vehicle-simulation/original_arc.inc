/* Frozen pre-change port function, checkpoint 031e79f5; diagnostic only. */
static bool vehicle_query_original_arc(const float origin[3],const float target[3],float speed,float gravity,bool high,float direction[3]){
    float dx=target[0]-origin[0],dz=target[2]-origin[2],height=target[1]-origin[1],range=hypotf(dx,dz),v2=speed*speed;
    float disc=v2*v2-gravity*(gravity*range*range+2*height*v2);if(range<.1f||disc<0||speed<.1f)return false;
    float tangent=(v2+(high?1:-1)*sqrtf(disc))/(gravity*range),co=1/sqrtf(1+tangent*tangent);
    direction[0]=dx/range*co;direction[1]=tangent*co;direction[2]=dz/range*co;
    float previous[3];memcpy(previous,origin,12);float duration=range/(speed*co);
    for(unsigned step=1;step<=12;step++){
        float t=duration*step/12,point[3],d[3];for(unsigned k=0;k<3;k++)point[k]=origin[k]+direction[k]*speed*t;point[1]-=.5f*gravity*t*t;
        sub(d,point,previous);float distance=sqrtf(dot(d,d));if(distance>.0001f){for(unsigned k=0;k<3;k++)d[k]/=distance;if(bg_raycast(previous,d,distance)<distance-.03f)return false;}memcpy(previous,point,12);
    }
    return true;
}
