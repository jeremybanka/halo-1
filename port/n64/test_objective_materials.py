"""Exercise the actual objective draw helpers and their material boundaries."""
from pathlib import Path
import subprocess
import tempfile
from test_render_matrix import function

ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'port/n64/scene_objectives.inc').read_text()
code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
typedef int T3DMat4FP;
typedef struct {unsigned triangle_count;} bg_model_asset;
typedef int surface_t;
enum {BG_OBJECTIVE_FLAG=0,BG_OBJECTIVE_BALL=1,FMT_RGBA16=0,TLUT_NONE=0,
 RDPQ_COMBINER_SHADE=0,RDPQ_COMBINER_TEX_SHADE=1,FILTER_POINT=0,TILE0=0,
 BG_CLOTH_TRIANGLES=40,T3D_FLAG_SHADED=1,T3D_FLAG_DEPTH=2,T3D_FLAG_TEXTURED=4,T3D_FLAG_CULL_BACK=8};
static bg_model_asset bg_objective_models[2]={{445},{386}},bg_objective_fp_models[2]={{793},{430}};
static int objective_blocks[2]={1,2},objective_fp_blocks[2]={3,4};
static int flag_cloth_fp_blocks[1][4]={{5,5,5,5}},flag_cloth_world_blocks[1][2]={{5,5}};
static unsigned slot;
static uint16_t bg_flag_textures[2][2048];
static unsigned triangles,flags,alpha,combiner,draws,matrix_calls,uploads;
static int expected_team;
static surface_t surface_make_linear(void*p,int f,int w,int h){
 assert(p==bg_flag_textures[expected_team]&&f==FMT_RGBA16&&w==64&&h==32);return 0;}
static void rdpq_sync_pipe(void){}
static void rdpq_sync_tile(void){}
static void rdpq_sync_load(void){}
static void rdpq_mode_tlut(int v){assert(v==TLUT_NONE);}
static void rdpq_mode_combiner(int v){combiner=v;}
static void rdpq_mode_persp(bool v){assert(v);}
static void rdpq_mode_filter(int v){assert(v==FILTER_POINT);}
static void rdpq_mode_alphacompare(unsigned v){alpha=v;}
static void rdpq_tex_upload(int tile,surface_t*p,void*params){assert(tile==0&&p&&!params);uploads++;}
static void t3d_state_set_drawflags(unsigned v){flags=v;}
static void t3d_matrix_set(T3DMat4FP*p,bool multiply){assert(p&&multiply);matrix_calls++;}
static void rspq_block_run(int block){
 assert((flags&(T3D_FLAG_SHADED|T3D_FLAG_DEPTH))==(T3D_FLAG_SHADED|T3D_FLAG_DEPTH));
 if(block==3||block==1){assert(!alpha&&combiner==RDPQ_COMBINER_SHADE);
   assert(!(flags&T3D_FLAG_TEXTURED)&&((flags&T3D_FLAG_CULL_BACK)!=0)==(block==3));}
 else if(block==5){assert(alpha==128&&combiner==RDPQ_COMBINER_TEX_SHADE);
   assert((flags&T3D_FLAG_TEXTURED)&&!(flags&T3D_FLAG_CULL_BACK));}
 else assert(!alpha&&combiner==RDPQ_COMBINER_SHADE&&!(flags&T3D_FLAG_TEXTURED));
 draws++;
}
'''
for name,args in [('objective_texture','int team'),('objective_texture_end','void'),
                  ('objective_instance','unsigned kind,int team,T3DMat4FP *transform,bool fp,unsigned player')]:
    code+='\nstatic void '+name+'('+args+'){'+function(source,name)+'}\n'
code+=r'''
int main(void){
 T3DMat4FP transform=0;
 for(unsigned team=0;team<2;team++){
  expected_team=team;draws=triangles=matrix_calls=uploads=0;
  objective_instance(BG_OBJECTIVE_FLAG,team,&transform,true,0);
  assert(draws==2&&triangles==833&&matrix_calls==1&&uploads==1&&!alpha&&!combiner);
  objective_instance(BG_OBJECTIVE_BALL,-1,&transform,true,0);
  assert(draws==3&&triangles==1263&&matrix_calls==2&&uploads==1);
  objective_instance(BG_OBJECTIVE_FLAG,team,&transform,false,0);
  assert(draws==5&&triangles==1748&&matrix_calls==3&&uploads==2&&!alpha&&!combiner);
 }
 puts("PASS: opaque flag hand/pole, two-sided alpha cloth, both teams and subsequent skull/world draws");
}
'''
with tempfile.TemporaryDirectory(prefix='halo-objective-materials-') as temp:
    c=Path(temp)/'test.c';c.write_text(code);exe=Path(temp)/'test'
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
