/* Explicit visual-bank experiment. Simulation and collision stay canonical. */
static uint8_t pve_ship_lod[4];
static rspq_block_t *pve_record_surface(unsigned kind,unsigned lod,T3DVertPacked*vertices,bool alpha){
    const bg_model_asset*m=&bg_pve_models[kind][lod];const uint8_t*modes=bg_pve_batch_modes[kind][lod];
    bool any=false;for(unsigned b=0;b<m->batch_count;b++)any|=!!(modes[b]&2)==alpha;
    if(!any)return NULL;
    rspq_block_begin();unsigned previous=~0u;
    for(unsigned b=0;b<m->batch_count;b++)if(!!(modes[b]&2)==alpha){
        unsigned flags=T3D_FLAG_SHADED|T3D_FLAG_DEPTH|((modes[b]&1)?0:T3D_FLAG_CULL_BACK);
        if(flags!=previous){t3d_state_set_drawflags(flags);previous=flags;}
        const bg_mesh_batch*batch=&m->batches[b];
        t3d_vert_load(vertices+batch->first/2,0,(batch->count+1)&~1u);
        t3d_tri_draw_strip(m->indices+batch->index_first,batch->index_count);t3d_tri_sync();
    }
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
    return rspq_block_end();
}
static void pve_prepare_ship_candidate(void){
    if(!bg_ff_dropship.phase)return;
    unsigned i=BG_PVE_MAX,wanted=0;bg_cull_bounds bounds;prepare_effect_bounds(&bounds,bg_ff_dropship.pos,9);
    for(unsigned v=0;v<views;v++){
        pve_ship_visible[v]=visible_bounds(&viewports[slot][v],&bounds,cull_selected[v]);
        if(!pve_ship_visible[v])continue;
        float distance2=0;for(unsigned a=0;a<3;a++){float delta=bg_ff_dropship.pos[a]-bg_players[v].pos[a];distance2+=delta*delta;}
        unsigned lod=distance2>(views==1?400:225)&&!bg_players[v].zoom;
#ifdef BG_PVE_MODEL_QA
        lod=bg_pve_model_qa_lod;
#endif
        pve_ship_lod[v]=lod;wanted|=1u<<lod;
    }
    if(!wanted)return;
    matrix(&pve_matrices[slot][i],BG_SCALE/BG_PVE_SCALE,bg_ff_dropship.yaw,0,bg_ff_dropship.pos);
    for(unsigned lod=0;lod<2;lod++)if(wanted&(1u<<lod)){
        const bg_model_asset*m=&bg_pve_models[BG_PVE_SPIRIT][lod];
        if(!pve_vertices[slot][i][lod]){
            pve_vertices[slot][i][lod]=malloc_uncached(m->vertex_count*16);assertf(pve_vertices[slot][i][lod],"Spirit vertices");
            memcpy(pve_vertices[slot][i][lod],m->vertices,m->vertex_count*16);
            pve_blocks[slot][i][lod]=pve_record_surface(BG_PVE_SPIRIT,lod,pve_vertices[slot][i][lod],false);
            pve_alpha_blocks[slot][i][lod]=pve_record_surface(BG_PVE_SPIRIT,lod,pve_vertices[slot][i][lod],true);
        }
        const bg_pve_animation*c=&bg_pve_animations[BG_PVE_SPIRIT][lod][PVE_EXIT];
        float frame=bg_ff_dropship.door*(c->frames-1);unsigned f0=frame,f1=f0+1<c->frames?f0+1:f0;int mix=(frame-f0)*256;
        uint32_t key=1+(f0<<16)+(f1<<8)+mix;
        if(pve_pose_keys[slot][i][lod]==key)continue;
        pve_pose_keys[slot][i][lod]=key;
        const uint16_t*samples=pve_motion_pair(c,f0,f1);T3DVertPacked*out=CachedAddr(pve_vertices[slot][i][lod]);
        for(unsigned v=0;v<c->vertices;v++){int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;unsigned track=c->indices[v];for(unsigned axis=0;axis<3;axis++){int a=samples[track*3+axis],b=samples[((f1-f0)*c->tracks+track)*3+axis];pos[axis]=c->origin[axis]+a+((b-a)*mix>>8);}}
        data_cache_hit_writeback(out,m->vertex_count*16);
    }
}
static void pve_draw_alpha(unsigned view){
    /* Energy/detail surfaces test world depth without hiding later geometry.
     * Standard alpha is a bounded N64 approximation of CE's layered additive
     * shaders; the RDP's additive blend can overflow instead of saturating. */
    rdpq_mode_zbuf(true,false);rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    if(pve_ship_visible[view]){
        rspq_block_t*block=pve_alpha_blocks[slot][BG_PVE_MAX][pve_ship_lod[view]];
        if(block){t3d_matrix_set(&pve_matrices[slot][BG_PVE_MAX],true);rspq_block_run(block);}
    }
    for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]){
        rspq_block_t*block=pve_alpha_blocks[slot][i][pve_lods[view][i]-1];
        if(block){t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(block);}
    }
    rdpq_mode_blender(0);rdpq_mode_zbuf(true,true);
}
