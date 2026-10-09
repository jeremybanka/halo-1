#ifndef BG_MOVEMENT_QA_H
#define BG_MOVEMENT_QA_H
/* Staged positions, then normal production input/ticks. Shared unchanged by
 * baseline and revised ROMs; recordings are explicitly labeled scripted. */
static unsigned movement_qa_phase;
static void movement_qa_input(bg_input in[4],float time){
    static int previous=-1;int cycle=(int)(time/12.f);float t=time-cycle*12.f;
    if(cycle!=previous){
        previous=cycle;bg_reset();bg_set_players(2);views=2;reset_view_state();
        bg_vehicle_count=bg_pickup_count=0;
        for(unsigned i=0;i<2;i++){
            bg_player*p=&bg_players[i];p->pos[0]=i?(BG_MOVEMENT_QA?-5:-8):-12;
            p->pos[2]=i&&!BG_MOVEMENT_QA?-1:5;
            p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
            p->yaw=i&&!BG_MOVEMENT_QA?-1.57079633f:0;p->pitch=0;
            bg_give_weapon(i,BG_W_PISTOL);p->weapon=BG_W_PISTOL;p->ammo=12;p->weapon_ready=p->cooldown=0;
        }
    }
#if BG_MOVEMENT_QA >= 2
    static int stage=-1;int next=cycle*3;
    if(stage!=next){
        stage=next;for(unsigned i=0;i<2;i++){
            bg_player*p=&bg_players[i];memset(p->velocity,0,sizeof(p->velocity));p->vy=0;p->crouch_amount=0;p->crouched=false;
#if BG_MOVEMENT_QA == 2
            p->pos[0]=i?26:22.2f;p->pos[2]=i?44:41.5f;
            p->pos[1]=bg_floor(p->pos[0],p->pos[2],i?100:1)+.015f;p->yaw=i?2.56f:0;

            p->grounded=true;
#else
            p->pos[0]=i?-7:-12;p->pos[2]=5;p->pos[1]=bg_floor(p->pos[0],5,100)+.015f+(i?0:5.2f);p->yaw=i?3.14159265f:0;p->grounded=i!=0;
#endif
            p->pitch=0;
        }
    }
#endif
    memset(in,0,sizeof(bg_input)*4);
#if BG_MOVEMENT_QA == 0
    movement_qa_phase=t<1?0:t<2.5f?1:t<4?2:t<5.5f?3:t<7?4:t<9?5:6;
    if(t>=1&&t<2.5f)in[0].forward=1;
    if(t>=4&&t<5.5f)in[0].forward=-1;
    if(t>=7&&t<9){in[0].forward=t<7.2f?1:-1;in[0].jump=t<7.04f;}
    if(t>=9&&t<11){in[0].crouch=true;in[0].forward=1;}
#elif BG_MOVEMENT_QA == 1
    movement_qa_phase=(unsigned)(t/4);
    if(t<4){if(t<.04f)bg_players[0].yaw=.22f;in[0].turn=-.35f;}
    else if(t<8){
        if(t<4.04f){bg_players[0].yaw=0;bg_players[1].pos[2]=5;}
        in[0].forward=.03f;in[1].strafe=t<6?.5f:-.5f;
    }else{
        if(t<8.04f){bg_players[0].yaw=.15f;bg_players[1].pos[2]=5;in[0].zoom=true;}
        in[0].turn=-.35f;
    }
#elif BG_MOVEMENT_QA == 2
    movement_qa_phase=t<1?0:t<3?1:t<6?2:t<9?3:4;
    if(t>=1&&t<3)in[0].forward=1;
    if(t>=3&&t<5)in[0].forward=-1;
    if(t>=6&&t<9){in[0].crouch=true;in[0].forward=.5f;}
    if(t>=9)in[0].forward=.5f;
#else
    movement_qa_phase=t<2?0:t<5?1:t<8?2:3;
    if(t>=1.5f&&t<5)in[0].forward=.4f;
    if(t>=5&&t<8){in[0].crouch=true;in[0].forward=.6f;}

#endif
}
static const char*movement_qa_title(void){
#if BG_MOVEMENT_QA == 0
    static const char*names[]={"REST","ACCELERATE","RELEASE","REVERSE","STOP","JUMP / AIR REVERSE","CROUCH WALK"};
#elif BG_MOVEMENT_QA == 1
    static const char*names[]={"FINE AIM SWEEP","MOVING TARGET ADHESION","2X AIM SWEEP"};
#elif BG_MOVEMENT_QA == 2
    static const char*names[]={"RAMP REST","UPHILL","DOWNHILL","CROUCH ON RAMP","STAND / UPHILL"};
#else
    static const char*names[]={"FALL","LAND / FORWARD INPUT","CROUCH WALK","STAND"};
#endif
    return names[movement_qa_phase];
}
#endif
