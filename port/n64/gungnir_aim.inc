/* Strong aim assist is an off-axis weapon ray, never a camera snap. It uses
 * the same visible target and screen-space circle for HUD, gun and shots. */
#include "gungnir.h"
#include "view_layout.h"
bool bg_gungnir_aim_active(const bg_player *p) {
    return (bg_armor_def(p->armor)->abilities&BG_ARMOR_AUTO_AIM)&&p->health>0&&
        !p->zoom&&bg_player_personal_weapon(p);
}
bg_aim_target bg_gungnir_target(unsigned owner) {
    bg_aim_target best={.player=-1,.distance=1e9f};
    if(owner>=active_players)return best;
    const bg_player *p=&bg_players[owner];if(!bg_gungnir_aim_active(p)||bg_player_objective(owner)>=0)return best;
    bg_view_rect view=bg_view_area(active_players,owner);
    float fov=view.w==320&&view.h==120?.72f:1.08f;
    float radius=2*BG_GUNGNIR_RADIUS*tanf(fov*.5f)*fminf(view.w,view.h)/view.h;
    float cp=cosf(p->pitch),sp=sinf(p->pitch),cy=cosf(p->yaw),sy=sinf(p->yaw);
    float forward[3]={cy*cp,sp,-sy*cp},right[3]={sy,0,cy},up[3]={-cy*sp,cp,sy*sp};
    float origin[3],unused[3];aim(p,unused,origin);float best_score=radius*radius;
    for(unsigned j=0;j<bg_unit_count();j++) {
        const bg_player *q=&bg_players[j];
        if(q->health<=0||bg_players_allied(owner,j)||bg_player_visibility(q)<=0)continue;
        /* Try exposed upper torso/head as well as the center. The score is
         * projected distance from the ring center, rather than world range. */
        for(unsigned sample=0;sample<3;sample++) {
            float height=bg_body_height(q),point[3]={q->pos[0],q->pos[1]+height*(float[]){.7f,.9f,.5f}[sample],q->pos[2]},d[3];
            sub(d,point,origin);float z=dot(d,forward),distance=sqrtf(dot(d,d));
            if(z<=.01f||distance>100)continue;
            float sx=dot(d,right)/z,sy_screen=dot(d,up)/z,score=sx*sx+sy_screen*sy_screen;
            if(score>best_score||(score==best_score&&distance>=best.distance))continue;
            for(unsigned k=0;k<3;k++)d[k]/=distance;
            if(bg_raycast(origin,d,distance)<distance-.015f)continue;
            bool blocked=false;
            for(unsigned v=0;v<bg_vehicle_count;v++)if((int)v!=p->vehicle&&bg_vehicle_body_present(&bg_vehicles[v])&&bg_vehicle_hit_ray(&bg_vehicles[v],origin,d,distance)<distance-.015f){blocked=true;break;}
            if(blocked)continue;
            best=(bg_aim_target){.player=(int)j,.distance=distance,.auto_level=1};memcpy(best.point,point,12);best_score=score;
        }
    }
    return best;
}
void bg_gungnir_weapon_angles(unsigned owner,float *yaw,float *pitch) {
    const bg_player *p=&bg_players[owner];*yaw=p->yaw;*pitch=p->pitch;
    bg_aim_target target=bg_gungnir_target(owner);if(target.player<0)return;
    float origin[3],unused[3];aim(p,unused,origin);
    float d[3]={target.point[0]-origin[0],target.point[1]-origin[1],target.point[2]-origin[2]};
    *yaw=atan2f(-d[2],d[0]);*pitch=atan2f(d[1],hypotf(d[0],d[2]));
}
