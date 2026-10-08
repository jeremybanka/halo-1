#ifndef BG_SKY_DRAW_H
#define BG_SKY_DRAW_H
#include "sky.h"

/* Sixteen shaded triangles replace the flat clear. No texture, depth writes,
 * persistent vertex storage, or RSP model transform. The center column keeps
 * the elevation gradient curved across wide fields of view. */
static void bg_sky_draw(const T3DViewport *vp)
{
    float vertices[5][3][6];
    for(unsigned row=0;row<5;row++)for(unsigned col=0;col<3;col++){
        float *v=vertices[row][col];
        v[0]=vp->offset[0]+vp->size[0]*col*.5f;
        v[1]=vp->offset[1]+vp->size[1]*row*.25f;
        bg_sky_color(vp->matCamera.m,vp->matProj.m,col-1.f,1-row*.5f,v+2);
        v[5]=1;
    }
    rdpq_set_mode_standard();
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    rdpq_mode_zbuf(false,false);
    rdpq_mode_antialias(AA_NONE);
    rdpq_mode_dithering(DITHER_SQUARE_NONE);
    for(unsigned row=0;row<4;row++)for(unsigned col=0;col<2;col++){
        rdpq_triangle(&TRIFMT_SHADE,vertices[row][col],vertices[row][col+1],vertices[row+1][col]);
        rdpq_triangle(&TRIFMT_SHADE,vertices[row][col+1],vertices[row+1][col+1],vertices[row+1][col]);
    }
}
#endif
