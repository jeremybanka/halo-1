#ifndef BG_COMBAT_QA_H
#define BG_COMBAT_QA_H
/* Identical staging in before/after ROMs; all attacks use production input. */
static void combat_qa_input(bg_input in[4],float time){
    static int previous=-1;int cycle=(int)(time/12);float t=time-cycle*12;
    if(cycle!=previous){
        previous=cycle;bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        views=4;bg_vehicle_count=bg_pickup_count=0;reset_view_state();
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];unsigned pair=p/2;
            float distance=BG_COMBAT_QA==2?(pair?3.8f:.9f):BG_COMBAT_QA==3?.6f:1.4f;
            q->pos[0]=(p&1)?distance:0;q->pos[2]=4+pair*5;
            q->pos[1]=bg_floor(q->pos[0],q->pos[2],100)+.015f;
            q->yaw=(p&1)?3.14159265f:0;q->pitch=0;
            if(BG_COMBAT_QA==3&&pair)q->yaw=0;
            int w=BG_COMBAT_QA==1?(pair?BG_W_PLASMA_RIFLE:BG_W_PLASMA_PISTOL):BG_COMBAT_QA==2?BG_W_SHOTGUN:BG_W_PISTOL;
            bg_give_weapon(p,w);q->weapon=w;q->inventory[q->slot]=w;
            q->ammo=bg_weapon_defs[w].magazine;q->weapon_ready=q->cooldown=0;
            if(BG_COMBAT_QA==1&&p==1)q->shield=300; /* Staged charged overshield. */
            memcpy(q->last_pos,q->pos,12);
        }
        for(unsigned p=0;p<4;p+=2){
            bg_player*a=&bg_players[p],*b=&bg_players[p+1];
            float height=BG_COMBAT_QA==0&&p==2?.60f:.36f;
            a->pitch=atan2f(b->pos[1]+height-a->pos[1]-bg_eye_height(a),b->pos[0]-a->pos[0]);
        }
    }
    memset(in,0,sizeof(bg_input)*4);
    for(unsigned p=0;p<4;p+=2){
        if(t<1||t>7||bg_players[p+1].health<=0)continue;
        float phase=fmodf(t-1,1.05f);
        if(BG_COMBAT_QA==3)in[p].melee=phase<.035f;
        else if(BG_COMBAT_QA==1&&p==0)in[p].fire=t<3;
        else in[p].fire=phase<.05f;
    }
}
static const char*combat_qa_title(void){
    return (const char*[]){"PISTOL: BODY / HEAD","OVERCHARGE / PLASMA RIFLE","SHOTGUN: NEAR / FAR","MELEE: FRONT / BACK"}[BG_COMBAT_QA];
}
#endif
