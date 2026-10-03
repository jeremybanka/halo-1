#include <assert.h>
#include <libdragon.h>
#include <t3d/t3dmath.h>
#include "asset_firstperson.h"
#include "firstperson_ammo.h"
#include "firstperson_ammo_logic.h"
#include "game.h"

static T3DVertPacked digits[2][4][4] __attribute__((aligned(16)));
static T3DMat4FP precision_matrix __attribute__((aligned(16)));
static surface_t texture;
static rspq_block_t *counter_blocks[2][4];
static int16_t indices[12] __attribute__((aligned(8)))={
    0,1,2,(int16_t)0x8002,1,3,(int16_t)0x8004,5,6,(int16_t)0x8006,5,7};
static void draw_counter(unsigned slot,unsigned player);

void bg_fp_ammo_init(void) {
    const float scale=BG_FP_SCALE/BG_AR_AMMO_SCALE;
    t3d_mat4fp_from_srt_euler(&precision_matrix,(float[]){scale,scale,scale},
        (float[]){0,0,0},(float[]){0,0,0});
    data_cache_hit_writeback(&precision_matrix,sizeof(precision_matrix));
    t3d_indexbuffer_convert(indices,12);
    data_cache_hit_writeback(indices,sizeof(indices));
    texture=surface_make((void*)bg_ar_ammo_texture,FMT_RGBA16,
        BG_AR_AMMO_TEXTURE_WIDTH,BG_AR_AMMO_TEXTURE_HEIGHT,BG_AR_AMMO_TEXTURE_WIDTH*2);
    /* Commands retain each fenced buffer's address, not its current contents.
     * Geometry/UV updates remain in bg_fp_ammo_prepare before the next use. */
    for(unsigned slot=0;slot<2;slot++)for(unsigned player=0;player<4;player++) {
        rspq_block_begin();
        draw_counter(slot,player);
        counter_blocks[slot][player]=rspq_block_end();
    }
}

void bg_fp_ammo_prepare(unsigned slot,unsigned player,unsigned weapon,unsigned clip,
        unsigned f0,unsigned f1,int fraction,int ammo,int reserve,float reload_elapsed,
        T3DVertPacked*firstperson_vertices) {
    assert(slot<2&&player<4);
    if(weapon==BG_W_AR) {
        int16_t positions[8][3],uv[8][2];
        bg_ar_ammo_sample(positions,uv,clip,f0,f1,fraction,ammo);
        T3DVertPacked*out=digits[slot][player];
        for(unsigned i=0;i<8;i++) {
            memcpy(t3d_vertbuffer_get_pos(out,i),positions[i],sizeof(positions[i]));
            memcpy(t3d_vertbuffer_get_uv(out,i),uv[i],sizeof(uv[i]));
            *t3d_vertbuffer_get_color(out,i)=0xffffffff;
        }
        data_cache_hit_writeback(out,sizeof(digits[slot][player]));
    } else if(weapon==BG_W_NEEDLER) {
        bg_needler_ammo_sample(firstperson_vertices,&bg_needler_ammo,clip,f0,f1,fraction,
            bg_needler_ammo_state(ammo,reserve,reload_elapsed));
        data_cache_hit_writeback(firstperson_vertices,(bg_needler_ammo.base_vertices+1u)/2u*32u);
    }
}

static void draw_counter(unsigned slot,unsigned player) {
    t3d_tri_sync();
    rdpq_mode_push();
    rdpq_mode_begin();
    rdpq_mode_combiner(RDPQ_COMBINER_TEX);
    rdpq_mode_blender(0);
    rdpq_mode_alphacompare(0);
    rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_persp(true);
    rdpq_mode_end();
    rdpq_tex_upload(TILE0,&texture,NULL);
    /* Original numeric shader planes face opposite the general FP bank's
     * triangle convention. Positive emitted normal dot eye is their screen
     * face; CULL_BACK retains it and hides the back during reload turns. */
    t3d_state_set_drawflags(T3D_FLAG_TEXTURED|T3D_FLAG_CULL_BACK);
    t3d_matrix_push(&precision_matrix);
    t3d_vert_load(digits[slot][player],0,8);
    t3d_tri_draw_strip(indices,12);
    t3d_tri_sync();
    t3d_matrix_pop(1);
    /* This Tiny3D strip bypasses rdpq's draw-resource tracking.
     * TriSync only submits triangles; finish their RDP pipe use before
     * mode_pop restores SET_COMBINE/SET_OTHER_MODES. */
    rdpq_sync_pipe();
    rdpq_mode_pop();
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_CULL_FRONT);
}

void bg_fp_ammo_draw(unsigned slot,unsigned player) {
    assert(slot<2&&player<4);
    rspq_block_run(counter_blocks[slot][player]);
}
