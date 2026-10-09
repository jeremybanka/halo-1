#ifndef BG_RELOAD_QA_H
#define BG_RELOAD_QA_H
/* Repeatable live production reloads; the fourth view stresses concurrent DMA. */
static void reload_qa_input(bg_input in[4],float seconds){
    static int previous=-1;static bool triggered[4];
    int cycle=(int)(seconds/12);float t=fmodf(seconds,12);
    memset(in,0,4*sizeof(*in));
    if(cycle!=previous){
        previous=cycle;memset(triggered,0,sizeof(triggered));bg_reset();bg_set_players(4);bg_set_score_limit(1000);
        for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
        for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
        for(unsigned p=0;p<4;p++){
            bg_player*q=&bg_players[p];int w=(cycle&1)?(int[]){BG_W_AR,BG_W_PLASMA_PISTOL,BG_W_ROCKET,BG_W_ROCKET}[p]:(int[]){BG_W_PISTOL,BG_W_PLASMA_RIFLE,BG_W_SNIPER,BG_W_SHOTGUN}[p];
            bg_give_weapon(p,w);q->weapon=w;q->inventory[q->slot]=w;q->weapon_ready=q->cooldown=0;
            q->ammo=(cycle&1)?(p==0?17:p==1?100:p==2?0:1):(p==0?((cycle&2)?0:3):p==1?100:p==2?((cycle&2)?0:2):8);q->reserve=240;
            q->pos[0]=p*2;q->pos[2]=4;q->pos[1]=bg_floor(q->pos[0],4,100)+.015f;
            q->yaw=-1.5707963f;q->pitch=.04f;memcpy(q->last_pos,q->pos,sizeof(q->pos));
            fired_at[p]=-100;
        }
    }
    if((cycle%4)==3&&t>=1&&t<1.75f)in[1].fire=true;
    for(unsigned p=0;p<4;p++)if(t>=1&&!triggered[p]){
        triggered[p]=true;if(p==1){bg_players[p].heat=.98f;in[p].fire=true;}
        else if(!(cycle&1)&&p==3)in[p].fire=true;else in[p].reload=true;
    }
    if(!(cycle&1)&&t>=3&&t<3.034f)in[3].fire=true;
}
#endif
