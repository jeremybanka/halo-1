#include "collision.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#define BLOCK(array) {sizeof(array)/sizeof((array)[0]),array,0}

static const blam_bsp3d_node halfspace_node[]={{0,{-1,INT32_MIN}}};
static const blam_bsp3d_node two_sided_node[]={{0,{INT32_MIN|1,INT32_MIN}}};
static const blam_plane3 planes[]={{{.n={0,0,1}},0}};
static const blam_collision_leaf leaves[]={{0,1,0}};
static const blam_collision_leaf two_sided_leaves[]={{1,1,0},{1,1,0}};
static const blam_bsp2d_reference references[]={{0,INT32_MIN}};
static const blam_collision_surface surfaces[]={{0,0,0,255,7}};
static const blam_collision_surface two_sided_surfaces[]={{0,0,1,255,7}};
static const blam_collision_vertex vertices[]={
    {{.n={-1,-1,0}},0},{{.n={1,-1,0}},1},{{.n={1,1,0}},2},{{.n={-1,1,0}},3},
};
static const blam_collision_edge edges[]={
    {{0,1},{1,3},{0,-1}},{{1,2},{2,0},{0,-1}},
    {{2,3},{3,1},{0,-1}},{{3,0},{0,2},{0,-1}},
};
static const blam_collision_bsp halfspace={
    {BLOCK(halfspace_node),BLOCK(planes)},BLOCK(leaves),BLOCK(references),{{0}},
    BLOCK(surfaces),BLOCK(edges),BLOCK(vertices),
};
static const blam_collision_bsp two_sided={
    {BLOCK(two_sided_node),BLOCK(planes)},BLOCK(two_sided_leaves),BLOCK(references),{{0}},
    BLOCK(two_sided_surfaces),BLOCK(edges),BLOCK(vertices),
};
int main(void){
    float from[3]={0,0,3},move[3]={0,0,-4};blam_collision_hit hit;
    assert(blam_collision_segment(&halfspace,from,move,false,&hit));
    assert(fabsf(hit.fraction-.75f)<1e-6f&&hit.surface==0&&hit.material==7&&hit.normal[2]==1);
    from[2]=-1;move[2]=4;
    assert(!blam_collision_segment(&halfspace,from,move,false,&hit));
    assert(blam_collision_segment(&halfspace,from,move,true,&hit)&&fabsf(hit.fraction-.25f)<1e-6f);
    from[2]=3;move[2]=-4;
    assert(blam_collision_segment(&two_sided,from,move,true,&hit));
    from[0]=2;assert(!blam_collision_segment(&two_sided,from,move,true,&hit));
    from[0]=0;move[2]=-.5f;assert(!blam_collision_segment(&halfspace,from,move,true,&hit));
    move[2]=0;assert(!blam_collision_segment(&halfspace,from,move,true,&hit));
    puts("Original Blam BSP traversal: solid, back-face, two-sided polygon and miss tests passed");
}
