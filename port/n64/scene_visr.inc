/* An independent per-view pass: no sky, world, held guns, effects or viewmodel.
 * No world depth is submitted, so even occluded and cloaked enemies appear.
 * Constant primitive color removes every material/shading detail. */
static void draw_visr(unsigned viewer, T3DViewport *vp) {
#ifdef BG_PROFILE
    unsigned before=triangles,animation_before=animation_us;uint64_t begin=get_ticks_us();
#endif
    int x=vp->offset[0], y=vp->offset[1], w=vp->size[0], h=vp->size[1];
    rdpq_set_scissor(x,y,x+w,y+h);
    rdpq_set_mode_fill(RGBA32(0,68,17,255));
    rdpq_fill_rectangle(x,y,x+w,y+h);
    rdpq_set_fill_color(RGBA32(2,77,24,255));
    for(int i=x+8;i<x+w;i+=8)rdpq_fill_rectangle(i,y,i+1,y+h);
    for(int i=y+8;i<y+h;i+=8)rdpq_fill_rectangle(x,i,x+w,i+1);
    t3d_frame_start();
    rdpq_set_mode_standard();
    rdpq_set_scissor(x,y,x+w,y+h);
    rdpq_mode_zbuf(false,false); rdpq_mode_blender(0);
    rdpq_mode_alphacompare(0); rdpq_mode_tlut(TLUT_NONE);
    rdpq_set_prim_color(RGBA32(187,255,204,255));
    rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,PRIM),(0,0,0,SHADE)));
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_CULL_BACK);
    t3d_matrix_push_pos(1);
    for(unsigned j=0;j<views;j++)if(body_lods[viewer][j]&&bg_visr_enemy(viewer,j)) {
        ensure_player_animation(j);
        bool lod=body_lods[viewer][j]==2;
        t3d_matrix_set(&transforms[slot][j],true);
        rspq_block_run(lod?armor_lod_blocks[slot][j]:player_blocks[slot][j]);
        triangles+=body_model(j,lod)->triangle_count;
#ifdef BG_PROFILE
        const bg_model_asset *m=body_model(j,lod);
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
    }
#ifdef BG_PVE
    if(bg_pve_is_active())for(unsigned i=0;i<bg_pve_count;i++)
        if(pve_lods[viewer][i]&&bg_visr_enemy(viewer,BG_PLAYERS+i)) {
            unsigned lod=pve_lods[viewer][i]-1,owner=i;
#ifndef BG_PVE_PREP_BASELINE
            owner=pve_pose_owner[i][lod];
#endif
            t3d_matrix_set(&pve_matrices[slot][i],true);
            rspq_block_run(pve_blocks[slot][owner][lod]);
#ifdef BG_PVE_MODEL_CANDIDATE
            if(pve_alpha_blocks[slot][owner][lod])rspq_block_run(pve_alpha_blocks[slot][owner][lod]);
#endif
            triangles+=bg_pve_models[bg_pve_actors[i].kind][lod].triangle_count;
#ifdef BG_PROFILE
            const bg_model_asset *m=&bg_pve_models[bg_pve_actors[i].kind][lod];
            submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        }
#endif
#ifdef BG_PROFILE
    object_us+=get_ticks_us()-begin-(animation_us-animation_before);
    category_triangles[2]+=triangles-before;
#endif
    t3d_matrix_pop(1);
    rdpq_mode_zbuf(true,true); rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
}
