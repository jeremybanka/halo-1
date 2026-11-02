"""Check original artwork, real packed indices/UVs and sanitized C decal state.

Host RDP calls are substitutes: native RDP validation remains a separate gate.
"""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(art,bank,source,output):
    output.mkdir(parents=True,exist_ok=True);metadata=json.loads((art/'faces.json').read_text());candidate=json.loads(source.read_text());body=json.loads((bank/'gungnir-report.json').read_text());text=(art/'gungnir_faces_data.c').read_text()
    assert metadata['source_candidate_sha256']==sha(source) and metadata['body_bank_sha256']==sha(bank/'gungnir.bin')==body['bank_sha256']
    assert metadata['tmem_bytes']==4096 and metadata['total_texture_bytes']==16384
    encoded=text.split('aligned(8)))={',1)[1].split('};',1)[0];values=np.array(list(map(int,re.findall(r'\d+',encoded))),dtype=np.uint8).reshape(4,64,64)
    for i,row in enumerate(metadata['profiles']):
        p=art/row['file'];assert row['profile']==i and sha(p)==row['sha256'];pixels=np.array(Image.open(p).convert('RGBA'));assert pixels.shape==(64,64,4)
        assert np.array_equal((values[i]&15)*17,pixels[:,:,3])
        visible=pixels[:,:,3]>0;expected=pixels[:,:,:3][visible].astype(int);actual=((values[i]>>4)*17)[visible,None]
        assert np.abs(expected-actual).max()<=8
        assert not ((expected[:,0]>150)&(expected[:,1]>50)&(expected[:,1]<210)&(expected[:,2]<70)).any()
    for lod,row in enumerate(metadata['lods']):
        d=np.load(bank/f'gungnir-{lod}-preview.npz');r=body['lods'][lod];indices=list(map(int,re.search(rf'static int16_t face_indices_{lod}\[\].*?=\{{([^}}]*)\}};',text).group(1).split(',')));actual=[]
        for first,count,off,num in row['batches']:
            assert first%2==off%4==0 and count<=60 and num<=120 and num%3==0 and first+count<=r['vertices']
            ids=np.array(indices[off:off+num]);assert ids.min()>=0 and ids.max()<count;actual.extend((ids+first).reshape(-1,3).tolist())
        expected=d['triangles'][row['triangle_ids']];assert np.array_equal(actual,expected)
        for triangle in expected:
            assert all(candidate['lods'][lod]['triangles'][int(d['sources'][vi])//3]['component']=='helmet-shell' for vi in triangle),'Decal reaches an optic or another armor surface'
        assert row['overlay_triangles']==len(expected) and row['body_vertices_unchanged']==r['vertices'] and row['body_triangles_unchanged']==r['triangles']
        assert np.isfinite(row['uv']).all() and len(row['uv'])==r['vertices']
    stub=output/'include';(stub/'t3d').mkdir(parents=True)
    (stub/'t3d/t3d.h').write_text('''#pragma once
#include <stdint.h>
typedef struct {int16_t a[3];uint16_t na;int16_t b[3];uint16_t nb;uint32_t ca,cb;int16_t sa[2],sb[2];} T3DVertPacked;
static inline int16_t*t3d_vertbuffer_get_uv(T3DVertPacked*p,unsigned i){return i&1?p[i/2].sb:p[i/2].sa;}
enum {T3D_FLAG_SHADED=1,T3D_FLAG_DEPTH=2,T3D_FLAG_CULL_BACK=4,T3D_FLAG_TEXTURED=8};
void t3d_indexbuffer_convert(int16_t*,unsigned);void t3d_vert_load(const T3DVertPacked*,unsigned,unsigned);void t3d_tri_draw_strip(const int16_t*,unsigned);void t3d_tri_sync(void);void t3d_state_set_drawflags(unsigned);
''')
    (stub/'libdragon.h').write_text('''#pragma once
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#define assertf(x,...) assert(x)
typedef struct{unsigned triangles,loads;}rspq_block_t;
typedef struct{void*buffer;int format,width,height;}surface_t;
static inline surface_t surface_make_linear(void*p,int f,int w,int h){return(surface_t){p,f,w,h};}
enum{FMT_IA8=8,AA_NONE,FILTER_BILINEAR,TLUT_NONE,MIPMAP_NONE,TILE0};
#define RDPQ_BLENDER_MULTIPLY 1
#define RDPQ_COMBINER_TEX 0
#define RDPQ_COMBINER1(...) 0
#define RDPQ_COMBINER2(...) 0
#define SOM_ZMODE_MASK 3072
#define SOM_ZMODE_DECAL 3072
void rspq_block_begin(void);rspq_block_t*rspq_block_end(void);void rspq_block_run(rspq_block_t*);
void rdpq_mode_push(void);void rdpq_mode_pop(void);void rdpq_mode_zbuf(bool,bool);void rdpq_change_other_modes_raw(uint64_t,uint64_t);int rdpq_tex_upload(int,const surface_t*,const void*);
#define data_cache_hit_writeback(p,n) ((void)(p),(void)(n))
#define rdpq_sync_pipe() ((void)0)
#define rdpq_sync_tile() ((void)0)
#define rdpq_sync_load() ((void)0)
#define rdpq_mode_begin() ((void)0)
#define rdpq_mode_end() ((void)0)
#define rdpq_mode_antialias(x) ((void)(x))
#define rdpq_mode_alphacompare(x) ((void)(x))
#define rdpq_mode_persp(x) ((void)(x))
#define rdpq_mode_filter(x) ((void)(x))
#define rdpq_mode_tlut(x) ((void)(x))
#define rdpq_mode_blender(x) ((void)(x))
#define rdpq_mode_combiner(x) ((void)(x))
#define rdpq_mode_mipmap(x,y) ((void)(x),(void)(y))
''')
    test=output/'test.c';test.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gungnir_faces.h"
static T3DVertPacked*bound;static unsigned bound_count,drawflags,conversions,uploads,expected_profile;static rspq_block_t recording;static bool compare,update;static unsigned zmode,stack;
void t3d_indexbuffer_convert(int16_t*p,unsigned n){assert(p&&n&&n<=120&&n%3==0);conversions++;}
void t3d_vert_load(const T3DVertPacked*p,unsigned off,unsigned n){assert(off==0&&n<=60&&(const uint8_t*)p>=(uint8_t*)bound&&(const uint8_t*)p+n*16<=(uint8_t*)bound+bound_count*16);recording.loads+=n;}
void t3d_tri_draw_strip(const int16_t*p,unsigned n){assert(p&&n<=120&&n%3==0);recording.triangles+=n/3;}
void t3d_tri_sync(void){}
void t3d_state_set_drawflags(unsigned f){drawflags=f;}
void rspq_block_begin(void){recording=(rspq_block_t){0};}
rspq_block_t*rspq_block_end(void){return &recording;}
void rspq_block_run(rspq_block_t*b){assert(b&&compare&&!update&&zmode==SOM_ZMODE_DECAL&&(drawflags&T3D_FLAG_TEXTURED));}
void rdpq_mode_push(void){assert(!stack);stack++;}
void rdpq_mode_pop(void){assert(stack==1);stack--;}
void rdpq_mode_zbuf(bool c,bool u){compare=c;update=u;}
void rdpq_change_other_modes_raw(uint64_t mask,uint64_t v){assert(mask==SOM_ZMODE_MASK);zmode=v;}
int rdpq_tex_upload(int tile,const surface_t*t,const void*p){assert(tile==TILE0&&t->format==FMT_IA8&&t->width==64&&t->height==64&&!p&&t->buffer==(void*)bg_gungnir_face_textures[expected_profile]);uploads++;return 4096;}
int main(void){
unsigned counts[2]={1064,784};
for(unsigned cycle=0;cycle<3;cycle++)for(unsigned lod=0;lod<2;lod++){
 bound_count=counts[lod];bound=malloc(bound_count*16);uint8_t*original=malloc(bound_count*16);
 for(unsigned i=0;i<bound_count*16;i++)((uint8_t*)bound)[i]=(i*17+lod)&255;
 memcpy(original,bound,bound_count*16);bg_model_asset model={.vertices=bound,.vertex_count=bound_count};bg_gungnir_faces_prepare(&model,lod);
 for(unsigned i=0;i<bound_count*16;i++)if(i%32<24)assert(((uint8_t*)bound)[i]==original[i]);
 const bg_gungnir_face_mesh*f=&bg_gungnir_faces[lod];for(unsigned i=0;i<f->uv_count;i++){const bg_gungnir_face_uv*u=&f->uv[i];int16_t*st=t3d_vertbuffer_get_uv(bound,u->vertex);assert(st[0]==u->s&&st[1]==u->t);}
 rspq_block_t*b=bg_gungnir_faces_record(bound,lod);assert(b->triangles==f->triangles&&b->loads==f->vertex_loads);
 for(expected_profile=0;expected_profile<4;expected_profile++)for(unsigned fading=0;fading<2;fading++)for(unsigned shield=0;shield<2;shield++){bg_gungnir_faces_draw(b,expected_profile,fading,shield);assert(!stack&&!(drawflags&T3D_FLAG_TEXTURED));}
 free(original);free(bound);
}
assert(conversions==bg_gungnir_faces[0].batch_count+bg_gungnir_faces[1].batch_count);assert(uploads==96);puts("PASS: exact-sized UV updates preserve positions/colors, reload-safe indices, 96 profile/fade/shield decal calls, 4096-byte textures and restored draw flags");return 0;
}
''')
    exe=output/'test';command=['clang','-std=gnu17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-I'+str(stub),'-I'+str(ROOT/'port/n64'),str(test),str(ROOT/'port/n64/gungnir_faces.c'),str(art/'gungnir_faces_data.c'),'-o',str(exe)]
    subprocess.run(command,check=True);subprocess.run([str(exe)],check=True)
    result=dict(schema=1,passed=True,source_candidate_sha256=sha(source),body_bank_sha256=sha(bank/'gungnir.bin'),generated_data_sha256=sha(art/'gungnir_faces_data.c'),metadata_sha256=sha(art/'faces.json'),sanitizers_passed=True,state_cases=96,tmem_bytes=4096,body_geometry_unchanged=True,original_alpha_unchanged=True,profiles=metadata['profiles'],overlay_triangles=[r['overlay_triangles'] for r in metadata['lods']],extra_vertex_loads=[r['extra_vertex_loads'] for r in metadata['lods']],inputs={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'port/n64/gungnir_faces.c',ROOT/'port/n64/gungnir_faces.h',ROOT/'port/n64/gungnir_faces.py',ROOT/'port/n64/test_gungnir_faces.py']},scope='Host source/packed-index/UV/alpha evidence and real C memory/state calls with substituted RDP/RSP APIs. Native RDP/appearance remains separate.')
    (output/'faces-validation.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('art','bank','source','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.art,a.bank,a.source,a.output)
