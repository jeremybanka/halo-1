#ifndef BG_INTERACTION_QA_H
#define BG_INTERACTION_QA_H
/* Each frozen image advances real use input through the production simulation.
 * Only staging and inspection cameras differ from ordinary gameplay. */
static int interaction_qa_vehicles[4];
static void interaction_qa_stage(void){
    bg_set_players(4);bg_reset();bg_set_score_limit(1000);bg_pickup_count=bg_vehicle_count=0;
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->pos[0]=p*6;q->pos[2]=4;q->pos[1]=bg_floor(q->pos[0],4,100)+.015f;
        q->yaw=-1.5707963f;q->pitch=0;
        if(BG_INTERACTION_QA<2){
            int weapon=(int[][4]){{BG_W_AR,BG_W_PISTOL,BG_W_SHOTGUN,BG_W_SNIPER},
                {BG_W_PLASMA_PISTOL,BG_W_PLASMA_RIFLE,BG_W_NEEDLER,BG_W_ROCKET}}[BG_INTERACTION_QA][p];
            q->inventory[0]=q->weapon=weapon==BG_W_AR?BG_W_PISTOL:BG_W_AR;q->inventory[1]=weapon==BG_W_NEEDLER?BG_W_PISTOL:BG_W_NEEDLER;
            float pos[3]={q->pos[0]+.6f,q->pos[1],q->pos[2]};bg_add_pickup(weapon,pos);
        }else{
            unsigned kind=BG_INTERACTION_QA==2||BG_INTERACTION_QA==4?p:BG_V_WARTHOG;
            if(BG_INTERACTION_QA==4)kind=(unsigned[]){BG_V_WARTHOG,BG_V_GHOST,BG_V_BANSHEE,BG_V_WARTHOG}[p];
            interaction_qa_vehicles[p]=bg_add_vehicle(kind,q->pos,0);
        }
    }
    bg_input in[4]={0};
    if(BG_INTERACTION_QA>=2){
        for(unsigned p=0;p<4;p++)bg_players[p].pos[2]+=5;
        for(unsigned tick=0;tick<45;tick++)bg_tick(in,1.f/30);
        for(unsigned p=0;p<4;p++){
            bg_vehicle*v=&bg_vehicles[interaction_qa_vehicles[p]];unsigned seat=BG_INTERACTION_QA==3?p%3:0;
            if(BG_INTERACTION_QA==4){v->pitch=3.14159265f;v->pos[1]+=.5f;v->physics_valid=false;}
            bg_vehicle_physics_prepare();
            bg_vehicle_seat_position(v,seat,true,bg_players[p].pos);bg_players[p].pos[1]=bg_floor(bg_players[p].pos[0],bg_players[p].pos[2],100)+.015f;
            if(BG_INTERACTION_QA==4){memcpy(bg_players[p].pos,v->pos,12);bg_players[p].pos[2]+=1.2f;}
            bg_players[p].yaw=v->yaw;bg_players[p].vy=0;
        }
    }
    for(unsigned tick=0;tick!=(unsigned)BG_INTERACTION_TICK;tick++){
        for(unsigned p=0;p<4;p++)in[p].interact=tick<10||(BG_INTERACTION_QA!=4&&tick>=90&&tick<100);
        bg_clear_events();bg_tick(in,1.f/30);
    }
    if(BG_INTERACTION_QA<2)for(unsigned p=0;p<4;p++)bg_players[p].invisibility=1;
    (*qa.seconds)=BG_INTERACTION_TICK/30.f;
    for(unsigned p=0;p<4;p++)debugf("INTERACTION P%u weapon=%d ready=%.3f vehicle=%d seat=%d state=%u time=%.3f\n",
        p,bg_players[p].weapon,bg_players[p].weapon_ready,bg_players[p].vehicle,bg_players[p].seat,bg_players[p].seat_state,bg_players[p].seat_time);
}
static void interaction_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){
    if(BG_INTERACTION_QA<2)return;
    const bg_vehicle*v=&bg_vehicles[interaction_qa_vehicles[p]];
    const float offsets[4][3]={{-1.6f,1.25f,-2.5f},{-1.5f,1.2f,2.4f},{-2.5f,1.7f,-3.5f},{-2.5f,1.4f,-2.4f}};
    for(unsigned a=0;a<3;a++){eye->v[a]=(v->pos[a]+offsets[p][a])*BG_SCALE;target->v[a]=v->pos[a]*BG_SCALE;}
    target->v[1]+=.3f*BG_SCALE;
}
#endif
