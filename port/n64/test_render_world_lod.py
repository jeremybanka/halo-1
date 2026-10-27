"""Exercise projected-error selection, zoom, viewport size and safe fallbacks."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
CODE=r'''
#include "render_world_lod.h"
#include <assert.h>
static unsigned rng=0x71237451;
static float random_unit(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return (rng%100001)/100000.f;}
static bool box_reference(const bg_world_lod_group *g,const float c[4][4],const float p[4][4]) {
 float lo[2]={INFINITY,INFINITY},hi[2]={-INFINITY,-INFINITY};
 for(unsigned corner=0;corner<8;corner++){
  float v[3]={c[3][0],c[3][1],c[3][2]};
  for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)v[a]+=g->bounds[b+((corner>>b&1)?3:0)]*c[b][a];
  float depth=-v[2];if(!isfinite(depth)||depth<=1.4f)return false;
  for(unsigned a=0;a<2;a++){float q=v[a]/depth;if(!isfinite(q))return false;lo[a]=fminf(lo[a],q);hi[a]=fmaxf(hi[a],q);}
 }
 float sx=(hi[0]-lo[0])*320*fabsf(p[0][0])*.5f,sy=(hi[1]-lo[1])*240*fabsf(p[1][1])*.5f;
 return isfinite(sx)&&isfinite(sy)&&fmaxf(sx,sy)+.01f<g->diameter_pixels;
}
int main(void){
 float c[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
 float p[4][4]={{1.25f,0,0,0},{0,1.67f,0,0},{0,0,-1,-1},{0,0,-2,0}};
 float eye[3]={0,0,0};
 bg_world_lod_group g={{0,0,-100},2,.1f,1,0,3,{-2,-2,-102,2,2,-98}};
 assert(bg_world_lod_far(&g,c,p,320,240,1.4f,eye));
 g.center[2]=-20;g.bounds[2]=-22;g.bounds[5]=-18;
 assert(!bg_world_lod_far(&g,c,p,320,240,1.4f,eye));
 assert(bg_world_lod_far(&g,c,p,160,120,1.4f,eye));
 p[0][0]*=10;p[1][1]*=10;
 assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));
 p[0][0]/=10;p[1][1]/=10;
 g.center[2]=-100;g.bounds[2]=-102;g.bounds[5]=-98;
 eye[2]=-99;assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));eye[2]=0;
 g.center[2]=1;assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));
 g.center[2]=-2.5f;assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));
 g.center[2]=NAN;assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));
 g.center[2]=-100;p[0][0]=INFINITY;assert(!bg_world_lod_far(&g,c,p,160,120,1.4f,eye));p[0][0]=1.25f;
 g.error=0;g.diameter_pixels=48;assert(bg_world_lod_far(&g,c,p,320,240,1.4f,eye));
 /* The box selector can accept a long thin region whose sphere crosses the
  * near plane. Zoom, nearby eyes, and an actual near-plane crossing keep near. */
 g.box_diameter=1;g.radius=200;g.diameter_pixels=48;
 assert(bg_world_lod_far(&g,c,p,320,240,1.4f,eye));
 p[0][0]*=10;p[1][1]*=10;assert(!bg_world_lod_far(&g,c,p,320,240,1.4f,eye));p[0][0]/=10;p[1][1]/=10;
 eye[2]=-99;assert(!bg_world_lod_far(&g,c,p,320,240,1.4f,eye));eye[2]=0;
 g.bounds[5]=-1;assert(!bg_world_lod_far(&g,c,p,320,240,1.4f,eye));g.bounds[5]=-98;
 p[0][0]=INFINITY;assert(!bg_world_lod_far(&g,c,p,320,240,1.4f,eye));p[0][0]=1.25f;
 /* Reusing products must preserve the direct eight-corner decision. Keep
  * the eye outside every random box so the independent near guard is open. */
 g.near_distance=0;
 for(unsigned trial=0;trial<200000;trial++){
  for(unsigned a=0;a<3;a++){g.bounds[a]=20+random_unit()*100;g.bounds[a+3]=g.bounds[a]+random_unit()*80;}
  for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)c[b][a]=random_unit()*2-1;
  c[3][2]=-40-random_unit()*300;g.diameter_pixels=1+random_unit()*400;
  assert(bg_world_lod_far(&g,c,p,320,240,1.4f,eye)==box_reference(&g,c,p));
 }
 uint16_t codes[]={0,1,2,3,4};uint8_t levels[]={0,1};
 bg_world_lod_data d={&g,codes,2,5,1};
 assert(bg_world_lod_keep(&d,levels,0));assert(bg_world_lod_keep(&d,levels,1));
 assert(!bg_world_lod_keep(&d,levels,2));assert(!bg_world_lod_keep(&d,levels,3));assert(bg_world_lod_keep(&d,levels,4));
 assert(bg_world_lod_keep(&d,levels,5));
}
'''
def main():
 with tempfile.TemporaryDirectory() as td:
  src=Path(td)/'test.c';exe=Path(td)/'test';src.write_text(CODE)
  subprocess.run(['clang','-std=c17','-fsanitize=address,undefined','-ffp-contract=off','-I'+str(ROOT/'port/n64'),str(src),'-lm','-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True)
 print('World LOD selector checks passed under ASan/UBSan.')
if __name__=='__main__':main()
