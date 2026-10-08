#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "game.h"
#include "movement.h"
#include "view_camera.h"
#include "sky_draw.h"
#include "shields.h"
#include "blam/vehicle_physics.h"
#include "controls.h"
#include "menu.h"
#include "menu_draw.h"
#include "frontend.h"
#include "frontend_draw.h"
#ifdef BG_FRONTEND_QA
#include "frontend_qa.h"
#endif
#if !defined(BG_MOVEMENT_QA) && !defined(BG_DESTRUCTION_QA) && !defined(BG_EFFECTS_QA) && !defined(BG_DEMO) && !defined(BG_SHOWCASE) && !defined(BG_SNAPSHOT_TICK) && !defined(BG_MENU_QA)
#define BG_FRONTEND
#endif
#ifdef BG_MENU_QA
#include "menu_qa.h"
#endif
#include "asset_models.h"
#include "asset_firstperson.h"
#include "asset_interaction.h"
#include "firstperson_ammo.h"
#include "weapon_effects.h"
#include "weapon_effects_draw.h"
#include "vehicle_visuals.h"
#include "render_animation.h"
#include "render_lod.h"
#include "asset_micro.h"
#include "render_micro_lod.h"
#include "render_pose_cache.h"
#include "render_visibility.h"
#include "rspq_metrics.h"
#include "blam/runtime.h"
#include "sound.h"
#include "hud.h"
#include "replay.h"
#ifdef BG_EFFECTS_QA
#include "effects_qa.h"
#endif
#ifdef BG_DESTRUCTION_QA
#include "destruction_qa.h"
#endif
#ifndef BG_PACED30_BUFFERS
#define BG_PACED30_BUFFERS 3
#endif
#if defined(BG_PACED30) && defined(BG_SNAPSHOT_TICK)
#undef BG_PACED30 /* Frozen pixel fixtures always use the ordinary presenter. */
#undef BG_PACED30_BUFFERS
#define BG_PACED30_BUFFERS 3
#endif
#if !defined(BG_PACED30) && BG_PACED30_BUFFERS != 3
#error "Extra display surfaces require the explicit paced30 experiment"
#endif
#if defined(BG_PACED30) && BG_PACED30_BUFFERS >= 4
#define BG_PRESENT_TRACK
#endif
#ifdef BG_PACED30
#include "render_pacing.h"
#endif
#ifdef BG_SNAPSHOT_TICK
#include "replay_snapshot.h"
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK) || defined(BG_SHOWCASE) || defined(BG_PROFILE) || (defined(RDPQ_VALIDATE) && !defined(BG_MODEL_QA) && !defined(BG_INTERACTION_QA) && !defined(BG_SHIELD_QA))
#error "Snapshot QA requires an overlay-free build without benchmark/showcase/profile/validation"
#endif
#endif
#if defined(BG_VI_BENCHMARK) && (defined(BG_BENCHMARK) || defined(BG_PROFILE) || defined(BG_GPU_DIAGNOSTIC) || defined(RDPQ_VALIDATE) || defined(BG_SHOWCASE))
#error "Quiet VI measurement cannot include full profiling or a different scene"
#endif
#if defined(BG_BENCHMARK) || defined(BG_VI_BENCHMARK)
#define BG_VI_MEASURE
#endif
#ifdef BG_BENCHMARK
#include "benchmark.h"
#include "cadence.h"
#include "cadence_tail.h"
#include "vi_meter.h"
#ifndef BG_PROFILE
#define BG_PROFILE
#endif
#endif
#ifdef BG_VI_BENCHMARK
#include "vi_meter.h"
#endif
#if defined(BG_GPU_DIAGNOSTIC) && !defined(BG_PROFILE)
#define BG_PROFILE
#endif
#ifdef BG_SHOWCASE
#include "showcase.h"
#endif

/* Two fenced geometry slots retain detailed models within base 4 MiB RAM.
 * Display surfaces are separate; geometry reuse always waits on RSP. */
#define BG_FRAME_SLOTS 2
extern T3DVertPacked bg_vertices[];
extern uint16_t bg_textures[][32*32];
static const color_t colors[4]={{225,45,38,255},{39,92,215,255},{215,179,44,255},{57,183,69,255}};
static surface_t textures[32];
static T3DVertPacked *armor[BG_FRAME_SLOTS][4], particles[7][12] __attribute__((aligned(16)));
static T3DVertPacked *firstperson[BG_FRAME_SLOTS][4];
static int firstperson_weapon[BG_FRAME_SLOTS][4];
static T3DVertPacked *armor_lod[BG_FRAME_SLOTS][4];
static rspq_block_t *armor_lod_blocks[BG_FRAME_SLOTS][4];
/* A segmented vertex address shares each weapon's commands across all
 * fenced player/slot buffers. Segment 1 is reserved for these draw calls. */
static rspq_block_t *firstperson_blocks[BG_FP_WEAPONS];
static float fired_at[4]={-100,-100,-100,-100};
static rspq_block_t *world_blocks[512], *player_blocks[BG_FRAME_SLOTS][4], *models[BG_M_COUNT], *particle_blocks[7];
static rspq_block_t *vehicle_lods[4];
static rspq_block_t *covenant_wreck_blocks[2];
static rspq_block_t *pickup_lod_blocks[BG_M_COUNT];
static rspq_block_t *vehicle_micro_blocks[4],*pickup_micro_blocks[BG_M_COUNT];
static bg_micro_sphere vehicle_micro_spheres[BG_MAX_VEHICLES],pickup_micro_spheres[BG_MAX_PICKUPS];
static bool vehicle_micro_available[4],pickup_micro_available[BG_M_COUNT];
static rspq_block_t *vehicle_parts[4][7];
static T3DMat4FP part_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES][7];
static bg_cull_bounds vehicle_part_bounds[BG_MAX_VEHICLES][7];
static float wheel_rotation[BG_MAX_VEHICLES];
static bg_vehicle_pose_cache vehicle_pose_cache[BG_MAX_VEHICLES];
static T3DViewport viewports[BG_FRAME_SLOTS][4] __attribute__((aligned(16)));
static T3DViewport gun_viewports[BG_FRAME_SLOTS][4] __attribute__((aligned(16)));
static T3DVertPacked scope_vertices[BG_FRAME_SLOTS][4][6] __attribute__((aligned(16)));
static T3DMat4FP scope_matrices[BG_FRAME_SLOTS][4];
static T3DMat4FP terrain_matrix;
static T3DMat4FP transforms[BG_FRAME_SLOTS][4], guns[BG_FRAME_SLOTS][4], vehicle_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES],
    pickup_matrices[BG_FRAME_SLOTS][BG_MAX_PICKUPS], projectile_matrices[BG_FRAME_SLOTS][BG_MAX_PROJECTILES], explosion_matrices[BG_FRAME_SLOTS][12];
static T3DMat4FP held_matrices[BG_FRAME_SLOTS][4];
static rspq_syncpoint_t fences[BG_FRAME_SLOTS];
static bool pending[BG_FRAME_SLOTS];
static unsigned slot,views=4,triangles,fps;
static bg_menu menu;
#ifdef BG_FRONTEND
static bg_frontend front;
static uint64_t match_ended;
static void firstperson_buffers_release(void);
static void body_buffers_load(void);
static void body_buffers_release(void);
static bool front_active(void){return front.page!=BG_FRONT_PLAY;}
#else
static inline bool front_active(void){return false;}
#endif
#ifndef BG_SNAPSHOT_TICK
static bool paused;
static bool scores[BG_PLAYERS];
#endif
static float game_time;
static int16_t triangle_lists[20][64] __attribute__((aligned(16)));
static bg_motion_track *motion_tracks;
static unsigned motion_capacity;
static T3DVec3 view_eyes[4];
/* 0: absent, 1: full mesh, 2: distant mesh. Visibility is evaluated once. */
static uint8_t body_lods[4][4],wanted_lods[4],held_masks[4],wanted_held;
static uint8_t vehicle_view_lods[4][BG_MAX_VEHICLES];
static uint8_t pickup_visible[4][BG_MAX_PICKUPS];
static bg_cull_bounds body_bounds[4],held_bounds[4],vehicle_bounds[BG_MAX_VEHICLES],pickup_bounds[BG_MAX_PICKUPS];
/* CPU-only effect boxes are immutable from preparation through all views. */
static bg_cull_bounds projectile_bounds[BG_MAX_PROJECTILES],explosion_bounds[12];
static T3DMat4 body_matrices[4];
static unsigned body_clips[4];
static int locomotion_clip(const bg_player*p);
static bool body_throwing[4];
/* CPU readiness resets after the geometry-slot fence, before any draw. */
static unsigned body_animation_ready,fp_animation_ready;
static void prepare_view(unsigned p);
#ifdef BG_PROFILE
static unsigned sim_us,prep_us,draw_us,wait_us;
static unsigned queue_us;
#ifdef BG_RSPQ_OVERRIDE
static bg_rspq_metrics previous_queue_metrics;
#endif
static unsigned camera_us,animation_us,matrix_us,world_us,object_us,fp_us,hud_us,audio_us,overlay_us,present_us;
static unsigned geometry_rsp_us,geometry_rdp_us;
static unsigned category_triangles[6]; /* Terrain, vehicles, bodies, pickups, effects, first person. */
static unsigned submitted_vertices,model_vertex_loads[BG_M_COUNT],pickup_vertex_loads[BG_M_COUNT];
static unsigned vehicle_vertex_loads[4],part_vertex_loads[4][7],spartan_lod_vertex_loads,fp_vertex_loads[BG_FP_WEAPONS];
static unsigned vehicle_micro_vertex_loads[4],pickup_micro_vertex_loads[BG_M_COUNT];
static unsigned animated_vertices,animated_tracks;
#ifndef BG_BENCHMARK
static uint32_t frame_times[120],frame_time_count,frame_time_next;
static unsigned frame_average,frame_minimum,frame_p95,frame_maximum;
static void profile_frame_time(uint32_t elapsed){
    frame_times[frame_time_next++%120]=elapsed;
    if(frame_time_count<120)frame_time_count++;
}
static void profile_frame_summary(void){
    uint32_t sorted[120];uint64_t sum=0;
    for(unsigned i=0;i<frame_time_count;i++){
        uint32_t value=frame_times[i];sum+=value;unsigned j=i;
        while(j&&sorted[j-1]>value){sorted[j]=sorted[j-1];j--;}
        sorted[j]=value;
    }
    if(frame_time_count){
        frame_average=sum/frame_time_count;frame_minimum=sorted[0];
        frame_p95=sorted[(frame_time_count*95+99)/100-1];frame_maximum=sorted[frame_time_count-1];
    }
}
#endif
#endif
#ifdef BG_BENCHMARK
static bg_benchmark benchmark;
static bg_cadence completed_cadence;
static bg_cadence_tail completed_tail;
#endif
#ifdef BG_VI_MEASURE
static bg_vi_meter visible_meter;
static unsigned result_heap_free,result_held_peak;
#ifdef BG_PRESENT_TRACK
static unsigned result_ready_peak,result_outstanding_peak;
#endif
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
typedef struct {
    surface_t*screen;unsigned vehicle;uint32_t pose_tick;
    uint64_t sampled_us,completed_us;
#ifdef BG_BENCHMARK
    bg_cadence_frame sample;
#endif
} bg_completion_frame;
/* Metadata follows DISPLAY buffers, not the two geometry slots. A
 * display buffer cannot be acquired again before completion AND presentation. */
static bg_completion_frame completion_frames[BG_PACED30_BUFFERS];
static uint32_t video_retraces,simulation_pose;
static uint64_t frame_sample_us;
#ifdef BG_PACED30
static bg_present30 presenter;
static unsigned paced_dropped_ticks;
#ifdef BG_PRESENT_TRACK
static volatile bg_present30_tracker present_tracker;
static void present_surface(unsigned id){
    bool released=bg_present30_track_release(&present_tracker,id);
    assertf(released,"Invalid display surface release");(void)released;
    display_show(completion_frames[id].screen);
}
#endif
static void paced_vi(void){
#ifdef BG_PRESENT_TRACK
    ++video_retraces;
    if(present_tracker.draining||(!presenter.started&&bg_present30_track_start_blocked(&present_tracker,video_retraces))){
        presenter.due=presenter.missed=false;return;
    }
    int id=bg_present30_vi(&presenter,video_retraces);
    if(id>=0)present_surface((unsigned)id);
#else
    int id=bg_present30_vi(&presenter,++video_retraces);
    if(id>=0)display_show(completion_frames[id].screen);
#endif
}
static void presentation_mode(bool enabled){
    disable_interrupts();
    if(presenter.enabled!=enabled){
        /* Release every held surface in FIFO. In-flight full-sync callbacks
         * use the new mode; libdragon retains acquisition order across both. */
        int id;
#ifdef BG_PRESENT_TRACK
        while((id=bg_present30_pop(&presenter))>=0){
            present_surface((unsigned)id);
        }
#else
        while((id=bg_present30_pop(&presenter))>=0)display_show(completion_frames[id].screen);
#endif
        presenter.enabled=enabled;presenter.started=false;
        presenter.due=presenter.missed=false;
#ifdef BG_PRESENT_TRACK
        if(enabled)bg_present30_track_begin_drain(&present_tracker);
        else bg_present30_track_cancel_drain(&present_tracker);
#endif
    }
    enable_interrupts();
}
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PRESENT_TRACK)
static void observe_vi(void){
#ifndef BG_PACED30
    ++video_retraces;
#endif
    /* VI_ORIGIN is the physical scanout address. This callback is registered
     * before display_init, so libdragon's prepended swap handler runs first. */
    uint32_t origin=*(volatile uint32_t*)0xA4400004u&0x00ffffffu;
    for(unsigned i=0;i<BG_PACED30_BUFFERS;i++){
        const bg_completion_frame*f=&completion_frames[i];
        if(!f->screen||PhysicalAddr(f->screen->buffer)!=origin)continue;
#ifdef BG_PRESENT_TRACK
        bg_present30_track_observe(&present_tracker,i,video_retraces);
#endif
#ifdef BG_VI_MEASURE
        bg_vi_frame sample={.pose_tick=f->pose_tick,.vehicle=f->vehicle,
            .sampled_us=f->sampled_us,.completed_us=f->completed_us};
        bool due=false,missed=false;
#ifdef BG_PACED30
        due=presenter.due;missed=presenter.missed;
#endif
        bg_vi_record(&visible_meter,get_ticks_us(),video_retraces,origin,&sample,due,missed);
#endif
        break;
    }
}
#endif
static void frame_complete(void*argument){
    bg_completion_frame*frame=argument;
    uint64_t now=get_ticks_us();frame->completed_us=now;
#ifdef BG_PACED30
    if(presenter.enabled
#ifdef BG_PRESENT_TRACK
       &&!present_tracker.draining
#endif
    ){
        bool queued=bg_present30_complete(&presenter,(unsigned)(frame-completion_frames));
        assertf(queued,"Paced presentation queue overflow/duplicate surface");
    }else
#endif
#ifdef BG_PRESENT_TRACK
    present_surface((unsigned)(frame-completion_frames));
#else
    display_show(frame->screen);
#endif
#ifdef BG_BENCHMARK
    bg_cadence_record_with_tail(&completed_cadence,&completed_tail,now,frame->vehicle,&frame->sample);
#endif
}
static void frame_present(surface_t*screen,unsigned vehicle){
    unsigned i=0;
    while(i<BG_PACED30_BUFFERS&&completion_frames[i].screen&&completion_frames[i].screen!=screen)i++;
    assertf(i<BG_PACED30_BUFFERS,"Display buffer metadata exhausted");
    completion_frames[i]=(bg_completion_frame){.screen=screen,.vehicle=vehicle,
        .pose_tick=simulation_pose,.sampled_us=frame_sample_us};
#ifdef BG_PRESENT_TRACK
    disable_interrupts();
    bool submitted=bg_present30_track_submit(&present_tracker,i);
    assertf(submitted,"Display surface reused before VI presentation");(void)submitted;
    enable_interrupts();
#endif
#ifdef BG_BENCHMARK
    bg_cadence_frame*sample=&completion_frames[i].sample;
    sample->sim_ms=(uint32_t)(game_time*1000.f);sample->triangles=triangles;sample->vertices=submitted_vertices;
    memcpy(sample->category_triangles,category_triangles,sizeof(sample->category_triangles));
    for(unsigned p=0;p<4;p++){
        if(bg_players[p].vehicle>=0)sample->vehicle_mask|=1u<<p;
        if(bg_players[p].zoom)sample->zoom_mask|=1u<<p;
        if(bg_players[p].health<=0)sample->dead_mask|=1u<<p;
    }
#endif
    /* libdragon's detach_show uses this same full-sync callback, with
     * display_show directly. No extra fence or wait is introduced. */
    rdpq_detach_cb(frame_complete,&completion_frames[i]);
}
#endif
#ifdef BG_BENCHMARK
static uint64_t benchmark_origin,benchmark_previous;
static uint64_t audio_pump_previous;
static uint32_t audio_pump_max_gap;
static unsigned benchmark_vehicle,benchmark_triangles,benchmark_vertices,benchmark_phases[BG_BENCHMARK_PHASES];
static unsigned benchmark_categories[BG_BENCHMARK_CATEGORIES];
#endif
#ifdef BG_GPU_DIAGNOSTIC
static volatile bool diagnostic_rdp_done;
static void diagnostic_rdp_complete(void*unused){(void)unused;diagnostic_rdp_done=true;}
#endif
#ifdef RDPQ_VALIDATE
static unsigned validation_errors,validation_warnings;
static char validation_line[192],validation_message[96];
static unsigned validation_length;
static int validation_write(void*cookie,const char*text,int length){
    for(int i=0;i<length;i++){
        if(text[i]=='\n'){
            validation_line[validation_length]=0;
            if(strstr(validation_line,"[RDPQ_VALIDATION]")){
                if(strstr(validation_line,"ERROR:")||strstr(validation_line,"CRASH:"))validation_errors++;
                if(strstr(validation_line,"WARN:"))validation_warnings++;
                if(strstr(validation_line,"ERROR:")||strstr(validation_line,"WARN:"))
                    snprintf(validation_message,sizeof(validation_message),"%.95s",validation_line+18);
            }
            validation_length=0;
        }else if(validation_length+1<sizeof(validation_line))validation_line[validation_length++]=text[i];
    }
    return fwrite(text,1,length,(FILE*)cookie);
}
#endif
static struct {float pos[3],life,radius;bg_explosion_kind kind;} explosions[12];
static unsigned explosion_next;

static void pump_audio(void){
#ifdef BG_PROFILE
    uint64_t begin=get_ticks_us();
#endif
#ifdef BG_BENCHMARK
    /* Reuse the profiler timestamp; no extra clock read in polling loops.
     * This is a scheduling gap, not an assertion about SDK queue occupancy. */
    if(audio_pump_previous&&benchmark_origin&&begin>=benchmark_origin+1000000){
        uint64_t gap=begin-audio_pump_previous;
        if(gap>audio_pump_max_gap)audio_pump_max_gap=gap>UINT32_MAX?UINT32_MAX:(uint32_t)gap;
    }
    audio_pump_previous=begin;
#endif
    bg_sound_pump();
#ifdef BG_PROFILE
    audio_us+=get_ticks_us()-begin;
#endif
}
static unsigned weapon_model(unsigned w){return w==BG_W_FLAMETHROWER?BG_M_FLAMETHROWER:w<8?w:BG_M_AR;}
static unsigned pickup_model(unsigned w){
    return w<BG_WEAPON_COUNT?weapon_model(w):w==BG_PICK_FRAG?BG_M_FRAG:
        w==BG_PICK_PLASMA?BG_M_PLASMA_GRENADE:w==BG_PICK_HEALTH?BG_M_HEALTHPACK:
        w==BG_PICK_OVERSHIELD?BG_M_OVERSHIELD:BG_M_CAMOUFLAGE;
}
static void tint_team(T3DVertPacked*vertices,unsigned count,const uint8_t*masks,unsigned player){
    player=bg_player_profiles[player];
    for(unsigned i=0;i<count;i++){
        uint32_t*rgba=t3d_vertbuffer_get_color(vertices,i);
        unsigned r=*rgba>>24,g=(*rgba>>16)&255,b=(*rgba>>8)&255,mask=masks[i];
        r=(r*(65025-mask*(255-colors[player].r))+32512)/65025;
        g=(g*(65025-mask*(255-colors[player].g))+32512)/65025;
        b=(b*(65025-mask*(255-colors[player].b))+32512)/65025;
        *rgba=(r<<24)|(g<<16)|(b<<8)|255;
    }
}
static rspq_block_t *record(T3DVertPacked *verts,unsigned count){
    rspq_block_begin();
    for(unsigned first=0;first<count;first+=60){
        unsigned n=count-first>60?60:count-first;
        t3d_vert_load(verts+first/2,0,(n+1)&~1u);
        /* Restart every triangle: exact original order/winding, one RSP
         * command per batch. 60 vertices leave 360 bytes of DMEM; indices
         * consume at most 120 bytes, within Tiny3D's documented cache limit. */
        t3d_tri_draw_strip(triangle_lists[n/3-1],n);
        t3d_tri_sync();
    }
    return rspq_block_end();
}
static void prepare_model(const bg_model_asset*asset){
    static const int16_t*converted[96];static unsigned converted_count;
    data_cache_hit_writeback(asset->vertices,((asset->vertex_count+1)&~1u)*16);
    if(!asset->batch_count)return;
    for(unsigned i=0;i<converted_count;i++)if(converted[i]==asset->indices)return;
    assertf(converted_count<96,"Model index conversion capacity");
    converted[converted_count++]=asset->indices;
    for(unsigned b=0;b<asset->batch_count;b++){
        const bg_mesh_batch*batch=&asset->batches[b];
        assertf(batch->count<=60&&batch->index_count<=120&&batch->index_count%3==0&&
            !(batch->first&1)&&!(batch->index_first&3)&&batch->first+batch->count<=asset->vertex_count,
            "Model batch capacity/alignment");
        int16_t*indices=asset->indices+batch->index_first;
        for(unsigned i=0;i<batch->index_count;i++){
            assertf(indices[i]>=0&&indices[i]<batch->count,"Model batch index range");
            if(i&&i%3==0)indices[i]|=0x8000;
        }
        t3d_indexbuffer_convert(indices,batch->index_count);
        data_cache_hit_writeback(indices,((batch->index_count+3u)&~3u)*2);
    }
}
static rspq_block_t *record_model_range(const bg_model_asset*asset,T3DVertPacked*vertices,
        unsigned first,unsigned count,unsigned batch_first,unsigned batch_count){
    if(!asset->batch_count)return record(vertices+first/2,count);
    assertf(batch_first+batch_count<=asset->batch_count,"Model batch range");
    rspq_block_begin();
    for(unsigned b=batch_first;b<batch_first+batch_count;b++){
        const bg_mesh_batch*batch=&asset->batches[b];
        t3d_vert_load(vertices+batch->first/2,0,(batch->count+1)&~1u);
        t3d_tri_draw_strip(asset->indices+batch->index_first,batch->index_count);t3d_tri_sync();
    }
    return rspq_block_end();
}
static rspq_block_t *record_model(const bg_model_asset*asset,T3DVertPacked*vertices){
    return record_model_range(asset,vertices,0,asset->vertex_count,0,asset->batch_count);
}
#ifdef BG_PROFILE
static unsigned model_load_count(const bg_model_asset*asset,unsigned count,unsigned first,unsigned batches){
    if(!asset->batch_count)return (count+1)&~1u;
    unsigned total=0;for(unsigned b=first;b<first+batches;b++)total+=(asset->batches[b].count+1)&~1u;
    return total;
}
#endif
static rspq_block_t *record_indexed(const bg_chunk*chunk){
    int16_t*indices=bg_chunk_indices+chunk->index_first;
    assertf(chunk->count<=60&&chunk->index_count<=120&&chunk->index_count%3==0,
        "Terrain batch capacity");
    for(unsigned i=3;i<chunk->index_count;i+=3)indices[i]|=0x8000;
    t3d_indexbuffer_convert(indices,chunk->index_count);
    data_cache_hit_writeback(indices,((chunk->index_count+3u)&~3u)*2);
    rspq_block_begin();
    t3d_vert_load(bg_vertices+chunk->first/2,0,(chunk->count+1)&~1u);
    t3d_tri_draw_strip(indices,chunk->index_count);t3d_tri_sync();
    return rspq_block_end();
}
static void init_scene(void){
    const float terrain_scale=BG_SCALE/BG_TERRAIN_SCALE;
    t3d_mat4fp_from_srt_euler(&terrain_matrix,(float[]){terrain_scale,terrain_scale,terrain_scale},
        (float[]){0,0,0},(float[]){0,0,0});
    data_cache_hit_writeback(&terrain_matrix,sizeof(terrain_matrix));
    assertf(bg_chunk_count<=512&&bg_material_count<=32,"Asset capacity exceeded");
    for(unsigned list=0;list<20;list++){
        unsigned count=(list+1)*3;
        for(unsigned i=0;i<count;i++)triangle_lists[list][i]=i|((i&&i%3==0)?0x8000:0);
        t3d_indexbuffer_convert(triangle_lists[list],count);
    }
    data_cache_hit_writeback(triangle_lists,sizeof(triangle_lists));
    for(unsigned clip=0;clip<BG_A_COUNT;clip++){
        if(bg_animations[clip].tracks>motion_capacity)motion_capacity=bg_animations[clip].tracks;
        if(bg_spartan_lod_animations[clip].tracks>motion_capacity)motion_capacity=bg_spartan_lod_animations[clip].tracks;
    }
    for(unsigned weapon=0;weapon<BG_FP_WEAPONS;weapon++)for(unsigned clip=0;clip<BG_FP_CLIPS;clip++)
        if(bg_fp_animations[weapon][clip].tracks>motion_capacity)motion_capacity=bg_fp_animations[weapon][clip].tracks;
    motion_tracks=malloc(motion_capacity*sizeof(*motion_tracks));
    assertf(motion_tracks,"Animation interpolation scratch allocation");
    data_cache_hit_writeback(bg_vertices,bg_vertex_count*16);
    data_cache_hit_writeback((void*)bg_ground_palette,32);
    for(unsigned i=0;i<bg_material_count;i++){
        unsigned size=bg_texture_sizes[i];
        textures[i]=surface_make(bg_textures[i],bg_texture_ci4[i]?FMT_CI4:FMT_RGBA16,size,size,bg_texture_ci4[i]?size/2:size*2);
        data_cache_hit_writeback(bg_textures[i],2048);
    }
    for(unsigned i=0;i<bg_chunk_count;i++)world_blocks[i]=record_indexed(&bg_chunks[i]);
    for(unsigned m=0;m<BG_M_COUNT;m++){
        const bg_model_asset*a=&bg_model_assets[m];
        prepare_model(a);models[m]=record_model(a,a->vertices);
        const bg_model_asset*far=&bg_pickup_lods[m];
#ifdef BG_PROFILE
        model_vertex_loads[m]=model_load_count(a,a->vertex_count,0,a->batch_count);
        pickup_vertex_loads[m]=model_load_count(far,far->vertex_count,0,far->batch_count);
#endif
        if(far->vertices==a->vertices&&far->indices==a->indices)pickup_lod_blocks[m]=models[m];
        else{
            prepare_model(far);pickup_lod_blocks[m]=record_model(far,far->vertices);
        }
    }
    for(unsigned m=0;m<4;m++){
        const bg_model_asset*a=&bg_vehicle_lods[m];
        prepare_model(a);vehicle_lods[m]=record_model(a,a->vertices);
#ifdef BG_PROFILE
        vehicle_vertex_loads[m]=model_load_count(a,a->vertex_count,0,a->batch_count);
#endif
        const bg_vehicle_rig*rig=&bg_vehicle_rigs[m];
        assertf(rig->count<=7,"Vehicle rig capacity");
        for(unsigned j=0;j<rig->count;j++){
            const bg_vehicle_part*part=&rig->parts[j];const bg_model_asset*full=&bg_model_assets[BG_M_WARTHOG+m];
            vehicle_parts[m][j]=record_model_range(full,full->vertices,part->first,part->count,part->batch_first,part->batch_count);
#ifdef BG_PROFILE
            part_vertex_loads[m][j]=model_load_count(full,part->count,part->batch_first,part->batch_count);
#endif
        }
    }
    /* New tables explicitly alias the existing far asset when absent. */
    for(unsigned m=0;m<BG_M_COUNT;m++){
        const bg_model_asset*a=bg_pickup_micro_lods[m],*old=&bg_pickup_lods[m];
        pickup_micro_available[m]=a->vertices!=old->vertices||a->indices!=old->indices;
        if(!pickup_micro_available[m])pickup_micro_blocks[m]=pickup_lod_blocks[m];
        else{prepare_model(a);pickup_micro_blocks[m]=record_model(a,a->vertices);}
#ifdef BG_PROFILE
        pickup_micro_vertex_loads[m]=model_load_count(a,a->vertex_count,0,a->batch_count);
#endif
    }
    for(unsigned m=0;m<4;m++){
        const bg_model_asset*a=bg_vehicle_micro_lods[m],*old=&bg_vehicle_lods[m];
        vehicle_micro_available[m]=a->vertices!=old->vertices||a->indices!=old->indices;
        if(!vehicle_micro_available[m])vehicle_micro_blocks[m]=vehicle_lods[m];
        else{prepare_model(a);vehicle_micro_blocks[m]=record_model(a,a->vertices);}
#ifdef BG_PROFILE
        vehicle_micro_vertex_loads[m]=model_load_count(a,a->vertex_count,0,a->batch_count);
#endif
    }
    for(unsigned m=0;m<2;m++){
        const bg_model_asset*a=&bg_covenant_wrecks[m];prepare_model(a);
        covenant_wreck_blocks[m]=record_model(a,a->vertices);
    }
    prepare_model(&bg_spartan_lod);
    for(unsigned weapon=0;weapon<BG_FP_WEAPONS;weapon++){
        const bg_model_asset*a=&bg_fp_models[weapon];prepare_model(a);
        for(unsigned prior=0;prior<weapon;prior++){
            const bg_model_asset*b=&bg_fp_models[prior];
            if(a->vertices==b->vertices&&a->indices==b->indices){
                firstperson_blocks[weapon]=firstperson_blocks[prior];break;
            }
        }
        if(!firstperson_blocks[weapon])
            firstperson_blocks[weapon]=record_model(a,t3d_segment_placeholder(T3D_SEGMENT_1));
    }
#ifdef BG_PROFILE
    spartan_lod_vertex_loads=model_load_count(&bg_spartan_lod,bg_spartan_lod.vertex_count,0,bg_spartan_lod.batch_count);
    for(unsigned weapon=0;weapon<BG_FP_WEAPONS;weapon++){
        const bg_model_asset*a=&bg_fp_models[weapon];fp_vertex_loads[weapon]=model_load_count(a,a->vertex_count,0,a->batch_count);
    }
#endif
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        viewports[s][p]=t3d_viewport_create();
    }
    static const int16_t points[6][3]={{0,32,0},{0,-32,0},{32,0,0},{0,0,32},{-32,0,0},{0,0,-32}};
    static const uint8_t indices[24]={0,3,2,0,4,3,0,5,4,0,2,5,1,2,3,1,3,4,1,4,5,1,5,2};
    const uint32_t hues[7]={0x54d9ffff,0xf15cffff,0xffd38aff,0x818977ff,0x76abffff,0xffbc50ff,0xff9836ff};
    for(unsigned k=0;k<7;k++){
        for(unsigned i=0;i<24;i++){
            memcpy(t3d_vertbuffer_get_pos(particles[k],i),points[indices[i]],6);
            *t3d_vertbuffer_get_color(particles[k],i)=hues[k];
        }
        data_cache_hit_writeback(particles[k],sizeof(particles[k]));particle_blocks[k]=record(particles[k],24);
    }
}
static void fill(int x,int y,int w,int h,color_t color){rdpq_set_mode_fill(color);rdpq_fill_rectangle(x,y,x+w,y+h);}
static void reset_view_state(void){
    for(unsigned p=0;p<4;p++)fired_at[p]=-100;
    bg_fx_reset();
    memset(explosions,0,sizeof(explosions));memset(wheel_rotation,0,sizeof(wheel_rotation));explosion_next=0;
}
#ifndef BG_SNAPSHOT_TICK
static uint32_t control_buttons(joypad_buttons_t buttons){
    uint32_t bits=0;
#define BUTTON(field,name) if(buttons.field)bits|=BG_BUTTON_##name
    BUTTON(a,A);BUTTON(b,B);BUTTON(l,L);BUTTON(r,R);BUTTON(z,Z);BUTTON(start,START);
    BUTTON(d_up,D_UP);BUTTON(d_down,D_DOWN);BUTTON(d_left,D_LEFT);BUTTON(d_right,D_RIGHT);
    BUTTON(c_up,C_UP);BUTTON(c_down,C_DOWN);BUTTON(c_left,C_LEFT);BUTTON(c_right,C_RIGHT);
#undef BUTTON
    return bits;
}
static bool input(bg_input in[4]){
    bg_control_state raw[4];bg_menu_input navigation[4];
    joypad_poll();
    for(unsigned i=0;i<4;i++){
        joypad_inputs_t stick=joypad_get_inputs(i);joypad_buttons_t held=joypad_get_buttons(i),pressed=joypad_get_buttons_pressed(i);
        raw[i]=(bg_control_state){.stick_x=stick.stick_x,.stick_y=stick.stick_y,
            .held=control_buttons(held),.pressed=control_buttons(pressed)};
    }
#ifdef BG_FRONTEND_QA
    bg_front_qa_input(&front,raw,get_ticks_us());
#endif
#ifdef BG_MENU_QA
    bg_menu_qa_input(raw,get_ticks_us());
#endif
#ifdef BG_SCORES_BENCHMARK
    /* A separately named replay measures all four live score overlays. */
    for(unsigned i=0;i<4;i++)raw[i]=(bg_control_state){.held=BG_BUTTON_R};
#endif
#ifdef BG_FRONTEND
    if(front_active()){
        bg_front_action action=bg_front_update(&front,raw,get_ticks_us());
        bg_sound_front_effect(front.sound);
        memset(in,0,sizeof(bg_input)*4);memset(scores,0,sizeof(scores));
        if(action==BG_FRONT_START_MATCH){
            bg_front_draw_release();views=front.count;bg_set_players(views);bg_set_score_limit(15);
            bg_reset();game_time=0;match_ended=0;reset_view_state();
            body_buffers_load();
            menu.player_count=views;menu.open=false;menu.shell_session=true;
            const bg_model_asset *spartan=&bg_model_assets[BG_M_SPARTAN];
            for(unsigned p=0;p<views;p++){
                bg_player_profiles[p]=front.profile[front.ports[p]];
                menu.styles[p]=front.styles[bg_player_profiles[p]];
                for(unsigned s=0;s<BG_FRAME_SLOTS;s++){
                    memcpy(armor[s][p],spartan->vertices,((spartan->vertex_count+1)&~1u)*16);
                    tint_team(armor[s][p],spartan->vertex_count,bg_spartan_team_mask,p);
                    memcpy(armor_lod[s][p],bg_spartan_lod.vertices,((bg_spartan_lod.vertex_count+1)&~1u)*16);
                    tint_team(armor_lod[s][p],bg_spartan_lod.vertex_count,bg_spartan_lod_team_mask,p);
                    firstperson_weapon[s][p]=-1;
                }
            }
            bg_sound_frontend(false);
        }else if(action==BG_FRONT_RESUME_MATCH){bg_front_draw_release();menu.open=false;}
        else if(action==BG_FRONT_LEAVE_MATCH){menu.open=false;bg_vehicle_world_release();firstperson_buffers_release();body_buffers_release();bg_sound_frontend(true);}
        paused=front_active();return true;
    }
    bg_front_map_controls(&front,raw,raw);
#endif
    bg_menu_inputs(&menu,raw,navigation);
    bg_menu_result result=bg_menu_update(&menu,navigation,views);
    paused=menu.open;
#ifdef BG_FRONTEND
    for(unsigned p=0;p<views;p++)front.styles[front.profile[front.ports[p]]]=menu.styles[p];
    if(result.action==BG_MENU_ACTION_QUIT){
        /* The full-screen confirmation needs its backdrop bank. Simulation
         * state survives; resume lazily recreates these render-only buffers. */
        firstperson_buffers_release();body_buffers_release();
        bg_front_quit(&front);paused=true;
    }
#endif
    if(result.action==BG_MENU_ACTION_RESTART){bg_reset();game_time=0;reset_view_state();
#ifdef BG_FRONTEND
        match_ended=0;
#endif
    }
    if(result.action==BG_MENU_ACTION_PLAYER_COUNT){views=result.player_count;bg_set_players(views);}
    memset(in,0,sizeof(bg_input)*4);
    memset(scores,0,sizeof(scores));
    if(!result.consumed)for(unsigned i=0;i<views;i++){
        bg_controls_map(&in[i],&raw[i],menu.styles[i],bg_players[i].vehicle>=0);
        scores[i]=bg_controls_show_scores(&raw[i],menu.styles[i]);
    }
#ifdef BG_MENU_QA
    bg_menu_qa_check(&menu,views,&result,in);
#endif
    return result.consumed;
}
#ifdef BG_PACED30
static surface_t*paced_acquire(blam_clock*clock,uint64_t*previous,
        bg_input latch[4],bg_input in[4],unsigned*ticks,bool*first,uint64_t*ui_deadline){
    unsigned pending_ticks=0,dropped_ticks=0;uint64_t last_poll=0;
    for(;;){
        uint64_t now=get_ticks_us();
        if(!last_poll||now-last_poll>=2000){
            if(input(in)){
                memset(latch,0,sizeof(bg_input)*4);
                /* Pausing/resuming consumes no queued gameplay input, as in
                 * the ordinary local clock's paused update. */
                clock->ticks-=pending_ticks;pending_ticks=0;
            }
            for(unsigned p=0;p<4;p++){
#define EDGE(field) latch[p].field|=in[p].field;in[p].field=latch[p].field
                EDGE(jump);EDGE(reload);EDGE(switch_weapon);EDGE(grenade);EDGE(switch_grenade);EDGE(melee);EDGE(zoom);
#undef EDGE
            }
            presentation_mode(views>=3&&!front_active());last_poll=now;
        }
        clock->paused=paused;
        dropped_ticks+=bg_paced_clock_accumulate(clock,now-*previous,&pending_ticks);*previous=now;
        /* Wait BEFORE acquiring: a repeated simulation pose never locks a
         * display surface. Paused menus may redraw on a wall-time permit. */
        bool redraw=views<3||pending_ticks||*first||(paused&&now>=*ui_deadline);
#ifdef BG_PRESENT_TRACK
        /* Drain old SDK-ready/in-flight frames before fresh paced prefill.
         * Input, clock accumulation and audio above/below continue normally. */
        if(present_tracker.draining)redraw=false;
#endif
        surface_t*screen=redraw?display_try_get():NULL;
        if(screen){
            if(dropped_ticks)clock->leftover_dt=0;
            paced_dropped_ticks+=dropped_ticks;
            *ticks=pending_ticks;*first=false;*ui_deadline=now+33333;
            frame_sample_us=last_poll;return screen;
        }
        pump_audio();
    }
}
#endif
#endif
static void prepare_effect_bounds(bg_cull_bounds*bounds,const float pos[3],float radius){
    bg_bounds box;
    for(unsigned a=0;a<3;a++){box.min[a]=(pos[a]-radius)*BG_SCALE;box.max[a]=(pos[a]+radius)*BG_SCALE;}
    bg_bounds_quantize(bounds,&box);
}
static bool visible_bounds(T3DViewport*vp,const bg_cull_bounds*bounds){
    return !bounds->valid||t3d_frustum_vs_aabb_s16(&vp->viewFrustum,bounds->min,bounds->max);
}
static void instance(unsigned model,T3DMat4FP*matrix){
    t3d_matrix_set(matrix,true);rspq_block_run(models[model]);triangles+=bg_model_assets[model].triangle_count;
#ifdef BG_PROFILE
    submitted_vertices+=model_vertex_loads[model];
#endif
}
static void small_model_instance(unsigned model,T3DMat4FP*matrix,T3DViewport*vp,const T3DVec3*eye,bool zoom,const bg_micro_sphere*micro_bounds){
    /* Positions in matrices are render units; asset radii are Halo units.
     * Camera-forward depth is conservative at the edges of the viewport,
     * unlike Euclidean distance. A bounding sphere controls the pixel LOD.
     * Held guns use the same size or shrink when crouching, so retaining the
     * unscaled source radius safely overestimates the crouched silhouette. */
    float pos[3];for(unsigned a=0;a<3;a++)pos[a]=t3d_mat4fp_get_float(matrix,3,a);
    float depth=-(pos[0]*vp->matCamera.m[0][2]+pos[1]*vp->matCamera.m[1][2]+
        pos[2]*vp->matCamera.m[2][2]+vp->matCamera.m[3][2])/BG_SCALE;
    float distance_squared=0;for(unsigned a=0;a<3;a++){float d=(pos[a]-eye->v[a])/BG_SCALE;distance_squared+=d*d;}
    bool far=!zoom&&bg_lod_diameter_below(bg_model_assets[model].radius,
        vp->size[1]*fabsf(vp->matProj.m[1][1]),depth,distance_squared,12.f);
    bool micro=far&&pickup_micro_available[model]&&bg_micro_lod_below(micro_bounds,vp->matCamera.m,vp->matProj.m,
        vp->size[0],vp->size[1],1.4f,BG_MICRO_PIXELS,true,zoom,views);
    t3d_matrix_set(matrix,true);rspq_block_run(micro?pickup_micro_blocks[model]:far?pickup_lod_blocks[model]:models[model]);
    triangles+=micro?bg_pickup_micro_lods[model]->triangle_count:far?bg_pickup_lods[model].triangle_count:bg_model_assets[model].triangle_count;
#ifdef BG_PROFILE
    submitted_vertices+=micro?pickup_micro_vertex_loads[model]:far?pickup_vertex_loads[model]:model_vertex_loads[model];
#endif
}
static void matrix(T3DMat4FP*out,float scale,float yaw,float pitch,const float pos[3]){
    t3d_mat4fp_from_srt_euler(out,(float[]){scale,scale,scale},(float[]){0,-yaw,-pitch},
        (float[]){pos[0]*BG_SCALE,pos[1]*BG_SCALE,pos[2]*BG_SCALE});
}
static void animate_mesh(T3DVertPacked*output,const bg_anim_asset*a,unsigned f0,unsigned f1,int fraction){
    assertf(a->tracks<=motion_capacity,"Animation scratch capacity");
    const uint8_t*src0=a->positions+f0*a->tracks*3,*src1=a->positions+f1*a->tracks*3;
    bg_motion_decode(motion_tracks,a->tracks,src0,src1,a->origin,fraction);
    bg_motion_scatter(output,a->vertices,a->indices,motion_tracks);
    data_cache_hit_writeback(output,((a->vertices+1)&~1u)*16);
#ifdef BG_PROFILE
    animated_tracks+=a->tracks;animated_vertices+=a->vertices;
#endif
}
static void prepare_player_bounds(unsigned p){
    bg_player*player=&bg_players[p];unsigned clip;
    float body_yaw=player->yaw,body_pitch=0;
    switch(player->animation){
        case BG_ANIM_WALK:case BG_ANIM_RUN:clip=BG_A_RUN;break;
        case BG_ANIM_FIRE:clip=BG_A_FIRE;break;case BG_ANIM_RELOAD:clip=BG_A_RELOAD;break;
        case BG_ANIM_DIE:clip=BG_A_DEATH;break;case BG_ANIM_JUMP:clip=BG_A_JUMP;break;
        case BG_ANIM_MELEE:clip=BG_A_MELEE;break;case BG_ANIM_DRIVE:clip=BG_A_DRIVE;break;
        default:clip=BG_A_IDLE;break;
    }
    const bg_seat_definition*seat=bg_player_seat(player);
    if(player->health>0&&seat){
        const bg_vehicle*vehicle=&bg_vehicles[player->vehicle];
        clip=player->seat==2?BG_A_PASSENGER:player->seat==1?BG_A_GUNNER:BG_A_DRIVE;
        body_yaw=vehicle->yaw+seat->yaw+(vehicle->kind==BG_V_WARTHOG&&player->seat==1?vehicle->turret_yaw:0);
        body_pitch=vehicle->pitch;
    }
    bool throwing=player->health>0&&player->grenade_cooldown>.55f&&player->vehicle<0;
    if(throwing)clip=BG_A_THROW;
    body_clips[p]=clip;body_throwing[p]=throwing;
    float size=1;
    float height_scale=locomotion_clip(player)<0?bg_body_height(player)/bg_movement.height[0]:1;
    T3DMat4*body=&body_matrices[p];
    t3d_mat4_from_srt_euler(body,(float[]){size,height_scale,size},(float[]){0,-body_yaw,-body_pitch},
        (float[]){player->pos[0]*BG_SCALE,player->pos[1]*BG_SCALE,player->pos[2]*BG_SCALE});
    if(player->health>0&&player->vehicle>=0){
        const bg_vehicle*v=&bg_vehicles[player->vehicle];
        if(v->physics_valid){
            const float*f=v->forward,*u=v->up;float r[3]={f[1]*u[2]-f[2]*u[1],f[2]*u[0]-f[0]*u[2],f[0]*u[1]-f[1]*u[0]};
            float relative=seat->yaw+(v->kind==BG_V_WARTHOG&&player->seat==1?v->turret_yaw:0),c=cosf(relative),s=sinf(relative);
            for(unsigned a=0;a<3;a++){body->m[0][a]=(f[a]*c-r[a]*s)*size;body->m[1][a]=u[a]*size;body->m[2][a]=(f[a]*s+r[a]*c)*size;}
        }
    }
    if(seat&&player->seat_blend>0)for(unsigned a=0;a<3;a++)
        body->m[3][a]+=player->seat_offset[a]*(player->seat_blend/(6.f/30))*BG_SCALE;
    const bg_bounds*source_bounds=seat?&bg_seat_poses[seat->pose][player->seat_state][0].bounds:
        player->weapon_ready>0?&bg_body_ready_poses[0].bounds:&bg_body_cull_bounds[clip];
    bg_bounds merged=*source_bounds;int locomotion=locomotion_clip(player);
    if(locomotion>=0){const bg_bounds*b=&bg_locomotion_poses[locomotion][0].bounds;
        for(unsigned k=0;k<3;k++){merged.min[k]=fminf(merged.min[k],b->min[k]);merged.max[k]=fmaxf(merged.max[k],b->max[k]);}}
    bg_bounds box;bg_bounds_transform(&box,&merged,body->m,BG_SCALE);
    bg_bounds_quantize(&body_bounds[p],&box);
    /* Any normalized hand quaternion keeps a weapon within its origin sphere.
     * Marker position interpolation stays inside this clip's endpoint box. */
    bg_bounds marker=bg_attachment_cull_bounds[clip];
    if(seat||player->weapon_ready>0||locomotion>=0)marker=(bg_bounds){{-1,-1,-1},{1,1,1}};
    bg_bounds_expand(&marker,bg_model_cull_radii[weapon_model(player->weapon)]);
    bg_bounds_transform(&box,&marker,body->m,BG_SCALE);bg_bounds_quantize(&held_bounds[p],&box);
    T3DMat4 armor_matrix=*body;
    for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)armor_matrix.m[a][b]*=BG_SCALE/BG_MODEL_SCALE;
    t3d_mat4_to_fixed_3x4(&transforms[slot][p],&armor_matrix);
}
static int locomotion_clip(const bg_player*p){
    if(p->health<=0||p->vehicle>=0||p->weapon_ready>0||p->melee_time>0||p->reload>0||p->flash>0||p->grenade_cooldown>.55f)return -1;
    if(p->landing_time>0)return 2+(p->hard_landing?1:0)+(p->crouch_amount>.5f?2:0);
    if(p->grounded&&p->crouch_amount>0)return hypotf(p->velocity[0],p->velocity[2])>.15f?1:0;
    return -1;
}
static float locomotion_seconds(const bg_player*p,int clip){
    return clip<2?p->anim_time:p->landing_duration-p->landing_time;
}
static void animate_player(unsigned p){
    if(!wanted_lods[p]&&!(wanted_held&(1u<<p)))return;
    bg_player*player=&bg_players[p];unsigned clip=body_clips[p];
    const bg_seat_definition*seat=bg_player_seat(player);
    bool ready=player->weapon_ready>0;
    if(seat||ready){
        float ready_seconds=ready?(1-player->weapon_ready/bg_ready_times[player->weapon])*bg_body_ready_poses[0].duration:0;
        for(unsigned lod=0;lod<2;lod++)if(wanted_lods[p]&(1u<<lod))
            bg_interaction_pose(CachedAddr(lod?armor_lod[slot][p]:armor[slot][p]),
                seat?&bg_seat_poses[seat->pose][player->seat_state][lod]:&bg_body_ready_poses[lod],
                seat?player->anim_time:ready_seconds,seat&&player->seat_state==BG_SEAT_STABLE);
        if(wanted_held&(1u<<p)){
            const bg_rom_pose*grip=seat?&bg_seat_grips[seat->pose]:&bg_body_ready_grip;
            float seconds=seat?fmodf(player->anim_time,grip->duration):ready_seconds;int16_t points[4][3];
            bg_interaction_points(points,grip,seconds);
            T3DMat4 hand,world;t3d_mat4_identity(&hand);
            for(unsigned a=0;a<3;a++){
                hand.m[3][a]=points[0][a]*(BG_SCALE/4096);
                for(unsigned c=0;c<3;c++)hand.m[c][a]=points[c+1][a]*(BG_SCALE/BG_OBJECT_SCALE/4096);
            }
            t3d_mat4_mul(&world,&body_matrices[p],&hand);t3d_mat4_to_fixed_3x4(&held_matrices[slot][p],&world);
        }
        return;
    }
    int locomotion=locomotion_clip(player);float loc_seconds=locomotion>=0?locomotion_seconds(player,locomotion):0;
    const bg_anim_asset*base=&bg_animations[clip];
    float phase=body_throwing[p]?(.9f-player->grenade_cooldown)/.35f:player->anim_time/base->duration;
    bool loop=clip==BG_A_RUN||clip==BG_A_IDLE||clip==BG_A_DRIVE||clip==BG_A_PASSENGER||clip==BG_A_GUNNER;
    if(loop)phase-=floorf(phase);else phase=fminf(fmaxf(phase,0),.9999f);
    float frame=phase*(base->frames-1);unsigned f0=(unsigned)frame,f1=f0+1<base->frames?f0+1:f0;
    int fraction=(frame-f0)*256;
    for(unsigned lod=0;lod<2;lod++)if(!seat&&(wanted_lods[p]&(1u<<lod))){
        const bg_anim_asset*a=lod?&bg_spartan_lod_animations[clip]:base;
        T3DVertPacked*output=CachedAddr(lod?armor_lod[slot][p]:armor[slot][p]);
        animate_mesh(output,a,f0,f1,fraction);
        if(locomotion>=0)bg_interaction_pose_blend(output,&bg_locomotion_poses[locomotion][lod],loc_seconds,locomotion<2,locomotion<2?player->crouch_amount:1);
    }
    if(wanted_held&(1u<<p)){
        const bg_attachment_clip*attach=&bg_weapon_attachment[clip];
        const bg_attachment_pose*pose0=&attach->poses[f0],*pose1=&attach->poses[f1];
        float q[4],pos[3],weight=frame-f0;
        blam_quaternions_interpolate_and_normalize(pose0->quat,pose1->quat,weight,q);
        for(unsigned c=0;c<3;c++)pos[c]=(pose0->pos[c]+(pose1->pos[c]-pose0->pos[c])*weight)*BG_SCALE;
        T3DMat4 hand,world;
        float model_scale=BG_SCALE/BG_OBJECT_SCALE;
        t3d_mat4_from_srt(&hand,(float[]){model_scale,model_scale,model_scale},q,pos);
        if(locomotion>=0){
            const bg_rom_pose*grip=&bg_locomotion_grips[locomotion];int16_t points[4][3];
            bg_interaction_points(points,grip,locomotion<2?fmodf(loc_seconds,grip->duration):loc_seconds);
            float weight=locomotion<2?player->crouch_amount:1;
            for(unsigned a=0;a<3;a++){
                hand.m[3][a]+=(points[0][a]*(BG_SCALE/4096)-hand.m[3][a])*weight;
                for(unsigned c=0;c<3;c++)hand.m[c][a]+=(points[c+1][a]*(BG_SCALE/BG_OBJECT_SCALE/4096)-hand.m[c][a])*weight;
            }
        }
        t3d_mat4_mul(&world,&body_matrices[p],&hand);t3d_mat4_to_fixed_3x4(&held_matrices[slot][p],&world);
    }
}
static void pivot_rotation(T3DMat4*out,const float pivot[3],float yaw,float pitch){
    t3d_mat4_from_srt_euler(out,(float[]){1,1,1},(float[]){0,-yaw,-pitch},(float[]){0,0,0});
    T3DVec3 p={{pivot[0]*BG_OBJECT_SCALE,pivot[1]*BG_OBJECT_SCALE,pivot[2]*BG_OBJECT_SCALE}},rotated;
    t3d_mat3_mul_vec3(&rotated,out,&p);
    for(unsigned a=0;a<3;a++)out->m[3][a]=p.v[a]-rotated.v[a];
}
static void compute_vehicle_pose(unsigned i){
    bg_vehicle*v=&bg_vehicles[i];const bg_vehicle_rig*rig=&bg_vehicle_rigs[v->kind];
    float model_scale=BG_SCALE/BG_OBJECT_SCALE;
    T3DMat4 base,yaw;t3d_mat4_from_srt_euler(&base,(float[]){model_scale,model_scale,model_scale},(float[]){0,-v->yaw,-v->pitch},
        (float[]){v->pos[0]*BG_SCALE,v->pos[1]*BG_SCALE,v->pos[2]*BG_SCALE});
    if(v->physics_valid){
        const float*f=v->forward,*u=v->up;
        float right[3]={f[1]*u[2]-f[2]*u[1],f[2]*u[0]-f[0]*u[2],f[0]*u[1]-f[1]*u[0]};
        for(unsigned a=0;a<3;a++){base.m[0][a]=f[a]*model_scale;base.m[1][a]=u[a]*model_scale;base.m[2][a]=right[a]*model_scale;}
    }
    t3d_mat4_to_fixed_3x4(&vehicle_matrices[slot][i],&base);
    bg_bounds combined;
    bg_bounds_transform(&combined,&bg_vehicle_micro_gate_bounds[v->kind],base.m,BG_OBJECT_SCALE);
    if(!v->active&&(v->kind==BG_V_GHOST||v->kind==BG_V_BANSHEE)){
        bg_bounds wreck;bg_bounds_transform(&wreck,&bg_covenant_wreck_bounds[v->kind==BG_V_BANSHEE],base.m,BG_OBJECT_SCALE);
        bg_bounds_union(&combined,&wreck);
    }
    pivot_rotation(&yaw,rig->turret_pivot,v->turret_yaw,0);
    for(unsigned j=0;j<rig->count;j++){
        const bg_vehicle_part*part=&rig->parts[j];T3DMat4 local,world;
        if(part->kind==BG_PART_BODY)world=base;
        else {
            if(part->kind==BG_PART_TURRET)local=yaw;
            else if(part->kind==BG_PART_HATCH){
                t3d_mat4_identity(&local);
                if(v->active){
                    const bg_rom_pose*pose=&bg_hatch_poses[v->kind==BG_V_BANSHEE][v->hatch_closing];
                    int16_t points[4][3];bg_interaction_points(points,pose,v->hatch*pose->duration);
                    for(unsigned a=0;a<3;a++){
                        local.m[3][a]=points[0][a]*(BG_OBJECT_SCALE/4096);
                        for(unsigned c=0;c<3;c++)local.m[c][a]=points[c+1][a]*(1.f/4096);
                    }
                }
            }
            else if(part->kind==BG_PART_WHEEL){
                /* Wheels rotate about their axle (local Z), then steer with
                 * the original opposite front/rear powered contact groups. */
                T3DMat4 spin,steer;
                pivot_rotation(&spin,part->pivot,0,-wheel_rotation[i]);
                float angle=v->physics_valid?v->steering*(part->pivot[0]>0?1:-1):0;
                pivot_rotation(&steer,part->pivot,angle,0);t3d_mat4_mul(&local,&steer,&spin);
                if(v->physics_valid&&v->kind==BG_V_WARTHOG){
                    unsigned channel=part->pivot[0]>0?(part->pivot[2]<0?2:3):(part->pivot[2]<0?0:1);
                    local.m[3][1]+=(v->suspension[channel]+.22f)*BG_OBJECT_SCALE;
                }
            }
            else{
                T3DMat4 pitch;pivot_rotation(&pitch,part->pivot,0,v->turret_pitch-v->pitch);
                t3d_mat4_mul(&local,&yaw,&pitch);
            }
            t3d_mat4_mul(&world,&base,&local);
        }
        t3d_mat4_to_fixed_3x4(&part_matrices[slot][i][j],&world);
        bg_bounds box;bg_bounds_transform(&box,&part->bounds,world.m,BG_OBJECT_SCALE);
        /* Reuse the exact current wheel/turret/barrel pose, not a sampled
         * rotation envelope. CPU-only bounds need no geometry-slot lifetime. */
        bg_bounds_quantize(&vehicle_part_bounds[i][j],&box);
        bg_bounds_union(&combined,&box);
    }
    bg_bounds_quantize(&vehicle_bounds[i],&combined);
}
static void prepare_vehicle(unsigned i){
    bg_vehicle_pose_cache*cache=&vehicle_pose_cache[i];uint32_t key[BG_VEHICLE_POSE_WORDS];
    bg_vehicle_pose_key(key,&bg_vehicles[i],&wheel_rotation[i]);
    if(cache->valid&&!memcmp(cache->key,key,sizeof(key))){
        if(!(cache->slot_mask&(1u<<slot))){
            /* The destination slot is fenced before prepare_frame. The other
             * slot is only read here; RSP matrix DMA never modifies it. */
            unsigned count=bg_vehicle_rigs[bg_vehicles[i].kind].count;
            memcpy(&vehicle_matrices[slot][i],&vehicle_matrices[cache->last_slot][i],sizeof(T3DMat4FP));
            memcpy(part_matrices[slot][i],part_matrices[cache->last_slot][i],count*sizeof(T3DMat4FP));
            cache->slot_mask|=1u<<slot;
        }
        /* These shared CPU bounds have no writer outside the miss path. */
    }else{
        compute_vehicle_pose(i);
        memcpy(cache->key,key,sizeof(key));cache->valid=true;cache->slot_mask=1u<<slot;
    }
    cache->last_slot=slot;
}
static void prepare_pickup_bounds(void){
    T3DMat4 rotation;float scale=BG_SCALE/BG_OBJECT_SCALE;
    t3d_mat4_from_srt_euler(&rotation,(float[]){scale,scale,scale},
        (float[]){0,-game_time*.5f,0},(float[]){0,0,0});
    T3DMat4FP fixed;t3d_mat4_to_fixed_3x4(&fixed,&rotation);
    for(unsigned i=0;i<bg_pickup_count;i++){
        const bg_pickup*q=&bg_pickups[i];if(!q->active)continue;
        float pos[3];memcpy(pos,q->pos,sizeof(pos));pos[1]+=.035f*sinf(game_time*2+i);
        for(unsigned a=0;a<3;a++){pos[a]*=BG_SCALE;rotation.m[3][a]=pos[a];}
        pickup_matrices[slot][i]=fixed;t3d_mat4fp_set_pos(&pickup_matrices[slot][i],pos);
        bg_bounds box;bg_bounds_transform(&box,&bg_pickup_micro_gate_bounds[pickup_model(q->weapon)],rotation.m,BG_OBJECT_SCALE);
        bg_bounds_quantize(&pickup_bounds[i],&box);
    }
}
/* Body commands retain their vertex addresses; allocate and release together. */
static void body_buffers_load(void){
    if(armor[0][0])return;
    const bg_model_asset*spartan=&bg_model_assets[BG_M_SPARTAN];
    unsigned bytes=((spartan->vertex_count+1)&~1u)*16;
    unsigned lod_bytes=((bg_spartan_lod.vertex_count+1)&~1u)*16;
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        armor[s][p]=malloc_uncached(bytes);assertf(armor[s][p],"Spartan buffer allocation");
        memcpy(armor[s][p],spartan->vertices,bytes);
        tint_team(armor[s][p],spartan->vertex_count,bg_spartan_team_mask,p);
        player_blocks[s][p]=record_model(spartan,armor[s][p]);
        armor_lod[s][p]=malloc_uncached(lod_bytes);assertf(armor_lod[s][p],"Spartan LOD allocation");
        memcpy(armor_lod[s][p],bg_spartan_lod.vertices,lod_bytes);
        tint_team(armor_lod[s][p],bg_spartan_lod.vertex_count,bg_spartan_lod_team_mask,p);
        armor_lod_blocks[s][p]=record_model(&bg_spartan_lod,armor_lod[s][p]);
    }
}
#ifdef BG_FRONTEND
static void body_buffers_release(void){
    if(!armor[0][0])return;
    /* Full-screen menus never draw gameplay bodies. The recorded blocks own
     * their vertex addresses, so fence and release both together; rebuild on
     * match entry. In-match pause/resume keeps this allocation intact. */
    rspq_wait();
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        rspq_block_free(player_blocks[s][p]);player_blocks[s][p]=NULL;
        rspq_block_free(armor_lod_blocks[s][p]);armor_lod_blocks[s][p]=NULL;
        free_uncached(armor[s][p]);armor[s][p]=NULL;
        free_uncached(armor_lod[s][p]);armor_lod[s][p]=NULL;
    }
}
#endif
/* Segment-based weapon commands do not retain these addresses. Keep their
 * animation workspace out of the full-screen menu texture peak. */
static void firstperson_buffers_load(void){
    if(firstperson[0][0])return;
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        firstperson[s][p]=malloc_uncached(bg_fp_max_vertices*16);
        assertf(firstperson[s][p],"First-person buffer allocation");
        firstperson_weapon[s][p]=-1;
    }
}
#ifdef BG_FRONTEND
static void firstperson_buffers_release(void){
    if(!firstperson[0][0])return;
    /* The RSP consumes vertices; the RDP only retains transformed triangles. */
    rspq_wait();
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        free_uncached(firstperson[s][p]);firstperson[s][p]=NULL;
        firstperson_weapon[s][p]=-1;
    }
}
#endif
static void animate_firstperson(unsigned p){
    if(p>=views)return;
    bg_player*player=&bg_players[p];unsigned w=player->weapon;
    if(player->vehicle>=0||player->health<=0||player->zoom||p>=views)return;
    const bg_model_asset*m=&bg_fp_models[w];
    T3DVertPacked*output=CachedAddr(firstperson[slot][p]);
    unsigned bytes=((m->vertex_count+1)&~1u)*16;
    if(firstperson_weapon[slot][p]!=(int)w){
        memset((uint8_t*)output+bytes,0,bg_fp_max_vertices*16-bytes);
        memcpy(output,m->vertices,bytes);
        tint_team(output,m->vertex_count,bg_fp_team_masks[w],p);
        /* The slot fence protects this buffer. Commands are shared and
         * select its address through the RSP's ordered segment table. */
        firstperson_weapon[slot][p]=w;
    }
    unsigned clip=BG_FP_IDLE;float seconds=game_time;
    if(player->reload>0){
        clip=BG_FP_RELOAD;seconds=player->anim_time;
        /* Fit the source needle-regrowth timeline to the game's reload
         * duration; mesh motion and ammunition overlay share that clock. */
        if(w==BG_W_NEEDLER)seconds*=bg_fp_animations[w][clip].duration/bg_weapon_defs[w].reload;
    }
    else if(player->overheated){clip=BG_FP_RELOAD;seconds=(1-player->heat)/.85f*bg_fp_animations[w][clip].duration;}
    else if(player->melee_time>0){clip=BG_FP_MELEE;seconds=.7f-player->melee_time;}
    else if(game_time>=fired_at[p]&&game_time-fired_at[p]<bg_fp_animations[w][BG_FP_FIRE].duration){clip=BG_FP_FIRE;seconds=game_time-fired_at[p];}
    const bg_anim_asset*a=&bg_fp_animations[w][clip];
    float phase=fmaxf(0,seconds/a->duration);
    if(clip==BG_FP_IDLE)phase-=floorf(phase);else phase=fminf(phase,.9999f);
    float frame=phase*(a->frames-1);unsigned f0=frame,f1=f0+1<a->frames?f0+1:f0;int fraction=(frame-f0)*256;
    if(player->weapon_ready>0)bg_interaction_pose(output,&bg_ready_poses[w],bg_ready_times[w]-player->weapon_ready,false);
    else animate_mesh(output,a,f0,f1,fraction);
    bg_fx_pose(p,w,clip,f0,f1,fraction);
    const bg_fp_detail_asset*detail=&bg_fp_details[w];
    if(detail->vertices){
        T3DVertPacked *scope=scope_vertices[slot][p];
        const int16_t (*a)[3]=&detail->poses[(detail->offsets[clip]+f0)*detail->vertices];
        const int16_t (*b)[3]=&detail->poses[(detail->offsets[clip]+f1)*detail->vertices];
        for(unsigned v=0;v<detail->vertices;v++){
            int16_t*point=t3d_vertbuffer_get_pos(scope,v);
            for(unsigned axis=0;axis<3;axis++)point[axis]=a[v][axis]+(((int)b[v][axis]-a[v][axis])*fraction>>8);
            *t3d_vertbuffer_get_color(scope,v)=detail->colors[v];
        }
        if(player->weapon_ready>0){
            int16_t points[12][3];bg_interaction_points(points,w==BG_W_SNIPER?&bg_ready_scope:&bg_ready_plasma[w==BG_W_PLASMA_RIFLE],bg_ready_times[w]-player->weapon_ready);
            for(unsigned v=0;v<detail->vertices;v++)memcpy(t3d_vertbuffer_get_pos(scope,v),points[v],sizeof(points[v]));
        }
        data_cache_hit_writeback(scope,sizeof(scope_vertices[slot][p]));
    }
    bg_fp_ammo_prepare(slot,p,w,clip,f0,f1,fraction,player->ammo,player->reserve,
        player->reload>0?seconds:-1,output);
}
static void ensure_player_animation(unsigned p){
    unsigned bit=1u<<p;if(body_animation_ready&bit)return;
#ifdef BG_PROFILE
    uint64_t begin=get_ticks_us();
#endif
    /* Prepare the union needed by ALL views exactly once. This must precede
     * the first near/far body or held-weapon command that borrows its buffer. */
    animate_player(p);
    if(wanted_held&bit)data_cache_hit_writeback(&held_matrices[slot][p],sizeof(T3DMat4FP));
    body_animation_ready|=bit;
#ifdef BG_PROFILE
    animation_us+=get_ticks_us()-begin;
#endif
}
static void ensure_firstperson_animation(unsigned p){
    unsigned bit=1u<<p;if(fp_animation_ready&bit)return;
#ifdef BG_PROFILE
    uint64_t begin=get_ticks_us();
#endif
    animate_firstperson(p);fp_animation_ready|=bit;
#ifdef BG_PROFILE
    animation_us+=get_ticks_us()-begin;
#endif
}
static void prepare_frame(void){
#ifdef BG_PROFILE
    uint64_t begin=get_ticks_us();
#endif
    body_animation_ready=fp_animation_ready=0;
    memset(wanted_lods,0,sizeof(wanted_lods));wanted_held=0;
    /* Matrix construction precedes visibility so culling uses the exact pose
     * later submitted, once per frame rather than once per viewport. */
    for(unsigned p=0;p<views;p++)prepare_player_bounds(p);
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicle_body_present(&bg_vehicles[i]))prepare_vehicle(i);
    prepare_pickup_bounds();
    if(views>=3){
        for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicle_body_present(&bg_vehicles[i])&&vehicle_micro_available[bg_vehicles[i].kind])
            bg_micro_sphere_from_bounds(&vehicle_micro_spheres[i],&vehicle_bounds[i]);
        for(unsigned i=0;i<bg_pickup_count;i++)if(bg_pickups[i].active&&pickup_micro_available[pickup_model(bg_pickups[i].weapon)])
            bg_micro_sphere_from_bounds(&pickup_micro_spheres[i],&pickup_bounds[i]);
    }
    for(unsigned p=0;p<views;p++)prepare_view(p);
#ifdef BG_PROFILE
    camera_us=get_ticks_us()-begin;begin=get_ticks_us();
#endif
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q||!q->active)continue;
        float scale=q->kind==BG_P_CANNON?.09f:q->kind==BG_P_FLAME?.18f:.045f;
        if(q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE)scale=BG_SCALE/BG_OBJECT_SCALE;
        matrix(&projectile_matrices[slot][i],scale,game_time*4,0,q->pos);
        prepare_effect_bounds(&projectile_bounds[i],q->pos,.2f);
    }
    for(unsigned i=0;i<12;i++)if(explosions[i].life>0){
        matrix(&explosion_matrices[slot][i],explosions[i].radius*(.4f+1-explosions[i].life/.35f),0,0,explosions[i].pos);
        prepare_effect_bounds(&explosion_bounds[i],explosions[i].pos,explosions[i].radius);
    }
    data_cache_hit_writeback(transforms[slot],sizeof(transforms[slot]));data_cache_hit_writeback(vehicle_matrices[slot],sizeof(vehicle_matrices[slot]));
    data_cache_hit_writeback(pickup_matrices[slot],sizeof(pickup_matrices[slot]));data_cache_hit_writeback(projectile_matrices[slot],sizeof(projectile_matrices[slot]));
    data_cache_hit_writeback(explosion_matrices[slot],sizeof(explosion_matrices[slot]));
    data_cache_hit_writeback(part_matrices[slot],sizeof(part_matrices[slot]));
#ifdef BG_PROFILE
    matrix_us=get_ticks_us()-begin;
#endif
}
static void update_effects(float dt){
    if(bg_match_time()<=dt+.00001f)reset_view_state();
    bg_fx_update(dt);
    for(unsigned i=0;i<bg_vehicle_count;i++)wheel_rotation[i]=bg_vehicles[i].wheel_phase;
    for(unsigned i=0;i<12;i++)explosions[i].life=fmaxf(0,explosions[i].life-dt);
    for(unsigned i=0;i<bg_event_count;i++)if(bg_events[i].kind==BG_EVENT_FIRE&&bg_events[i].player>=0&&bg_events[i].player<4)
        fired_at[bg_events[i].player]=game_time;
    for(unsigned i=0;i<bg_event_count;i++)if(bg_events[i].kind==BG_EVENT_EXPLOSION){
        /* One lethal hit produces a rocket/grenade impact and a vehicle death
         * event. Let the source vehicle fireburst replace the overlapping old
         * polygon blast, without altering damage or either gameplay event. */
        bool vehicle_burst=false;
        for(unsigned k=0;k<bg_event_count;k++)if(bg_events[k].kind==BG_EVENT_VEHICLE_DESTROYED&&bg_events[k].player==bg_events[i].player){
            float distance=0;for(unsigned a=0;a<3;a++){float d=bg_events[k].pos[a]-bg_events[i].pos[a];distance+=d*d;}
            if(distance<9){vehicle_burst=true;break;}
        }
        if(vehicle_burst)continue;
        unsigned j=explosion_next++%12;memcpy(explosions[j].pos,bg_events[i].pos,12);
        explosions[j].life=.35f;explosions[j].radius=bg_events[i].amount*.4f;
        explosions[j].kind=(bg_explosion_kind)bg_events[i].weapon;
    }
}
#ifdef BG_MODEL_QA
#if defined(BG_AIM_QA)
#include "aim_qa.h"
#elif defined(BG_HUD_QA)
#include "hud_qa.h"
#elif defined(BG_ENVIRONMENT_QA)
#include "environment_qa.h"
#elif defined(BG_GROUND_QA)
#include "ground_qa.h"
#elif defined(BG_GEOMETRY_QA)
#include "geometry_qa.h"
#elif defined(BG_PLASMA_QA)
#include "plasma_qa.h"
#elif defined(BG_WEAPON_QA)
#include "weapon_qa.h"
#else
#include "model_qa.h"
#endif
#endif
#ifdef BG_INTERACTION_QA
#include "interaction_qa.h"
#endif
#ifdef BG_SHIELD_QA
#include "shield_fixture.h"
#endif
#ifdef BG_MOVEMENT_QA
#include "movement_qa.h"
#endif
static void prepare_view(unsigned p){
    int w=views>=3?160:320,h=views==1?240:120,x=views>=3?(p%2)*160:0,y=views==1?0:(views>=3?p/2:p)*120;
    bg_player*player=&bg_players[p];float cp=cosf(player->pitch),sy=sinf(player->yaw),cy=cosf(player->yaw);
    float head=bg_eye_height(player);
    T3DVec3 eye={{player->pos[0]*BG_SCALE,(player->pos[1]+head)*BG_SCALE,player->pos[2]*BG_SCALE}};
    T3DVec3 target={{eye.v[0]+cy*cp,eye.v[1]+sinf(player->pitch),eye.v[2]-sy*cp}};
    if(player->vehicle>=0&&!bg_player_third_person(player)){
        float camera[3];bg_vehicle_camera_position(&bg_vehicles[player->vehicle],player->seat,camera);
        for(unsigned a=0;a<3;a++)eye.v[a]=camera[a]*BG_SCALE;
        target=(T3DVec3){{eye.v[0]+cy*cp,eye.v[1]+sinf(player->pitch),eye.v[2]-sy*cp}};
    }
    if(bg_player_third_person(player)){
        const bg_vehicle*vehicle=&bg_vehicles[player->vehicle];
        const bg_camera_track*track=&bg_camera_tracks[vehicle->kind][player->seat];
        float origin[3],offset[3];
        /* units.c: unnamed vehicle camera markers use the hull origin. */
        bg_vehicle_transform(vehicle,track->origin,origin);
        bg_camera_track_offset(track,player->yaw,player->pitch,offset);
        float length=sqrtf(offset[0]*offset[0]+offset[1]*offset[1]+offset[2]*offset[2]);
        float direction[3];for(unsigned a=0;a<3;a++)direction[a]=offset[a]/fmaxf(length,.001f);
        /* Keep the existing bounded terrain obstruction test. */
        float distance=fmaxf(.15f,fminf(length,bg_raycast(origin,direction,length)-.15f));
        for(unsigned a=0;a<3;a++)eye.v[a]=(origin[a]+direction[a]*distance)*BG_SCALE;
        /* Mounted weapons start one unit ahead of the player's aim origin.
         * Follow that pitch-aware trajectory so the reticle tracks the shot. */
        float aim_direction[3]={cy*cp,sinf(player->pitch),-sy*cp};
        float muzzle[3]={player->pos[0],player->pos[1]+bg_eye_height(player),player->pos[2]};
        for(unsigned a=0;a<3;a++)muzzle[a]+=aim_direction[a];
        float aim_distance=fmaxf(2.f,bg_raycast(muzzle,aim_direction,150.f));
        for(unsigned a=0;a<3;a++)target.v[a]=(muzzle[a]+aim_direction[a]*aim_distance)*BG_SCALE;
    }else if(player->health<=0){
        /* Pull the death view away from the corpse. If the wall behind it is
         * close, choose a clear shoulder direction before placing the camera. */
        const float directions[3][3]={{-cy*.82f,.572f,sy*.82f},{sy*.82f,.572f,cy*.82f},{-sy*.82f,.572f,-cy*.82f}};
        float origin[3]={player->pos[0],player->pos[1]+.5f,player->pos[2]};
        unsigned direction=0;float distance=bg_raycast(origin,directions[0],2.f)-.1f;
        if(distance<.75f)for(unsigned d=1;d<3;d++){
            float candidate=bg_raycast(origin,directions[d],2.f)-.1f;
            if(candidate>distance){direction=d;distance=candidate;}
        }
        if(distance<.2f)distance=.2f;
        for(unsigned a=0;a<3;a++){eye.v[a]=(origin[a]+directions[direction][a]*distance)*BG_SCALE;target.v[a]=player->pos[a]*BG_SCALE;}
        target.v[1]+=.3f*BG_SCALE;
    }
#ifdef BG_MODEL_QA
    model_qa_camera(p,&eye,&target);
#endif
#ifdef BG_INTERACTION_QA
    interaction_qa_camera(p,&eye,&target);
#endif
#ifdef BG_SHIELD_QA
    const float angle=(BG_SHIELD_QA==1?2.5f:.6f);
    eye=(T3DVec3){{(player->pos[0]+cosf(angle)*1.7f)*BG_SCALE,(player->pos[1]+.7f)*BG_SCALE,(player->pos[2]+sinf(angle)*1.7f)*BG_SCALE}};
    target=(T3DVec3){{player->pos[0]*BG_SCALE,(player->pos[1]+.38f)*BG_SCALE,player->pos[2]*BG_SCALE}};
#endif
    T3DViewport*vp=&viewports[slot][p];t3d_viewport_set_area(vp,x,y,w,h);
#ifdef BG_GUARDBAND4
    /* Tiny3D supports factors 1–4. Enlarge only the clipping guard band;
     * projection, viewport scissor and full triangle clipping stay active. */
    vp->guardBandScale=views>=3?4:2;
#endif
    float fov=views==2?.72f:1.08f;
    bool scoped=player->health>0&&player->zoom;
    if(scoped)fov=bg_camera_zoom_fov(fov,player->weapon==BG_W_SNIPER&&player->zoom==2?10:2);
    float near,far;bg_camera_depth(scoped,&near,&far);
    t3d_viewport_set_projection(vp,fov,near,far);
    /* Tiny3D rounds viewport scales to integers after W normalization. At
     * far=6200, 160x120 becomes scales 3/-2; changing far changes framing.
     * 1/512 gives exact 20/-15 (40/-30 full screen) and exact 16-bit W/depth
     * factors. Keep it independent of clipping distance and zoom. */
    t3d_viewport_set_w_normalize(vp,0,BG_CAMERA_NORMALIZE_SUM);
    bg_hud_aim_projection(vp->matProj.m,views,p);
    t3d_viewport_look_at(vp,&eye,&target,&(T3DVec3){{0,1,0}});
    bg_visibility_side_planes((float (*)[4])vp->viewFrustum.planes,vp->matCamProj.m,w,h);
    /* Camera-space arms cross the world's near plane. Give the foreground
     * its own projection and depth range, while preserving FOV and aim offset.
     * Separate slot storage keeps queued RSP camera matrices immutable. */
    T3DViewport *gun_vp=&gun_viewports[slot][p];*gun_vp=*vp;
    t3d_viewport_set_projection(gun_vp,fov,.125f,128.f);
    t3d_viewport_set_w_normalize(gun_vp,0,BG_CAMERA_NORMALIZE_SUM);
    bg_hud_aim_projection(gun_vp->matProj.m,views,p);
    view_eyes[p]=eye;held_masks[p]=0;
    for(unsigned j=0;j<views;j++){
        bg_player*q=&bg_players[j];body_lods[p][j]=0;
        if(q->invisibility>0)continue;
#if !defined(BG_MODEL_QA) && !defined(BG_INTERACTION_QA) && !defined(BG_SHIELD_QA)
        if(j==p&&!bg_player_third_person(player)&&player->health>0)continue;
#endif
        if(q->vehicle>=0&&bg_vehicles[q->vehicle].kind==BG_V_BANSHEE&&q->seat_state==BG_SEAT_STABLE)continue;
        float distance=0;for(unsigned a=0;a<3;a++){float d=q->pos[a]-eye.v[a]/BG_SCALE;distance+=d*d;}
        bool personal=bg_player_personal_weapon(q);
        bool held=(distance<=16||player->zoom)&&q->health>0&&personal;
        if(visible_bounds(vp,&body_bounds[j])){
            unsigned lod=distance>(views>=3?4.f:16.f)&&player->zoom==0;
            body_lods[p][j]=lod+1;wanted_lods[j]|=1u<<lod;
        }
        if(held&&visible_bounds(vp,&held_bounds[j])){held_masks[p]|=1u<<j;wanted_held|=1u<<j;}
    }
    for(unsigned i=0;i<bg_vehicle_count;i++){
        const bg_vehicle*v=&bg_vehicles[i];vehicle_view_lods[p][i]=0;
        if(!bg_vehicle_body_visible(v)||!visible_bounds(vp,&vehicle_bounds[i]))continue;
        float distance=0;for(unsigned a=0;a<3;a++){float d=v->pos[a]-eye.v[a]/BG_SCALE;distance+=d*d;}
        unsigned lod=distance>36&&player->zoom==0;
        if(v->active&&(v->kind==BG_V_BANSHEE||v->kind==BG_V_SCORPION)&&v->occupants[0]>=0&&(!v->hatch_closing||v->hatch<1))lod=0;
        if(lod&&vehicle_micro_available[v->kind]&&bg_micro_lod_below(&vehicle_micro_spheres[i],vp->matCamera.m,vp->matProj.m,
            vp->size[0],vp->size[1],1.4f,BG_MICRO_PIXELS,true,player->zoom!=0,views))lod=2;
        vehicle_view_lods[p][i]=lod+1;
    }
    for(unsigned i=0;i<bg_pickup_count;i++){
        pickup_visible[p][i]=bg_pickups[i].active&&visible_bounds(vp,&pickup_bounds[i]);
    }
}
static void draw_view(unsigned p){
    T3DViewport*vp=&viewports[slot][p];T3DVec3 eye=view_eyes[p];bg_player*player=&bg_players[p];
#ifdef BG_PROFILE
    uint64_t begin=get_ticks_us();
    unsigned before=triangles,animation_before=animation_us;
#endif
    t3d_viewport_attach(vp);bg_sky_draw(vp);triangles+=16;t3d_frame_start();
    rdpq_mode_dithering(DITHER_NONE_NONE);t3d_light_set_ambient((uint8_t[]){255,255,255,255});t3d_light_set_count(0);
    rdpq_mode_tlut(TLUT_NONE);rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);rdpq_mode_persp(true);rdpq_mode_filter(FILTER_BILINEAR);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_TEXTURED|T3D_FLAG_CULL_FRONT);
    t3d_matrix_push(&terrain_matrix);
    unsigned bound=~0u;bool palette_mode=false,overlay_mode=false;
    for(unsigned b=0;b<bg_chunk_count;b++){
        const bg_chunk*c=&bg_chunks[b];if(!t3d_frustum_vs_aabb_s16(&vp->viewFrustum,c->bounds,c->bounds+3))continue;
        if(bound!=c->material){
            bool overlay=bg_texture_overlay[c->material];
            if(overlay!=overlay_mode){
                rdpq_mode_begin();
                rdpq_mode_zbuf(true,!overlay);rdpq_mode_alphacompare(overlay?128:0);
                rdpq_mode_blender(0);rdpq_mode_antialias(overlay?AA_NONE:AA_STANDARD);
                __rdpq_mode_change_som(SOM_ZMODE_MASK,overlay?SOM_ZMODE_TRANSPARENT:SOM_ZMODE_OPAQUE);
                rdpq_mode_end();overlay_mode=overlay;
            }
            bool paletted=bg_texture_ci4[c->material];
            if(paletted!=palette_mode){rdpq_mode_tlut(paletted?TLUT_RGBA16:TLUT_NONE);palette_mode=paletted;}
            if(paletted)rdpq_tex_upload_tlut((uint16_t*)bg_ground_palette,0,16);
            rdpq_tex_upload(TILE0,&textures[c->material],&(rdpq_texparms_t){.s.repeats=REPEAT_INFINITE,.t.repeats=REPEAT_INFINITE});
            bound=c->material;
        }
        rspq_block_run(world_blocks[b]);triangles+=c->index_count/3;
#ifdef BG_PROFILE
        submitted_vertices+=(c->count+1)&~1u;
#endif
    }
    t3d_matrix_pop(1);
    if(overlay_mode){
        rdpq_mode_begin();rdpq_mode_zbuf(true,true);rdpq_mode_alphacompare(0);rdpq_mode_blender(0);rdpq_mode_antialias(AA_STANDARD);
        __rdpq_mode_change_som(SOM_ZMODE_MASK,SOM_ZMODE_OPAQUE);rdpq_mode_end();
    }
    if(palette_mode)rdpq_mode_tlut(TLUT_NONE);
    /* Extracted model faces are outward-wound. Terrain uses its own winding. */
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
    /* Every object matrix below is already in world space, including vehicle
     * parts, held weapons and first person. Reserve one sibling stack entry:
     * matrix_set(...,true) always multiplies the unchanged camera entry below
     * it, avoiding a redundant camera reload/normalization between objects. */
    /* Writes do not wake a sleeping RSP. The depth-clear flush may have
     * drained before this terrain batch; start it while objects are queued. */
    rspq_flush();
    t3d_matrix_push_pos(1);
    bg_fx_draw_begin(slot,p,vp,&eye);
#ifdef BG_PROFILE
    world_us+=get_ticks_us()-begin;begin=get_ticks_us();
    category_triangles[0]+=triangles-before;before=triangles;
#endif
    for(unsigned i=0;i<bg_vehicle_count;i++)if(vehicle_view_lods[p][i]){
        bg_vehicle*v=&bg_vehicles[i];
        bool wreck=!v->active;
        if(wreck){
            rdpq_sync_pipe();rdpq_set_prim_color(RGBA32(75,70,66,255));
            rdpq_mode_combiner(RDPQ_COMBINER1((SHADE,0,PRIM,0),(0,0,0,1)));
        }
        if(wreck&&(v->kind==BG_V_GHOST||v->kind==BG_V_BANSHEE)&&vehicle_view_lods[p][i]<3){
            unsigned m=v->kind==BG_V_BANSHEE;
            /* Burned source shaders already supply the correct diffuse colors. */
            rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
            t3d_matrix_set(&vehicle_matrices[slot][i],true);rspq_block_run(covenant_wreck_blocks[m]);
            triangles+=bg_covenant_wrecks[m].triangle_count;
#ifdef BG_PROFILE
            submitted_vertices+=model_load_count(&bg_covenant_wrecks[m],bg_covenant_wrecks[m].vertex_count,0,bg_covenant_wrecks[m].batch_count);
#endif
        }else
        if(vehicle_view_lods[p][i]>=2){
            bool micro=vehicle_view_lods[p][i]==3;
            t3d_matrix_set(&vehicle_matrices[slot][i],true);rspq_block_run(micro?vehicle_micro_blocks[v->kind]:vehicle_lods[v->kind]);
            triangles+=micro?bg_vehicle_micro_lods[v->kind]->triangle_count:bg_vehicle_lods[v->kind].triangle_count;
#ifdef BG_PROFILE
            submitted_vertices+=micro?vehicle_micro_vertex_loads[v->kind]:vehicle_vertex_loads[v->kind];
#endif
        }else{
            const bg_vehicle_rig*rig=&bg_vehicle_rigs[v->kind];
            for(unsigned j=0;j<rig->count;j++){
                if(!visible_bounds(vp,&vehicle_part_bounds[i][j]))continue;
                t3d_matrix_set(&part_matrices[slot][i][j],true);rspq_block_run(vehicle_parts[v->kind][j]);
                triangles+=rig->parts[j].count/3;
#ifdef BG_PROFILE
                submitted_vertices+=part_vertex_loads[v->kind][j];
#endif
            }
        }
        if(wreck){rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);}
    }
#ifdef BG_PROFILE
    category_triangles[1]+=triangles-before;before=triangles;
#endif
    for(unsigned j=0;j<views;j++){
        if(body_lods[p][j]||(held_masks[p]&(1u<<j)))ensure_player_animation(j);
        if(body_lods[p][j]){
            bool lod=body_lods[p][j]==2;
            float shield=bg_shield_glow(&bg_players[j]);
            if(shield>0){
                /* One-pass bounded color glow: no duplicate skinned shell,
                 * extra triangles, transparent sorting, or z fighting. */
                unsigned intensity=(unsigned)(shield*(.48f+.04f*sinf(game_time*31+j))*255);
                rdpq_sync_pipe();rdpq_set_prim_color(RGBA32(255,139,62,intensity));
                rdpq_mode_combiner(RDPQ_COMBINER1((PRIM,SHADE,PRIM_ALPHA,SHADE),(0,0,0,SHADE)));
            }
            t3d_matrix_set(&transforms[slot][j],true);rspq_block_run(lod?armor_lod_blocks[slot][j]:player_blocks[slot][j]);
            triangles+=lod?bg_spartan_lod.triangle_count:bg_model_assets[BG_M_SPARTAN].triangle_count;
            if(shield>0){rdpq_sync_pipe();rdpq_mode_combiner(RDPQ_COMBINER_SHADE);}
#ifdef BG_PROFILE
            submitted_vertices+=lod?spartan_lod_vertex_loads:model_vertex_loads[BG_M_SPARTAN];
#endif
        }
        if(held_masks[p]&(1u<<j))small_model_instance(weapon_model(bg_players[j].weapon),&held_matrices[slot][j],vp,&eye,player->zoom!=0,NULL);
    }
#ifdef BG_PROFILE
    category_triangles[2]+=triangles-before;before=triangles;
#endif
    for(unsigned i=0;i<bg_pickup_count;i++){
        bg_pickup*q=&bg_pickups[i];if(!pickup_visible[p][i])continue;
        unsigned model=pickup_model(q->weapon);
        small_model_instance(model,&pickup_matrices[slot][i],vp,&eye,player->zoom!=0,&pickup_micro_spheres[i]);
    }
#ifdef BG_PROFILE
    category_triangles[3]+=triangles-before;before=triangles;
#endif
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH);
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q||!q->active||!visible_bounds(vp,&projectile_bounds[i]))continue;
        if(q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE){instance(q->kind==BG_P_FRAG?BG_M_FRAG:BG_M_PLASMA_GRENADE,&projectile_matrices[slot][i]);continue;}
        t3d_matrix_set(&projectile_matrices[slot][i],true);rspq_block_run(particle_blocks[q->kind]);triangles+=8;
#ifdef BG_PROFILE
        submitted_vertices+=24;
#endif
    }
    for(unsigned i=0;i<12;i++)if(explosions[i].life>0&&visible_bounds(vp,&explosion_bounds[i])){
        unsigned particle=explosions[i].kind==BG_EXPLOSION_NEEDLER?BG_P_NEEDLE:6;
        t3d_matrix_set(&explosion_matrices[slot][i],true);rspq_block_run(particle_blocks[particle]);triangles+=8;
#ifdef BG_PROFILE
        submitted_vertices+=24;
#endif
    }
    unsigned fx_triangles=bg_fx_draw_trails(game_time);
    for(unsigned j=0;j<views;j++)if(held_masks[p]&(1u<<j))
        fx_triangles+=bg_fx_draw_weapon(j,&held_matrices[slot][j],BG_OBJECT_SCALE,false,game_time);
    fx_triangles+=bg_fx_draw_vehicle_destruction();
    fx_triangles+=bg_fx_draw_shield_breaks(p);
    triangles+=fx_triangles;
#ifdef BG_PROFILE
    submitted_vertices+=fx_triangles*2;
#endif
#ifdef BG_PROFILE
    object_us+=get_ticks_us()-begin-(animation_us-animation_before);begin=get_ticks_us();
    animation_before=animation_us;
    category_triangles[4]+=triangles-before;before=triangles;
#endif
    if(player->health>0&&bg_player_personal_weapon(player)&&!bg_player_third_person(player)&&!player->zoom
#ifdef BG_INTERACTION_QA
       &&BG_INTERACTION_QA<2
#endif
#ifdef BG_SHIELD_QA
       &&false
#endif
#ifdef BG_DESTRUCTION_QA
       &&false /* Inspection cameras omit the viewmodel, preserving world effects. */
#endif
#ifdef BG_MODEL_QA
       &&model_qa_firstperson()
#endif
    ){
        ensure_firstperson_animation(p);
        float pos[3]={eye.v[0]/BG_SCALE,eye.v[1]/BG_SCALE+sinf(player->gait)*.007f,eye.v[2]/BG_SCALE};
        matrix(&guns[slot][p],BG_SCALE/BG_FP_SCALE,player->yaw,player->pitch,pos);data_cache_hit_writeback(&guns[slot][p],sizeof(T3DMat4FP));
        /* Clear only this viewport's depth so the gun stays in front of the world,
         * while its own surfaces and hands still occlude each other. */
        rdpq_clear_z(ZBUF_MAX);
        t3d_viewport_attach(&gun_viewports[slot][p]);
        t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);rdpq_mode_zbuf(true,true);
        t3d_segment_set(T3D_SEGMENT_1,firstperson[slot][p]);
        t3d_matrix_set(&guns[slot][p],true);rspq_block_run(firstperson_blocks[player->weapon]);triangles+=bg_fp_models[player->weapon].triangle_count;
#ifdef BG_PROFILE
        submitted_vertices+=fp_vertex_loads[player->weapon];
#endif
        if(player->weapon==BG_W_AR){
            bg_fp_ammo_draw(slot,p);triangles+=4;
#ifdef BG_PROFILE
            submitted_vertices+=8;
#endif
        }
        const bg_fp_detail_asset*detail=&bg_fp_details[player->weapon];
        if(detail->vertices){
            /* Thin weapon display topology, with finer coordinates and real
             * depth testing. It remains occluded by the gun/hands in motion. */
            matrix(&scope_matrices[slot][p],BG_SCALE/4096.f,player->yaw,player->pitch,pos);
            data_cache_hit_writeback(&scope_matrices[slot][p],sizeof(T3DMat4FP));
            t3d_matrix_set(&scope_matrices[slot][p],true);
            t3d_vert_load(scope_vertices[slot][p],0,(detail->vertices+1)&~1u);
            for(unsigned v=0;v<detail->triangles*3;v+=3)
                t3d_tri_draw(detail->indices[v],detail->indices[v+1],detail->indices[v+2]);
            t3d_tri_sync();triangles+=detail->triangles;
#ifdef BG_PROFILE
            submitted_vertices+=detail->vertices;
#endif
        }
        unsigned flash_triangles=bg_fx_draw_weapon(p,&guns[slot][p],BG_FP_SCALE,true,game_time);
        triangles+=flash_triangles;
#ifdef BG_PROFILE
        submitted_vertices+=flash_triangles*2;
#endif
    }
#ifdef BG_PROFILE
    fp_us+=get_ticks_us()-begin-(animation_us-animation_before);
    category_triangles[5]+=triangles-before;
#endif
    /* Restore depth zero before the next viewport replaces camera/projection. */
    t3d_matrix_pop(1);
}
#ifndef BG_SNAPSHOT_TICK
static void draw_menu(void){
    bg_menu_draw(&menu);
}
#endif
#ifndef BG_FRONTEND
static void draw_result(void){
    fill(66,45,188,146,RGBA32(12,27,56,255));fill(66,45,188,2,RGBA32(114,176,233,255));
    rdpq_set_mode_standard();rdpq_text_print(NULL,1,124,64,"GAME OVER");
    rdpq_text_printf(NULL,1,112,80,"PLAYER %d WINS",bg_match_winner()+1);
    for(unsigned p=0;p<views;p++){
        fill(83,90+p*17,5,9,colors[bg_player_profiles[p]]);rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,96,98+p*17,"PLAYER %u       %2d",p+1,bg_players[p].score);
    }
    rdpq_text_print(NULL,1,90,178,"START FOR MATCH OPTIONS");
}
#endif
#ifdef BG_BENCHMARK
static void benchmark_page(surface_t*screen,bool completed){
    rdpq_attach(screen,NULL);rdpq_set_mode_standard();
    rdpq_set_scissor(0,0,320,240);rdpq_clear(RGBA32(9,20,39,255));
    rdpq_text_print(NULL,1,8,16,completed?"RDP COMPLETION / 4-PLAYER":"CPU ACQUISITION / 4-PLAYER");
#ifdef BG_GPU_DIAGNOSTIC
    rdpq_text_print(NULL,1,8,38,"GPU DIAGNOSTIC / SERIALIZED");
#endif
    rdpq_text_printf(NULL,1,8,28,"%u MS MEASURED / 1S WARMUP",(unsigned)((completed?completed_cadence.result[0].elapsed:benchmark.result[0].elapsed)/1000));
    const char*labels[]={"ALL FRAMES","COMBAT","VEHICLES"};
    for(unsigned g=0;g<3;g++){
        bg_benchmark_result completion={0};
        if(completed){
            const bg_cadence_result*c=&completed_cadence.result[g];
            completion.elapsed=c->elapsed;completion.frames=c->frames;
            completion.minimum=c->minimum;completion.maximum=c->maximum;
            completion.p95=c->p95;completion.slow_frames=c->slow_frames;
        }
        const bg_benchmark_result*r=completed?&completion:&benchmark.result[g];
        unsigned average=r->frames?r->elapsed/r->frames:0;
        unsigned fps10=r->elapsed?(uint64_t)r->frames*10000000/r->elapsed:0;
        int y=48+g*42;
        rdpq_text_printf(NULL,1,8,y,"%s: %u FRAMES / %u.%u FPS",labels[g],r->frames,fps10/10,fps10%10);
        rdpq_text_printf(NULL,1,8,y+12,"AVG %u.%u  P95 %u.%u  MAX %u.%u MS",average/1000,(average/100)%10,
            r->p95/1000,(r->p95/100)%10,r->maximum/1000,(r->maximum/100)%10);
        rdpq_text_printf(NULL,1,8,y+24,"MIN %u.%u MS / >33.33MS: %u",r->minimum/1000,(r->minimum/100)%10,r->slow_frames);
        debugf("BENCH %s group=%s frames=%u elapsed_us=%llu avg_us=%u min_us=%u p95_us=%u max_us=%u over_33333=%u triangles_avg=%u triangles_max=%u vertices_avg=%u vertices_max=%u\n",
            completed?"rdp_completed":"cpu_acquisition",labels[g],r->frames,(unsigned long long)r->elapsed,average,r->minimum,r->p95,r->maximum,r->slow_frames,
            r->frames?(unsigned)(r->triangles/r->frames):0,r->max_triangles,r->frames?(unsigned)(r->vertices/r->frames):0,r->max_vertices);
    }
    if(completed){
        rdpq_text_print(NULL,1,8,180,"TIMESTAMP AT RDP FULL-SYNC CALLBACK");
#ifdef BG_PACED30
        rdpq_text_print(NULL,1,8,192,"EXPERIMENT: TWO-RETRACE FIFO");
#else
        rdpq_text_print(NULL,1,8,192,"DISPLAY_SHOW PIPELINE UNCHANGED");
#endif
        rdpq_text_print(NULL,1,8,204,"NOT A VI SCANOUT MEASUREMENT");
        rdpq_text_print(NULL,1,8,228,"TAIL PAGE IN 8S / A TO SWITCH");
        if(completed_cadence.overflow)rdpq_text_print(NULL,1,8,216,"CAPACITY EXCEEDED: P95 INVALID");
        return;
    }
    const bg_benchmark_result*r=&benchmark.result[0];
    unsigned average_phases[BG_BENCHMARK_PHASES];
    for(unsigned p=0;p<BG_BENCHMARK_PHASES;p++)average_phases[p]=r->frames?r->phase_us[p]/r->frames:0;
    rdpq_text_printf(NULL,1,8,180,"TRIANGLES AVG %u / MAX %u",r->frames?(unsigned)(r->triangles/r->frames):0,r->max_triangles);
    rdpq_text_printf(NULL,1,8,192,"SIM %u ANIM %u WORLD %u OBJ %u MS",average_phases[0]/1000,average_phases[2]/1000,average_phases[4]/1000,average_phases[5]/1000);
    rdpq_text_printf(NULL,1,8,204,"HUD %u AUDIO %u WAIT %u QUEUE %u",average_phases[7]/1000,average_phases[8]/1000,average_phases[9]/1000,average_phases[12]/1000);
#ifdef BG_GPU_DIAGNOSTIC
    rdpq_text_printf(NULL,1,8,216,"GPU WAIT RSP %u RDP %u MS",average_phases[10]/1000,average_phases[11]/1000);
#else
    rdpq_text_printf(NULL,1,8,216,"VERTICES AVG %u / MAX %u",r->frames?(unsigned)(r->vertices/r->frames):0,r->max_vertices);
#endif
    unsigned cats[BG_BENCHMARK_CATEGORIES];for(unsigned c=0;c<BG_BENCHMARK_CATEGORIES;c++)cats[c]=r->frames?r->category_triangles[c]/r->frames:0;
    rdpq_text_print(NULL,1,8,228,"RDP PAGE IN 8S / A TO SWITCH");
    if(benchmark.overflow)rdpq_text_print(NULL,1,8,234,"SAMPLE CAPACITY EXCEEDED: P95 INVALID");
    debugf("BENCH phase_us sim=%u camera=%u animation=%u matrix=%u world=%u objects=%u firstperson=%u hud=%u audio=%u wait=%u geometry_rsp_wait=%u geometry_rdp_wait=%u queue_stall=%u overflow=%u\n",
        average_phases[0],average_phases[1],average_phases[2],average_phases[3],average_phases[4],average_phases[5],average_phases[6],average_phases[7],average_phases[8],average_phases[9],average_phases[10],average_phases[11],average_phases[12],benchmark.overflow);
    debugf("BENCH triangles world=%u vehicles=%u bodies_held=%u pickups=%u effects=%u firstperson=%u\n",cats[0],cats[1],cats[2],cats[3],cats[4],cats[5]);
}
static void benchmark_tail_page(surface_t*screen,unsigned first){
    rdpq_attach(screen,NULL);rdpq_set_mode_standard();
    rdpq_set_scissor(0,0,320,240);rdpq_clear(RGBA32(9,20,39,255));
    rdpq_text_printf(NULL,1,8,16,"SLOWEST RDP COMPLETIONS / %u-%u",first+1,first+4);
    rdpq_text_print(NULL,1,8,28,"SCENE AT COMPLETING FRAME / 4 VIEWS");
    for(unsigned i=first;i<first+4&&i<completed_tail.count;i++){
        const bg_cadence_tail_entry*entry=&completed_tail.entry[i];
        const bg_cadence_frame*f=&entry->frame;const unsigned*c=f->category_triangles;
        int y=46+(i-first)*40;
        rdpq_text_printf(NULL,1,8,y,"#%u %u.%uMS T%u.%uS VERT%u",i+1,entry->elapsed/1000,(entry->elapsed/100)%10,
            f->sim_ms/1000,(f->sim_ms/100)%10,f->vertices);
        rdpq_text_printf(NULL,1,8,y+12,"TRI %u W%u V%u B%u",f->triangles,c[0],c[1],c[2]);
        rdpq_text_printf(NULL,1,8,y+24,"P%u E%u F%u / M%X Z%X D%X",c[3],c[4],c[5],
            (unsigned)f->vehicle_mask,(unsigned)f->zoom_mask,(unsigned)f->dead_mask);
        debugf("BENCH rdp_tail rank=%u interval_us=%u sim_ms=%u vertices=%u triangles=%u world=%u vehicles=%u bodies_held=%u pickups=%u effects=%u firstperson=%u mounted_mask=%u zoom_mask=%u dead_mask=%u\n",
            i+1,entry->elapsed,f->sim_ms,f->vertices,f->triangles,c[0],c[1],c[2],c[3],c[4],c[5],
            (unsigned)f->vehicle_mask,(unsigned)f->zoom_mask,(unsigned)f->dead_mask);
    }
    rdpq_text_print(NULL,1,8,204,"M MOUNTED / Z ZOOM / D DEAD");
    rdpq_text_print(NULL,1,8,216,"MASK BITS 1/2/4/8 = PLAYERS 1/2/3/4");
    rdpq_text_print(NULL,1,8,228,"NEXT PAGE IN 8S / A TO SWITCH");
}
#endif
#ifdef BG_VI_MEASURE
static void benchmark_vi_page(surface_t*screen){
    rdpq_attach(screen,NULL);rdpq_set_mode_standard();
    rdpq_set_scissor(0,0,320,240);rdpq_clear(RGBA32(9,20,39,255));
#if defined(BG_VI_BENCHMARK) && defined(BG_PACED30)
    rdpq_text_printf(NULL,1,8,16,"QUIET VI / PACED30 / %u BUFFERS",(unsigned)BG_PACED30_BUFFERS);
#elif defined(BG_VI_BENCHMARK)
    rdpq_text_print(NULL,1,8,16,"QUIET VI ONLY / UNPACED");
#elif defined(BG_PACED30)
    rdpq_text_print(NULL,1,8,16,"VI FRESH POSES / PACED30 EXPERIMENT");
#else
    rdpq_text_print(NULL,1,8,16,"VI FRESH POSES / UNPACED");
#endif
    rdpq_text_printf(NULL,1,8,28,"%u MS / 1S WARMUP / 2 VI TARGET",
        (unsigned)(visible_meter.fresh.result[0].elapsed/1000));
    const char*labels[]={"ALL","COMBAT","VEHICLES"};
    for(unsigned g=0;g<3;g++){
        const bg_cadence_result*c=&visible_meter.fresh.result[g];
        const bg_vi_result*r=&visible_meter.result[g];
        unsigned fps10=c->elapsed?(uint64_t)c->frames*10000000/c->elapsed:0;
        int y=48+g*42;
        rdpq_text_printf(NULL,1,8,y,"%s: %u POSES / %u.%u FPS",labels[g],c->frames,fps10/10,fps10%10);
        rdpq_text_printf(NULL,1,8,y+12,"P95 %u.%u MAX %u.%u MS / MAX %u VI",
            c->p95/1000,(c->p95/100)%10,c->maximum/1000,(c->maximum/100)%10,r->max_gap);
        rdpq_text_printf(NULL,1,8,y+24,"1VI %u  2VI %u  >2VI %u",r->gap_one,r->gap_two,r->gap_long);
        debugf("BENCH vi_fresh group=%s frames=%u elapsed_us=%llu p95_us=%u max_us=%u gap1=%u gap2=%u gap_long=%u max_gap=%u flips=%u duplicate_poses=%u skipped_poses=%u deadlines=%u missed=%u sample_latency_avg=%u sample_latency_max=%u ready_wait_avg=%u ready_wait_max=%u\n",
            labels[g],c->frames,(unsigned long long)c->elapsed,c->p95,c->maximum,
            r->gap_one,r->gap_two,r->gap_long,r->max_gap,r->flips,r->duplicates,r->skipped_poses,r->due,r->missed,
            c->frames?(unsigned)(r->latency_us/c->frames):0,r->max_latency_us,
            c->frames?(unsigned)(r->ready_wait_us/c->frames):0,r->max_ready_wait_us);
    }
    const bg_cadence_result*c=&visible_meter.fresh.result[0];const bg_vi_result*r=&visible_meter.result[0];
    unsigned latency=c->frames?r->latency_us/c->frames:0,ready=c->frames?r->ready_wait_us/c->frames:0;
    rdpq_text_printf(NULL,1,8,180,"BUFFER FLIPS %u / SAME POSE %u",r->flips,r->duplicates);
    rdpq_text_printf(NULL,1,8,192,"SAMPLE->VI AVG %u MAX %u MS",latency/1000,r->max_latency_us/1000);
    rdpq_text_printf(NULL,1,8,204,"READY->VI AVG %u MAX %u MS",ready/1000,r->max_ready_wait_us/1000);
    unsigned dropped=0;
#ifdef BG_PACED30
    dropped=paced_dropped_ticks;
#endif
    rdpq_text_printf(NULL,1,8,216,"MISS %u / POSE SKIP %u / DROP %u",r->missed,r->skipped_poses,dropped);
    debugf("BENCH paced_catchup_dropped_ticks_total=%u (includes warmup; original seven-tick catch-up ceiling)\n",dropped);
#ifdef BG_BENCHMARK
    rdpq_text_printf(NULL,1,8,228,"PUMP GAP MAX %u.%u MS / VI ORIGIN",
        (unsigned)(audio_pump_max_gap/1000),(unsigned)((audio_pump_max_gap/100)%10));
    debugf("BENCH audio_pump_max_entry_gap_us=%u (after warmup; not SDK queue occupancy)\n",(unsigned)audio_pump_max_gap);
#else
#ifdef BG_PRESENT_TRACK
    rdpq_text_printf(NULL,1,8,228,"QPEAK H%u R%u S%u / FREE%uK",result_held_peak,
        result_ready_peak,result_outstanding_peak,result_heap_free/1024);
#else
    rdpq_text_printf(NULL,1,8,228,"HELD PEAK %u / LIVE FREE %uK",result_held_peak,result_heap_free/1024);
#endif
#endif
}
static void benchmark_results(surface_t*screen){
    /* Snapshot queue peaks before teardown releases every held frame at once.
     * These are whole-run peaks, including warmup. Heap is live, with audio and
     * the result screen still allocated; no per-frame allocator walk occurs. */
    heap_stats_t result_heap;sys_get_heap_stats(&result_heap);
    result_heap_free=result_heap.total-result_heap.used;
#ifdef BG_PACED30
    disable_interrupts();result_held_peak=presenter.peak;
#ifdef BG_PRESENT_TRACK
    result_ready_peak=present_tracker.peak_ready;
    result_outstanding_peak=present_tracker.peak_outstanding;
#endif
    enable_interrupts();
#endif
    debugf("BENCH display_buffers=%u held_peak=%u live_heap_free_bytes=%u (whole-run peak including warmup; before teardown)\n",
        (unsigned)BG_PACED30_BUFFERS,result_held_peak,result_heap_free);
#ifdef BG_PRESENT_TRACK
    debugf("BENCH sdk_ready_peak=%u submitted_not_presented_peak=%u (excludes currently acquired unsubmitted surface)\n",
        result_ready_peak,result_outstanding_peak);
#endif
    /* The ISR stops writing before publication; sorting happens only here. */
#ifdef BG_BENCHMARK
    bg_benchmark_finish(&benchmark);bg_cadence_finish(&completed_cadence);
#endif
    bg_cadence_finish(&visible_meter.fresh);
#ifdef BG_PACED30
    /* Flush existing callbacks before handing every retained surface back to
     * ordinary FIFO presentation. No locked surface is abandoned at results. */
    rspq_wait();presentation_mode(false);
    disable_interrupts();unregister_VI_handler(paced_vi);enable_interrupts();
#endif
    audio_close();
#ifdef BG_BENCHMARK
    unsigned page=0;
#endif
    for(;;){
#ifdef BG_BENCHMARK
        if(page<2)benchmark_page(screen,page==1);
        else if(page<4)benchmark_tail_page(screen,(page-2)*4);
        else benchmark_vi_page(screen);
#else
        benchmark_vi_page(screen);
#endif
        rdpq_detach_show();rspq_wait();
        uint64_t next_page=get_ticks_us()+8000000;
        do {wait_ms(20);joypad_poll();}
        while(!joypad_get_buttons_pressed(0).a&&get_ticks_us()<next_page);
#ifdef BG_BENCHMARK
        page=(page+1)%5;
#endif
        screen=display_get();
    }
}
#endif
int main(void){
    debug_init_isviewer();debug_init_usblog();
#ifdef BG_BLAM_BSP
    assertf(get_memory_size()>=8*1024*1024,"Original Blam BSP requires an 8 MiB Expansion Pak");
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PRESENT_TRACK)
    register_VI_handler(observe_vi);
#endif
    display_init(RESOLUTION_320x240,DEPTH_16_BPP,BG_PACED30_BUFFERS,GAMMA_NONE,FILTERS_RESAMPLE);
#ifdef BG_PACED30
    assertf(get_tv_type()!=TV_PAL,"Experimental paced30 requires NTSC/MPAL (60 Hz)");
    register_VI_handler(paced_vi);
#endif
    joypad_init();rdpq_init();
#ifdef RDPQ_VALIDATE
    FILE*original_log=stderr;stderr=funopen(original_log,NULL,validation_write,NULL,NULL);
    assertf(stderr,"Validation log allocation");setvbuf(stderr,NULL,_IONBF,0);
    rdpq_debug_start();
#endif
    t3d_init((T3DInitParams){});
    bg_fp_ammo_init();
    bg_fx_draw_init();
    rdpq_text_register_font(1,rdpq_font_load_builtin(FONT_BUILTIN_DEBUG_VAR));
    bg_menu_init(&menu,views);
#ifdef BG_SCORES_BENCHMARK
    for(unsigned p=0;p<4;p++)menu.styles[p]=BG_CONTROLS_XBOX;
#endif
#ifndef BG_SNAPSHOT_TICK
    bg_menu_draw_init();
#endif
    surface_t depth=surface_alloc(FMT_RGBA16,320,240);init_scene();bg_hud_init();bg_reset();bg_set_players(views);bg_sound_init();
    assertf(dfs_init(DFS_DEFAULT_LOCATION)==DFS_ESUCCESS,"Game filesystem");
#ifdef BG_FRONTEND
    bg_front_init(&front);paused=true;bg_vehicle_world_release();firstperson_buffers_release();bg_sound_frontend(true);
#endif
#ifdef BG_SNAPSHOT_TICK
    /* No rendering or wall-clock scheduling during this advance. Presentation
     * state follows every tick, including recoil timestamps, explosions and
     * wheel rotations; the final state is then rendered indefinitely. */
    views=4;game_time=0;reset_view_state();
    for(uint32_t tick=0;tick!=(uint32_t)BG_SNAPSHOT_TICK;tick++){
        bg_replay_snapshot_tick(&game_time);
        update_effects(BLAM_TICK_SECONDS);bg_sound_update();
    }
    debugf("SNAPSHOT fixed_ticks=%u game_time=%.9g / frozen pixel QA, not FPS proof\n",
        (unsigned)BG_SNAPSHOT_TICK,game_time);
#endif
#ifdef BG_SHOWCASE
    bg_showcase_begin(BG_SHOWCASE);views=bg_showcase_views();menu.player_count=views;
#endif
#ifdef BG_INTERACTION_QA
    interaction_qa_stage();
#endif
#ifdef BG_SHIELD_QA
    shield_fixture_stage(BG_SHIELD_QA);game_time=bg_match_time();
    for(unsigned p=0;p<4;p++)debugf("SHIELD P%u vitality=%.2f hit=%.2f break=%.2f charge=%d overcharge=%d health=%d\n",p,bg_players[p].shield,bg_players[p].shield_hit,bg_players[p].shield_break,bg_players[p].shield_charging,bg_players[p].shield_overcharging,bg_players[p].health);
#endif
    heap_stats_t heap;sys_get_heap_stats(&heap);
    debugf("HALO N64 world=%u textures=%u RAM=%d free=%d\n",bg_collision_count,bg_material_count,get_memory_size(),heap.total-heap.used);
    uint64_t previous=get_ticks_us(),fps_time=previous;unsigned frames=0;
#ifndef BG_SNAPSHOT_TICK
    blam_clock clock;blam_clock_reset(&clock);
    bg_input latch[4]={0};
#ifdef BG_PACED30
    bool first_pose=true;uint64_t ui_deadline=0;
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
    uint64_t last_acquisition=previous;
#endif
#endif
#endif
    while(1){
#ifdef BG_PROFILE
        uint64_t profile_start=get_ticks_us();
        camera_us=animation_us=matrix_us=world_us=object_us=fp_us=hud_us=audio_us=0;
        geometry_rsp_us=geometry_rdp_us=0;memset(category_triangles,0,sizeof(category_triangles));
        animated_vertices=animated_tracks=0;
#endif
#ifdef BG_PACED30
        unsigned ticks;bg_input in[4]={0};
        surface_t*screen=paced_acquire(&clock,&previous,latch,in,&ticks,&first_pose,&ui_deadline);
#else
        surface_t*screen;while(!(screen=display_try_get()))pump_audio();
#endif
#ifdef BG_PROFILE
        wait_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        uint64_t now=get_ticks_us();
#ifdef BG_MODEL_QA
        model_qa_stage(now);
#endif
#ifndef BG_SNAPSHOT_TICK
#ifdef BG_VI_BENCHMARK
        /* Only the actual VI observer measures this run. No CPU/RDP cadence,
         * per-draw counters or audio polling timestamps execute in this mode. */
        if(bg_vi_complete(&visible_meter))benchmark_results(screen);
#endif
#ifndef BG_PACED30
        float dt=(now-previous)*.000001f;
#endif
#ifdef BG_BENCHMARK
        if(!benchmark_origin)benchmark_origin=now;
        if(benchmark_previous>=benchmark_origin+1000000&&benchmark.result[0].elapsed<75000000)
            bg_benchmark_add(&benchmark,now-benchmark_previous,benchmark_vehicle,benchmark_triangles,benchmark_vertices,benchmark_phases,benchmark_categories);
        if(benchmark.result[0].elapsed>=75000000&&bg_cadence_complete(&completed_cadence)&&bg_vi_complete(&visible_meter))
            benchmark_results(screen);
        benchmark_previous=now;
#endif
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
#ifdef BG_PACED30
        if(frames||frame_time_count)profile_frame_time(now-last_acquisition);
        last_acquisition=now;
#else
        if(frames||frame_time_count)profile_frame_time(now-previous);
#endif
#endif
#ifndef BG_PACED30
        previous=now;
        bg_input in[4]={0};if(input(in))memset(latch,0,sizeof(latch));clock.paused=paused;
        for(unsigned p=0;p<4;p++){
#define EDGE(field) latch[p].field|=in[p].field;in[p].field=latch[p].field
            EDGE(jump);EDGE(reload);EDGE(switch_weapon);EDGE(grenade);EDGE(switch_grenade);EDGE(melee);EDGE(zoom);
#undef EDGE
        }
        unsigned ticks=blam_clock_update(&clock,dt);
#endif
        for(unsigned t=0;t<ticks;t++){
#ifdef BG_DEMO
            bg_replay_input(in,game_time);views=4;bg_set_players(4);
#endif
#ifdef BG_SHOWCASE
            bg_showcase_input(in,game_time);views=bg_showcase_views();
#endif
#ifdef BG_FRONTEND_QA
            bg_front_qa_tick(in,game_time);
#endif
#ifdef BG_EFFECTS_QA
            bg_effects_qa_input(in,game_time);views=4;bg_set_players(4);
#endif
#ifdef BG_DESTRUCTION_QA
            bg_destruction_qa_input(in,game_time);views=4;bg_set_players(4);
#endif
#ifdef BG_MOVEMENT_QA
            movement_qa_input(in,game_time);
#endif
            bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);game_time+=BLAM_TICK_SECONDS;
#ifdef BG_SHOWCASE
            bg_showcase_observe();
#endif
            update_effects(BLAM_TICK_SECONDS);bg_sound_update();
            for(unsigned p=0;p<4;p++){
                if(bg_players[p].vehicle<0)in[p].jump=false;
                in[p].reload=in[p].switch_weapon=in[p].grenade=in[p].switch_grenade=in[p].melee=in[p].zoom=false;
            }
            memset(latch,0,sizeof(latch));
        }
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
        simulation_pose=clock.ticks;
#ifndef BG_PACED30
        frame_sample_us=now;
#endif
#endif
#endif
#ifdef BG_PROFILE
        sim_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
#ifdef BG_FRONTEND
        if(!front_active()&&bg_match_finished()){
            if(!match_ended)match_ended=now;
            if(now-match_ended>=2500000){
                int final_scores[4];for(unsigned p=0;p<4;p++)final_scores[p]=bg_players[p].score;
                bg_front_results(&front,final_scores,bg_match_winner());front.statistics=*bg_match_stats();menu.open=false;paused=true;bg_vehicle_world_release();firstperson_buffers_release();body_buffers_release();bg_sound_frontend(true);
            }
        }
        if(front_active()){
            bg_interaction_render_release();
#ifdef BG_PACED30
            presentation_mode(false);
#endif
            bg_vehicle_world_release();
            rdpq_attach(screen,&depth);rdpq_clear_z(ZBUF_MAX);bg_front_draw(&front,now);pump_audio();
#ifdef BG_FRONTEND_QA
            sys_get_heap_stats(&heap);rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,215,"LIVE HEAP %uK",(heap.total-heap.used)/1024);
            rdpq_text_printf(NULL,1,4,237,"SCRIPTED FRONTEND %u/%u%s",bg_front_qa_step()+1,bg_front_qa_steps(),bg_front_qa_done()?" PASS":"");
#ifdef RDPQ_VALIDATE
            rdpq_text_printf(NULL,1,4,226,"RDP %u ERRORS %u WARNINGS",validation_errors,validation_warnings);
            if(validation_errors||validation_warnings)rdpq_text_print(NULL,1,4,215,validation_message);
#endif
#endif
#ifdef BG_PACED30
            frame_present(screen,0);
#else
            rdpq_detach_show();
#endif
            continue;
        }
#endif
        body_buffers_load();firstperson_buffers_load();
        if(pending[slot])while(!rspq_syncpoint_check(fences[slot]))pump_audio();
#ifdef BG_PROFILE
        wait_us+=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        /* Frame preparation only writes the fenced geometry slot on the CPU.
         * Begin this frame's ordered depth clear while those matrices/vertices
         * are prepared; clear_z's nested detach already wakes the RSP. */
        rdpq_attach(screen,&depth);rdpq_clear_z(ZBUF_MAX);
#ifdef BG_PROFILE
        uint64_t attach_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        if(views==3)rdpq_clear(RGBA32(0,0,0,255));
        prepare_frame();
#ifdef BG_PROFILE
        prep_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        triangles=0;
#ifdef BG_PROFILE
        submitted_vertices=0;
#endif
        for(unsigned p=0;p<views;p++){
            draw_view(p);
            /* Submit each completed view before mixing audio. This is a
             * nonblocking wakeup, not a fence or a new RDP command. */
            rspq_flush();pump_audio();
        }
#ifdef BG_GPU_DIAGNOSTIC
        uint64_t geometry_begin=get_ticks_us();
#endif
        /* All RSP reads of this slot's vertices, matrices and viewports end
         * with the 3D pass. HUD rectangles are copied into commands on the
         * CPU; HUD textures/blocks are immutable and own no slot resources.
         * Release geometry before HUD work so the CPU can prepare its next
         * use while that work drains. RDP completion/display ownership still
         * belongs to detach below, independently of this RSP-only fence. */
        fences[slot]=rspq_syncpoint_new();pending[slot]=true;
#ifdef BG_GPU_DIAGNOSTIC
        /* Diagnostic-only serialization: separate pending 3D work from HUD
         * submission. These results are not the production FPS benchmark. */
        rspq_flush();
        while(!rspq_syncpoint_check(fences[slot]))pump_audio();
        geometry_rsp_us=get_ticks_us()-geometry_begin;geometry_begin=get_ticks_us();
        diagnostic_rdp_done=false;rdpq_sync_full(diagnostic_rdp_complete,NULL);rspq_flush();
        while(!diagnostic_rdp_done)pump_audio();
        geometry_rdp_us=get_ticks_us()-geometry_begin;
#endif
        /* Complete every 3D view before the HUD pass to keep sprite/text
         * submission together. HUD scissoring preserves each viewport. */
#ifdef BG_PROFILE
        uint64_t hud_begin=get_ticks_us();
#endif
        for(unsigned p=0;p<views;p++){
            T3DViewport*vp=&viewports[slot][p];
            bg_hud_draw(p,vp->offset[0],vp->offset[1],vp->size[0],vp->size[1],menu.styles[p]);
        }
#ifndef BG_SNAPSHOT_TICK
        for(unsigned p=0;p<views;p++)if(scores[p]){
            T3DViewport*vp=&viewports[slot][p];
            bg_scores_draw(p,vp->offset[0],vp->offset[1],vp->size[0],vp->size[1]);
        }
#endif
#ifdef BG_PROFILE
        hud_us=get_ticks_us()-hud_begin;
#endif
        rdpq_set_scissor(0,0,320,240);
        if(views>1)fill(0,119,320,2,RGBA32(0,0,0,255));
        if(views>=3)fill(159,0,2,240,RGBA32(0,0,0,255));
#if defined(BG_DEMO) && !defined(BG_VI_MEASURE) && !defined(BG_SNAPSHOT_TICK)
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,116,118,"REPLAY %u FPS",fps);
#endif
#ifdef BG_FRONTEND_QA
        sys_get_heap_stats(&heap);rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,215,"LIVE HEAP %uK",(heap.total-heap.used)/1024);
        rdpq_text_printf(NULL,1,4,237,"SCRIPTED FRONTEND COMBAT");
#endif
#ifdef BG_MOVEMENT_QA
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,237,"SCRIPTED | %s",movement_qa_title());
#endif
#ifdef BG_DESTRUCTION_QA
        rdpq_set_mode_standard();rdpq_text_print(NULL,1,4,237,bg_destruction_qa_label());
#endif
#ifdef BG_EFFECTS_QA
        rdpq_set_mode_standard();rdpq_text_print(NULL,1,4,237,bg_effects_qa_label());
#endif
#ifdef BG_MODEL_QA
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,237,"MODEL QA %u: %s",model_qa_page,model_qa_labels[model_qa_page]);
#endif
#ifdef BG_SHOWCASE
        fill(50,222,220,16,RGBA32(8,19,37,255));rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,56,233,"SCRIPTED | %s",bg_showcase_title());
        const char*caption=bg_showcase_caption();
        if(caption&&caption[0]){
            fill(50,207,220,14,RGBA32(8,19,37,255));rdpq_set_mode_standard();
            rdpq_text_print(NULL,1,56,218,caption);
        }
#endif
#ifdef BG_PROFILE
        draw_us=get_ticks_us()-profile_start+attach_us;profile_start=get_ticks_us();
#ifndef BG_BENCHMARK
        sys_get_heap_stats(&heap);rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,2,202,"C%u A%u X%u SND%u V%u/%u",camera_us/1000,animation_us/1000,matrix_us/1000,audio_us/1000,animated_tracks,animated_vertices);
        rdpq_text_printf(NULL,1,2,212,"WRL%u OBJ%u FP%u HUD%u",world_us/1000,object_us/1000,fp_us/1000,hud_us/1000);
        rdpq_text_printf(NULL,1,2,222,"FRAME %u MIN%u P95%u MAX%u",frame_average/1000,frame_minimum/1000,frame_p95/1000,frame_maximum/1000);
        rdpq_text_printf(NULL,1,2,232,"S%u P%u D%u W%u T%u M%d",sim_us/1000,prep_us/1000,draw_us/1000,wait_us/1000,triangles,(heap.total-heap.used)/1024);
#endif
#endif
#if defined(RDPQ_VALIDATE) && !defined(BG_MENU_QA)
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,215,"RDP %u ERRORS %u WARNINGS",validation_errors,validation_warnings);
        if(validation_errors||validation_warnings)rdpq_text_print(NULL,1,4,225,validation_message);
#endif
#ifndef BG_FRONTEND
        if(bg_match_finished())draw_result();
#endif
#ifndef BG_SNAPSHOT_TICK
        if(paused)draw_menu();
#endif
#ifdef BG_MENU_QA
        rdpq_set_mode_standard();
        fill(0,0,320,12,RGBA32(6,15,30,255));rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,4,9,"SCRIPTED MENU QA %u/40%s",bg_menu_qa_step()+1,bg_menu_qa_done()?" PASS":"");
#ifdef RDPQ_VALIDATE
        fill(0,228,320,12,RGBA32(6,15,30,255));rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,4,237,"RDP %u ERRORS %u WARNINGS",validation_errors,validation_warnings);
#endif
#endif
#ifdef BG_PROFILE
        overlay_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
        frame_present(screen,fmodf(game_time,75.f)>=36.f);
#else
        rdpq_detach_show();
#endif
        slot=(slot+1)%BG_FRAME_SLOTS;
#ifdef BG_PROFILE
        present_us=get_ticks_us()-profile_start;
#ifdef BG_RSPQ_OVERRIDE
        bg_rspq_metrics current_queue_metrics;bg_rspq_get_metrics(&current_queue_metrics);
        queue_us=current_queue_metrics.stall_us-previous_queue_metrics.stall_us;
        previous_queue_metrics=current_queue_metrics;
#endif
#endif
#ifdef BG_BENCHMARK
        benchmark_vehicle=fmodf(game_time,75.f)>=36.f;benchmark_triangles=triangles;benchmark_vertices=submitted_vertices;
        const unsigned phase_values[BG_BENCHMARK_PHASES]={sim_us,camera_us,animation_us,matrix_us,world_us,object_us,fp_us,hud_us,audio_us,wait_us,geometry_rsp_us,geometry_rdp_us,queue_us};
        memcpy(benchmark_phases,phase_values,sizeof(benchmark_phases));
        memcpy(benchmark_categories,category_triangles,sizeof(benchmark_categories));
#endif
        frames++;
        if(now-fps_time>=1000000){
            fps=frames*1000000ULL/(now-fps_time);frames=0;fps_time=now;
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
            sys_get_heap_stats(&heap);
            profile_frame_summary();
            debugf("PHASE camera=%u anim=%u matrix=%u world=%u objects=%u fp=%u hud=%u audio=%u overlay=%u present=%u queue=%u tracks=%u corners=%u frame_avg=%u frame_min=%u frame_p95=%u frame_max=%u samples=%u\n",camera_us,animation_us,matrix_us,world_us,object_us,fp_us,hud_us,audio_us,overlay_us,present_us,queue_us,animated_tracks,animated_vertices,frame_average,frame_minimum,frame_p95,frame_maximum,(unsigned)frame_time_count);
            debugf("PERF views=%u fps=%u triangles=%u free=%d audio=%d p1=(%.2f %.2f %.2f)\n",views,fps,triangles,heap.total-heap.used,audio_can_write(),
                bg_players[0].pos[0],bg_players[0].pos[1],bg_players[0].pos[2]);
#endif
        }
    }
}
