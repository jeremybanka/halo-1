/* Local multiplayer rules. Included after inventory/scenario helpers: gameplay
 * owns all mutation, while rendering reads the bounded objective records. */
static bool mode_enabled;
static unsigned mode_id;
static uint8_t mode_teams[BG_PLAYERS];
static int mode_scores[BG_PLAYERS], mode_team_scores[2], mode_targets[BG_PLAYERS];
static unsigned mode_penalty[BG_PLAYERS];
static float mode_speed[BG_PLAYERS],mode_death_time[BG_PLAYERS],mode_fraction;
static uint32_t mode_rng, race_mask, race_visited[BG_PLAYERS];
static unsigned race_first,rally_flag,hill_id,hill_ticks;
/* Only the first 31 completed ticks matter to Invasion's spawn warmup. */
static unsigned mode_spawn_ticks;
static float mode_spawn_fraction;
bg_objective bg_objectives[BG_MAX_OBJECTIVES];
unsigned bg_objective_count;

void bg_configure_mode(unsigned id,const uint8_t teams[4]) {
    mode_id=id<BG_MODE_COUNT?id:0;mode_enabled=true;
    for(unsigned i=0;i<BG_PLAYERS;i++)mode_teams[i]=teams?teams[i]&1:i&1;
    const bg_mode_rules *r=bg_mode_preset(mode_id);
    bg_set_score_limit(r->goal*(bg_mode_timed(r)?60:1));
}
unsigned bg_current_mode(void) { return mode_id; }
const bg_mode_rules *bg_current_rules(void) { return bg_mode_preset(mode_id); }
bool bg_mode_has_teams(void) { return mode_enabled&&bg_current_rules()->teams; }
unsigned bg_player_team(unsigned p) { return p<BG_PLAYERS?mode_teams[p]:0; }
bool bg_players_allied(unsigned a,unsigned b) {
#ifdef BG_PVE
    if(bg_pve_is_active())return (a<BG_PLAYERS)==(b<BG_PLAYERS);
#endif
    return a<active_players&&b<active_players&&(a==b||(bg_mode_has_teams()&&mode_teams[a]==mode_teams[b]));
}
unsigned bg_player_color(unsigned p) {
    return bg_mode_has_teams()?(mode_teams[p]?1:0):bg_player_profiles[p];
}
int bg_team_score(unsigned team) {
    int value=team<2?mode_team_scores[team]:0;
    return bg_mode_timed(bg_current_rules())?value/30:value;
}
int bg_display_score(unsigned p) {
    return bg_mode_has_teams()?bg_team_score(mode_teams[p]):bg_players[p].score;
}
bool bg_player_is_winner(unsigned p) {
    return match_winner>=0&&(p==(unsigned)match_winner||bg_players_allied(p,(unsigned)match_winner));
}
int bg_player_objective(unsigned p) {
    if(!mode_enabled)return -1;
    if(bg_current_rules()->engine==BG_ENGINE_BALL&&bg_current_rules()->ball_type)return -1;
    for(unsigned i=0;i<bg_objective_count;i++)if(bg_objectives[i].owner==(int)p)return i;
    return -1;
}
float bg_player_melee_duration(unsigned p) {
    int carried=bg_player_objective(p);
    if(carried<0)return bg_melee_duration(bg_players[p].weapon);
    /* Original flag/skull clips: 40/28 frames, CE uses the first 3/4. */
    return bg_objectives[carried].kind==BG_OBJECTIVE_FLAG?1.f:.7f;
}
unsigned bg_player_ball_count(unsigned p) {
    unsigned count=0;
    for(unsigned i=0;i<bg_objective_count;i++)count+=bg_objectives[i].owner==(int)p;
    return count;
}
int bg_player_target(unsigned p) { return mode_enabled&&p<active_players?mode_targets[p]:-1; }
bool bg_player_eliminated(unsigned p) {
#ifdef BG_PVE
    if(bg_ff.active)return bg_players[p].health<=0&&!bg_ff_can_respawn(p);
#endif
    return mode_enabled&&bg_current_rules()->lives&&bg_players[p].health<=0&&
           statistics.deaths[p]>=bg_current_rules()->lives;
}
bool bg_player_waiting(unsigned p) {
    if(!mode_enabled||!(bg_current_rules()->flags&BG_MODE_ODD_MAN)||active_players<2||bg_players[p].health>0)return false;
    for(unsigned q=0;q<active_players;q++)if(q!=p&&bg_players[q].health<=0&&
        (mode_death_time[q]>mode_death_time[p]||(mode_death_time[q]==mode_death_time[p]&&q>p)))return false;
    return true;
}
float bg_mode_speed(unsigned p) {
    if(!mode_enabled)return 1;
    if(bg_current_rules()->engine==BG_ENGINE_BALL&&bg_player_ball_count(p)) {
        unsigned speed=bg_current_rules()->ball_speed;
        return speed==1?1:speed==2?1.25f:.75f;
    }
    return mode_speed[p];
}
static unsigned mode_trait(unsigned p) {
    if(!mode_enabled||bg_current_rules()->engine!=BG_ENGINE_BALL)return 0;
    return bg_player_ball_count(p)?bg_current_rules()->trait_with_ball:bg_current_rules()->trait_without_ball;
}
static float mode_damage(unsigned victim,int owner) {
    if(!mode_enabled)return 1;
    float scale=1.f/bg_current_rules()->health;
    if(owner>=0&&owner<(int)active_players) {
        if(mode_trait(owner)==2)scale*=1.5f;
        if(mode_trait(victim)==3)scale*=.5f;
    }
    return scale;
}
bool bg_mode_radar(void) {
#ifdef BG_PVE
    if(bg_ff_cloud())return false;
#endif
    return !mode_enabled||(bg_current_rules()->flags&BG_MODE_SENSOR); }
static unsigned mode_random(unsigned count) {
    mode_rng=mode_rng*1664525u+1013904223u;
    return count?(mode_rng>>8)%count:0;
}
static const bg_mode_marker *mode_marker(unsigned kind,unsigned id) {
    const bg_mode_map *map=bg_current_mode_map();
    if(map)for(unsigned i=0;i<map->marker_count;i++)
        if(map->markers[i].kind==kind&&map->markers[i].id==id)return &map->markers[i];
    return NULL;
}
static float mode_spawn_height(unsigned index,float height) {
    return mode_enabled&&bg_current_mode_map()?bg_current_mode_map()->spawn_positions[index][1]:height;
}
static const float *mode_spawn_position(unsigned index) {
    return mode_enabled&&bg_current_mode_map()?bg_current_mode_map()->spawn_positions[index]:bg_spawns[index].pos;
}
static bool mode_spawn_eligible(unsigned player,unsigned index) {
    if(!mode_enabled||!bg_current_mode_map())return bg_slayer_spawns[index]!=0;
    const bg_mode_rules *r=bg_current_rules();
    if(!(bg_current_mode_map()->spawn_modes[index]&(1u<<r->engine)))return false;
    /* Source CTF starts are partitioned by team. Other team modes share the
     * mode's spawn set and use the friendly distance bonus. */
    return r->engine!=BG_ENGINE_CTF||bg_spawns[index].team==(int)mode_teams[player];
}
static void mode_advance_spawn_clock(float dt) {
    if(!mode_enabled||mode_spawn_ticks>30)return;
    mode_spawn_fraction+=dt*30;
    unsigned ticks=(unsigned)(mode_spawn_fraction+1e-5f);
    mode_spawn_fraction=fmaxf(0,mode_spawn_fraction-ticks);
    mode_spawn_ticks+=ticks;
}
static float mode_spawn_weight(unsigned player,const float pos[3],float rating) {
    if(bg_mode_has_teams()&&rating>0) {
        float bonus=0;
        for(unsigned i=0;i<active_players;i++)
            if(mode_teams[player]==mode_teams[i]&&bg_players[i].health>0) {
                float distance=(float)sqrt(spawn_distance_squared(pos,bg_players[i].pos));
                if(distance>=1&&distance<=6)
                    bonus+=(float)pow((double)(1.f-(distance-1.f)*.2f),(double).6f);
            }
        if(bonus>3)bonus=3;
        rating*=bonus*3+1;
    }
    if(mode_enabled&&bg_current_rules()->engine==BG_ENGINE_CTF&&
       (bg_current_rules()->flags&BG_MODE_ASSAULT)) {
        /* Invasion swaps the source flag slots on map initialization. Its
         * opposite-slot lookup therefore means our team's authored marker,
         * before the port's floor adjustment of the drawable objective. */
        const bg_mode_marker *flag=mode_marker(BG_MARK_FLAG,mode_teams[player]);
        if(flag) {
            float d2=clamp(spawn_distance_squared(flag->pos,pos),.5f,10.f);
            float preference=1.f/d2;
            if(mode_spawn_ticks>30) {
                if(d2>1)preference=(float)pow(preference,.33f);
                preference=clamp(preference,.5f,2.f);
            }
            rating*=preference;
        }
    }
    return rating;
}
static void mode_loadout(int weapons[2],int grenades[2]) {
    memcpy(weapons,bg_start_weapons,2*sizeof(int));memcpy(grenades,bg_start_grenades,2*sizeof(int));
    if(!mode_enabled)return;
    const bg_mode_rules *r=bg_current_rules();const bg_mode_map *map=bg_current_mode_map();
    if(map){memcpy(weapons,map->starts[r->engine],2*sizeof(int));memcpy(grenades,map->starts[r->engine]+2,2*sizeof(int));}
    if(r->flags&BG_MODE_GENERIC){weapons[0]=BG_W_AR;weapons[1]=BG_W_PISTOL;grenades[0]=4;grenades[1]=0;}
    if(r->weapon>=0){weapons[0]=r->weapon;weapons[1]=-1;}
}
static void mode_finish(int winner) {
    if(match_winner!=-1)return;
    match_winner=winner;
    unsigned p=winner>=0?(unsigned)winner:0;
    event(BG_EVENT_GAME_OVER,winner,bg_players[p].weapon,bg_players[p].pos,bg_display_score(p));
}
static void mode_add_score(unsigned p,int amount) {
    mode_scores[p]+=amount;
    bg_players[p].score=bg_mode_timed(bg_current_rules())?mode_scores[p]/30:mode_scores[p];
    if(bg_mode_has_teams())mode_team_scores[mode_teams[p]]+=amount;
    int score=bg_mode_has_teams()?mode_team_scores[mode_teams[p]]:mode_scores[p];
    unsigned limit=bg_score_limit()*(bg_mode_timed(bg_current_rules())?30:1);
    if(score>=(int)limit)mode_finish(p);
}
static void mode_next_target(unsigned p) {
    unsigned candidates[BG_PLAYERS],count=0;
    for(unsigned q=0;q<active_players;q++)if(q!=p&&(int)q!=mode_targets[p]&&!bg_player_eliminated(q))candidates[count++]=q;
    if(!count)for(unsigned q=0;q<active_players;q++)if(q!=p&&!bg_player_eliminated(q))candidates[count++]=q;
    mode_targets[p]=count?(int)candidates[mode_random(count)]:-1;
}
static void mode_reset_objective(bg_objective *o) {
    memcpy(o->pos,o->home,sizeof(o->pos));o->owner=-1;o->ignore_player=-1;
    o->reset_time=o->pickup_delay=o->fall_speed=0;o->at_home=true;o->active=true;
}
void bg_drop_objective(unsigned p) {
    int index=bg_player_objective(p);if(index<0)return;
    bg_objective *o=&bg_objectives[index];
    memcpy(o->pos,bg_players[p].pos,sizeof(o->pos));o->pos[1]+=.1f;
    o->owner=-1;o->at_home=false;o->reset_time=o->kind==BG_OBJECTIVE_FLAG?17:40;
    o->ignore_player=p;o->pickup_delay=1;o->fall_speed=0;
    bg_players[p].zoom=0;bg_players[p].weapon_ready=.25f;
    bg_players[p].melee_time=0;bg_players[p].melee_tick=0;
    event(BG_EVENT_OBJECTIVE,p,o->kind,o->pos,BG_OBJECTIVE_DROPPED);
}
static void mode_reset(void) {
    memset(mode_scores,0,sizeof(mode_scores));memset(mode_team_scores,0,sizeof(mode_team_scores));
    memset(mode_penalty,0,sizeof(mode_penalty));memset(mode_death_time,0,sizeof(mode_death_time));
    memset(race_visited,0,sizeof(race_visited));memset(bg_objectives,0,sizeof(bg_objectives));
    bg_objective_count=0;mode_fraction=0;mode_rng=0x4d4f4445;race_mask=0;hill_id=0;hill_ticks=1800;
    mode_spawn_ticks=0;mode_spawn_fraction=0;
    for(unsigned i=0;i<BG_PLAYERS;i++){mode_speed[i]=1;mode_targets[i]=-1;}
    if(!mode_enabled)return;
    const bg_mode_rules *r=bg_current_rules();const bg_mode_map *map=bg_current_mode_map();
    if(r->flags&BG_MODE_TARGETS)for(unsigned i=0;i<active_players;i++)mode_next_target(i);
    if(!map)return;
    if(r->engine==BG_ENGINE_CTF) {
        bg_objective_count=2;
        for(unsigned t=0;t<2;t++) {
            const bg_mode_marker *m=mode_marker(BG_MARK_FLAG,(r->flags&BG_MODE_ASSAULT)?1-t:t);
            if(!m)continue;
            bg_objective *o=&bg_objectives[t];o->kind=BG_OBJECTIVE_FLAG;o->team=t;
            memcpy(o->home,m->pos,12);o->yaw=m->yaw;
            float floor=bg_floor(o->home[0],o->home[2],o->home[1]+.8f);
            if(floor>-999)o->home[1]=floor+.08f;
            mode_reset_objective(o);
        }
    } else if(r->engine==BG_ENGINE_BALL) {
        bg_objective_count=r->balls;
        for(unsigned i=0;i<bg_objective_count;i++) {
            const bg_mode_marker *m=mode_marker(BG_MARK_BALL,i);
            if(!m)m=mode_marker(BG_MARK_BALL,0);
            if(!m)for(unsigned j=0;j<map->marker_count;j++)if(map->markers[j].kind==BG_MARK_BALL){m=&map->markers[j];break;}
            bg_objective *o=&bg_objectives[i];o->kind=BG_OBJECTIVE_BALL;o->team=-1;
            if(m){memcpy(o->home,m->pos,12);o->yaw=m->yaw;}
            float floor=bg_floor(o->home[0],o->home[2],o->home[1]+.8f);
            if(floor>-999)o->home[1]=floor+.08f;
            mode_reset_objective(o);
            /* Transfer modes have abstract owners, never physical balls. */
            if(r->ball_type)o->active=false;
            else {o->active=false;o->reset_time=15.f*(i+1);}
        }
    } else if(r->engine==BG_ENGINE_RACE) {
        for(unsigned i=0;i<map->marker_count;i++)if(map->markers[i].kind==BG_MARK_RACE)race_mask|=1u<<map->markers[i].id;
        race_first=0;while(race_first<31&&!(race_mask&(1u<<race_first)))race_first++;
        rally_flag=race_first;
    }
}
static void mode_prepare_scenario(void) {
    if(!mode_enabled)return;
    const bg_mode_rules *r=bg_current_rules();const bg_mode_map *map=bg_current_mode_map();
    if(map&&r->engine!=BG_ENGINE_SLAYER) {
        bg_pickup_count=0;memset(bg_pickups,0,sizeof(bg_pickups));
        for(unsigned i=0;i<map->item_count;i++)if(map->items[i].modes&(1u<<r->engine)) {
            const bg_map_item *m=&map->items[i].item;int id=bg_add_pickup(m->kind[0],m->pos);if(id<0)break;
            bg_pickup *q=&bg_pickups[id];q->yaw=m->yaw;q->period=q->respawn=m->period;
            q->alternate=m->kind[1];q->first_weight=m->first_weight;q->total_weight=m->total_weight;
            if(bg_map_item_second_weight(m))q->alternate|=bg_map_item_third(m)<<8|bg_map_item_second_weight(m)<<16;
            refill_pickup(q);
        }
    }
    if(r->weapon>=0)for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].weapon<BG_WEAPON_COUNT) {
        bg_pickups[i].weapon=bg_pickups[i].base_weapon=r->weapon;bg_pickups[i].alternate=-1;refill_pickup(&bg_pickups[i]);
    }
    if(!r->vehicles)bg_vehicle_count=0;
    if(map&&r->engine==BG_ENGINE_RACE) {
        bg_vehicle_count=0;
        /* The source creates at most one race vehicle per participant. */
        for(unsigned i=0;i<map->marker_count&&bg_vehicle_count<active_players;i++)if(map->markers[i].kind==BG_MARK_VEHICLE)
            bg_add_vehicle(BG_V_WARTHOG,map->markers[i].pos,-map->markers[i].yaw);
    } else if(mode_id!=BG_MODE_SLAYER&&r->vehicles) {
        unsigned kept=0;int kind=r->vehicles==2?BG_V_SCORPION:BG_V_WARTHOG;
        for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].kind==kind)bg_vehicles[kept++]=bg_vehicles[i];
        bg_vehicle_count=kept;
    }
}
static void mode_killed(unsigned victim,int owner) {
    if(!mode_enabled)return;
    const bg_mode_rules *r=bg_current_rules();bool valid=owner>=0&&owner<(int)active_players;
    bool enemy=valid&&!bg_players_allied(victim,owner);
    mode_death_time[victim]=match_time;
    unsigned delay=r->respawn_ticks+mode_penalty[victim]+(enemy?0:r->suicide_ticks);
    bg_players[victim].respawn=fmaxf(3,delay/30.f);
    if(r->growth_ticks) {
        mode_penalty[victim]+=r->growth_ticks;
        if(mode_penalty[victim]>r->growth_ticks*5u)mode_penalty[victim]=r->growth_ticks*5u;
        if(enemy)mode_penalty[owner]=mode_penalty[owner]>r->growth_ticks?mode_penalty[owner]-r->growth_ticks:0;
    }
    if(r->engine==BG_ENGINE_SLAYER&&valid) {
        if(enemy) {
            if(!(r->flags&BG_MODE_NO_KILL_PENALTY)) {
                mode_speed[owner]-=.02f;
                if(mode_speed[owner]>=1)mode_speed[owner]=fmaxf(1,mode_speed[owner]-.15000001f);
                mode_speed[owner]=fmaxf(.9f,mode_speed[owner]);
            }
            if(!(r->flags&BG_MODE_NO_DEATH_BONUS)) {
                mode_speed[victim]+=.1f;
                if(mode_speed[victim]<=1)mode_speed[victim]=fminf(1,mode_speed[victim]+.1f);
                mode_speed[victim]=fminf(1.5f,mode_speed[victim]);
            }
            if(!(r->flags&BG_MODE_TARGETS)||mode_targets[owner]==(int)victim) {
                mode_add_score(owner,1);if(r->flags&BG_MODE_TARGETS)mode_next_target(owner);
            }
        } else mode_add_score(owner,-1);
    }
    if(r->engine==BG_ENGINE_BALL&&r->ball_type) {
        if(enemy) {
            bool had=bg_player_ball_count(victim)>0,has=bg_player_ball_count(owner)>0;
            int available=-1,transfer=-1;
            for(unsigned i=0;i<bg_objective_count;i++) {
                if(bg_objectives[i].owner<0&&available<0)available=i;
                if(bg_objectives[i].owner==(int)victim&&transfer<0)transfer=i;
            }
            if((r->ball_type==2&&(had||has))||(!had&&!has&&available>=0))mode_add_score(owner,1);
            if(transfer<0)transfer=available;
            if(transfer>=0) {
                bg_objectives[transfer].owner=owner;
                event(BG_EVENT_OBJECTIVE,owner,BG_OBJECTIVE_BALL,bg_players[owner].pos,BG_OBJECTIVE_TAKEN);
            }
        }
        for(unsigned i=0;i<bg_objective_count;i++)if(bg_objectives[i].owner==(int)victim)bg_objectives[i].owner=-1;
    }
}
static bool mode_near(unsigned p,const float pos[3],float radius) {
    float eye[3]={bg_players[p].pos[0],bg_players[p].pos[1]+.35f,bg_players[p].pos[2]},d[3];
    sub(d,pos,eye);float length=sqrtf(dot(d,d));
    if(length>radius)return false;
    if(length<.001f)return true;
    for(unsigned a=0;a<3;a++)d[a]/=length;
    return bg_raycast(eye,d,length)>=length-.03f;
}
static void mode_take(unsigned p,unsigned index) {
    bg_objective *o=&bg_objectives[index];o->owner=p;o->at_home=false;o->reset_time=0;
    bg_players[p].zoom=0;stop_reload(&bg_players[p]);bg_players[p].charge=0;
    event(BG_EVENT_OBJECTIVE,p,o->kind,o->pos,BG_OBJECTIVE_TAKEN);
}
bool bg_player_in_hill(unsigned p) {
    const bg_mode_map *map=bg_current_mode_map();if(!map)return false;
    if(!mode_enabled||bg_current_rules()->engine!=BG_ENGINE_KING||p>=active_players)return false;
    float points[12][3],bottom=1e9f,top=-1e9f;unsigned count=0;
    for(unsigned i=0;i<map->marker_count&&count<12;i++)if(map->markers[i].kind==BG_MARK_HILL&&map->markers[i].id==hill_id) {
        memcpy(points[count],map->markers[i].pos,12);bottom=fminf(bottom,points[count][1]);top=fmaxf(top,points[count][1]);count++;
    }
    float y=bg_players[p].pos[1]+.35f;
    if(count<3||y<bottom-.1f||y>top+.8f)return false;
    for(unsigned i=0;i<count;i++) {
        const float *a=points[i],*b=points[(i+1)%count];
        float cross=(b[0]-a[0])*(bg_players[p].pos[2]-a[2])-(b[2]-a[2])*(bg_players[p].pos[0]-a[0]);
        if(cross<0)return false;
    }
    return true;
}
bool bg_mode_hill_point(unsigned index,float out[3]) {
    const bg_mode_map *map=bg_current_mode_map();
    if(!mode_enabled||bg_current_rules()->engine!=BG_ENGINE_KING||!map)return false;
    unsigned n=0;
    for(unsigned i=0;i<map->marker_count;i++)if(map->markers[i].kind==BG_MARK_HILL&&map->markers[i].id==hill_id)
        if(n++==index){memcpy(out,map->markers[i].pos,12);return true;}
    return false;
}
static unsigned mode_race_target(unsigned p) {
    if(bg_current_rules()->race_type==2)return rally_flag;
    uint32_t remaining=race_mask&~race_visited[p];
    if(!remaining)return race_first;
    for(unsigned i=0;i<32;i++)if(remaining&(1u<<i))return i;
    return race_first;
}
static void mode_race_lap(unsigned p) {
    mode_scores[p]++;bg_players[p].score=mode_scores[p];race_visited[p]=0;
    int score=mode_scores[p];
    if(bg_mode_has_teams()) {
        for(unsigned q=0;q<active_players;q++)if(mode_teams[q]==mode_teams[p]&&mode_scores[q]<score)score=mode_scores[q];
        mode_team_scores[mode_teams[p]]=score;
    }
    event(BG_EVENT_OBJECTIVE,p,BG_OBJECTIVE_RACE,bg_players[p].pos,BG_OBJECTIVE_SCORED);
    if(score>=(int)bg_score_limit())mode_finish(p);
}
static void mode_tick(float dt) {
    if(!mode_enabled||bg_match_finished())return;
    const bg_mode_rules *r=bg_current_rules();const bg_mode_map *map=bg_current_mode_map();
    mode_fraction+=dt*30;
    unsigned ticks=(unsigned)(mode_fraction+1e-5f);mode_fraction=fmaxf(0,mode_fraction-ticks);
    for(unsigned p=0;p<active_players;p++) {
        if(r->flags&BG_MODE_TARGETS)if(mode_targets[p]<0||bg_player_eliminated(mode_targets[p]))mode_next_target(p);
        if(bg_players[p].health<=0)continue;
        if((r->flags&BG_MODE_INVISIBLE)||mode_trait(p)==1) {
            if(bg_players[p].invisibility<=0)bg_players[p].camo_opacity=1;
            bg_players[p].invisibility=1;
        }
    }
    if(r->lives) {
        unsigned contenders=0,seen=0,deaths=0;int survivor=-2;
        for(unsigned p=0;p<active_players;p++) {
            deaths+=statistics.deaths[p];
            if(bg_player_eliminated(p))continue;
            unsigned side=bg_mode_has_teams()?mode_teams[p]:p;
            if(!(seen&(1u<<side))){seen|=1u<<side;contenders++;survivor=p;}
        }
        if(deaths&&contenders<2&&active_players>1){mode_finish(survivor);return;}
    }
    if(!map)return;
    if(r->engine==BG_ENGINE_CTF||(r->engine==BG_ENGINE_BALL&&!r->ball_type)) {
        for(unsigned i=0;i<bg_objective_count;i++) {
            bg_objective *o=&bg_objectives[i];
            if(o->owner>=0) {
                memcpy(o->pos,bg_players[o->owner].pos,12);o->pos[1]+=.45f;
                continue;
            }
            o->pickup_delay=fmaxf(0,o->pickup_delay-dt);
            if(o->reset_time>0) {
                o->reset_time=fmaxf(0,o->reset_time-dt);
                if(o->reset_time<=.0001f){mode_reset_objective(o);event(BG_EVENT_OBJECTIVE,-1,o->kind,o->pos,BG_OBJECTIVE_RETURNED);}
            }
            if(!o->active)continue;
            if(!o->at_home){
                float floor=bg_floor(o->pos[0],o->pos[2],o->pos[1]+.1f)+.08f;
                o->fall_speed+=bg_movement.gravity*dt;
                o->pos[1]=fmaxf(floor,o->pos[1]-o->fall_speed*dt);
                if(o->pos[1]<=floor)o->fall_speed=0;
            }
            if(o->pos[1]<bg_map_void_height()+2){mode_reset_objective(o);continue;}
            for(unsigned p=0;p<active_players;p++)if(bg_players[p].health>0&&bg_players[p].vehicle<0&&
                !(o->pickup_delay>0&&o->ignore_player==(int)p)&&mode_near(p,o->pos,.8f)) {
                if(o->kind==BG_OBJECTIVE_FLAG&&mode_teams[p]==(unsigned)o->team) {
                    if(!o->at_home&&!(r->flags&BG_MODE_FLAG_RESET)) {
                        mode_reset_objective(o);event(BG_EVENT_OBJECTIVE,p,o->kind,o->pos,BG_OBJECTIVE_RETURNED);
                    }
                } else if(bg_player_objective(p)<0){mode_take(p,i);break;}
            }
        }
        if(r->engine==BG_ENGINE_CTF)for(unsigned p=0;p<active_players&&!bg_match_finished();p++) {
            int carried=bg_player_objective(p);if(carried<0||bg_players[p].health<=0)continue;
            unsigned team=mode_teams[p];
            if(mode_near(p,bg_objectives[team].home,1)&&(!(r->flags&BG_MODE_FLAG_HOME)||bg_objectives[team].at_home)) {
                mode_add_score(p,1);mode_reset_objective(&bg_objectives[carried]);
                event(BG_EVENT_OBJECTIVE,p,BG_OBJECTIVE_FLAG,bg_players[p].pos,BG_OBJECTIVE_SCORED);
            }
        }
    }
    if(r->engine==BG_ENGINE_BALL&&r->ball_type!=2)for(unsigned p=0;p<active_players&&!bg_match_finished();p++)
        if(bg_players[p].health>0&&bg_player_ball_count(p))mode_add_score(p,ticks*bg_player_ball_count(p));
    if(r->engine==BG_ENGINE_KING) {
        if((r->flags&BG_MODE_MOVING_HILL)&&ticks) {
            if(ticks>=hill_ticks) {
                unsigned ids[64],count=0;
                for(unsigned id=0;id<64;id++)if(id!=hill_id&&mode_marker(BG_MARK_HILL,id))ids[count++]=id;
                if(count)hill_id=ids[mode_random(count)];
                hill_ticks=1800;
                event(BG_EVENT_OBJECTIVE,-1,BG_OBJECTIVE_HILL,bg_players[0].pos,BG_OBJECTIVE_MOVED);
            }else hill_ticks-=ticks;
        }
        unsigned scored=0;
        /* Halo CE scores every occupying side, including contested hills;
         * several teammates do not multiply their team's per-tick score. */
        for(unsigned p=0;p<active_players&&!bg_match_finished();p++)if(bg_players[p].health>0&&bg_player_in_hill(p)) {
            unsigned team=bg_mode_has_teams()?mode_teams[p]:p;
            if(!(scored&(1u<<team))){mode_add_score(p,ticks);scored|=1u<<team;}
        }
    }
    if(r->engine==BG_ENGINE_RACE)for(unsigned p=0;p<active_players&&!bg_match_finished();p++)if(bg_players[p].health>0&&mode_scores[p]<(int)bg_score_limit()) {
        unsigned target=mode_race_target(p);const bg_mode_marker *m=mode_marker(BG_MARK_RACE,target);if(!m)continue;
        const float *pos=bg_players[p].vehicle>=0?bg_vehicles[bg_players[p].vehicle].pos:bg_players[p].pos;
        float dx=pos[0]-m->pos[0],dz=pos[2]-m->pos[2],dy=pos[1]+.35f-m->pos[1];
        bool hit=bg_players[p].vehicle>=0?(dx*dx+dz*dz+dy*dy<=6.25f):(dx*dx+dz*dz<=2.25f&&fabsf(dy)<=.6f);
        if(!hit)continue;
        if(r->race_type==2) {
            mode_race_lap(p);unsigned ids[32],count=0;
            for(unsigned id=0;id<32;id++)if(id!=rally_flag&&(race_mask&(1u<<id)))ids[count++]=id;
            if(count)rally_flag=ids[mode_random(count)];
        }else if(race_visited[p]==race_mask)mode_race_lap(p);
        else {race_visited[p]|=1u<<target;event(BG_EVENT_OBJECTIVE,p,BG_OBJECTIVE_RACE,pos,BG_OBJECTIVE_CHECKPOINT);}
    }
}
bool bg_mode_navpoint(unsigned viewer,unsigned index,float pos[3],unsigned *kind,unsigned *team) {
    if(!mode_enabled||bg_current_rules()->radar==2||!bg_current_mode_map())return false;
    const bg_mode_rules *r=bg_current_rules();
    if(r->flags&BG_MODE_TARGETS) {
        int p=mode_targets[viewer];if(index||p<0)return false;
        memcpy(pos,bg_players[p].pos,12);pos[1]+=.8f;*kind=BG_OBJECTIVE_RACE;*team=2;return true;
    }
    if(r->engine==BG_ENGINE_RACE) {
        const bg_mode_marker *m=mode_marker(BG_MARK_RACE,mode_race_target(viewer));if(index||!m)return false;
        memcpy(pos,m->pos,12);*kind=BG_OBJECTIVE_RACE;*team=2;return true;
    }
    if(r->engine==BG_ENGINE_KING) {
        if(index)return false;
        float p[3];unsigned count=0;pos[0]=pos[1]=pos[2]=0;
        while(bg_mode_hill_point(count,p)){for(unsigned a=0;a<3;a++)pos[a]+=p[a];count++;}
        if(!count)return false;
        for(unsigned a=0;a<3;a++)pos[a]/=count;
        *kind=BG_OBJECTIVE_HILL;*team=2;return true;
    }
    if(r->engine==BG_ENGINE_CTF&&index==bg_objective_count&&bg_player_objective(viewer)>=0){
        for(unsigned i=0;i<bg_objective_count;i++)if(bg_objectives[i].team==(int)mode_teams[viewer]){
            memcpy(pos,bg_objectives[i].home,12);*kind=BG_OBJECTIVE_FLAG;*team=mode_teams[viewer];return true;
        }
    }
    if(index>=bg_objective_count)return false;
    const bg_objective *o=&bg_objectives[index];
    if(o->owner==(int)viewer)return false;
    if(o->owner>=0){memcpy(pos,bg_players[o->owner].pos,12);pos[1]+=.8f;}
    else {if(!o->active)return false;memcpy(pos,o->pos,12);}
    *kind=o->kind;*team=o->team<0?2:(unsigned)o->team;return true;
}
