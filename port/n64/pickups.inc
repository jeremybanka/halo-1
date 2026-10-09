/* Inventory and map-item adapter. Included after inventory/event helpers so
 * all transfers are atomic with the authoritative active-slot state. */
static void refill_pickup(bg_pickup*q){
    q->weapon=q->base_weapon;
    if(q->alternate>=0&&blam_real_seed_random_range(&item_random,0,q->total_weight)>=q->first_weight)q->weapon=q->alternate;
    q->active=true;q->age=q->unseen=q->heat=0;q->overheated=false;q->generation=++pickup_generation;
    q->quantity=1;
    if(q->weapon<BG_WEAPON_COUNT){q->ammo=bg_ammo_rules[q->weapon].loaded;q->reserve=bg_ammo_rules[q->weapon].reserve;}
}
int bg_add_pickup(int weapon,const float pos[3]){
    if(bg_pickup_count>=BG_MAX_PICKUPS||weapon<0||weapon>BG_PICK_CAMO)return -1;
    int index=bg_pickup_count++;bg_pickup*q=&bg_pickups[index];memset(q,0,sizeof(*q));
    memcpy(q->pos,pos,sizeof(q->pos));q->base_weapon=q->weapon=weapon;q->alternate=-1;q->ignore_player=-1;
    q->period=weapon==BG_PICK_OVERSHIELD?60:weapon==BG_PICK_CAMO?180:30;q->respawn=q->period;
    float floor=bg_floor(pos[0],pos[2],pos[1]+.4f);if(floor>-999)q->pos[1]=floor+.12f;
    refill_pickup(q);return index;
}
void bg_pickup_mark_visible(unsigned index){
    if(index<bg_pickup_count)bg_pickups[index].visible_until=match_time+.5f;
}
static bool pickup_near_player(const bg_pickup*q){
    for(unsigned i=0;i<active_players;i++)if(bg_players[i].health>0&&distance2(q->pos,bg_players[i].pos)<6.25f)return true;
    return false;
}
static int drop_slot(void){
    for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].dropped&&!bg_pickups[i].active)return i;
    if(bg_pickup_count<BG_MAX_PICKUPS)return bg_pickup_count++;
    int candidate=-1;float best=-1;
    for(unsigned i=0;i<bg_pickup_count;i++){
        const bg_pickup*q=&bg_pickups[i];if(!q->dropped)continue;
        /* Pool pressure first reclaims old unseen, distant items. If everyone
         * is watching a full pool, oldest is the bounded-memory fallback. */
        float score=q->age+(q->unseen>2&&!pickup_near_player(q)?1000:0);
        if(score>best){best=score;candidate=i;}
    }
    BG_COUNT(candidate<0?BG_COUNT_DROP_FULL:BG_COUNT_DROP_RECLAIM,1);
    return candidate;
}
static void drop_item(unsigned owner,int weapon,int ammo,int reserve,float heat,bool overheated,int quantity,unsigned offset){
    if(weapon<0||(weapon<BG_WEAPON_COUNT&&ammo+reserve<=0)||quantity<=0)return;
    int index=drop_slot();if(index<0)return;
    bg_pickup*q=&bg_pickups[index];bg_player*p=&bg_players[owner];memset(q,0,sizeof(*q));
    q->active=q->dropped=true;q->generation=++pickup_generation;q->weapon=q->base_weapon=weapon;
    q->ammo=ammo;q->reserve=reserve;q->heat=heat;q->overheated=overheated;q->quantity=quantity;
    q->ignore_player=owner;q->ignore_time=1;q->yaw=p->yaw+(offset&1?1.2f:-1.2f);
    memcpy(q->pos,p->pos,sizeof(q->pos));
    float angle=p->yaw+offset*1.5707963f;
    float trial[3]={p->pos[0]+cosf(angle)*.22f,p->pos[1]+.2f,p->pos[2]+sinf(angle)*.22f};
    float floor=bg_floor(trial[0],trial[2],p->pos[1]+.8f);
    if(floor>-999&&fabsf(floor-p->pos[1])<.8f){q->pos[0]=trial[0];q->pos[2]=trial[2];q->pos[1]=floor+.08f;}
    else q->pos[1]+=.08f;
    q->visible_until=match_time+1;
}
static void drop_inventory(unsigned owner){
    bg_player*p=&bg_players[owner];stop_reload(p);store_inventory(p);
    for(unsigned slot=0;slot<2;slot++)drop_item(owner,p->inventory[slot],p->magazines[slot],p->reserves[slot],p->heats[slot],p->overheated_slots[slot],1,slot);
    for(unsigned kind=0;kind<2;kind++){
        drop_item(owner,kind?BG_PICK_PLASMA:BG_PICK_FRAG,0,0,0,false,p->grenades[kind],kind+2);
        p->grenades[kind]=0;
    }
    p->ammo=p->reserve=0;memset(p->magazines,0,sizeof(p->magazines));memset(p->reserves,0,sizeof(p->reserves));
}
static void pickup_weapon(unsigned owner,bg_pickup*q){
    bg_player*p=&bg_players[owner];bg_pickup acquired=*q;q->active=false;
    stop_reload(p);store_inventory(p);
    int target=p->slot;
    /* A second weapon fills the free slot. Matching batteries swap the same
     * slot; walking over a plasma weapon never recharges a carried battery. */
    for(unsigned slot=0;slot<2;slot++)if(p->inventory[slot]==acquired.weapon)target=slot;
    if(p->inventory[0]!=acquired.weapon&&p->inventory[1]!=acquired.weapon)
        for(unsigned slot=0;slot<2;slot++)if(p->inventory[slot]<0){target=slot;break;}
    drop_item(owner,p->inventory[target],p->magazines[target],p->reserves[target],p->heats[target],p->overheated_slots[target],1,0);
    p->slot=target;p->inventory[target]=p->weapon=acquired.weapon;
    p->ammo=acquired.ammo;p->reserve=acquired.reserve;p->heat=acquired.heat;p->overheated=acquired.overheated;
    p->charge=p->reload=p->zoom=p->melee_time=0;p->melee_tick=0;p->animation=BG_ANIM_IDLE;p->anim_time=0;
    p->fire_ticks[target]=65535;p->trigger_rate[target]=p->trigger_error[target]=0;
    store_inventory(p);event(BG_EVENT_PICKUP,owner,p->weapon,p->pos,1);
}
static void collect_nearby(unsigned owner){
    bg_player*p=&bg_players[owner];
    for(unsigned i=0;i<bg_pickup_count;i++){
        bg_pickup*q=&bg_pickups[i];if(!q->active||distance2(p->pos,q->pos)>.38f*.38f||(q->ignore_time>0&&q->ignore_player==(int)owner))continue;
        bool consume=false;int amount=0;
        if(q->weapon<BG_WEAPON_COUNT){
            if(bg_weapon_defs[q->weapon].energy)continue;
            int slot=p->inventory[0]==q->weapon?0:p->inventory[1]==q->weapon?1:-1;
            if(slot<0)continue;
            store_inventory(p);int space=bg_ammo_rules[q->weapon].maximum_reserve-p->reserves[slot];
            if(space<=0)continue;
            /* Transfer actual loose rounds, then the dropped magazine, to
             * reserve only. Never refill a held magazine or create rounds. */
            amount=space<q->reserve?space:q->reserve;q->reserve-=amount;
            int loaded=space-amount<q->ammo?space-amount:q->ammo;q->ammo-=loaded;amount+=loaded;
            p->reserves[slot]+=amount;if(slot==p->slot)p->reserve=p->reserves[slot];
            consume=q->ammo+q->reserve==0;
        }else if(q->weapon==BG_PICK_FRAG||q->weapon==BG_PICK_PLASMA){
            int kind=q->weapon==BG_PICK_PLASMA,space=4-p->grenades[kind];amount=space<q->quantity?space:q->quantity;
            p->grenades[kind]+=amount;q->quantity-=amount;consume=q->quantity==0;
        }else if(q->weapon==BG_PICK_HEALTH&&p->health<100){p->health=100;consume=true;amount=1;
        }else if(q->weapon==BG_PICK_OVERSHIELD&&p->shield<=100&&!p->shield_overcharging){
            p->shield=fmaxf(1,p->shield);p->shield_delay=0;p->shield_overcharging=p->shield_charging=true;consume=true;amount=1;
            event(BG_EVENT_SHIELD,owner,p->weapon,p->pos,1);
        }else if(q->weapon==BG_PICK_CAMO){if(p->invisibility<=0){p->camo_opacity=1;p->camo_quiet=0;}p->invisibility=bg_camo_duration;consume=true;amount=1;}
        if(consume)q->active=false;
        if(amount>0)event(BG_EVENT_PICKUP,owner,q->weapon,p->pos,amount);
    }
}
static void update_pickups(float dt){
    unsigned drops=0;for(unsigned i=0;i<bg_pickup_count;i++)drops+=bg_pickups[i].active&&bg_pickups[i].dropped;
    for(unsigned i=0;i<bg_pickup_count;i++){
        bg_pickup*q=&bg_pickups[i];q->ignore_time=fmaxf(0,q->ignore_time-dt);
        if(!q->dropped){
            /* Source game-time modulo schedule, independent of when an item
             * was picked up. Keep one object per pedestal instead of stacking
             * untouched copies at every source interval. */
            q->respawn-=dt;
            if(q->respawn<=.0001f){do{q->respawn+=q->period;}while(q->respawn<=0);if(!q->active)refill_pickup(q);}
            continue;
        }
        if(!q->active)continue;
        q->age+=dt;q->heat=fmaxf(0,q->heat-.24f*dt);if(q->heat<.3f)q->overheated=false;
        bool protected=pickup_near_player(q)||q->visible_until>=match_time;
        q->unseen=protected?0:q->unseen+dt;
        /* N64 policy: 30 s ordinary lifetime; 10 s old and 2 s unseen,
         * or 3 s old/unseen with 12+ live drops. No heap allocation. */
        if(q->age>=30||(q->unseen>=2&&q->age>=10)||(drops>=12&&q->unseen>=3&&q->age>=3))q->active=false;
    }
}
