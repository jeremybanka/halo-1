"""Exercise the real streamed C loader/pose decoder with both production LODs.

Only the DMA/cache APIs are host substitutes. Feed native
endian copies of the actual N64 bank, with exact-sized ASan pose allocations.
"""
from pathlib import Path
import json,struct,subprocess,tempfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'halo64-assets/assets/jorge/playable-lods/compiled'

def run():
    report=json.loads((DATA/'jorge-report.json').read_text());original=(DATA/'jorge.bin').read_bytes();native=bytearray(original)
    for r in report['lods']:
        start=r['bank_offset']
        for v in range(0,r['vertices'],2):
            at=start+v*16
            struct.pack_into('=3hH3hHII4h',native,at,*struct.unpack_from('>3hH3hHII4h',original,at))
        for off,end in [(r['indices_offset'],r['batches_offset']),
                        (r['batches_offset'],r['batches_offset']+r['batches']*8)]:
            for at in range(start+off,start+end,2):struct.pack_into('=H',native,at,struct.unpack_from('>H',original,at)[0])
        for c in r['clips']:
            for frame in range(c['frames']):
                at=c['offset']+frame*c['stride'];n=r['vertices']*3
                native[at:at+n*2]=np.frombuffer(original,dtype='>i2',count=n,offset=at).astype('=i2').tobytes()
                native[at+n*2:at+n*2+28]=np.frombuffer(original,dtype='>f4',count=7,offset=at+n*2).astype('=f4').tobytes()
    with tempfile.TemporaryDirectory(prefix='jorge-lod-runtime-') as directory:
        tmp=Path(directory);(tmp/'t3d').mkdir()
        (tmp/'native.bin').write_bytes(native)
        (tmp/'t3d/t3d.h').write_text('''#pragma once
#include <stdint.h>
typedef struct { int16_t a[3]; uint16_t na; int16_t b[3]; uint16_t nb; uint32_t ca,cb; int16_t ua[2],ub[2]; } T3DVertPacked;
static inline int16_t *t3d_vertbuffer_get_pos(T3DVertPacked *p,unsigned i){return i&1?p[i/2].b:p[i/2].a;}
''')
        (tmp/'malloc.h').write_text('''#pragma once
#include <stdlib.h>
static inline void *memalign(size_t alignment,size_t bytes){void *p=NULL;return posix_memalign(&p,alignment,bytes)?NULL:p;}
''')
        (tmp/'libdragon.h').write_text('''#pragma once
#include <assert.h>
#include <stdint.h>
#define assertf(value,...) assert(value)
uint32_t dfs_rom_addr(const char *);
unsigned dfs_rom_size(const char *);
void dma_read(void *,uint32_t,unsigned);
static inline void data_cache_hit_invalidate(void *p,unsigned n){(void)p;(void)n;}
static inline void data_cache_hit_writeback(void *p,unsigned n){(void)p;(void)n;}
''')
        (tmp/'test.c').write_text('''#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "asset_jorge.h"
static unsigned char *bank;static unsigned bank_size,reads;
uint32_t dfs_rom_addr(const char *name){assert(!strcmp(name,"jorge.bin"));return 4096;}
unsigned dfs_rom_size(const char *name){assert(!strcmp(name,"jorge.bin"));return bank_size;}
void dma_read(void *out,uint32_t address,unsigned bytes){assert(address>=4096&&address-4096+bytes<=bank_size);memcpy(out,bank+address-4096,bytes);reads++;}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);bank_size=ftell(f);rewind(f);bank=malloc(bank_size);assert(fread(bank,bank_size,1,f)==1);fclose(f);
unsigned tested=0;
for(unsigned cycle=0;cycle<3;cycle++){
assert(bg_jorge_load());assert(!bg_jorge_load());
assert(bg_jorge_model.vertices!=bg_jorge_lod_model.vertices);
assert(bg_jorge_model.vertex_count==bg_jorge_mesh.vertices&&bg_jorge_lod_model.vertex_count==bg_jorge_lod_mesh.vertices);
for(unsigned clip=0;clip<BG_J_CLIP_COUNT;clip++)for(unsigned sample=0;sample<5;sample++)for(unsigned player=0;player<4;player++)for(unsigned lod=0;lod<2;lod++){
 const bg_jorge_mesh_info *m=lod?&bg_jorge_lod_mesh:&bg_jorge_mesh;
 const bg_jorge_clip *c=&(lod?bg_jorge_lod_clips:bg_jorge_clips)[clip];
 T3DVertPacked *out=malloc(m->vertices*16);memset(out,0,m->vertices*16);
 float phase=(sample==4?1.25f:sample/3.f)+player*.017f;bool loop=sample==4;
 float seconds=phase*c->duration;phase=seconds/c->duration;phase=loop?phase-floorf(phase):fminf(phase,1);
 float frame=phase*(c->frames-1);unsigned a=frame,b=a+1<c->frames?a+1:a;float t=frame-a;
 const int16_t *x=(const int16_t*)(bank+c->offset+a*c->stride),*y=(const int16_t*)(bank+c->offset+b*c->stride);
 bg_attachment_pose hand={0};bg_jorge_pose(out,lod,clip,seconds,loop,1,&hand);
 for(unsigned v=0;v<m->vertices;v++)for(unsigned k=0;k<3;k++)assert(labs(t3d_vertbuffer_get_pos(out,v)[k]-lroundf(x[v*3+k]+(y[v*3+k]-x[v*3+k])*t))<=1);
 const float *hx=(const float*)(x+m->vertices*3),*hy=(const float*)(y+m->vertices*3);
 for(unsigned k=0;k<3;k++)assert(fabsf(hand.pos[k]-(hx[k]+(hy[k]-hx[k])*t))<1e-5);
 // A blended update must stay within the two endpoints; neither LOD can
 // write using the other mesh's vertex count or socket offset.
 bg_jorge_pose(out,lod,(clip+1)%BG_J_CLIP_COUNT,0,false,.35f,NULL);
 bg_jorge_pose(NULL,lod,clip,seconds,loop,1,&hand);free(out);tested++;
}
bg_jorge_release();assert(!bg_jorge_model.vertices&&!bg_jorge_lod_model.vertices);bg_jorge_release();
}
printf("PASS: %u C decode cases, alternating LODs/four players, endpoint/loop/blend/socket paths, 3 bank reloads (%u DMA reads)\\n",tested,reads);free(bank);return 0;}
''')
        subprocess.run(['clang','-std=c17','-D_POSIX_C_SOURCE=200112L','-Wall','-Wextra','-Werror',
                        '-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'port/n64'),
                        str(tmp/'test.c'),str(ROOT/'port/n64/jorge_render.c'),str(ROOT/'port/n64/blam/runtime.c'),str(DATA/'jorge_data.c'),
                        '-o',str(tmp/'test')],check=True)
        subprocess.run([str(tmp/'test'),str(tmp/'native.bin')],check=True)

if __name__=='__main__':run()
