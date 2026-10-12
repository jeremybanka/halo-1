"""Trace actual terrain draw code: legacy flags remain command-identical."""
from pathlib import Path
import subprocess,tempfile,re
from test_render_matrix import function,compact
ROOT=Path(__file__).resolve().parents[2]
def world_region(source):
    body=function(source,'draw_view');start=body.index('unsigned bound = ~0u;')
    end=body.index('/* Every object matrix',start)
    return body[start:end]
old=subprocess.check_output(['git','show','0ac2d7c9:port/n64/scene.c'],cwd=ROOT,text=True)
new=(ROOT/'port/n64/scene.c').read_text()
STUB=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
enum {T3D_FLAG_TEXTURED=1,T3D_FLAG_SHADED=2,T3D_FLAG_DEPTH=4,T3D_FLAG_CULL_FRONT=8,T3D_FLAG_CULL_BACK=16,
 AA_NONE=0,AA_STANDARD=1,SOM_ZMODE_MASK=3,SOM_ZMODE_TRANSPARENT=2,SOM_ZMODE_OPAQUE=0,TLUT_RGBA16=1,TLUT_NONE=0,RDPQ_COMBINER_SHADE=42};
typedef struct {unsigned material,index_count,count;int bounds[6];} bg_chunk;
static bg_chunk chunks[64];static bg_chunk *bg_chunks=chunks;
static unsigned bg_chunk_count,triangles,texture_blocks[4]={100,101,102,103},world_blocks[64],cull_selected[4];
static uint8_t bg_texture_overlay[4],bg_texture_ci4[4];
static unsigned words[4096],word_count;
static void word(unsigned v){assert(word_count<4096);words[word_count++]=v;}
static void rdpq_mode_begin(void){word(1);}static void rdpq_mode_end(void){word(2);}
static void rdpq_mode_zbuf(bool a,bool b){word(3);word(a);word(b);}
static void rdpq_mode_alphacompare(unsigned a){word(4);word(a);}
static void rdpq_mode_blender(unsigned a){word(5);word(a);}
static void rdpq_mode_antialias(unsigned a){word(6);word(a);}
static void __rdpq_mode_change_som(unsigned a,unsigned b){word(7);word(a);word(b);}
static void rdpq_mode_tlut(unsigned a){word(8);word(a);}
static void rspq_block_run(unsigned a){word(9);word(a);}
static void t3d_matrix_pop(unsigned a){word(10);word(a);}
static void rdpq_mode_combiner(unsigned a){word(11);word(a);}
static void t3d_state_set_drawflags(unsigned a){word(12);word(a);}
static bool bg_frustum_box_cached(const float p[6][4],unsigned selected,const int b[6]){(void)p;(void)selected;return b[0]>=0;}
static struct {struct {float planes[6][4];} viewFrustum;} view,*vp=&view;
'''
with tempfile.TemporaryDirectory(prefix='halo-map-modes-') as tmp:
    tmp=Path(tmp);source=tmp/'test.c'
    source.write_text(STUB+'\nstatic void before(unsigned p){'+world_region(old)+'}\nstatic void after(unsigned p){'+world_region(new)+r'''}
int main(void){
 unsigned seed=0xCE064,expected[4096];
 for(unsigned trial=0;trial<2000;trial++){
  for(unsigned m=0;m<4;m++){seed=seed*1664525u+1013904223u;bg_texture_overlay[m]=seed>>31;bg_texture_ci4[m]=(seed>>30)&1;}
  bg_chunk_count=1+seed%64;
  for(unsigned c=0;c<bg_chunk_count;c++){
   seed=seed*1664525u+1013904223u;chunks[c]=(bg_chunk){.material=seed%4,.index_count=3+(seed%40)*3,.count=1+seed%60,.bounds={seed&16?0:-1}};world_blocks[c]=200+c;
  }
  word_count=triangles=0;before(0);unsigned count=word_count,tris=triangles;memcpy(expected,words,count*sizeof(*words));
  word_count=triangles=0;after(0);assert(word_count==count&&triangles==tris&&!memcmp(expected,words,count*sizeof(*words)));
 }
 // Cutout foliage must write depth, retain alpha testing and be two-sided.
 bg_chunk_count=1;chunks[0]=(bg_chunk){.material=0,.index_count=3,.count=3,.bounds={0}};bg_texture_ci4[0]=0;bg_texture_overlay[0]=6;
 word_count=0;after(0);assert(words[0]==12&&words[1]==(1|2|4));
 assert(words[2]==1&&words[3]==3&&words[4]==1&&words[5]==1&&words[6]==4&&words[7]==128);
 puts("PASS: 2000 legacy terrain command streams byte-identical; new two-sided cutouts alpha-test and write depth");
}
''')
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(source),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
