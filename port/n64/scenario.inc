/* Scenario coordinates from the supplied Xbox Blood Gulch map. */
static void load_scenario(void){
    bg_add_vehicle(BG_V_WARTHOG,(float[]){-38.863001f,0.286439f,-27.165802f},-0.848279f);
    bg_add_vehicle(BG_V_WARTHOG,(float[]){34.312370f,0.579716f,26.626144f},1.895099f);
    bg_add_vehicle(BG_V_GHOST,(float[]){-41.011095f,0.426602f,-31.166359f},-0.778145f);
    bg_add_vehicle(BG_V_GHOST,(float[]){-16.889324f,0.200095f,-28.021378f},-2.106262f);
    bg_add_vehicle(BG_V_GHOST,(float[]){36.687675f,0.197242f,31.324677f},1.866184f);
    bg_add_vehicle(BG_V_GHOST,(float[]){14.222473f,-0.094405f,35.987000f},2.005298f);
    bg_add_vehicle(BG_V_SCORPION,(float[]){27.463425f,0.748604f,56.392944f},1.610201f);
    bg_add_vehicle(BG_V_SCORPION,(float[]){-27.619904f,0.905973f,-54.037434f},-1.611491f);
    bg_add_vehicle(BG_V_BANSHEE,(float[]){-22.000000f,0.000000f,-52.000000f},-1.5f);
    bg_add_vehicle(BG_V_BANSHEE,(float[]){22.000000f,0.000000f,54.000000f},1.5f);
    for(unsigned i=0;i<bg_map_item_count;i++){
        const bg_map_item*m=&bg_map_items[i];int index=bg_add_pickup(m->kind[0],m->pos);
        if(index<0)break;
        bg_pickup*q=&bg_pickups[index];
        q->yaw=m->yaw;q->period=m->period;q->respawn=m->period;
        q->alternate=m->kind[1];q->first_weight=m->first_weight;q->total_weight=m->total_weight;
        refill_pickup(q);
    }
    /* Deliberate expanded-catalog placements retained from the demake. */
    bg_add_pickup(BG_W_NEEDLER,(float[]){-28,1.8f,-40});
    bg_add_pickup(BG_W_NEEDLER,(float[]){28,1.8f,43});
    bg_add_pickup(BG_W_PLASMA_PISTOL,(float[]){-26,1.8f,-40});
    bg_add_pickup(BG_W_PLASMA_PISTOL,(float[]){26,1.8f,43});
}
