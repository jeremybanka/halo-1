"""Regional selection boundaries, finite fallback, and immutable gameplay data."""
import json,subprocess
from pathlib import Path
from sidewinder_budget import ROOT,OUT,BASE,validate,sections

TEST=r'''
#include "render_world_rep.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 const float planes[][3]={{1,0,1},{-1,0,-3},{0,1,2},{0,-1,-4}};
 const bg_world_rep_data d={{0,0,0,4,4,5},10,20,1,planes,4};
 assert(bg_world_rep_active(&d,1,(float[]){2,2,3}));
 assert(!bg_world_rep_active(&d,2,(float[]){2,2,3}));
 assert(!bg_world_rep_active(&d,1,(float[]){1,2,3}));
 assert(!bg_world_rep_active(&d,1,(float[]){2,0,3}));
 assert(!bg_world_rep_active(&d,1,(float[]){NAN,2,3}));
 assert(!bg_world_rep_active(&d,1,(float[]){2,INFINITY,3}));
 assert(!bg_world_rep_active(0,1,(float[]){2,2,3}));
 for(unsigned b=0;b<20;b++){
  assert(bg_world_rep_keep(&d,false,b)==(b<10));
  assert(bg_world_rep_keep(&d,true,b)==(b>=10));
 }
 assert(bg_world_rep_keep(&d,false,21));
 const float p[3]={52.2788773f*32,.792942643f*32,-24.1915627f*32};
 assert(bg_world_rep_active(&bg_world_rep,1,p));
 assert(!bg_world_rep_active(&bg_world_rep,1,(float[]){48*32,.79f*32,-27*32}));
 puts("PASS: real target, footprint, strict boundaries, map identity, NaN/infinity, uncertain chunk fallback");
}
'''
def run():
 data=json.loads((OUT/'visibility.json').read_text());validate(data,(OUT/'candidate-maps/sidewinder.map64').read_bytes());work=OUT/'contracts';work.mkdir(exist_ok=True);(work/'test.c').write_text(TEST)
 for label,flags in [('strict',['-fno-fast-math']),('target',['-ffast-math','-ftrapping-math','-fno-associative-math','-fno-finite-math-only'])]:
  subprocess.run(['clang','-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off',*flags,'-Iport/n64',str(work/'test.c'),str(OUT/'visibility-data.c'),'-lm','-o',str(work/label)],cwd=ROOT,check=True);subprocess.run([str(work/label)],check=True)
 print('PASS: original rendering prefix and all texture/collision/movement/gameplay sections byte-identical')
if __name__=='__main__':run()
