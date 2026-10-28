/* Included by test_modes.c, which exercises the real game.c implementation. */
#include "test_spawn_reference.h"
static unsigned spawn_comparisons,spawn_selections;
static spawn_reference_state spawn_state(void) {
    spawn_reference_state s={.count=active_players,.ticks=mode_spawn_ticks,
        .teams=bg_mode_has_teams(),.ctf=bg_current_rules()->engine==BG_ENGINE_CTF,
        .assault=(bg_current_rules()->flags&BG_MODE_ASSAULT)!=0};
    for(unsigned p=0;p<active_players;p++) {
        memcpy(s.players[p].pos,bg_players[p].pos,12);
        s.players[p].team=mode_teams[p];s.players[p].present=bg_players[p].health>0;
    }
    for(unsigned t=0;t<2;t++) {
        const bg_mode_marker *m=mode_marker(BG_MARK_FLAG,t);
        if(m)memcpy(s.flags[t],m->pos,12);
    }
    return s;
}
static float reference_start(const spawn_reference_state *s,unsigned p,unsigned index) {
    /* Scenario selection is separately tested by catalog_and_maps. The
     * source bodies themselves check CTF teams; do not mask that check here. */
    if(!(bg_current_mode_map()->spawn_modes[index]&(1u<<bg_current_rules()->engine)))return 0;
    return spawn_reference_rating(s,p,mode_spawn_position(index),bg_spawns[index].team);
}
static void same_rating(float actual,float expected,unsigned p,unsigned index) {
    if(actual!=expected)fprintf(stderr,"SPAWN map%u mode%u tick%u p%u start%u: port %.9g source %.9g\n",
        bg_map_id(),mode_id,mode_spawn_ticks,p,index,actual,expected);
    assert(actual==expected);spawn_comparisons++;
}
static void check_spawn_candidates(void) {
    spawn_reference_state s=spawn_state();assert(bg_vehicle_count==0);
    for(unsigned p=0;p<active_players;p++) {
        uint32_t seed=spawn_random;float best=0;int selected=-1;
        for(unsigned index=0;index<bg_spawn_count;index++) {
            float expected=reference_start(&s,p,index);
            same_rating(bg_spawn_rating(p,index),expected,p,index);
            float weighted=expected*sqrtf(blam_real_seed_random_range(&seed,0,1));
            if(weighted>best){best=weighted;selected=(int)index;}
        }
        assert(bg_select_spawn(p)==selected);assert(spawn_random==seed);spawn_selections++;
    }
}
static void spawn_map_checks(void) {
    /* All presets, both team layouts, 1..4 active players, dead/live/self
     * units, vertical distances, and both sides of the Invasion warmup. */
    uint32_t random=0x534f5552;
    const unsigned times[]={0,29,30,31,32,300};
    for(unsigned mode=0;mode<BG_MODE_COUNT;mode++) {
        start(mode);bg_vehicle_count=0;
        for(unsigned sample=0;sample<12;sample++) {
            bg_set_players(1+sample%4);mode_spawn_ticks=times[sample%6];
            for(unsigned p=0;p<active_players;p++) {
                random=random*1664525u+1013904223u;
                memcpy(bg_players[p].pos,mode_spawn_position((random>>8)%bg_spawn_count),12);
                for(unsigned a=0;a<3;a++) {
                    random=random*1664525u+1013904223u;
                    bg_players[p].pos[a]+=((int)((random>>16)%129)-64)*.0625f;
                }
                mode_teams[p]=(p+sample/4)&1;
                bg_players[p].health=(sample+p)%3?100:0;
            }
            check_spawn_candidates();
        }
    }
}
static void spawn_boundaries(void) {
    const unsigned modes[]={BG_MODE_SLAYER,BG_MODE_TEAM_SLAYER,BG_MODE_CTF,BG_MODE_INVASION};
    const float distances[]={0,.25f,.5f,1,2,5,6};
    for(unsigned m=0;m<sizeof(modes)/sizeof(*modes);m++) {
        start(modes[m]);bg_vehicle_count=0;
        unsigned index=0;while(!mode_spawn_eligible(0,index)){index++;assert(index<bg_spawn_count);}
        const float *pos=mode_spawn_position(index);
        for(unsigned other=0;other<4;other++)for(unsigned n=0;n<7;n++)
            for(unsigned axis=0;axis<3;axis++)for(unsigned side=0;side<3;side++) {
                for(unsigned p=0;p<4;p++)bg_players[p].health=0;
                bg_players[other].health=100;memcpy(bg_players[other].pos,pos,12);
                float *v=&bg_players[other].pos[axis];*v+=distances[n];
                if(side!=1)*v=nextafterf(*v,side==0?-1e30f:1e30f);
                spawn_reference_state s=spawn_state();
                same_rating(bg_spawn_rating(0,index),reference_start(&s,0,index),0,index);
            }
    }
    /* Friendly contributions add (not multiply); at three they saturate.
     * A fourth live unit can be the queried player itself. */
    start(BG_MODE_TEAM_SLAYER);bg_vehicle_count=0;const float origin[3]={0};
    for(unsigned p=0;p<4;p++) { mode_teams[p]=0;bg_players[p].health=0;memset(bg_players[p].pos,0,12);bg_players[p].pos[0]=1; }
    for(unsigned count=0;count<=4;count++) {
        if(count)bg_players[count-1].health=100;
        float expected=1+3*(count>3?3:count);
        spawn_reference_state s=spawn_state();
        same_rating(mode_spawn_weight(0,origin,1),spawn_reference_rating(&s,0,origin,0),0,0);
        assert(mode_spawn_weight(0,origin,1)==expected);
    }
    /* Zero threat ratings remain zero even with the maximum friendly bonus. */
    assert(mode_spawn_weight(0,origin,0)==0);
    start(BG_MODE_INVASION);bg_vehicle_count=0;
    for(unsigned p=0;p<4;p++)bg_players[p].health=0;
    const float offsets[]={0,.25f,.5f,1,2,3.1622777f,4,20};
    for(unsigned p=0;p<2;p++)for(unsigned t=30;t<=31;t++)for(unsigned a=0;a<3;a++)
        for(unsigned n=0;n<sizeof(offsets)/sizeof(*offsets);n++) {
            mode_spawn_ticks=t;float pos[3];memcpy(pos,mode_marker(BG_MARK_FLAG,p)->pos,12);pos[a]+=offsets[n];
            spawn_reference_state s=spawn_state();
            same_rating(mode_spawn_weight(p,pos,1),spawn_reference_rating(&s,p,pos,p),p,n);
        }
    /* The authored marker, not its floor-adjusted drawable or carried flag. */
    mode_spawn_ticks=0;float home[3];memcpy(home,mode_marker(BG_MARK_FLAG,0)->pos,12);
    assert(mode_spawn_weight(0,home,1)==2);
    for(unsigned i=0;i<2;i++)for(unsigned a=0;a<3;a++)bg_objectives[i].pos[a]=bg_objectives[i].home[a]=1000;
    assert(mode_spawn_weight(0,home,1)==2);
    home[0]+=20;assert(mode_spawn_weight(0,home,1)==.1f);
    mode_spawn_ticks=31;assert(mode_spawn_weight(0,home,1)==.5f);
    start(BG_MODE_CTF);for(unsigned p=0;p<4;p++)bg_players[p].health=0;
    assert(mode_spawn_weight(0,home,1)==1);
    /* The vehicle exclusion must still win over every positive bonus. */
    start(BG_MODE_INVASION);for(unsigned p=0;p<4;p++)bg_players[p].health=0;
    bg_vehicle_count=0;unsigned index=0;while(!mode_spawn_eligible(0,index))index++;
    assert(bg_spawn_rating(0,index)>0);
    bg_add_vehicle(BG_V_WARTHOG,mode_spawn_position(index),0);
    assert(bg_spawn_rating(0,index)==0);
}
static void spawn_clock(void) {
    bg_input in[4]={0};start(BG_MODE_INVASION);bg_vehicle_count=bg_pickup_count=0;
    for(unsigned p=0;p<4;p++){bg_players[p].health=0;bg_players[p].respawn=100;}
    assert(mode_spawn_ticks==0);
    bg_tick(in,0);bg_tick(in,-1);assert(mode_spawn_ticks==0);
    for(unsigned t=1;t<=30;t++){bg_tick(in,1.f/30);assert(mode_spawn_ticks==t);}
    /* Source game_time_get is 30 during the next simulation step, then 31.
     * Check a real respawn in that step against a source-selected candidate. */
    spawn_reference_state s=spawn_state();uint32_t seed=spawn_random;float best=0;int selected=-1;
    for(unsigned i=0;i<bg_spawn_count;i++) {
        float rating=reference_start(&s,0,i)*sqrtf(blam_real_seed_random_range(&seed,0,1));
        if(rating>best){best=rating;selected=(int)i;}
    }
    assert(selected>=0);bg_players[0].respawn=0;bg_tick(in,1.f/30);
    assert(mode_spawn_ticks==31&&bg_players[0].health>0&&spawn_random==seed);
    assert(distance2(bg_players[0].pos,mode_spawn_position(selected))<1e-10f);
    start(BG_MODE_INVASION);assert(mode_spawn_ticks==0&&mode_spawn_fraction==0);
    for(unsigned p=0;p<4;p++){bg_players[p].health=0;bg_players[p].respawn=100;}
    for(unsigned t=0;t<62;t++){bg_tick(in,1.f/60);assert(mode_spawn_ticks==(t+1)/2);}
    mode_spawn_ticks=0;match_winner=0;bg_tick(in,1.f/30);assert(mode_spawn_ticks==0);
    start(BG_MODE_INVASION);assert(mode_spawn_ticks==0);
}
