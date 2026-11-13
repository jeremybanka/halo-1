"""Compare segmented PvE DMA commands with direct-address commands on real banks.

The shim checks opaque/alpha batches and shared pose owners; it does not emulate
the RSP/RDP. Native crash, pixel and validator checks remain separate.
"""
import argparse
import json
from pathlib import Path
import subprocess
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
HEADER = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "asset_pve.h"
#define assertf(v,...) assert(v)
#define T3D_SEGMENT_2 2
#define T3D_FLAG_SHADED 1
#define T3D_FLAG_DEPTH 2
#define T3D_FLAG_CULL_BACK 4
typedef struct {unsigned kind,count;uintptr_t address;} command;
typedef struct {unsigned count;command commands[512];} rspq_block_t;
static rspq_block_t recording;
static unsigned blocks;
static void emit(unsigned kind,uintptr_t address,unsigned count){
    assert(recording.count<512);
    recording.commands[recording.count++]=(command){kind,count,address};
}
static void rspq_block_begin(void){memset(&recording,0,sizeof(recording));}
static rspq_block_t*rspq_block_end(void){
    rspq_block_t*b=malloc(sizeof(*b));assert(b);*b=recording;blocks++;return b;
}
static void t3d_vert_load(T3DVertPacked*v,unsigned first,unsigned count){assert(!first);emit(1,(uintptr_t)v,count);}
static void t3d_tri_draw_strip(int16_t*indices,unsigned count){emit(2,(uintptr_t)indices,count);}
static void t3d_tri_sync(void){emit(3,0,0);}
static void __attribute__((unused)) t3d_state_set_drawflags(unsigned flags){emit(4,0,flags);}
extern const bg_pve_animation bg_enemy_pilot_animations[BG_VEHICLE_COUNT][3][3];
'''
TEST = r'''
int main(void){
    unsigned capacity=pve_decode_capacity(),independent=0;
    for(unsigned k=0;k<BG_PVE_MODELS;k++)for(unsigned l=0;l<BG_PVE_LODS;l++)for(unsigned c=0;c<PVE_CLIPS;c++){
        const bg_pve_animation*a=&bg_pve_animations[k][l][c];
        assert(a->tracks<=capacity);
        if(a->tracks>independent)independent=a->tracks;
    }
#ifdef BG_ENEMY_VEHICLES
    for(unsigned k=0;k<BG_VEHICLE_COUNT;k++)for(unsigned l=0;l<BG_PVE_LODS;l++)for(unsigned c=0;c<3;c++){
        unsigned n=bg_enemy_pilot_animations[k][l][c].tracks;assert(n<=capacity);
        if(n>independent)independent=n;
    }
#endif
    assert(independent==capacity);
    rspq_block_t*shared[BG_PVE_MODELS][BG_PVE_LODS][2];
    for(unsigned k=0;k<BG_PVE_MODELS;k++)for(unsigned l=0;l<BG_PVE_LODS;l++)for(unsigned alpha=0;alpha<2;alpha++)
        shared[k][l][alpha]=pve_record_surface(k,l,(void*)(uintptr_t)(T3D_SEGMENT_2<<26),alpha);
    unsigned initialized=blocks,checked=0;
    for(unsigned frame=0;frame<120;frame++)for(unsigned actor=0;actor<13;actor++)for(unsigned l=0;l<BG_PVE_LODS;l++){
        unsigned k=actor==12?BG_PVE_SPIRIT:(actor+frame/7)%BG_PVE_KINDS;
        /* Some actors borrow an earlier owner's vertices in this fenced slot. */
        unsigned owner=actor?actor-actor%3:0;
        for(unsigned memory=4;memory<=8;memory+=4){
            unsigned bytes=bg_pve_models[k][l].vertex_count*16;
            uintptr_t base=(frame&1)?(memory<<20)-bytes:0x10000+owner*0x2000;
            for(unsigned alpha=0;alpha<2;alpha++){
                rspq_block_t*direct=pve_record_surface(k,l,(void*)base,alpha),*b=shared[k][l][alpha];
                assert(!!direct==!!b);
                if(!b)continue;
                assert(direct->count==b->count);
                for(unsigned i=0;i<b->count;i++){
                    command actual=b->commands[i],expected=direct->commands[i];
                    if(actual.kind==1){
                        assert(actual.address>>26==T3D_SEGMENT_2);
                        actual.address=base+(actual.address&0xffffff);
                        assert(actual.address>=base&&actual.address+actual.count*16<=base+bytes);
                    }
                    assert(actual.kind==expected.kind&&actual.count==expected.count&&actual.address==expected.address);
                    checked++;
                }
                free(direct);
            }
        }
    }
    for(unsigned k=0;k<BG_PVE_MODELS;k++)for(unsigned l=0;l<BG_PVE_LODS;l++)for(unsigned a=0;a<2;a++)free(shared[k][l][a]);
    printf("PASS: %u shared blocks, %u exact commands; all species/LODs, opaque/alpha, pose owners, fenced slots and 4/8 MiB addresses; decode capacity %u tracks (%u bytes)\n",initialized,checked,capacity,capacity*8);
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bank',type=Path,action='append')
    a=p.parse_args();out=a.output.resolve();(out/'t3d').mkdir(parents=True,exist_ok=True)
    (out/'t3d/t3d.h').write_text('#pragma once\n#include <stdint.h>\ntypedef struct {int16_t posA[3];uint16_t normA;int16_t posB[3];uint16_t normB;uint32_t rgbaA,rgbaB;int16_t stA[2],stB[2];} T3DVertPacked;\n_Static_assert(sizeof(T3DVertPacked)==32,"vertex layout");\n')
    draw=(ROOT/'port/n64/pve_draw.inc').read_text()
    candidate=(ROOT/'port/n64/pve_model_candidate.inc').read_text()
    source=out/'commands.c'
    banks=a.bank or [ROOT/'halo64-assets/generated/pve',ROOT/'halo64-assets/assets/enemy-vehicles/bank']
    for i,bank in enumerate(banks):
        report=json.loads((bank/'pve-report.json').read_text())
        flags=[];extra=[]
        if report.get('lod_count',2)==3:flags+=['-DBG_PVE_CRUNCH']
        if report.get('roster'):flags+=['-DBG_PVE_ROSTER']
        if (bank/'enemy_pilot_data.c').is_file():flags+=['-DBG_ENEMY_VEHICLES'];extra+=[bank/'enemy_pilot_data.c']
        if report.get('lod_count',2)==3 or 'batch_modes' in report['grunt'][0]:
            recorder='static rspq_block_t*pve_record_surface(unsigned kind,unsigned lod,T3DVertPacked*vertices,bool alpha){'+function(candidate,'pve_record_surface')+'}\n'
        else:
            scene=(ROOT/'port/n64/scene.c').read_text()
            recorder='static rspq_block_t*record(T3DVertPacked*v,unsigned count){(void)v;(void)count;abort();}\n'
            recorder+='static rspq_block_t*record_model_range(const bg_model_asset*asset,T3DVertPacked*vertices,unsigned first,unsigned count,unsigned batch_first,unsigned batch_count){'+function(scene,'record_model_range')+'}\n'
            recorder+='static rspq_block_t*pve_record_surface(unsigned kind,unsigned lod,T3DVertPacked*vertices,bool alpha){const bg_model_asset*m=&bg_pve_models[kind][lod];if(alpha)return NULL;return record_model_range(m,vertices,0,m->vertex_count,0,m->batch_count);}\n'
        source.write_text(HEADER+'\nstatic unsigned pve_decode_capacity(void){'+function(draw,'pve_decode_capacity')+'}\n'+recorder+TEST)
        binary=out/f'commands-{i}'
        subprocess.run(['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',*flags,
            '-I'+str(out),'-I'+str(ROOT/'port/n64'),str(source),str(bank/'pve_data.c'),*map(str,extra),'-o',str(binary)],check=True)
        print('BANK',bank,flush=True);subprocess.run([str(binary)],check=True)


if __name__=='__main__':main()
