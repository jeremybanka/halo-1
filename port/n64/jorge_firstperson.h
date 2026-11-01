#ifndef BG_JORGE_FIRSTPERSON_H
#define BG_JORGE_FIRSTPERSON_H
#include "asset_firstperson.h"
#include "armor_palette.h"
#include <math.h>
typedef struct { const uint16_t *indices; const float *coefficients; uint16_t count; } bg_jorge_fp_frame;
typedef struct { uint8_t frame; float affine[4]; } bg_jorge_fp_vertex;
extern const bg_model_asset bg_jorge_fp_model;
extern const bg_jorge_fp_vertex bg_jorge_fp_vertices[];
extern const bg_jorge_fp_frame *const bg_jorge_fp_frames[BG_FP_WEAPONS];
extern const uint8_t *const bg_jorge_fp_colors[BG_FP_WEAPONS];
/* Recover the source armor's rigid frames from the fully animated CE glove
 * cage, after ready/service/reload animation. No independent animation clock. */
static inline void bg_jorge_firstperson_pose(T3DVertPacked *out,
                                             const T3DVertPacked *hands, unsigned weapon) {
    float frames[2][4][3] = {0};
    for (unsigned b=0;b<2;b++) {
        const bg_jorge_fp_frame *f=&bg_jorge_fp_frames[weapon][b];
        for (unsigned i=0;i<f->count;i++) {
            const int16_t *p=t3d_vertbuffer_get_pos((T3DVertPacked *)hands,f->indices[i]);
            for(unsigned k=0;k<4;k++)
                for(unsigned a=0;a<3;a++) frames[b][k][a]+=p[a]*f->coefficients[k*f->count+i];
        }
    }
    for (unsigned i=0;i<bg_jorge_fp_model.vertex_count;i++) {
        const bg_jorge_fp_vertex *v=&bg_jorge_fp_vertices[i];
        int16_t *p=t3d_vertbuffer_get_pos(out,i);
        for(unsigned a=0;a<3;a++) {
            float x=0;for(unsigned k=0;k<4;k++)x+=v->affine[k]*frames[v->frame][k][a];
            p[a]=lroundf(x);
        }
    }
}
static inline void bg_jorge_firstperson_tint(T3DVertPacked *out,unsigned weapon,unsigned profile) {
    static const unsigned tint[4][3]={{255,255,255},{175,175,165},{62,69,48},{145,126,82}};
    for(unsigned i=0;i<bg_fp_models[weapon].vertex_count;i++) {
        unsigned kind=bg_jorge_fp_colors[weapon][i];if(!kind)continue;
        uint32_t *c=t3d_vertbuffer_get_color(out,i),old=*c;
        *c=(((old>>24)*tint[kind][0]/255)<<24)|((((old>>16)&255)*tint[kind][1]/255)<<16)|
           ((((old>>8)&255)*tint[kind][2]/255)<<8)|255;
        if (kind!=1) *c=bg_jorge_palette_color(*c,profile,BG_JORGE_SECONDARY);
    }
}
#endif
