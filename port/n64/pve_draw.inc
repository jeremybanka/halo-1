/* Source low/superlow geometry; animation is shared across all viewports. */
#include "asset_pve.h"
#ifdef BG_PVE_MODEL_QA
extern unsigned bg_pve_model_qa_lod;
#endif
static T3DVertPacked *pve_vertices[BG_FRAME_SLOTS][BG_PVE_MAX+1][2];
static rspq_block_t *pve_blocks[BG_FRAME_SLOTS][BG_PVE_MAX+1][2];
static T3DMat4FP pve_matrices[BG_FRAME_SLOTS][BG_PVE_MAX+1],pve_guns[BG_FRAME_SLOTS][BG_PVE_MAX+1];
static uint8_t pve_lods[4][BG_PVE_MAX+1];
static bool pve_initialized;
static uint8_t pve_buffer_kind[BG_FRAME_SLOTS][BG_PVE_MAX+1][2];
static bool pve_ship_visible[4];
static uint32_t pve_pose_keys[BG_FRAME_SLOTS][BG_PVE_MAX+1][2];
static int16_t pve_decoded[8192][3];
unsigned bg_pve_animation_us;
#ifdef BG_PVE_MODEL_CANDIDATE
static rspq_block_t *pve_alpha_blocks[BG_FRAME_SLOTS][BG_PVE_MAX+1][2];
#endif
static void pve_release(void){
    rspq_wait();
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned i=0;i<=BG_PVE_MAX;i++)for(unsigned l=0;l<2;l++){
        if(pve_blocks[s][i][l])rspq_block_free(pve_blocks[s][i][l]);
#ifdef BG_PVE_MODEL_CANDIDATE
        if(pve_alpha_blocks[s][i][l])rspq_block_free(pve_alpha_blocks[s][i][l]);
#endif
        if(pve_vertices[s][i][l])free_uncached(pve_vertices[s][i][l]);
    }
    memset(pve_blocks,0,sizeof(pve_blocks));memset(pve_vertices,0,sizeof(pve_vertices));
    memset(pve_pose_keys,0,sizeof(pve_pose_keys));memset(pve_lods,0,sizeof(pve_lods));
#ifdef BG_PVE_MODEL_CANDIDATE
    memset(pve_alpha_blocks,0,sizeof(pve_alpha_blocks));
#endif
}
/* Samples live on the cartridge; one bounded transfer window is reused after
 * CPU interpolation. No DMA destination is shared with pending RSP work. */
static uint8_t pve_motion_window[2*8192*6+32] __attribute__((aligned(16)));
static const uint16_t*pve_motion_pair(const bg_pve_animation*c,unsigned f0,unsigned f1){
    static uint32_t rom,size;
    if(!rom){rom=dfs_rom_addr("pve-motion.bin");size=dfs_rom_size("pve-motion.bin");assertf(rom&&size,"PvE motion bank");}
    uint32_t offset=(uintptr_t)c->positions+f0*c->tracks*6,start=offset&~15u,end=((uintptr_t)c->positions+(f1+1)*c->tracks*6+15)&~15u;
    assertf(end<=size&&end-start<=sizeof(pve_motion_window),"PvE motion bounds");
    data_cache_hit_invalidate(pve_motion_window,end-start);dma_read(pve_motion_window,rom+start,end-start);
    return (const uint16_t*)(pve_motion_window+offset-start);
}
#ifdef BG_PVE_MODEL_CANDIDATE
#include "pve_model_candidate.inc"
#endif
static void pve_prepare(void){
    bg_pve_animation_us=0;
    memset(pve_lods,0,sizeof(pve_lods));memset(pve_ship_visible,0,sizeof(pve_ship_visible));
    if(!bg_pve_is_active())return;
    uint32_t begin=get_ticks_us();
    if(!pve_initialized){
        for(unsigned kind=0;kind<BG_PVE_MODELS;kind++)for(unsigned lod=0;lod<2;lod++)prepare_model(&bg_pve_models[kind][lod]);
        pve_initialized=true;
    }
    memset(pve_lods,0,sizeof(pve_lods));memset(pve_ship_visible,0,sizeof(pve_ship_visible));
    for(unsigned i=0;i<bg_pve_count;i++){
        bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];unsigned wanted=0;
        if(!a->occupied||(p->health<=0&&a->death_time>15))continue;
        if(a->arrival==1&&bg_ff_dropship.door<.05f)continue;
        bg_cull_bounds bounds;float center[3]={p->pos[0],p->pos[1]+.4f,p->pos[2]};prepare_effect_bounds(&bounds,center,2.f);
        for(unsigned v=0;v<views;v++){
            T3DViewport*vp=&viewports[slot][v];if(!visible_bounds(vp,&bounds,cull_selected[v]))continue;
            float dx=p->pos[0]-bg_players[v].pos[0],dy=p->pos[1]-bg_players[v].pos[1],dz=p->pos[2]-bg_players[v].pos[2];
            unsigned lod=dx*dx+dy*dy+dz*dz>(views==1?36:16)&&!bg_players[v].zoom;
#ifdef BG_PVE_MODEL_QA
            lod=bg_pve_model_qa_lod;
#endif
            pve_lods[v][i]=lod+1;wanted|=1u<<lod;
        }
        if(!wanted)continue;
        matrix(&pve_matrices[slot][i],BG_SCALE/BG_PVE_SCALE,p->yaw,0,p->pos);
        for(unsigned lod=0;lod<2;lod++)if(wanted&(1u<<lod)){
            const bg_model_asset*m=&bg_pve_models[a->kind][lod];
            if(pve_vertices[slot][i][lod]&&pve_buffer_kind[slot][i][lod]!=a->kind){
#ifdef BG_PVE_MODEL_CANDIDATE
                if(pve_alpha_blocks[slot][i][lod]){rspq_wait();rspq_block_free(pve_alpha_blocks[slot][i][lod]);pve_alpha_blocks[slot][i][lod]=NULL;}
#endif
                rspq_wait();rspq_block_free(pve_blocks[slot][i][lod]);free_uncached(pve_vertices[slot][i][lod]);pve_vertices[slot][i][lod]=NULL;pve_pose_keys[slot][i][lod]=0;
            }
            if(!pve_vertices[slot][i][lod]){
                pve_buffer_kind[slot][i][lod]=a->kind;
                pve_vertices[slot][i][lod]=malloc_uncached(m->vertex_count*16);assertf(pve_vertices[slot][i][lod],"PvE vertex buffers");
                memcpy(pve_vertices[slot][i][lod],m->vertices,m->vertex_count*16);
#ifdef BG_PVE_MODEL_CANDIDATE
                pve_blocks[slot][i][lod]=pve_record_surface(a->kind,lod,pve_vertices[slot][i][lod],false);
                pve_alpha_blocks[slot][i][lod]=pve_record_surface(a->kind,lod,pve_vertices[slot][i][lod],true);
#else
                pve_blocks[slot][i][lod]=record_model(m,pve_vertices[slot][i][lod]);
#endif
            }
            const bg_pve_animation*clip=&bg_pve_animations[a->kind][lod][a->clip];
            float phase=a->time/clip->duration;if(a->clip==PVE_DEATH||a->clip==PVE_MELEE||a->clip==PVE_THROW||a->clip==PVE_EXIT||a->clip==PVE_EVADE_LEFT||a->clip==PVE_EVADE_RIGHT)phase=fminf(phase,.99999f);else phase-=floorf(phase);
            float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;int mix=(frame-f0)*256;
            uint32_t key=1u+((uint32_t)a->clip<<24)+(f0<<16)+(f1<<8)+mix+((a->kind==BG_PVE_JACKAL&&p->shield<=0)?(1u<<30):0);
            if(pve_pose_keys[slot][i][lod]==key)continue;
            pve_pose_keys[slot][i][lod]=key;
            T3DVertPacked*out=CachedAddr(pve_vertices[slot][i][lod]);
            assertf(clip->tracks<=8192,"PvE track capacity");
            const uint16_t*samples=pve_motion_pair(clip,f0,f1);
            for(unsigned t=0;t<clip->tracks;t++)for(unsigned c=0;c<3;c++){
                int x=samples[t*3+c],y=samples[((f1-f0)*clip->tracks+t)*3+c];
                pve_decoded[t][c]=clip->origin[c]+x+((y-x)*mix>>8);
            }
            for(unsigned v=0;v<clip->vertices;v++){
                int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;
                memcpy(pos,pve_decoded[clip->indices[v]],6);
                if(a->kind==BG_PVE_JACKAL&&p->shield<=0&&bg_pve_shield_vertices[lod][v])memset(pos,0,6);
            }
            data_cache_hit_writeback(out,m->vertex_count*16);
#ifdef BG_PROFILE
            animated_tracks+=clip->tracks;animated_vertices+=clip->vertices;
#endif
        }
        const bg_attachment_clip*clip=&bg_pve_grips[a->kind][a->clip];float phase=a->time/clip->duration;
        if(a->clip==PVE_DEATH||a->clip==PVE_MELEE||a->clip==PVE_THROW||a->clip==PVE_EXIT||a->clip==PVE_EVADE_LEFT||a->clip==PVE_EVADE_RIGHT)phase=fminf(phase,.99999f);else phase-=floorf(phase);
        float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;
        float q[4],pos[3];blam_quaternions_interpolate_and_normalize(clip->poses[f0].quat,clip->poses[f1].quat,frame-f0,q);
        for(unsigned c=0;c<3;c++)pos[c]=(clip->poses[f0].pos[c]+(clip->poses[f1].pos[c]-clip->poses[f0].pos[c])*(frame-f0))*BG_SCALE;
        T3DMat4 hand,body,world;
        t3d_mat4_from_srt(&hand,(float[]){BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE},q,pos);
        t3d_mat4_from_srt_euler(&body,(float[]){1,1,1},(float[]){0,-p->yaw,0},(float[]){p->pos[0]*BG_SCALE,p->pos[1]*BG_SCALE,p->pos[2]*BG_SCALE});
        t3d_mat4_mul(&world,&body,&hand);t3d_mat4_to_fixed_3x4(&pve_guns[slot][i],&world);
    }
#ifdef BG_PVE_MODEL_CANDIDATE
    pve_prepare_ship_candidate();
#else
    if(bg_ff_dropship.phase){
        unsigned i=BG_PVE_MAX;const bg_model_asset*m=&bg_pve_models[BG_PVE_SPIRIT][0];
        bg_cull_bounds bounds;prepare_effect_bounds(&bounds,bg_ff_dropship.pos,9);
        bool visible=false;for(unsigned v=0;v<views;v++){pve_ship_visible[v]=visible_bounds(&viewports[slot][v],&bounds,cull_selected[v]);visible|=pve_ship_visible[v];}
        if(visible){
            matrix(&pve_matrices[slot][i],BG_SCALE/BG_PVE_SCALE,bg_ff_dropship.yaw,0,bg_ff_dropship.pos);
            if(!pve_vertices[slot][i][0]){pve_vertices[slot][i][0]=malloc_uncached(m->vertex_count*16);assertf(pve_vertices[slot][i][0],"Spirit vertices");memcpy(pve_vertices[slot][i][0],m->vertices,m->vertex_count*16);pve_blocks[slot][i][0]=record_model(m,pve_vertices[slot][i][0]);}
            const bg_pve_animation*c=&bg_pve_animations[BG_PVE_SPIRIT][0][PVE_EXIT];
            float frame=bg_ff_dropship.door*(c->frames-1);unsigned f0=frame,f1=f0+1<c->frames?f0+1:f0;int mix=(frame-f0)*256;
            const uint16_t*samples=pve_motion_pair(c,f0,f1);
            T3DVertPacked*out=CachedAddr(pve_vertices[slot][i][0]);
            for(unsigned v=0;v<c->vertices;v++){int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;unsigned track=c->indices[v];for(unsigned axis=0;axis<3;axis++){int a=samples[track*3+axis],b=samples[((f1-f0)*c->tracks+track)*3+axis];pos[axis]=c->origin[axis]+a+((b-a)*mix>>8);}}
            data_cache_hit_writeback(out,m->vertex_count*16);
        }
    }
#endif
    bg_pve_animation_us=get_ticks_us()-begin;
    data_cache_hit_writeback(pve_matrices[slot],sizeof(pve_matrices[slot]));data_cache_hit_writeback(pve_guns[slot],sizeof(pve_guns[slot]));
}
static void pve_draw(unsigned view){
    if(!bg_pve_is_active())return;
    if(pve_ship_visible[view]){
        unsigned lod=0;
#ifdef BG_PVE_MODEL_CANDIDATE
        lod=pve_ship_lod[view];
#endif
        const bg_model_asset*m=&bg_pve_models[BG_PVE_SPIRIT][lod];t3d_matrix_set(&pve_matrices[slot][BG_PVE_MAX],true);rspq_block_run(pve_blocks[slot][BG_PVE_MAX][lod]);triangles+=m->triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
    }
    for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]){
        unsigned lod=pve_lods[view][i]-1;const bg_model_asset*m=&bg_pve_models[bg_pve_actors[i].kind][lod];
        t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(pve_blocks[slot][i][lod]);triangles+=m->triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].kind!=BG_PVE_HUNTER)instance(weapon_model(bg_players[BG_PLAYERS+i].weapon),&pve_guns[slot][i]);
    }
}
