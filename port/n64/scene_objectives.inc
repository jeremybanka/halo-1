/* Objective geometry uses the same frame-slot fences as ordinary weapons.
 * Map selection owns no renderer buffers; the bounded assets are shared. */
static rspq_block_t *objective_blocks[2],*objective_fp_blocks[2];
static rspq_block_t *flag_fp_cloth_block;
static T3DMat4FP objective_matrices[BG_FRAME_SLOTS][BG_MAX_OBJECTIVES];
static T3DVertPacked hill_vertices[BG_FRAME_SLOTS][24] __attribute__((aligned(16)));
static unsigned hill_vertices_count;
static int objective_kind(unsigned player){
    int i=bg_player_objective(player);return i<0?-1:bg_objectives[i].kind;
}
static void objectives_init(void){
    for(unsigned k=0;k<2;k++){
        prepare_model(&bg_objective_models[k]);
        objective_blocks[k]=record_model(&bg_objective_models[k],bg_objective_models[k].vertices);
        prepare_model(&bg_objective_fp_models[k]);
        const bg_model_asset *fp=&bg_objective_fp_models[k];
        T3DVertPacked *vertices=t3d_segment_placeholder(T3D_SEGMENT_1);
        if(k==BG_OBJECTIVE_FLAG){
            objective_fp_blocks[k]=record_model_range(fp,vertices,0,fp->vertex_count,0,bg_flag_fp_body_batches);
            flag_fp_cloth_block=record_model_range(fp,vertices,0,fp->vertex_count,
                bg_flag_fp_body_batches,fp->batch_count-bg_flag_fp_body_batches);
        }else objective_fp_blocks[k]=record_model(fp,vertices);
    }
    data_cache_hit_writeback((void*)bg_flag_textures,sizeof(bg_flag_textures));
}
static void objective_texture(int team){
    surface_t image=surface_make_linear((void*)bg_flag_textures[team==1],FMT_RGBA16,64,32);
    rdpq_sync_pipe();rdpq_mode_tlut(TLUT_NONE);rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);
    rdpq_mode_persp(true);rdpq_mode_filter(FILTER_POINT);rdpq_mode_alphacompare(128);
    rdpq_sync_tile();rdpq_sync_load();rdpq_tex_upload(TILE0,&image,NULL);
    /* The original cloth is two-sided. Keep the small pole mesh two-sided too. */
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_TEXTURED);
}
static void objective_texture_end(void){
    rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);rdpq_mode_alphacompare(0);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH);
}
static void objective_instance(unsigned kind,int team,T3DMat4FP *transform,bool fp){
    const bg_model_asset *a=fp?&bg_objective_fp_models[kind]:&bg_objective_models[kind];
    t3d_matrix_set(transform,true);
    if(kind==BG_OBJECTIVE_FLAG&&fp){
        /* The closed hand/pole must never sample the cloth atlas or its alpha.
         * Only the two-sided banner uses the textured cutout pass. */
        rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);rdpq_mode_alphacompare(0);
        t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
        rspq_block_run(objective_fp_blocks[kind]);
        objective_texture(team);rspq_block_run(flag_fp_cloth_block);
    }else{
        if(kind==BG_OBJECTIVE_FLAG)objective_texture(team);
        rspq_block_run(fp?objective_fp_blocks[kind]:objective_blocks[kind]);
    }
    triangles+=a->triangle_count;
#ifdef BG_PROFILE
    for(unsigned b=0;b<a->batch_count;b++)submitted_vertices+=a->batches[b].count;
#endif
    if(kind==BG_OBJECTIVE_FLAG)objective_texture_end();
}
static void objectives_prepare(void){
    for(unsigned i=0;i<bg_objective_count;i++){
        const bg_objective *o=&bg_objectives[i];if(!o->active||o->owner>=0)continue;
        float pos[3];memcpy(pos,o->pos,12);
        /* Source pole origin is its hand grip; lift the shaft above the floor. */
        pos[1]+=o->kind==BG_OBJECTIVE_FLAG?.43f:.07f;
        matrix(&objective_matrices[slot][i],BG_SCALE/BG_OBJECT_SCALE,o->yaw,0,pos);
    }
    data_cache_hit_writeback(objective_matrices[slot],sizeof(objective_matrices[slot]));
    float points[12][3];unsigned count=0;
    while(count<12&&bg_mode_hill_point(count,points[count]))count++;
    hill_vertices_count=count>=3?count*4:0;
    for(unsigned i=0;i<count&&count>=3;i++)for(unsigned c=0;c<4;c++){
        const float *p=points[(i+(c==1||c==2))%count];
        int16_t *v=t3d_vertbuffer_get_pos(hill_vertices[slot],i*4+c);
        for(unsigned a=0;a<3;a++)v[a]=lroundf((p[a]+(a==1?(c<2?.02f:.18f):0))*BG_SCALE);
        *t3d_vertbuffer_get_color(hill_vertices[slot],i*4+c)=0x66baffff;
    }
    data_cache_hit_writeback(hill_vertices[slot],sizeof(hill_vertices[slot]));
}
static void objectives_draw(unsigned viewer,T3DViewport *vp){
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH);
    for(unsigned i=0;i<bg_objective_count;i++){
        const bg_objective *o=&bg_objectives[i];if(!o->active||o->owner>=0)continue;
        bg_cull_bounds bounds;prepare_effect_bounds(&bounds,o->pos,bg_objective_models[o->kind].radius+.5f);
        if(visible_bounds(vp,&bounds,cull_selected[viewer]))
            objective_instance(o->kind,o->team,&objective_matrices[slot][i],false);
    }
    if(hill_vertices_count){
        t3d_matrix_set(&terrain_matrix,true);t3d_vert_load(hill_vertices[slot],0,hill_vertices_count);
        for(unsigned i=0;i<hill_vertices_count;i+=4){t3d_tri_draw(i,i+1,i+2);t3d_tri_draw(i,i+2,i+3);}
        t3d_tri_sync();triangles+=hill_vertices_count/2;
#ifdef BG_PROFILE
        submitted_vertices+=hill_vertices_count;
#endif
    }
}
static void animate_objective(unsigned p,unsigned kind){
    bg_player *player=&bg_players[p];const bg_model_asset *m=&bg_objective_fp_models[kind];
    unsigned bytes=((m->vertex_count+1)&~1u)*16;
    firstperson_buffer_resize(p,bytes);T3DVertPacked *output=CachedAddr(firstperson[slot][p]);
    int key=BG_FP_WEAPONS+kind;
    if(firstperson_weapon[slot][p]!=key){
        memcpy(output,m->vertices,bytes);tint_team(output,m->vertex_count,bg_objective_fp_team_masks[kind],p);
        firstperson_weapon[slot][p]=key;
    }
    unsigned clip=player->melee_time>0?BG_FP_MELEE:BG_FP_IDLE;
#ifdef BG_OBJECTIVE_PHOTO
    clip=BG_OBJECTIVE_PHOTO<4?BG_FP_IDLE:BG_FP_MELEE;
#endif
    const bg_anim_asset *a=&bg_objective_fp_animations[kind][clip];
    float phase=clip==BG_FP_IDLE?game_time/a->duration:player->anim_time/bg_player_melee_duration(p);
    phase=clip==BG_FP_IDLE?phase-floorf(phase):fminf(.9999f,phase);
#ifdef BG_MODES_PREVIEW
    if(clip==BG_FP_IDLE)phase=0; /* Stable pose for repeatable visual appraisal. */
#endif
    float frame=phase*(a->frames-1);
#ifdef BG_OBJECTIVE_PHOTO
    frame=BG_OBJECTIVE_PHOTO<4?BG_OBJECTIVE_PHOTO:BG_OBJECTIVE_PHOTO-4;
    assertf(frame<a->frames,"Objective photo pose");
#endif
    unsigned f0=frame,f1=f0+1<a->frames?f0+1:f0;
    if(kind==BG_OBJECTIVE_FLAG){
        assertf(!a->positions&&a->tracks<=motion_capacity,"Flag motion bank");
        const uint16_t *poses=bg_flag_fp_positions[clip];
        BG_ANIM_COUNT(meshes);
        BG_ANIM_BEGIN(decode_begin);
        bg_motion_decode16(motion_tracks,a->tracks,poses+f0*a->tracks*3,
                           poses+f1*a->tracks*3,a->origin,(frame-f0)*256);
        BG_ANIM_END(decode,decode_begin);
        BG_ANIM_BEGIN(scatter_begin);
        bg_motion_scatter(output,a->vertices,a->indices,motion_tracks);
        BG_ANIM_END(scatter,scatter_begin);
#ifdef BG_PROFILE
        animated_tracks+=a->tracks;animated_vertices+=a->vertices;
#endif
    }else animate_mesh(output,a,f0,f1,(frame-f0)*256);
    data_cache_hit_writeback(output,bytes);
}
