/* Source low/superlow geometry; animation is shared across all viewports. */
#include "asset_pve.h"
static T3DVertPacked *pve_vertices[BG_FRAME_SLOTS][BG_PVE_MAX][2];
static rspq_block_t *pve_blocks[BG_FRAME_SLOTS][BG_PVE_MAX][2];
static T3DMat4FP pve_matrices[BG_FRAME_SLOTS][BG_PVE_MAX],pve_guns[BG_FRAME_SLOTS][BG_PVE_MAX];
static uint8_t pve_lods[4][BG_PVE_MAX];
static bool pve_initialized;
static uint32_t pve_pose_keys[BG_FRAME_SLOTS][BG_PVE_MAX][2];
static int16_t pve_decoded[2048][3];
unsigned bg_pve_animation_us;
static void pve_release(void){
    rspq_wait();
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned i=0;i<BG_PVE_MAX;i++)for(unsigned l=0;l<2;l++){
        if(pve_blocks[s][i][l])rspq_block_free(pve_blocks[s][i][l]);
        if(pve_vertices[s][i][l])free_uncached(pve_vertices[s][i][l]);
    }
    memset(pve_blocks,0,sizeof(pve_blocks));memset(pve_vertices,0,sizeof(pve_vertices));
    memset(pve_pose_keys,0,sizeof(pve_pose_keys));memset(pve_lods,0,sizeof(pve_lods));
}
static void pve_prepare(void){
    bg_pve_animation_us=0;
    if(!bg_pve_is_active())return;
    uint32_t begin=get_ticks_us();
    if(!pve_initialized){
        for(unsigned kind=0;kind<2;kind++)for(unsigned lod=0;lod<2;lod++)prepare_model(&bg_pve_models[kind][lod]);
        pve_initialized=true;
    }
    memset(pve_lods,0,sizeof(pve_lods));
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];unsigned wanted=0;
        bg_cull_bounds bounds;float center[3]={p->pos[0],p->pos[1]+.4f,p->pos[2]};prepare_effect_bounds(&bounds,center,1.4f);
        for(unsigned v=0;v<views;v++){
            T3DViewport*vp=&viewports[slot][v];if(!visible_bounds(vp,&bounds,cull_selected[v]))continue;
            float dx=p->pos[0]-bg_players[v].pos[0],dy=p->pos[1]-bg_players[v].pos[1],dz=p->pos[2]-bg_players[v].pos[2];
            unsigned lod=dx*dx+dy*dy+dz*dz>(views==1?36:16)&&!bg_players[v].zoom;
            pve_lods[v][i]=lod+1;wanted|=1u<<lod;
        }
        if(!wanted)continue;
        matrix(&pve_matrices[slot][i],BG_SCALE/BG_PVE_SCALE,p->yaw,0,p->pos);
        for(unsigned lod=0;lod<2;lod++)if(wanted&(1u<<lod)){
            const bg_model_asset*m=&bg_pve_models[a->kind][lod];
            if(!pve_vertices[slot][i][lod]){
                pve_vertices[slot][i][lod]=malloc_uncached(m->vertex_count*16);assertf(pve_vertices[slot][i][lod],"PvE vertex buffers");
                memcpy(pve_vertices[slot][i][lod],m->vertices,m->vertex_count*16);
                pve_blocks[slot][i][lod]=record_model(m,pve_vertices[slot][i][lod]);
            }
            const bg_pve_animation*clip=&bg_pve_animations[a->kind][lod][a->clip];
            float phase=a->time/clip->duration;if(a->clip==PVE_DEATH||a->clip==PVE_MELEE)phase=fminf(phase,.99999f);else phase-=floorf(phase);
            float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;int mix=(frame-f0)*256;
            uint32_t key=1u+((uint32_t)a->clip<<24)+(f0<<16)+(f1<<8)+mix;
            if(pve_pose_keys[slot][i][lod]==key)continue;
            pve_pose_keys[slot][i][lod]=key;
            T3DVertPacked*out=CachedAddr(pve_vertices[slot][i][lod]);
            assertf(clip->tracks<=2048,"PvE track capacity");
            for(unsigned t=0;t<clip->tracks;t++)for(unsigned c=0;c<3;c++){
                int x=clip->positions[(f0*clip->tracks+t)*3+c],y=clip->positions[(f1*clip->tracks+t)*3+c];
                pve_decoded[t][c]=clip->origin[c]+x+((y-x)*mix>>8);
            }
            for(unsigned v=0;v<clip->vertices;v++){
                int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;
                memcpy(pos,pve_decoded[clip->indices[v]],6);
            }
            data_cache_hit_writeback(out,m->vertex_count*16);
#ifdef BG_PROFILE
            animated_tracks+=clip->tracks;animated_vertices+=clip->vertices;
#endif
        }
        const bg_attachment_clip*clip=&bg_pve_grips[a->kind][a->clip];float phase=a->time/clip->duration;
        if(a->clip==PVE_DEATH||a->clip==PVE_MELEE)phase=fminf(phase,.99999f);else phase-=floorf(phase);
        float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;
        float q[4],pos[3];blam_quaternions_interpolate_and_normalize(clip->poses[f0].quat,clip->poses[f1].quat,frame-f0,q);
        for(unsigned c=0;c<3;c++)pos[c]=(clip->poses[f0].pos[c]+(clip->poses[f1].pos[c]-clip->poses[f0].pos[c])*(frame-f0))*BG_SCALE;
        T3DMat4 hand,body,world;
        t3d_mat4_from_srt(&hand,(float[]){BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE},q,pos);
        t3d_mat4_from_srt_euler(&body,(float[]){1,1,1},(float[]){0,-p->yaw,0},(float[]){p->pos[0]*BG_SCALE,p->pos[1]*BG_SCALE,p->pos[2]*BG_SCALE});
        t3d_mat4_mul(&world,&body,&hand);t3d_mat4_to_fixed_3x4(&pve_guns[slot][i],&world);
    }
    bg_pve_animation_us=get_ticks_us()-begin;
    data_cache_hit_writeback(pve_matrices[slot],sizeof(pve_matrices[slot]));data_cache_hit_writeback(pve_guns[slot],sizeof(pve_guns[slot]));
}
static void pve_draw(unsigned view){
    for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]){
        unsigned lod=pve_lods[view][i]-1;const bg_model_asset*m=&bg_pve_models[bg_pve_actors[i].kind][lod];
        t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(pve_blocks[slot][i][lod]);triangles+=m->triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        if(bg_players[BG_PLAYERS+i].health>0)instance(weapon_model(bg_players[BG_PLAYERS+i].weapon),&pve_guns[slot][i]);
    }
}
