/* One immutable source mesh for every Jackal and every body LOD. */
#include "jackal_shield.h"
#include "jackal_shield_flash.h"
static rspq_block_t *jackal_shield_block;
static T3DMat4FP jackal_shield_matrices[BG_FRAME_SLOTS][BG_PVE_MAX];
static bool jackal_shield_ready[BG_PVE_MAX];
static bg_jackal_flash jackal_shield_flashes[BG_PVE_MAX];
static float jackal_shield_flash_values[BG_PVE_MAX];
static void jackal_shield_reset(void){memset(jackal_shield_flashes,0,sizeof(jackal_shield_flashes));memset(jackal_shield_flash_values,0,sizeof(jackal_shield_flash_values));}
static void jackal_shield_track(unsigned i){
    const bg_pve_actor*a=&bg_pve_actors[i];const bg_player*p=&bg_players[BG_PLAYERS+i];
    if(!a->occupied||a->kind!=BG_PVE_JACKAL||p->health<=0){memset(&jackal_shield_flashes[i],0,sizeof(jackal_shield_flashes[i]));jackal_shield_flash_values[i]=0;return;}
    jackal_shield_flash_values[i]=bg_jackal_flash_step(&jackal_shield_flashes[i],a->generation,p->shield,p->hurt,bg_pve_tick_number);
}
static void jackal_shield_prepare(unsigned i,unsigned render_clip){
    bg_pve_actor*a=&bg_pve_actors[i];bg_player*p=&bg_players[BG_PLAYERS+i];
    if(a->kind!=BG_PVE_JACKAL||p->health<=0||p->shield<=0)return;
    if(!jackal_shield_block){
        prepare_model(&bg_jackal_shield_model);
        jackal_shield_block=record_model(&bg_jackal_shield_model,bg_jackal_shield_model.vertices);
        data_cache_hit_writeback((void*)bg_jackal_shield_texture,sizeof(bg_jackal_shield_texture));
    }
    const bg_attachment_clip*c=&bg_jackal_shield_grips[render_clip];
    float phase=a->time/c->duration;
    if(a->clip==PVE_DEATH||a->clip==PVE_MELEE||a->clip==PVE_THROW||a->clip==PVE_EXIT||a->clip==PVE_EVADE_LEFT||a->clip==PVE_EVADE_RIGHT)phase=fminf(phase,.99999f);else phase-=floorf(phase);
    float frame=phase*(c->frames-1);unsigned f0=frame,f1=f0+1<c->frames?f0+1:f0;
    float q[4],pos[3];blam_quaternions_interpolate_and_normalize(c->poses[f0].quat,c->poses[f1].quat,frame-f0,q);
    for(unsigned k=0;k<3;k++)pos[k]=(c->poses[f0].pos[k]+(c->poses[f1].pos[k]-c->poses[f0].pos[k])*(frame-f0))*BG_SCALE;
    T3DMat4 bone,body,world;
    t3d_mat4_from_srt(&bone,(float[]){BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE,BG_SCALE/BG_OBJECT_SCALE},q,pos);
    t3d_mat4_from_srt_euler(&body,(float[]){1,1,1},(float[]){0,-p->yaw,0},(float[]){p->pos[0]*BG_SCALE,p->pos[1]*BG_SCALE,p->pos[2]*BG_SCALE});
    t3d_mat4_mul(&world,&body,&bone);t3d_mat4_to_fixed_3x4(&jackal_shield_matrices[slot][i],&world);
    jackal_shield_ready[i]=true;
}
static void jackal_shield_draw(unsigned view){
    unsigned order[BG_PVE_MAX],count=0;float depth[BG_PVE_MAX];
    for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]&&jackal_shield_ready[i]){
        const bg_player*p=&bg_players[BG_PLAYERS+i];float distance=0;
        for(unsigned k=0;k<3;k++){float d=p->pos[k]-bg_players[view].pos[k];distance+=d*d;}
        unsigned at=count++;while(at&&depth[at-1]<distance){order[at]=order[at-1];depth[at]=depth[at-1];at--;}
        order[at]=i;depth[at]=distance;
    }
    if(!count)return;
    surface_t image=surface_make_linear((void*)bg_jackal_shield_texture,FMT_RGBA32,32,32);
    rdpq_sync_pipe();rdpq_mode_tlut(TLUT_NONE);rdpq_mode_persp(true);rdpq_mode_filter(FILTER_BILINEAR);rdpq_mode_alphacompare(0);
    rdpq_mode_combiner(RDPQ_COMBINER1((TEX0,0,ENV,0),(TEX0,0,ENV,0)));
    rdpq_sync_tile();rdpq_sync_load();rdpq_tex_upload(TILE0,&image,NULL);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_TEXTURED); /* source two-sided */
    for(unsigned n=0;n<count;n++){
        unsigned i=order[n];const bg_pve_actor*a=&bg_pve_actors[i];const bg_player*p=&bg_players[BG_PLAYERS+i];
        const bg_pve_definition*d=a->variant?&bg_pve_variants[a->variant].def:&bg_pve_definitions[BG_PVE_JACKAL];
        float maximum=d->shield*bg_pve_difficulties[bg_ff.active?bg_ff.difficulty:1].shield;
        float strength=fminf(1,p->shield/fmaxf(1,maximum)),flash=jackal_shield_flash_values[i];
        const float*color=bg_jackal_shield_colors[a->variant==PVE_R_JACKAL_MAJOR];
        /* Source C colors distinguish Minor/Major; damage briefly adds white.
         * One-pass alpha approximates CE's seven-stage additive/noise shader. */
        rdpq_sync_pipe();rdpq_set_env_color(RGBA32((unsigned)(255*(color[0]+(1-color[0])*flash)),(unsigned)(255*(color[1]+(1-color[1])*flash)),(unsigned)(255*(color[2]+(1-color[2])*flash)),(unsigned)(128+127*strength)));
        t3d_matrix_set(&jackal_shield_matrices[slot][i],true);rspq_block_run(jackal_shield_block);triangles+=76;
#ifdef BG_PROFILE
        submitted_vertices+=model_load_count(&bg_jackal_shield_model,bg_jackal_shield_model.vertex_count,0,bg_jackal_shield_model.batch_count);
#endif
    }
    rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);rdpq_mode_filter(FILTER_POINT);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
}
