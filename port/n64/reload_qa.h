#ifndef BG_RELOAD_QA_H
#define BG_RELOAD_QA_H
/* Repeatable live production reloads; the fourth view stresses concurrent DMA. */
static void reload_qa_input(bg_input in[4],float seconds){
    static int previous=-1;static bool triggered[4];
    int cycle=(int)(seconds/9);float t=fmodf(seconds,9);
    memset(in,0,4*sizeof(*in));
    if(cycle!=previous){
        previous=cycle;memset(triggered,0,sizeof(triggered));bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];int w=(int[]){BG_W_AR,BG_W_PLASMA_PISTOL,BG_W_ROCKET,BG_W_ROCKET}[p];
            bg_give_weapon(p,w);q->weapon=w;q->inventory[q->slot]=w;q->weapon_ready=q->cooldown=0;
            q->ammo=p==0?17:p==1?100:p==2?0:1;q->reserve=240;
            q->pos[0]=p*2;q->pos[2]=4;q->pos[1]=bg_floor(q->pos[0],4,100)+.015f;
            q->yaw=-1.5707963f;q->pitch=.04f;memcpy(q->last_pos,q->pos,sizeof(q->pos));
            fired_at[p]=-100;
        }
    }
    if((cycle&1)&&t>=1&&t<1.75f)in[1].fire=true;
    for(unsigned p=0;p<4;p++)if(t>=1&&!triggered[p]){
        triggered[p]=true;if(p==1){bg_players[p].heat=.98f;in[p].fire=true;}
        else in[p].reload=true;
    }
}
#endif
