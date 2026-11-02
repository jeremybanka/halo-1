#include "hud_palette.h"
/* The normal terrain/vehicle pass has already populated depth. Replace color
 * only, then retain that depth for all friendly/hostile silhouettes. */
/* Three players mix wide and narrow views. Cache both without per-frame rebuilds. */
static uint8_t visr_grid_pixels[320*240/2+160*120/2] __attribute__((aligned(16)));
static int visr_grid_w[2],visr_grid_h[2];
static void visr_background(T3DViewport *vp){
    int x=vp->offset[0],y=vp->offset[1],w=vp->size[0],h=vp->size[1];
    assertf(w<=320&&h<=240&&(w%8)==0,"VISR grid dimensions");
    unsigned cache=w==160&&h==120;
    uint8_t *pixels=visr_grid_pixels+(cache?320*240/2:0);
    if(w!=visr_grid_w[cache]||h!=visr_grid_h[cache]){
        /* Fence prior uploads before replacing a cached IA4 grid. */
        rdpq_sync_full(NULL,NULL);rspq_wait();
        memset(pixels,0,w*h/2);
        for(int j=0;j<h;j++)for(int i=0;i<w;i++){
            float nx=(2.f*(i+.5f)/w-1),ny=(2.f*(j+.5f)/h-1);
            /* Inverse barrel map: a fixed grid becomes denser at the center. */
            float lens=1-.10f*(nx*nx+ny*ny);
            float u=(nx*lens+1)*w*.5f,v=(ny*lens+1)*h*.5f;
            float dx=u-8*(int)(u*.125f),dy=v-8*(int)(v*.125f);
            if(fminf(dx,8-dx)<.55f||fminf(dy,8-dy)<.55f){
                unsigned pixel=j*w+i;pixels[pixel/2]|=(pixel&1)?15:240;
            }
        }
        data_cache_hit_writeback(pixels,w*h/2);visr_grid_w[cache]=w;visr_grid_h[cache]=h;
#ifdef BG_ODST_QA
        debugf("VISR_GRID_BUILD width=%d height=%d\n",w,h);
#endif
    }
    rdpq_set_scissor(x,y,x+w,y+h);
    rdpq_set_mode_fill(RGBA32(0,68,17,255));rdpq_fill_rectangle(x,y,x+w,y+h);
    rdpq_set_mode_standard();rdpq_mode_zbuf(false,false);rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_filter(FILTER_POINT);rdpq_mode_persp(false);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,PRIM),(TEX0,0,PRIM,0)));
    rdpq_set_prim_color(RGBA32(2,77,24,255));
    surface_t grid=surface_make_linear(pixels,FMT_IA4,w,h);
    rdpq_tex_blit(&grid,x,y,NULL);
}
static void visr_color(bool enemy){
    rdpq_sync_pipe();rdpq_mode_zbuf(true,true);rdpq_mode_blender(0);
    rdpq_mode_alphacompare(0);rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,PRIM),(0,0,0,SHADE)));
    rdpq_set_prim_color(enemy?RGBA32(187,255,204,255):RGBA32(BG_VISR_FRIENDLY_R,BG_VISR_FRIENDLY_G,BG_VISR_FRIENDLY_B,255));
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
}
static void draw_visr_units(unsigned viewer,T3DViewport *vp){
    visr_background(vp);visr_color(false);
    for(unsigned j=0;j<views;j++)if(body_lods[viewer][j]||held_masks[viewer]&(1u<<j)){
        ensure_player_animation(j);visr_color(bg_visr_enemy(viewer,j));
        if(body_lods[viewer][j]){
            bool lod=body_lods[viewer][j]==2;t3d_matrix_set(&transforms[slot][j],true);
            rspq_block_run(lod?armor_lod_blocks[slot][j]:player_blocks[slot][j]);triangles+=body_model(j,lod)->triangle_count;
#ifdef BG_PROFILE
            const bg_model_asset*m=body_model(j,lod);submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        }
        if(held_masks[viewer]&(1u<<j)){
            int kind=objective_kind(j);t3d_matrix_set(&held_matrices[slot][j],true);
            if(kind>=0){rspq_block_run(objective_blocks[kind]);triangles+=bg_objective_models[kind].triangle_count;}
            else instance(weapon_model(bg_players[j].weapon),&held_matrices[slot][j]);
        }
    }
#ifdef BG_PVE
    if(bg_pve_is_active())for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[viewer][i]){
        unsigned lod=pve_lods[viewer][i]-1,owner=i;
#ifndef BG_PVE_PREP_BASELINE
        owner=pve_pose_owner[i][lod];
#endif
        visr_color(bg_visr_enemy(viewer,BG_PLAYERS+i));t3d_matrix_set(&pve_matrices[slot][i],true);
        rspq_block_run(pve_blocks[slot][owner][lod]);
#ifdef BG_PVE_MODEL_CANDIDATE
        if(pve_alpha_blocks[slot][owner][lod])rspq_block_run(pve_alpha_blocks[slot][owner][lod]);
#endif
        const bg_model_asset*m=&bg_pve_models[bg_pve_actors[i].kind][lod];triangles+=m->triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        if(bg_players[BG_PLAYERS+i].vehicle<0){
#ifdef BG_PVE_ROSTER
            const bg_pve_actor *actor=&bg_pve_actors[i];
            if(actor->armament){
                unsigned weapon=actor->armament-1;const bg_model_asset *gun=&bg_pve_roster_weapons[weapon];
                t3d_matrix_set(&pve_guns[slot][i],true);rspq_block_run(pve_roster_weapon_blocks[weapon]);triangles+=gun->triangle_count;
#ifdef BG_PROFILE
                submitted_vertices+=model_load_count(gun,gun->vertex_count,0,gun->batch_count);
#endif
            }else
#endif
            if(bg_pve_actors[i].kind!=BG_PVE_HUNTER)
                instance(weapon_model(bg_players[BG_PLAYERS+i].weapon),&pve_guns[slot][i]);
        }
    }
#endif
}
