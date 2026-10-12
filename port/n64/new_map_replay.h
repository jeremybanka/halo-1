#ifndef BG_NEW_MAP_REPLAY_H
#define BG_NEW_MAP_REPLAY_H
/* Staged source locations and changing loadouts; movement, shots, grenade
 * fuses, damage, deaths, respawns and pickups use production simulation. */
static void new_map_replay_input(bg_input in[4],float time){
    static int previous_cycle=-1,previous_stage=-1,weapon_for[4]={-1,-1,-1,-1};
    static unsigned previous_map=~0u;
    int c=(int)(time/75.f),stage=(int)(fmodf(time,75.f)/15.f);float t=fmodf(time,75.f);
    memset(in,0,sizeof(bg_input)*4);
    if(c!=previous_cycle||previous_map!=bg_map_id()){
        previous_map=bg_map_id();
        previous_cycle=c;previous_stage=-1;bg_set_players(4);bg_reset();bg_set_score_limit(1000);
        for(unsigned p=0;p<4;p++)weapon_for[p]=-1;
    }
    if(stage!=previous_stage&&stage){
        previous_stage=stage;
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];if(q->health<=0)continue;
            unsigned eligible=0;for(unsigned i=0;i<bg_spawn_count;i++)eligible+=bg_slayer_spawns[i]!=0;
            unsigned nth=(stage*4+p)%eligible,index=0;
            while(index<bg_spawn_count){if(bg_slayer_spawns[index]&&nth--==0)break;index++;}
            if(index==bg_spawn_count)index=0;
            memcpy(q->pos,bg_spawns[index].pos,12);q->yaw=bg_spawns[index].yaw;
            float floor=bg_floor(q->pos[0],q->pos[2],q->pos[1]+.5f);q->pos[1]=floor+.015f;
            memset(q->velocity,0,12);q->vy=0;q->grounded=true;q->climbing=false;
            q->grenades[0]=q->grenades[1]=2;weapon_for[p]=-1;
        }
    }
    if(t<5)return;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];if(q->health<=0){weapon_for[p]=-1;continue;}
        int weapon=(((int)(t/7))+(int)p*2)%8;
        if(weapon_for[p]!=weapon){equip(p,weapon,&in[p]);weapon_for[p]=weapon;}
        unsigned target=(p+1)%4;
        for(unsigned n=1;n<4;n++)if(bg_players[(p+n)%4].health>0){target=(p+n)%4;break;}
        const bg_player*other=&bg_players[target];
        float dx=other->pos[0]-q->pos[0],dz=other->pos[2]-q->pos[2];
        float yaw=-atan2f(dz,dx),pitch=atan2f(other->pos[1]+.35f-q->pos[1]-bg_eye_height(q),hypotf(dx,dz));
        in[p].turn=clamp(angle_delta(yaw,q->yaw)*.6f,-.65f,.65f);
        in[p].look=clamp((pitch-q->pitch)*1.2f,-.5f,.5f);
        in[p].strafe=fmodf(t+p,6)<3?.35f:-.35f;
        in[p].forward=fmodf(t+p,8)<2?.25f:0;
        in[p].fire=fmodf(t+p*.3f,1.5f)<1;
        in[p].grenade=fmodf(t+p,5)<1.f/30;
        if(q->ammo==0&&q->reserve)in[p].reload=true;
    }
}
#endif
