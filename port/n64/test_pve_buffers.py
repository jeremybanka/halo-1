"""Exercise production enemy-buffer retirement with a bounded host heap."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

HEADER = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define BG_FRAME_SLOTS 2
#define BG_PVE_MAX 12
#ifndef BG_PVE_LODS
#define BG_PVE_LODS 2
#endif
typedef struct {unsigned bytes;} T3DVertPacked;
static T3DVertPacked *pve_vertices[2][13][BG_PVE_LODS];
static uint32_t pve_pose_keys[2][13][BG_PVE_LODS];
static unsigned slot=1,live_bytes,limit=100000,fences;
static void rspq_wait(void){fences++;}
static void free_uncached(T3DVertPacked *p){assert(live_bytes>=p->bytes);live_bytes-=p->bytes;free(p);}
static T3DVertPacked *malloc_uncached(unsigned bytes){
 if(live_bytes+bytes>limit)return NULL;
 T3DVertPacked *p=malloc(sizeof(*p));assert(p);p->bytes=bytes;live_bytes+=bytes;return p;
}
'''

TEST = r'''
int main(void){
 for(unsigned s=0;s<2;s++)for(unsigned i=0;i<13;i++)for(unsigned l=0;l<BG_PVE_LODS;l++){
  pve_vertices[s][i][l]=malloc_uncached(16);pve_pose_keys[s][i][l]=123;
 }
 T3DVertPacked *kept=pve_vertices[slot][3][1];
 pve_trim_actor(3,1u<<1);
 assert(pve_vertices[slot][3][1]==kept&&pve_pose_keys[slot][3][1]==123);
 for(unsigned l=0;l<BG_PVE_LODS;l++)if(l!=1){
  assert(!pve_vertices[slot][3][l]&&!pve_pose_keys[slot][3][l]);
 }
 unsigned before=live_bytes;limit=before+32;
 T3DVertPacked *allocated=pve_allocate(3,128);assert(allocated&&fences==1);
 /* Earlier owners and their current-frame aliases remain valid. */
 for(unsigned i=0;i<3;i++)for(unsigned l=0;l<BG_PVE_LODS;l++)assert(pve_vertices[slot][i][l]);
 assert(pve_vertices[slot][3][1]==kept);
 for(unsigned s=0;s<2;s++)for(unsigned i=0;i<13;i++)if(s!=slot||i>3)
  for(unsigned l=0;l<BG_PVE_LODS;l++)assert(!pve_vertices[s][i][l]&&!pve_pose_keys[s][i][l]);
 /* Failure cannot sacrifice owners already prepared for this frame. */
 limit=0;assert(!pve_allocate(3,128)&&fences==2);
 assert(pve_vertices[slot][3][1]==kept);
 free_uncached(allocated);
 for(unsigned i=0;i<13;i++){pve_trim_actor(i,0);pve_trim_actor(i,0);}
 assert(live_bytes==0);
 printf("PASS: %u LODs, wanted-mask retirement, fenced recovery, prepared owners preserved, idempotent teardown\n",BG_PVE_LODS);
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = (ROOT/'port/n64/pve_draw.inc').read_text()
    helpers = source[source.index('static void pve_drop_buffer('):source.index('static void pve_release(')]
    test = out/'buffers.c'
    test.write_text(HEADER+helpers+TEST)
    for lods, alpha in ((2, False), (3, True)):
        binary = out/f'buffers-{lods}'
        command = ['clang', '-std=c17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', f'-DBG_PVE_LODS={lods}']
        if alpha:
            command += ['-DBG_PVE_MODEL_CANDIDATE']
        subprocess.run([*command, str(test), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

if __name__ == '__main__':
    main()
