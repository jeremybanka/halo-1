/* CPU state is per flag, shared by every camera. Only slot-local output
 * vertices are borrowed by the RSP, and are filled after the frame fence. */
static bg_cloth_state flag_cloth_states[2];
static bg_cloth_wind_state flag_wind_state;
static float flag_cloth_shape[2][BG_CLOTH_VERTICES][3];
static int flag_cloth_owner[2];
static float flag_cloth_time,flag_cloth_fraction;
static unsigned flag_cloth_map=~0u;
static T3DVertPacked flag_cloth_world[BG_FRAME_SLOTS][2][BG_CLOTH_VERTICES/2] __attribute__((aligned(16)));
static T3DVertPacked flag_cloth_fp[BG_FRAME_SLOTS][4][BG_CLOTH_VERTICES/2] __attribute__((aligned(16)));
static rspq_block_t *flag_cloth_world_blocks[BG_FRAME_SLOTS][2],*flag_cloth_fp_blocks[BG_FRAME_SLOTS][4];
static int16_t flag_cloth_indices[BG_CLOTH_TRIANGLES*3] __attribute__((aligned(8)));
static void flag_cloth_basis(const float corners[3][3],float axes[3][3],float lengths[2]) {
    for(unsigned a=0;a<3;a++){axes[0][a]=corners[2][a]-corners[0][a];axes[1][a]=corners[1][a]-corners[0][a];}
    lengths[0]=bg_cloth_unit(axes[0]);lengths[1]=bg_cloth_unit(axes[1]);
    bg_cloth_cross(axes[2],axes[0],axes[1]);bg_cloth_unit(axes[2]);
}
static rspq_block_t *flag_cloth_record(T3DVertPacked *v) {
    memset(v,0,BG_CLOTH_VERTICES*16);
    for(unsigned x=0;x<BG_CLOTH_COLS;x++)for(unsigned y=0;y<BG_CLOTH_ROWS;y++) {
        unsigned i=x*BG_CLOTH_ROWS+y;
        *t3d_vertbuffer_get_color(v,i)=0xffffffff;
        int16_t *uv=t3d_vertbuffer_get_uv(v,i);
        uv[0]=x*(63*32)/(BG_CLOTH_COLS-1);uv[1]=y*(30*32)/(BG_CLOTH_ROWS-1);
    }
    rspq_block_begin();t3d_vert_load(v,0,BG_CLOTH_VERTICES);
    t3d_tri_draw_strip(flag_cloth_indices,BG_CLOTH_TRIANGLES*3);t3d_tri_sync();
    return rspq_block_end();
}
static void flag_cloth_init(void) {
    unsigned i=0;
    for(unsigned x=0;x<BG_CLOTH_COLS-1;x++)for(unsigned y=0;y<BG_CLOTH_ROWS-1;y++) {
        unsigned a=x*BG_CLOTH_ROWS+y,b=a+1,c=a+BG_CLOTH_ROWS+1,d=a+BG_CLOTH_ROWS;
        unsigned indices[6]={a,b,c,a,c,d};
        for(unsigned j=0;j<6;j++,i++)flag_cloth_indices[i]=indices[j]|((i&&i%3==0)?0x8000:0);
    }
    t3d_indexbuffer_convert(flag_cloth_indices,i);
    data_cache_hit_writeback(flag_cloth_indices,sizeof(flag_cloth_indices));
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++) {
        for(unsigned f=0;f<2;f++)flag_cloth_world_blocks[s][f]=flag_cloth_record(flag_cloth_world[s][f]);
        for(unsigned p=0;p<4;p++)flag_cloth_fp_blocks[s][p]=flag_cloth_record(flag_cloth_fp[s][p]);
    }
}
static void flag_cloth_emit(T3DVertPacked *v,unsigned team,const float corners[3][3],float scale) {
    float axes[3][3],lengths[2];flag_cloth_basis(corners,axes,lengths);
    for(unsigned i=0;i<BG_CLOTH_VERTICES;i++) {
        const float *shape=flag_cloth_shape[team][i];int16_t *p=t3d_vertbuffer_get_pos(v,i);
        for(unsigned a=0;a<3;a++)p[a]=lroundf(scale*(corners[0][a]+
            axes[0][a]*shape[0]*lengths[0]+axes[1][a]*shape[1]*lengths[1]+axes[2][a]*shape[2]*lengths[0]));
    }
    data_cache_hit_writeback(v,BG_CLOTH_VERTICES*16);
}
static void objectives_cloth_prepare(void) {
#ifdef BG_FLAG_CLOTH_QA
    uint64_t begin=get_ticks_us();
#endif
    bool active[2]={false,false};float corners[2][3][3];
    unsigned map=bg_map_id();
    if(map!=flag_cloth_map||game_time<flag_cloth_time||bg_match_time()<.05f) {
        memset(flag_cloth_states,0,sizeof(flag_cloth_states));memset(&flag_wind_state,0,sizeof(flag_wind_state));
        flag_cloth_map=map;flag_cloth_time=game_time;flag_cloth_fraction=0;
    }
    for(unsigned i=0;i<bg_objective_count;i++) {
        const bg_objective *o=&bg_objectives[i];if(!o->active||o->kind!=BG_OBJECTIVE_FLAG)continue;
        unsigned team=o->team==1;active[team]=true;
        const T3DMat4FP *m=&objective_matrices[slot][i];
        if(o->owner>=0) {
            wanted_held|=1u<<o->owner;ensure_player_animation(o->owner);m=&held_matrices[slot][o->owner];
        }
        for(unsigned p=0;p<3;p++)for(unsigned a=0;a<3;a++) {
            float value=t3d_mat4fp_get_float(m,3,a);
            for(unsigned b=0;b<3;b++)value+=t3d_mat4fp_get_float(m,b,a)*bg_flag_world_corners[p][b]*BG_OBJECT_SCALE;
            corners[team][p][a]=value/BG_SCALE;
        }
        if(!flag_cloth_states[team].initialized||flag_cloth_owner[team]!=o->owner)
            bg_cloth_reset(&flag_cloth_states[team],corners[team]);
        flag_cloth_owner[team]=o->owner;
    }
    float elapsed=fmaxf(0,game_time-flag_cloth_time);flag_cloth_time=game_time;
    if(!active[0]&&!active[1]){flag_cloth_fraction=0;memset(flag_cloth_states,0,sizeof(flag_cloth_states));return;}
    if(elapsed>.15f){for(unsigned f=0;f<2;f++)if(active[f])bg_cloth_reset(&flag_cloth_states[f],corners[f]);elapsed=0;flag_cloth_fraction=0;}
    flag_cloth_fraction+=elapsed;
    const bg_cloth_weather *weather=&bg_flag_weather[map<13?map:0];
    const float *origin=bg_map_origin();
#ifdef BG_FLAG_CLOTH_QA
    uint64_t sim_begin=get_ticks_us();unsigned steps=0;
#endif
    for(unsigned step=0;step<4&&flag_cloth_fraction+1e-6f>=1.f/30;step++) {
#ifdef BG_FLAG_CLOTH_QA
        steps++;
#endif
        flag_cloth_fraction-=1.f/30;bg_cloth_wind_step(&flag_wind_state,weather);
        for(unsigned f=0;f<2;f++)if(active[f]) {
            float winds[BG_CLOTH_VERTICES][3]={{0}};
            bool windy=bg_cloth_has_wind(weather,corners[f][0]);
            for(unsigned i=0;i<BG_CLOTH_VERTICES&&windy;i++) {
                const float *p=flag_cloth_states[f].points[i].p;
                float source[3]={p[0]+origin[0],-p[2]+origin[1],p[1]+origin[2]};
                bg_cloth_wind_at(winds[i],weather,&flag_wind_state,bg_flag_wind_noise,source);
            }
            bg_cloth_step(&flag_cloth_states[f],&bg_flag_cloth_physics,corners[f],winds,1.f/30);
        }
    }
#ifdef BG_FLAG_CLOTH_QA
    uint64_t sim_us=get_ticks_us()-sim_begin;
#endif
    for(unsigned f=0;f<2;f++)if(active[f]) {
        float axes[3][3],lengths[2];flag_cloth_basis(corners[f],axes,lengths);
        for(unsigned i=0;i<BG_CLOTH_VERTICES;i++) {
            float delta[3];for(unsigned a=0;a<3;a++)delta[a]=flag_cloth_states[f].points[i].p[a]-corners[f][0][a];
            for(unsigned a=0;a<3;a++)flag_cloth_shape[f][i][a]=bg_cloth_dot(delta,axes[a])/lengths[a==1];
        }
        /* The two attachments follow the exact current render pose, even on
         * a render between simulation ticks. */
        memset(flag_cloth_shape[f][0],0,12);memset(flag_cloth_shape[f][BG_CLOTH_ROWS-1],0,12);
        flag_cloth_shape[f][BG_CLOTH_ROWS-1][1]=1;
        flag_cloth_emit(flag_cloth_world[slot][f],f,bg_flag_world_corners,BG_OBJECT_SCALE);
    }
#ifdef BG_FLAG_CLOTH_QA
    static uint64_t total,sim;static unsigned frames,sim_steps,maximum;
    unsigned elapsed_us=get_ticks_us()-begin;total+=elapsed_us;sim+=sim_us;sim_steps+=steps;frames++;
    if(elapsed_us>maximum)maximum=elapsed_us;
    if(frames==300){
        debugf("CLOTH_QA frames=%u steps=%u total_us=%u sim_us=%u max_us=%u time_ms=%u\n",frames,sim_steps,(unsigned)total,(unsigned)sim,maximum,(unsigned)(game_time*1000));
        total=sim=frames=sim_steps=maximum=0;
    }
#endif
}
