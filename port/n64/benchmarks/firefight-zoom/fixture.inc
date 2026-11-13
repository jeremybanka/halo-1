/* Allocation regression only: three standard Spartans, fixture healing,
 * disabled human fire and periodic direct kills. Never ship this game source.
 * Build with --pve-squad --pve-players 3 --pve-qa 3 --profile. */
#define bg_tick zoom_original_tick
#include "../../game.c"
#undef bg_tick

void bg_tick(const bg_input inputs[4],float dt){
    static unsigned tick,last_report;
    bg_input in[4];memcpy(in,inputs,sizeof(in));
    for(unsigned h=0;h<3;h++){
        bg_player*p=&bg_players[h];
        if(p->health>0){p->health=100;p->shield=200;}
        in[h].fire=false;in[h].forward=in[h].strafe=0;
    }
    if(!tick){
#ifdef BG_ZOOM_CROWDED
#ifdef BG_ZOOM_FRONTEND
        unsigned selected_fight=bg_ff.fight;
#endif
        bg_ff_qa_stage(3,4);
#ifdef BG_ZOOM_FRONTEND
        bg_ff.fight=selected_fight;
#endif
        /* Ten living actors plus two recent corpses fit the production pool.
         * Cluster them to expose every requested representation at once. */
#ifdef BG_ZOOM_JACKALS
        for(unsigned i=0;i<12;i++){
            float pos[3]={5,0,2};pos[1]=bg_floor(pos[0],pos[2],12)+.015f;
            pve_spawn_actor(i,BG_PVE_JACKAL,BG_W_PLASMA_PISTOL,BG_FF_MIXED,pos,3.14159265f);
            if(i>=10)pve_killed(4+i,0);
        }
#else
        for(unsigned i=10;i<12;i++){
            float pos[3]={5,0,2};pos[1]=bg_floor(pos[0],pos[2],12)+.015f;
            pve_spawn_actor(i,BG_PVE_HUNTER,BG_W_PLASMA_RIFLE,BG_FF_MIXED,pos,3.14159265f);
            pve_killed(4+i,0);
        }
#endif
#else
        if(bg_ff.fight!=BG_ZOOM_FIGHT)bg_ff_start_fight(3,BG_ZOOM_FIGHT);
#endif
    }
    zoom_original_tick(in,dt);tick++;
#ifdef BG_ZOOM_CROWDED
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_player*q=&bg_players[4+i];bg_pve_actor*a=&bg_pve_actors[i];
        q->pos[0]=4+(i%3)*.25f;q->pos[2]=1.5f+(i/3)*.25f;
        q->pos[1]=bg_floor(q->pos[0],q->pos[2],12)+.015f;
        a->arrival=0;a->death_time=1;
#ifdef BG_ZOOM_JACKALS
        a->clip=i>=10?PVE_DEATH:PVE_IDLE;a->time=fmodf((tick-1)/30.f+i*.031f,.25f);
#else
        a->time=(tick-1)/30.f+i*.107f;
#endif
    }
#endif
    for(unsigned h=0;h<3;h++){
        bg_player*p=&bg_players[h];p->health=100;p->shield=200;
        p->weapon=(tick/300)%2?BG_W_SNIPER:BG_W_PISTOL;
        p->zoom=(tick/30+h)%3;
        if(p->weapon==BG_W_PISTOL&&p->zoom>1)p->zoom=0;
        p->ammo=12;p->weapon_ready=0;
    }
#ifndef BG_ZOOM_CROWDED
    if(tick%300==0)for(unsigned i=0;i<bg_pve_count;i++)
        if(bg_players[4+i].health>0&&!bg_pve_actors[i].arrival)
            damage_player_profile(4+i,0,100000,false,false,0,false,false,1);
#endif
    if(tick-last_report>=30){
        heap_stats_t heap;sys_get_heap_stats(&heap);
        debugf("ZOOM_SOAK tick=%u elapsed=%.2f round=%u wave=%u phase=%u actors=%u free=%u zoom=%d,%d,%d\n",
            tick,bg_ff.elapsed,bg_ff.round,bg_ff.wave,bg_ff.phase,bg_pve_count,
            (unsigned)(heap.total-heap.used),bg_players[0].zoom,bg_players[1].zoom,bg_players[2].zoom);
        last_report=tick;
    }
}
