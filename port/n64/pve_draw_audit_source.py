"""Generate isolated frozen omission diagnostics; leave playable renderer intact."""
def replace(text, old, new, count=1):
    assert text.count(old)==count, (old, text.count(old))
    return text.replace(old,new)

HELPERS=r'''
extern unsigned bg_draw_audit_frame;
static unsigned audit_vertices,audit_triangles;
#ifdef BG_GPU_DIAGNOSTIC
static uint32_t audit_clock;
#endif
static bool audit_skip(unsigned actor){return bg_draw_audit_frame==actor+2;}
static void audit_category(unsigned view,const char*name){
#ifdef BG_GPU_DIAGNOSTIC
    if(bg_draw_audit_frame==1){
        uint32_t before=get_ticks_us();rspq_wait();uint32_t after=get_ticks_us();
        debugf("DRAW_TIMING view=%u category=%s submit_us=%u remaining_rsp_us=%u span_us=%u\n",view,name,(unsigned)(before-audit_clock),(unsigned)(after-before),(unsigned)(after-audit_clock));audit_clock=get_ticks_us();
    }
#endif
    if(!bg_draw_audit_frame)debugf("DRAW_CATEGORY view=%u category=%s vertices=%u triangles=%u\n",view,name,submitted_vertices-audit_vertices,triangles-audit_triangles);
    audit_vertices=submitted_vertices;audit_triangles=triangles;
}
static void audit_mesh_bounds(bg_bounds*out,const T3DVertPacked*verts,unsigned count,const T3DMat4FP*matrix){
    for(unsigned a=0;a<3;a++){out->min[a]=1e20f;out->max[a]=-1e20f;}
    float mat[4][3];for(unsigned c=0;c<4;c++)for(unsigned a=0;a<3;a++)mat[c][a]=t3d_mat4fp_get_float(matrix,c,a);
    for(unsigned v=0;v<count;v++){
        const int16_t*pos=v&1?verts[v/2].posB:verts[v/2].posA;
        for(unsigned a=0;a<3;a++){
            float x=mat[3][a];for(unsigned c=0;c<3;c++)x+=mat[c][a]*pos[c];
            out->min[a]=fminf(out->min[a],x);out->max[a]=fmaxf(out->max[a],x);
        }
    }
}
static void audit_actor(unsigned view,unsigned actor,unsigned lod,unsigned owner){
    if(bg_draw_audit_frame)return;
    const bg_pve_actor*a=&bg_pve_actors[actor];const bg_player*p=&bg_players[BG_PLAYERS+actor];
    const bg_model_asset*m=&bg_pve_models[a->kind][lod];T3DViewport*vp=&viewports[slot][view];
    bg_bounds box;bg_cull_bounds quantized;
    audit_mesh_bounds(&box,CachedAddr(pve_vertices[slot][owner][lod]),m->vertex_count,&pve_matrices[slot][actor]);
    bg_bounds_quantize(&quantized,&box);bool body_in=visible_bounds(vp,&quantized,cull_selected[view]);
    unsigned gun=0,far_loads=0;bool gun_in=false,gun_far=false;
    if(p->health>0&&a->kind!=BG_PVE_HUNTER){
        unsigned w=weapon_model(p->weapon);gun=model_vertex_loads[w];far_loads=pickup_vertex_loads[w];
        audit_mesh_bounds(&box,bg_model_assets[w].vertices,bg_model_assets[w].vertex_count,&pve_guns[slot][actor]);
        bg_bounds_quantize(&quantized,&box);gun_in=visible_bounds(vp,&quantized,cull_selected[view]);
        float pos[3],distance2=0;for(unsigned c=0;c<3;c++){pos[c]=t3d_mat4fp_get_float(&pve_guns[slot][actor],3,c);float d=(pos[c]-view_eyes[view].v[c])/BG_SCALE;distance2+=d*d;}
        float depth=-(pos[0]*vp->matCamera.m[0][2]+pos[1]*vp->matCamera.m[1][2]+pos[2]*vp->matCamera.m[2][2]+vp->matCamera.m[3][2])/BG_SCALE;
        gun_far=!bg_players[view].zoom&&bg_lod_diameter_below(bg_model_assets[w].radius,vp->size[1]*fabsf(vp->matProj.m[1][1]),depth,distance2,12.f);
#if defined(BG_PVE_CRUNCH) && !defined(BG_PVE_CRUNCH_BASELINE)
        if(gun_far)gun=far_loads;
#endif
    }
    debugf("DRAW_ACTOR view=%u actor=%u kind=%u lod=%u body=%u gun=%u batches=%u body_in=%u gun_in=%u gun_far=%u far_gun=%u hp=%.3f clip=%u phase=%.6f pos=%.6f,%.6f,%.6f yaw=%.6f\n",view,actor,a->kind,lod,model_load_count(m,m->vertex_count,0,m->batch_count),gun,m->batch_count,body_in,gun_in,gun_far,far_loads,p->health,a->clip,a->time,p->pos[0],p->pos[1],p->pos[2],p->yaw);
}
'''

def generate(directory):
    main=(directory/'main.c').read_text()
    main='unsigned bg_draw_audit_frame;\n'+main
    # Disable timing-dependent overlay while retaining counters. Normal HUD remains.
    main=replace(main,'#ifndef BG_BENCHMARK\n        sys_get_heap_stats(&heap);','#if 0\n        sys_get_heap_stats(&heap);')
    main=replace(main,'        if(photo_exported<\n','        if(photo_exported<\n#if 1\n            17\n#elif 0\n')
    # Close added branch before existing model-QA branch, avoiding nested ifs.
    main=replace(main,'#elif 0\n#ifdef BG_PVE_MODEL_QA','#elif defined(BG_PVE_MODEL_QA)')
    main=replace(main,'            photo_exported++;','            photo_exported++;')
    main=replace(main,'            debugf("FF_PHOTO_END\\n");','            debugf("FF_PHOTO_END\\n");\n            bg_draw_audit_frame=photo_exported;')
    main=replace(main,'        bg_scene_prepare(slot, views, game_time);','        if(!bg_draw_audit_frame)debugf("DRAW_STATE tick=%u time=%.6f alive=%u\\n",(unsigned)bg_ff.tick,game_time,(bg_players[0].health>0)+(bg_players[1].health>0)+(bg_players[2].health>0)+(bg_players[3].health>0));\n        bg_scene_prepare(slot, views, game_time);')
    scene=(directory/'scene.c').read_text()
    # Helpers follow pve include because they inspect its prepared buffers.
    scene=replace(scene,'#include "pve_draw.inc"','extern unsigned bg_draw_audit_frame;\nstatic bool audit_skip(unsigned actor);\nstatic void audit_actor(unsigned view,unsigned actor,unsigned lod,unsigned owner);\n#include "pve_draw.inc"\n'+HELPERS)
    scene=replace(scene,'static void draw_view(unsigned p) {','static void draw_view(unsigned p) {\n    audit_vertices=submitted_vertices;audit_triangles=triangles;\n#ifdef BG_GPU_DIAGNOSTIC\n    if(bg_draw_audit_frame==1){rspq_wait();audit_clock=get_ticks_us();}\n#endif')
    scene=replace(scene,'    bg_player *player = &bg_players[p];\n#ifdef BG_PROFILE\n    uint64_t begin', '    bg_player *player = &bg_players[p];\n    if(!bg_draw_audit_frame)debugf("DRAW_CAMERA view=%u x=%d y=%d width=%d height=%d eye=%.6f,%.6f,%.6f yaw=%.6f pitch=%.6f hp=%.3f\\n",p,(int)vp->offset[0],(int)vp->offset[1],(int)vp->size[0],(int)vp->size[1],eye.v[0]/BG_SCALE,eye.v[1]/BG_SCALE,eye.v[2]/BG_SCALE,player->yaw,player->pitch,player->health);\n#ifdef BG_PROFILE\n    uint64_t begin')
    for n,name in enumerate(('world','vehicles','players','pickups','effects','firstperson')):
        needle=f'    category_triangles[{n}] += triangles - before;'
        scene=replace(scene,needle,f'    audit_category(p,"{name}");\n'+needle)
    scene=replace(scene,'    pve_draw(p);','    pve_draw(p);\n    audit_category(p,"covenant");')
    draw=(directory/'pve_draw.inc').read_text()
    draw=replace(draw,'if(pve_ship_visible[view]){','if(pve_ship_visible[view]&&!audit_skip(BG_PVE_MAX)){')
    draw=replace(draw,'for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]){','for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]&&!audit_skip(i)){')
    draw=replace(draw,'        t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(pve_blocks[slot][owner][lod]);','        audit_actor(view,i,lod,owner);\n        t3d_matrix_set(&pve_matrices[slot][i],true);rspq_block_run(pve_blocks[slot][owner][lod]);')
    draw=replace(draw,'if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].kind!=BG_PVE_HUNTER){','if(bg_draw_audit_frame!=15&&bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].kind!=BG_PVE_HUNTER){')
    draw=replace(draw,'        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);\n#endif\n    }','        submitted_vertices+=model_load_count(m,m->vertex_count,0,m->batch_count);\n        if(!bg_draw_audit_frame)debugf("DRAW_SHIP view=%u lod=%u body=%u triangles=%u\\n",view,lod,model_load_count(m,m->vertex_count,0,m->batch_count),m->triangle_count);\n#endif\n    }')
    alpha=(directory/'pve_model_candidate.inc').read_text()
    alpha=replace(alpha,'if(pve_ship_visible[view]){','if(pve_ship_visible[view]&&!audit_skip(BG_PVE_MAX)){')
    alpha=replace(alpha,'for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]){','for(unsigned i=0;i<bg_pve_count;i++)if(pve_lods[view][i]&&!audit_skip(i)){')
    return {'main.c':main,'scene.c':scene,'pve_draw.inc':draw,'pve_model_candidate.inc':alpha}
