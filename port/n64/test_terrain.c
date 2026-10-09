#include "terrain.h"
#include "movement.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static float floor_p[3][3]={{-10,0,-10},{10,0,-10},{0,0,10}};
static float roof_p[3][3]={{-10,3,-10},{10,3,-10},{0,3,10}};
static float wall_p[3][3]={{1,-10,-10},{1,10,-10},{1,0,10}};
const bg_triangle bg_collision[]={{{floor_p[0],floor_p[1],floor_p[2]}},{{roof_p[0],roof_p[1],roof_p[2]}},{{wall_p[0],wall_p[1],wall_p[2]}}};
const unsigned bg_collision_count=3;
const bg_cell bg_grid[BG_GRID*BG_GRID]={{0,3}};
const uint16_t bg_grid_indices[]={0,1,2};
const float bg_grid_origin[2]={-10,-10},bg_grid_size[2]={20,20};
static void near(float a,float b){assert(fabsf(a-b)<.0002f);}
int main(){
    float a[3],b[3];bg_player p={.pos={0,.015f,0},.grounded=true,.ground_normal={0,1,0}};
    near(bg_capsule_triangle(p.pos,.7f,.2f,&bg_collision[0],a,b),.215f*.215f);
    /* Wall crosses the middle of the capsule where the old samples had gaps. */
    near(bg_capsule_triangle((float[]){.85f,0,0},.7f,.2f,&bg_collision[2],a,b),.15f*.15f);
    assert(bg_terrain_clearance(&p));p.pos[0]=.95f;assert(!bg_terrain_clearance(&p));p.pos[0]=0;
    p.crouch_amount=1;for(int i=0;i<3;i++)roof_p[i][1]=.6f;
    bg_terrain_reset();assert(!bg_can_stand(&p));p.pos[0]=-3;assert(!bg_can_stand(&p));
    p.pos[0]=0;for(int i=0;i<3;i++)roof_p[i][1]=3;bg_terrain_reset();assert(bg_can_stand(&p));
    p.crouch_amount=0;p.velocity[0]=6;p.velocity[1]=-.25f;
    bg_move_capsule(&p,.5f);assert(p.pos[0]<.786f&&p.pos[0]>.78f);near(p.velocity[0],0);assert(p.grounded);
    /* Upward travel hits the ceiling, including high-speed/substep motion. */
    p=(bg_player){.pos={0,.015f,0},.velocity={0,12,0}};bg_move_capsule(&p,.3f);assert(p.pos[1]+.7f<3.001f);near(p.velocity[1],0);
    /* A wall never becomes a floor. */
    p=(bg_player){.pos={.79f,1,0},.velocity={1,-1,0}};bg_move_capsule(&p,.03f);assert(!p.grounded);
    /* Original slope curve: 45-degree uphill 0.65, downhill 1.25. */
    p=(bg_player){.grounded=true,.ground_normal={-.70710678f,.70710678f,0}};
    for(int i=0;i<60;i++)bg_walk_velocity(&p,1,0,1.f/30);
    near(hypotf(p.velocity[0],p.velocity[1]),2.25f*.65f);near(p.velocity[0],p.velocity[1]);
    for(int i=0;i<60;i++)bg_walk_velocity(&p,-1,0,1.f/30);
    near(hypotf(p.velocity[0],p.velocity[1]),2.f*1.25f);
    p=(bg_player){0};bg_start_landing(&p,1.49f);near(p.landing_time,0);
    bg_start_landing(&p,3.25f);assert(!p.hard_landing);near(p.landing_time,.3f);
    bg_start_landing(&p,5);assert(p.hard_landing);near(p.landing_time,1);
    p.grounded=true;p.ground_normal[1]=1;bg_walk_velocity(&p,1,0,1.f/30);near(p.velocity[0],0);
    /* A 60-degree face stays airborne and sheds the player downhill even
     * with uphill input; a steep wall must never become walkable support. */
    for(int j=0;j<3;j++){floor_p[j][1]=floor_p[j][0]*1.7320508f;roof_p[j][1]=50;wall_p[j][0]=50;}
    bg_terrain_reset();p=(bg_player){.pos={0,.22f,0}};
    for(int j=0;j<60;j++){bg_walk_velocity(&p,1,0,1.f/30);p.velocity[1]=p.vy-bg_movement.gravity/30;bg_move_capsule(&p,1.f/30);assert(!p.grounded);}
    assert(p.pos[0]<-.1f&&p.pos[1]<0);
    /* Original adjacent-support recovery: stay attached across a shallow
     * convex seam, but never snap a fast outward move or airborne jump. */
    const float previous[3][3]={{-10,0,-10},{0,0,-10},{0,0,10}};
    const float next[3][3]={{0,0,-10},{10,-3,0},{0,0,10}};
    memcpy(floor_p,previous,sizeof(floor_p));memcpy(roof_p,next,sizeof(roof_p));bg_terrain_reset();
    p=(bg_player){.pos={.25f,.015f,0},.velocity={2,0,0},.grounded=true,.support_triangle=1};
    bg_move_capsule(&p,0);assert(p.grounded&&p.support_triangle==2&&p.pos[1]<0&&p.ground_normal[1]>.95f);
    p=(bg_player){.pos={.25f,.015f,0},.velocity={10,0,0},.grounded=true,.support_triangle=1};
    bg_move_capsule(&p,0);assert(!p.grounded);
    p=(bg_player){.pos={.25f,.015f,0},.velocity={2,0,0},.grounded=false,.support_triangle=1};
    bg_move_capsule(&p,0);assert(!p.grounded);
    puts("PASS terrain: continuous capsule axis, wall/ceiling clearance, high-speed contacts, slope projection/curve and original landing recovery");
}
