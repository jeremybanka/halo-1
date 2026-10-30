/* Matched native zoom route: ordinary production cameras and HUDs. */
#define BG_SCOPE_QA_PAGES 10
static void scope_qa_stage(unsigned *count,unsigned page) {
    *count=page==4||page==5||page==8?4:page==6?2:page==7?3:1;
    bg_set_players(*count);memcpy(bg_players,polish_players,sizeof(polish_players));
    bg_vehicle_count=bg_pickup_count=0;
    for(unsigned p=0;p<*count;p++) {
        bg_player *q=&bg_players[p];q->health=q->shield=100;q->vehicle=-1;
        q->weapon=BG_W_PISTOL;q->zoom=1;q->yaw=0;q->pitch=-.6f;q->flashlight_on=false;
        q->crouch_amount=page==1?1:0;
        if(page==2){q->weapon=BG_W_SNIPER;q->zoom=2;q->pitch=-1.3f;}
        if(page>=6&&page<=8){q->weapon=p&1?BG_W_SNIPER:BG_W_PISTOL;q->zoom=p&1?2:1;}
        if(page==9){q->pitch=-1.3f;q->crouch_amount=1;}
        if(page==0)q->damage_indicator[0]=.8f;
    }
    if(page==3) {
        static float position[3],yaw;static bool found;
        if(!found)for(unsigned s=0;s<bg_spawn_count&&!found;s++)for(unsigned d=0;d<8&&!found;d++) {
            float a=d*.7853981634f,dir[3]={cosf(a),0,-sinf(a)},normal[3];
            float origin[3]={bg_spawns[s].pos[0],bg_spawns[s].pos[1]+.62f,bg_spawns[s].pos[2]};
            float hit=bg_world_raycast_normal(origin,dir,4,normal);
            if(hit>.5f&&hit<3.9f&&fabsf(normal[1])<.2f){
                for(unsigned k=0;k<3;k++)position[k]=origin[k]+dir[k]*(hit-.2f);
                position[1]-=.62f;yaw=a;found=true;
            }
        }
        assertf(found,"Scope near-wall fixture");memcpy(bg_players[0].pos,position,sizeof(position));
        bg_players[0].yaw=yaw;bg_players[0].pitch=0;
    }
    if(page==4||page==5) {
        float target_pos[3]={26,bg_floor(26,34,100)+.02f,34};
        bg_add_vehicle(BG_V_SCORPION,target_pos,0);bg_vehicle_physics_prepare();
        for(unsigned p=0;p<4;p++){
            bg_player *q=&bg_players[p];q->pos[0]=-26;q->pos[2]=-31;q->pos[1]=bg_floor(-26,-31,100)+6;
            float target[3]={26,bg_floor(26,34,100)+.8f,34};
            q->yaw=-atan2f(target[2]-q->pos[2],target[0]-q->pos[0])+(page==5?.002f:0);
            q->pitch=atan2f(target[1]-q->pos[1]-.62f,hypotf(52,65));q->invisibility=1;
            q->weapon=p<2?BG_W_PISTOL:BG_W_SNIPER;q->zoom=p==0?0:p==3?2:1;
        }
    }
    bg_scene_update(0,0);
}
