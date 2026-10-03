#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "game.h"

extern T3DVertPacked bg_vertices[], *bg_spartan, *bg_rifle;
extern uint16_t bg_textures[][32*32];
static const color_t colors[4] = {{241,91,67,255},{76,160,246,255},{227,199,79,255},{121,221,152,255}};
static surface_t textures[32];
static T3DVertPacked *armor[4];
static rspq_block_t *world_blocks[512], *player_blocks[4], *rifle_block;
static T3DViewport viewports[3][4] __attribute__((aligned(16)));
static T3DMat4FP transforms[3][4], guns[3][4];
static rspq_syncpoint_t fences[3];
static bool pending[3], tour;
static unsigned slot, views = 2, triangles, fps;
static float tour_time;

static rspq_block_t *record(T3DVertPacked *verts, unsigned count) {
    rspq_block_begin();
    for (unsigned first = 0; first < count; first += 60) {
        unsigned n = count-first > 60 ? 60 : count-first;
        t3d_vert_load(verts+first/2, 0, (n+1)&~1u);
        for (unsigned j=0; j<n; j+=3) t3d_tri_draw(j,j+1,j+2);
        t3d_tri_sync();
    }
    return rspq_block_end();
}

static void init_scene(void) {
    assertf(bg_chunk_count<=512 && bg_material_count<=32, "Asset capacity exceeded");
    data_cache_hit_writeback(bg_vertices, bg_vertex_count*16);
    data_cache_hit_writeback(bg_spartan, ((bg_spartan_vertices+1)&~1u)*16);
    data_cache_hit_writeback(bg_rifle, ((bg_rifle_vertices+1)&~1u)*16);
    for (unsigned i=0; i<bg_material_count; i++) {
        textures[i]=surface_make(bg_textures[i], FMT_RGBA16, 32, 32, 64);
        data_cache_hit_writeback(bg_textures[i], 2048);
    }
    for (unsigned i=0; i<bg_chunk_count; i++)
        world_blocks[i]=record(bg_vertices+bg_chunks[i].first/2,bg_chunks[i].count);
    for (unsigned p=0; p<4; p++) {
        unsigned bytes=((bg_spartan_vertices+1)/2)*sizeof(T3DVertPacked);
        armor[p]=malloc_uncached(bytes);
        memcpy(armor[p],bg_spartan,bytes);
        for (unsigned i=0; i<bg_spartan_vertices; i++) {
            uint32_t *rgba = i%2 ? &armor[p][i/2].rgbaB : &armor[p][i/2].rgbaA;
            unsigned r=*rgba>>24, g=(*rgba>>16)&255, b=(*rgba>>8)&255;
            if (r==g && g==b) *rgba=((r*colors[p].r/255)<<24)|((g*colors[p].g/255)<<16)|((b*colors[p].b/255)<<8)|255;
        }
        player_blocks[p]=record(armor[p],bg_spartan_vertices);
        for (unsigned f=0;f<3;f++) viewports[f][p]=t3d_viewport_create();
    }
    rifle_block=record(bg_rifle,bg_rifle_vertices);
}

static void input(bg_input in[4]) {
    joypad_poll();
    for (unsigned i=0;i<4;i++) {
        joypad_inputs_t stick=joypad_get_inputs(i);
        joypad_buttons_t held=joypad_get_buttons(i), pressed=joypad_get_buttons_pressed(i);
        float x=stick.stick_x/80.f,y=stick.stick_y/80.f;
        if (fabsf(x)<.12f) x=0;
        if (fabsf(y)<.12f) y=0;
        if (held.d_left) x=-1;
        if (held.d_right) x=1;
        if (held.d_up) y=1;
        if (held.d_down) y=-1;
        in[i]=(bg_input){.forward=y, .turn=-x, .strafe=held.c_right-held.c_left,
            .look=held.c_up-held.c_down, .jump=pressed.a, .fire=held.z, .reload=pressed.b};
        if (i==0) {
            if (pressed.start) {views=views==2?4:views==4?1:2;bg_set_players(views);}
            if (pressed.l) tour=!tour;
            if (pressed.r) bg_reset();
        }
    }
}

static void fill(int x,int y,int w,int h,color_t color) {
    rdpq_set_mode_fill(color);
    rdpq_fill_rectangle(x,y,x+w,y+h);
}

static void draw_view(unsigned p) {
    int w=views==4?160:320, h=views==1?208:104;
    int x=views==4?(p%2)*160:0, y=16+(views==4?p/2:p)*h;
    bg_player *player=&bg_players[p];
    float cp=cosf(player->pitch), sy=sinf(player->yaw),cy=cosf(player->yaw);
    T3DVec3 eye={{player->pos[0]*BG_SCALE,(player->pos[1]+.62f)*BG_SCALE,player->pos[2]*BG_SCALE}};
    T3DVec3 target={{eye.v[0]+cy*cp,eye.v[1]+sinf(player->pitch),eye.v[2]-sy*cp}};
    if (tour) {
        float angle=tour_time*.10f+p*1.57f;
        eye=(T3DVec3){{cosf(angle)*1450,1050,sinf(angle)*1850}};
        target=(T3DVec3){{0,100,0}};
    }
    T3DViewport *vp=&viewports[slot][p];
    t3d_viewport_set_area(vp,x,y,w,h);
    t3d_viewport_set_projection(vp,views==4?1.15f:.83f,2.f,6200.f);
    t3d_viewport_look_at(vp,&eye,&target,&(T3DVec3){{0,1,0}});
    t3d_viewport_attach(vp);
    rdpq_clear(RGBA32(154,190,212,255));
    t3d_frame_start();
    rdpq_mode_dithering(DITHER_NONE_NONE);
    t3d_light_set_ambient((uint8_t[]){255,255,255,255});
    t3d_light_set_count(0);
    unsigned bound=~0u;
    for (unsigned b=0;b<bg_chunk_count;b++) {
        const bg_chunk *c=&bg_chunks[b];
        if (!t3d_frustum_vs_aabb_s16(&vp->viewFrustum,c->bounds,c->bounds+3)) continue;
        if (bound!=c->material) {
            rdpq_tex_upload(TILE0,&textures[c->material],&(rdpq_texparms_t){.s.repeats=REPEAT_INFINITE,.t.repeats=REPEAT_INFINITE});
            rdpq_mode_tlut(TLUT_NONE);
            rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);
            rdpq_mode_persp(true);
            rdpq_mode_filter(FILTER_BILINEAR);
            /* Halo cache surfaces use the opposite front-face convention. */
            t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_TEXTURED|T3D_FLAG_CULL_FRONT);
            bound=c->material;
        }
        rspq_block_run(world_blocks[b]);
        triangles+=c->count/3;
    }
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_FRONT);
    for (unsigned j=0;j<views;j++) {
        if ((!tour && j==p)||bg_players[j].health<=0) continue;
        float *pos=bg_players[j].pos;
        int16_t a[3]={(pos[0]-.3f)*BG_SCALE,pos[1]*BG_SCALE,(pos[2]-.3f)*BG_SCALE};
        int16_t b[3]={(pos[0]+.3f)*BG_SCALE,(pos[1]+.8f)*BG_SCALE,(pos[2]+.3f)*BG_SCALE};
        if (!t3d_frustum_vs_aabb_s16(&vp->viewFrustum,a,b)) continue;
        t3d_matrix_push(&transforms[slot][j]);
        rspq_block_run(player_blocks[j]);
        t3d_matrix_pop(1);
        triangles+=bg_spartan_vertices/3;
    }
    if (!tour && player->health>0) {
        float recoil=player->flash>0?.025f:0, lower=player->reload>0?.16f:0;
        float gun_pos[3]={eye.v[0]+(cy*.22f+sy*.14f)*BG_SCALE,eye.v[1]-(.17f+lower)*BG_SCALE,eye.v[2]+(-sy*.22f+cy*.14f)*BG_SCALE};
        t3d_mat4fp_from_srt_euler(&guns[slot][p],(float[]){1.4f,1.4f,1.4f},(float[]){0,-player->yaw,-player->pitch-recoil},gun_pos);
        data_cache_hit_writeback(&guns[slot][p],sizeof(T3DMat4FP));
        t3d_matrix_push(&guns[slot][p]);
        rspq_block_run(rifle_block);
        t3d_matrix_pop(1);
    }
    fill(x,y,w,2,colors[p]);
    fill(x+6,y+7,54,5,RGBA32(24,32,37,255));
    fill(x+7,y+8,player->health/2,3,player->hurt>0?RGBA32(242,83,60,255):RGBA32(96,202,227,255));
    int cx=x+w/2,cy_screen=y+h/2;
    if (!tour) {
        color_t c=player->flash>0?RGBA32(255,207,93,255):RGBA32(153,230,233,255);
        fill(cx-5,cy_screen,3,1,c);fill(cx+3,cy_screen,3,1,c);
        fill(cx,cy_screen-5,1,3,c);fill(cx,cy_screen+3,1,3,c);
    }
    rdpq_set_mode_standard();
    rdpq_text_printf(NULL,1,x+6,y+h-6,"P%u %02d  K %d",p+1,player->ammo,player->score);
    if (player->health<=0) rdpq_text_print(NULL,1,cx-28,cy_screen,"RESPAWNING");
    else if (player->reload>0) rdpq_text_print(NULL,1,x+w-48,y+h-6,"RELOAD");
}

int main(void) {
    debug_init_isviewer();debug_init_usblog();
    display_init(RESOLUTION_320x240,DEPTH_16_BPP,3,GAMMA_NONE,FILTERS_RESAMPLE);
    joypad_init();rdpq_init();t3d_init((T3DInitParams){});
#ifdef RDPQ_VALIDATE
    rdpq_debug_start();
#endif
    rdpq_text_register_font(1,rdpq_font_load_builtin(FONT_BUILTIN_DEBUG_VAR));
    surface_t depth=surface_alloc(FMT_RGBA16,320,240);
    init_scene();bg_reset();
    heap_stats_t heap;sys_get_heap_stats(&heap);
    debugf("HALO N64 world=%u triangles textures=%u RAM=%d free=%d\n",bg_collision_count,bg_material_count,get_memory_size(),heap.total-heap.used);
    uint64_t previous=get_ticks_us(),fps_time=previous;
    unsigned accumulator=0,frames=0;
    bool jump_latch[4]={0},reload_latch[4]={0};
    while (1) {
        surface_t *screen=display_get();
        uint64_t now=get_ticks_us(),elapsed=now-previous;previous=now;
        accumulator+=elapsed>250000?250000:elapsed;
        bg_input in[4]={0};input(in);
#ifdef BG_DEMO
        /* Deterministic inputs exercise the same simulation as controllers.
         * This separate ROM is visibly marked REPLAY; the normal ROM is live. */
        unsigned phase=((unsigned)tour_time/10)%4;
        views=phase==1||phase==3?4:2;bg_set_players(views);
        tour=phase>=2;
        memset(in,0,sizeof(in));
        if (!tour) for (unsigned p=0;p<views;p++) {
            in[p].turn=p%2?-.18f:.23f;
            in[p].forward=.5f;
            in[p].fire=((unsigned)(tour_time*2)+p)%4==0;
            in[p].reload=bg_players[p].ammo==0;
        }
#endif
        /* Preserve button edges across render frames with no simulation step. */
        for (unsigned p=0;p<4;p++) {
            jump_latch[p]|=in[p].jump;reload_latch[p]|=in[p].reload;
            in[p].jump=jump_latch[p];in[p].reload=reload_latch[p];
        }
        while (accumulator>=16667) {
            bg_tick(in,1.f/60);tour_time+=1.f/60;accumulator-=16667;
            for (unsigned p=0;p<4;p++) {
                in[p].jump=in[p].reload=false;
                jump_latch[p]=reload_latch[p]=false;
            }
        }
        if (pending[slot]) rspq_syncpoint_wait(fences[slot]);
        for (unsigned p=0;p<4;p++) {
            float *pos=bg_players[p].pos;
            t3d_mat4fp_from_srt_euler(&transforms[slot][p],(float[]){1,1,1},(float[]){0,-bg_players[p].yaw,0},
                (float[]){pos[0]*BG_SCALE,pos[1]*BG_SCALE,pos[2]*BG_SCALE});
        }
        data_cache_hit_writeback(transforms[slot],sizeof(transforms[slot]));
        rdpq_attach(screen,&depth);rdpq_clear(RGBA32(17,26,30,255));rdpq_clear_z(ZBUF_MAX);
        triangles=0;
        for (unsigned p=0;p<views;p++) draw_view(p);
        rdpq_set_scissor(0,0,320,240);
        if (views==4) fill(159,16,2,208,RGBA32(17,26,30,255));
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,6,11,"HALO / BLOOD GULCH   %uP",views);
        rdpq_text_printf(NULL,1,272,11,"%u FPS",fps);
#ifdef BG_DEMO
        sys_get_heap_stats(&heap);
        rdpq_text_printf(NULL,1,6,235,"REPLAY / %dMB RAM / %dKB FREE",get_memory_size()/1048576,(heap.total-heap.used)/1024);
#else
        rdpq_text_print(NULL,1,6,235,tour?"L RETURN   START VIEWS   R RESET":"Z FIRE  A JUMP  B LOAD  START VIEWS");
#endif
        rdpq_detach_show();
        fences[slot]=rspq_syncpoint_new();pending[slot]=true;slot=(slot+1)%3;
        frames++;
        if (now-fps_time>=1000000) {
            fps=frames*1000000ULL/(now-fps_time);frames=0;fps_time=now;
            debugf("PERF views=%u fps=%u triangles=%u p1=(%.2f %.2f %.2f) p2=(%.2f %.2f %.2f)\n",views,fps,triangles,
                bg_players[0].pos[0],bg_players[0].pos[1],bg_players[0].pos[2],bg_players[1].pos[0],bg_players[1].pos[1],bg_players[1].pos[2]);
        }
    }
}
