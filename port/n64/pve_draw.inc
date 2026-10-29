/* Source low/superlow geometry; animation is shared across all viewports. */
#include "asset_pve.h"
#include "pve_prepare_profile.h"
#ifdef BG_PVE_PREP_PROFILE
bg_pve_prepare_profile_data bg_pve_prepare_profile;
#endif
#ifdef BG_PVE_MODEL_QA
extern unsigned bg_pve_model_qa_lod;
#endif
static T3DVertPacked *pve_vertices[BG_FRAME_SLOTS][BG_PVE_MAX+1][BG_PVE_LODS];
static rspq_block_t *pve_blocks[BG_FRAME_SLOTS][BG_PVE_MAX+1][BG_PVE_LODS];
static T3DMat4FP pve_matrices[BG_FRAME_SLOTS][BG_PVE_MAX+1],pve_guns[BG_FRAME_SLOTS][BG_PVE_MAX+1];
static uint8_t pve_lods[4][BG_PVE_MAX+1];
static bool pve_initialized;
static uint8_t pve_buffer_kind[BG_FRAME_SLOTS][BG_PVE_MAX+1][BG_PVE_LODS];
static bool pve_ship_visible[4];
static uint32_t pve_pose_keys[BG_FRAME_SLOTS][BG_PVE_MAX+1][BG_PVE_LODS];
#ifdef BG_PVE_PREP_BASELINE
static int16_t pve_decoded[8192][3];
#else
#include "pve_prepare_math.h"
static bg_motion_track pve_decoded[8192];
#endif
#ifndef BG_PVE_PREP_BASELINE
#include "pve_motion_cache.h"
static bg_pve_motion_cache pve_motion_cache;
/* Aliases only borrow an earlier actor's prepared geometry in the SAME fenced
 * frame slot. Matrices/attachments remain per actor. No quantized-time changes. */
static uint8_t pve_pose_owner[BG_PVE_MAX+1][BG_PVE_LODS];
static uint32_t pve_frame_keys[BG_PVE_MAX][BG_PVE_LODS];
static unsigned pve_shared_pose(unsigned i,unsigned lod,uint32_t key){
    unsigned owner=i;
    for(unsigned j=0;j<i;j++)if(pve_frame_keys[j][lod]==key&&bg_pve_actors[j].kind==bg_pve_actors[i].kind){owner=pve_pose_owner[j][lod];break;}
    pve_frame_keys[i][lod]=key;return owner;
}
#endif
unsigned bg_pve_animation_us;
#ifdef BG_PVE_MODEL_CANDIDATE
static rspq_block_t *pve_alpha_blocks[BG_FRAME_SLOTS][BG_PVE_MAX+1][BG_PVE_LODS];
#endif
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
#include "pve_crunch_lod.h"
static bg_pve_crunch_state pve_crunch_states[4][BG_PVE_MAX];
#endif
static void pve_release(void){
    rspq_wait();
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned i=0;i<=BG_PVE_MAX;i++)for(unsigned l=0;l<BG_PVE_LODS;l++){
        if(pve_blocks[s][i][l])rspq_block_free(pve_blocks[s][i][l]);
#ifdef BG_PVE_MODEL_CANDIDATE
        if(pve_alpha_blocks[s][i][l])rspq_block_free(pve_alpha_blocks[s][i][l]);
#endif
        if(pve_vertices[s][i][l])free_uncached(pve_vertices[s][i][l]);
    }
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
    memset(pve_crunch_states,0,sizeof(pve_crunch_states));
#endif
    memset(pve_blocks,0,sizeof(pve_blocks));memset(pve_vertices,0,sizeof(pve_vertices));
    memset(pve_pose_keys,0,sizeof(pve_pose_keys));memset(pve_lods,0,sizeof(pve_lods));
#ifndef BG_PVE_PREP_BASELINE
    bg_pve_motion_cache_reset(&pve_motion_cache);memset(pve_frame_keys,0,sizeof(pve_frame_keys));
#endif
#ifdef BG_PVE_MODEL_CANDIDATE
    memset(pve_alpha_blocks,0,sizeof(pve_alpha_blocks));
#endif
}
/* Samples live on the cartridge; one bounded transfer window is reused after
 * CPU interpolation. No DMA destination is shared with pending RSP work. */
#ifdef BG_PVE_PREP_BASELINE
static uint8_t pve_motion_window[2*8192*6+32] __attribute__((aligned(16)));
#endif
static const uint16_t*pve_motion_pair(const bg_pve_animation*c,unsigned f0,unsigned f1){
    uint32_t begin=PVE_PREP_NOW();PVE_PREP_COUNT(pair_requests,1);
    static uint32_t rom,size;
    if(!rom){rom=dfs_rom_addr("pve-motion.bin");size=dfs_rom_size("pve-motion.bin");assertf(rom&&size,"PvE motion bank");}
    uint32_t offset=(uintptr_t)c->positions+f0*c->tracks*6,start=offset&~15u,end=((uintptr_t)c->positions+(f1+1)*c->tracks*6+15)&~15u;
    assertf(end<=size&&end-start<=2*8192*6+32,"PvE motion bounds");
#ifdef BG_PVE_PREP_BASELINE
    uint8_t*window=pve_motion_window;bool hit=false;
#else
    bool hit;uint8_t*window=bg_pve_motion_reserve(&pve_motion_cache,start,end-start,&hit);
#endif
    if(hit)PVE_PREP_COUNT(pair_hits,1);
    else{data_cache_hit_invalidate(window,end-start);dma_read(window,rom+start,end-start);PVE_PREP_COUNT(dma_bytes,end-start);}
    PVE_PREP_COUNT(motion_us,PVE_PREP_NOW()-begin);(void)begin;
    return (const uint16_t*)(window+offset-start);
}
#ifdef BG_PVE_MODEL_CANDIDATE
#include "pve_model_candidate.inc"
#endif
static void pve_prepare(void){
    bg_pve_animation_us=0;
#ifdef BG_PVE_PREP_PROFILE
    memset(&bg_pve_prepare_profile,0,sizeof(bg_pve_prepare_profile));
#endif
    memset(pve_lods,0,sizeof(pve_lods));memset(pve_ship_visible,0,sizeof(pve_ship_visible));
#ifndef BG_PVE_PREP_BASELINE
    memset(pve_frame_keys,0,sizeof(pve_frame_keys));
    for(unsigned i=0;i<=BG_PVE_MAX;i++)for(unsigned l=0;l<BG_PVE_LODS;l++)pve_pose_owner[i][l]=i;
#endif
    if(!bg_pve_is_active())return;
    uint32_t begin=get_ticks_us();
    if(!pve_initialized){
        for(unsigned kind=0;kind<BG_PVE_MODELS;kind++)for(unsigned lod=0;lod<BG_PVE_LODS;lod++)prepare_model(&bg_pve_models[kind][lod]);
        pve_initialized=true;
    }
    memset(pve_lods,0,sizeof(pve_lods));memset(pve_ship_visible,0,sizeof(pve_ship_visible));
    for(unsigned i=0;i<bg_pve_count;i++){
        uint32_t section=PVE_PREP_NOW();
        bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];unsigned wanted=0;
        if(!a->occupied||(p->health<=0&&a->death_time>15))continue;
        if(a->arrival==1&&bg_ff_dropship.door<.05f)continue;
        bg_cull_bounds bounds;float center[3]={p->pos[0],p->pos[1]+.4f,p->pos[2]};prepare_effect_bounds(&bounds,center,2.f);
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
        /* Whole-clip, all-tier bounds: animation cannot make LOD flicker.
         * Only used for representation choice; gameplay/hit meshes stay exact. */
        T3DMat4 body_lod;bg_bounds world_lod;bg_cull_bounds lod_bounds;
        t3d_mat4_from_srt_euler(&body_lod,(float[]){1,1,1},(float[]){0,-p->yaw,0},
            (float[]){p->pos[0]*BG_SCALE,p->pos[1]*BG_SCALE,p->pos[2]*BG_SCALE});
        bg_bounds_transform(&world_lod,&bg_pve_crunch_bounds[a->kind][a->clip],body_lod.m,BG_SCALE);
        bg_bounds_quantize(&lod_bounds,&world_lod);
#endif
        for(unsigned v=0;v<views;v++){
            T3DViewport*vp=&viewports[slot][v];if(!visible_bounds(vp,&bounds,cull_selected[v]))continue;
            float dx=p->pos[0]-bg_players[v].pos[0],dy=p->pos[1]-bg_players[v].pos[1],dz=p->pos[2]-bg_players[v].pos[2];
            unsigned lod=dx*dx+dy*dy+dz*dz>(views==1?36:16)&&!bg_players[v].zoom;
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
            float near,far;bg_camera_depth(bg_players[v].zoom!=0,&near,&far);
            if(bg_pve_crunch_select(&pve_crunch_states[v][i],a->generation,a->kind,&lod_bounds,
                vp->matCamera.m,vp->matProj.m,vp->size[0],vp->size[1],near,lod!=0,bg_players[v].zoom!=0))lod=2;
#endif
#ifdef BG_PVE_MODEL_QA
            lod=bg_pve_model_qa_lod;
#endif
            pve_lods[v][i]=lod+1;wanted|=1u<<lod;
        }
        PVE_PREP_COUNT(visibility_us,PVE_PREP_NOW()-section);section=PVE_PREP_NOW();
        if(!wanted)continue;
        matrix(&pve_matrices[slot][i],BG_SCALE/BG_PVE_SCALE,p->yaw,0,p->pos);
        PVE_PREP_COUNT(matrices_us,PVE_PREP_NOW()-section);
        for(unsigned lod=0;lod<BG_PVE_LODS;lod++)if(wanted&(1u<<lod)){
            section=PVE_PREP_NOW();PVE_PREP_COUNT(pose_requests,1);
            const bg_model_asset*m=&bg_pve_models[a->kind][lod];
            const bg_pve_animation*clip=&bg_pve_animations[a->kind][lod][a->clip];
            float phase=a->time/clip->duration;if(a->clip==PVE_DEATH||a->clip==PVE_MELEE||a->clip==PVE_THROW||a->clip==PVE_EXIT||a->clip==PVE_EVADE_LEFT||a->clip==PVE_EVADE_RIGHT)phase=fminf(phase,.99999f);else phase-=floorf(phase);
            float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;int mix=(frame-f0)*256;
            uint32_t key=1u+((uint32_t)a->clip<<24)+(f0<<16)+(f1<<8)+mix+((a->kind==BG_PVE_JACKAL&&p->shield<=0)?(1u<<30):0);
#ifndef BG_PVE_PREP_BASELINE
            pve_pose_owner[i][lod]=pve_shared_pose(i,lod,key);
            if(pve_pose_owner[i][lod]!=i){PVE_PREP_COUNT(shared_poses,1);PVE_PREP_COUNT(buffers_us,PVE_PREP_NOW()-section);continue;}
#endif
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
            PVE_PREP_COUNT(buffers_us,PVE_PREP_NOW()-section);
            if(pve_pose_keys[slot][i][lod]==key){PVE_PREP_COUNT(pose_hits,1);continue;}
            pve_pose_keys[slot][i][lod]=key;
            T3DVertPacked*out=CachedAddr(pve_vertices[slot][i][lod]);
            assertf(clip->tracks<=8192,"PvE track capacity");
            const uint16_t*samples=pve_motion_pair(clip,f0,f1);
            section=PVE_PREP_NOW();
#ifdef BG_PVE_PREP_BASELINE
            for(unsigned t=0;t<clip->tracks;t++)for(unsigned c=0;c<3;c++){
                int x=samples[t*3+c],y=samples[((f1-f0)*clip->tracks+t)*3+c];
                pve_decoded[t][c]=clip->origin[c]+x+((y-x)*mix>>8);
            }
#else
            bg_pve_motion_decode(pve_decoded,clip->tracks,samples,samples+(f1-f0)*clip->tracks*3,clip->origin,mix);
#endif
            PVE_PREP_COUNT(decode_us,PVE_PREP_NOW()-section);section=PVE_PREP_NOW();
#ifdef BG_PVE_PREP_BASELINE
            for(unsigned v=0;v<clip->vertices;v++){
                int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;
                memcpy(pos,pve_decoded[clip->indices[v]],6);
                if(a->kind==BG_PVE_JACKAL&&p->shield<=0&&bg_pve_shield_vertices[lod][v])memset(pos,0,6);
            }
#else
            bg_motion_scatter(out,clip->vertices,clip->indices,pve_decoded);
            if(a->kind==BG_PVE_JACKAL&&p->shield<=0)for(unsigned v=0;v<clip->vertices;v++)
                if(bg_pve_shield_vertices[lod][v]){int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;memset(pos,0,6);}
#endif
            PVE_PREP_COUNT(scatter_us,PVE_PREP_NOW()-section);section=PVE_PREP_NOW();
            data_cache_hit_writeback(out,m->vertex_count*16);
            PVE_PREP_COUNT(writeback_us,PVE_PREP_NOW()-section);
#ifdef BG_PROFILE
            animated_tracks+=clip->tracks;animated_vertices+=clip->vertices;
#endif
        }
        section=PVE_PREP_NOW();
        const bg_attachment_clip*clip=&bg_pve_grips[a->kind][a->clip];float phase=a->time/clip->duration;
        if(a->clip==PVE_DEATH||a->clip==PVE_MELEE||a->clip==PVE_THROW||a->clip==PVE_EXIT||a->clip==PVE_EVADE_LEFT||a->clip==PVE_EVADE_RIGHT)phase=fminf(phase,.99999f);else phase-=floorf(phase);
        float frame=phase*(clip->frames-1);unsigned f0=frame,f1=f0+1<clip->frames?f0+1:f0;
        float q[4],pos[3];blam_quaternions_interpolate_and_normalize(clip->poses[f0].quat,clip->poses[f1].quat,frame-f0,q);
        for(unsigned c=0;c<3;c++)pos[c]=(clip->poses[f0].pos[c]+(clip->poses[f1].pos[c]-clip->poses[f0].pos[c])*(frame-f0))*BG_SCALE;
        T3DMat4 hand,body,world;
        t3d_mat4_from_srt(&hand,(float[]){BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE},q,pos);
        t3d_mat4_from_srt_euler(&body,(float[]){1,1,1},(float[]){0,-p->yaw,0},(float[]){p->pos[0]*BG_SCALE,p->pos[1]*BG_SCALE,p->pos[2]*BG_SCALE});
        t3d_mat4_mul(&world,&body,&hand);t3d_mat4_to_fixed_3x4(&pve_guns[slot][i],&world);
        PVE_PREP_COUNT(grip_us,PVE_PREP_NOW()-section);(void)section;
    }
    uint32_t ship_begin=PVE_PREP_NOW();
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
#ifdef BG_PVE_PREP_BASELINE
            for(unsigned v=0;v<c->vertices;v++){int16_t*pos=v&1?out[v/2].posB:out[v/2].posA;unsigned track=c->indices[v];for(unsigned axis=0;axis<3;axis++){int a=samples[track*3+axis],b=samples[((f1-f0)*c->tracks+track)*3+axis];pos[axis]=c->origin[axis]+a+((b-a)*mix>>8);}}
#else
            bg_pve_motion_decode(pve_decoded,c->tracks,samples,samples+(f1-f0)*c->tracks*3,c->origin,mix);
            bg_motion_scatter(out,c->vertices,c->indices,pve_decoded);
#endif
            data_cache_hit_writeback(out,m->vertex_count*16);
        }
    }
#endif
    PVE_PREP_COUNT(ship_us,PVE_PREP_NOW()-ship_begin);(void)ship_begin;
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
        unsigned owner=i;
#ifndef BG_PVE_PREP_BASELINE
        owner=pve_pose_owner[i][lod];
#endif
        t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(pve_blocks[slot][owner][lod]);triangles+=m->triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);
#endif
        if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].kind!=BG_PVE_HUNTER){
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
            small_model_instance(weapon_model(bg_players[BG_PLAYERS+i].weapon),&pve_guns[slot][i],
                &viewports[slot][view],&view_eyes[view],bg_players[view].zoom,NULL);
#else
            instance(weapon_model(bg_players[BG_PLAYERS+i].weapon),&pve_guns[slot][i]);
#endif
        }
    }
}
