#ifndef BG_AIM_QA_H
#define BG_AIM_QA_H
/* Frozen views through the production camera, projection and HUD paths. */
static unsigned model_qa_page=BG_AIM_QA;
static const char *const model_qa_labels[]={"AIM: LEVEL","AIM: DOWN","AIM: UP","AIM: SCOPES"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
    (void)now;static bool ready;if(ready)return;ready=true;
    bg_set_players(4);bg_reset();views=4;reset_view_state();game_time=0;
    bg_vehicle_count=bg_pickup_count=0;
    if(BG_AIM_QA<3){
        for(unsigned p=0;p<4;p++){
            float pos[3]={-12+p*7.f,bg_floor(-12+p*7.f,5,100)+.2f,5};
            bg_add_vehicle(p,pos,-.6f);bg_players[p].pos[0]=-30;bg_players[p].pos[2]=-30;
        }
        bg_input in[4]={0};for(unsigned t=0;t<60;t++)bg_tick(in,1.f/30);
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];bg_vehicle*v=&bg_vehicles[p];unsigned seat=p==BG_V_WARTHOG?1:0;
            q->vehicle=p;q->seat=seat;q->seat_state=BG_SEAT_STABLE;v->occupants[seat]=p;
            bg_vehicle_seat_position(v,seat,false,q->pos);q->yaw=-.6f;
            q->pitch=BG_AIM_QA==1?-.25f:BG_AIM_QA==2?.25f:0;
            v->turret_yaw=q->yaw-v->yaw;v->turret_pitch=q->pitch;
            q->animation=BG_ANIM_DRIVE;q->anim_time=0;
        }
    }else{
        /* Elevated inspection vantage clears the central ridge; the actual
         * projection/HUD/LOD paths are unchanged. Target is ~83 units away. */
        float target_pos[3]={26,bg_floor(26,34,100)+.02f,34};
        bg_add_vehicle(BG_V_SCORPION,target_pos,0);
        bg_vehicle_physics_prepare();
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];q->pos[0]=-26;q->pos[2]=-31;q->pos[1]=bg_floor(-26,-31,100)+6;
            float target[3]={26,bg_floor(26,34,100)+.8f,34};
            q->yaw=-atan2f(target[2]-q->pos[2],target[0]-q->pos[0]);
            q->pitch=atan2f(target[1]-q->pos[1]-.62f,hypotf(52,65));q->invisibility=1;
            bg_give_weapon(p,p<2?BG_W_PISTOL:BG_W_SNIPER);q->weapon=p<2?BG_W_PISTOL:BG_W_SNIPER;q->ammo=bg_weapon_defs[q->weapon].magazine;q->zoom=p==0?0:p==3?2:1;
            q->weapon_ready=q->cooldown=0;
        }
    }
}
#endif
