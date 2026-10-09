"""Exercise production mesh allocation/release helpers across fenced slots.

Host ASan/UBSan checks size changes, reuse, slot independence and full teardown.
Ares frontend QA separately cycles all eight meshes in four views.
"""
from pathlib import Path
import subprocess
import tempfile
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'port/n64/main.c').read_text()
code = r'''
#include <assert.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdio.h>
#define BG_FRAME_SLOTS 2
#define assertf(v,...) assert(v)
typedef unsigned char T3DVertPacked;
static T3DVertPacked *firstperson[2][4];
static unsigned firstperson_bytes[2][4];
static int firstperson_weapon[2][4];
static unsigned slot,allocated,fences;
static bool busy[2];
static void *malloc_uncached(unsigned n){assert(!busy[slot]);allocated++;return malloc(n);}
static void free_uncached(void*p){assert(!busy[slot]);assert(allocated);allocated--;free(p);}
static void rspq_wait(void){busy[0]=busy[1]=false;fences++;}
'''
for name,args in [('firstperson_buffers_load','void'),('firstperson_buffers_release','void'),('firstperson_buffer_resize','unsigned p,unsigned bytes')]:
    code += '\nstatic void '+name+'('+args+'){'+function(source,name)+'}\n'
code += r'''
int main(void){
 unsigned sizes[]={504,536,512,576,626,466,576,566};
 for(unsigned lifecycle=0;lifecycle<20;lifecycle++){
  firstperson_buffers_load();assert(allocated==0);
  for(unsigned frame=0;frame<64;frame++){
   slot=frame%2;busy[slot]=false; /* The renderer's completed frame-slot fence. */
   for(unsigned p=0;p<4;p++){
    unsigned bytes=sizes[(frame/2+p)%8]*16;
    firstperson_buffer_resize(p,bytes);
    assert(firstperson_bytes[slot][p]==bytes&&firstperson_weapon[slot][p]==-1);
    firstperson[slot][p][bytes-1]=42;
    void*old=firstperson[slot][p];firstperson_weapon[slot][p]=3;
    firstperson_buffer_resize(p,bytes);assert(firstperson[slot][p]==old&&firstperson_weapon[slot][p]==3);
    firstperson_weapon[slot][p]=-1;
   }
   busy[slot]=true;
  }
  assert(allocated==8);firstperson_buffers_release();assert(allocated==0);
  for(unsigned s=0;s<2;s++)for(unsigned p=0;p<4;p++)assert(!firstperson[s][p]&&!firstperson_bytes[s][p]&&firstperson_weapon[s][p]==-1);
 }
 assert(fences==20);puts("PASS: weapon workspace resize/reuse, fenced slots and 20 complete allocation lifecycles");
}
'''
with tempfile.TemporaryDirectory(prefix='halo-workspace-') as temp:
    c=Path(temp)/'test.c';c.write_text(code);exe=Path(temp)/'test'
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
