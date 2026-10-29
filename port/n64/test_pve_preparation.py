"""Check actual motion banks/cache/pose ownership against independent old loops."""
import argparse,subprocess
from pathlib import Path
from test_render_matrix import function
ROOT=Path(__file__).resolve().parents[2]
BASE='1ab58a383edbe0d12c0457feb25d598ed60a2e4d'
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/firefight-preparation/host-preparation');p.add_argument('--bank',type=Path,action='append');a=p.parse_args()
    out=a.output.resolve();(out/'t3d').mkdir(parents=True,exist_ok=True)
    (out/'t3d/t3d.h').write_text('#pragma once\n#include <stdint.h>\ntypedef struct {int16_t posA[3];uint16_t normA;int16_t posB[3];uint16_t normB;uint32_t rgbaA,rgbaB;int16_t stA[2],stB[2];} T3DVertPacked;\n_Static_assert(sizeof(T3DVertPacked)==32,"packed vertex layout");\n')
    old=subprocess.check_output(['git','show',BASE+':port/n64/pve_draw.inc'],cwd=ROOT,text=True)
    loops=old[old.index('            for(unsigned t=0;t<clip->tracks;t++)'):old.index('            data_cache_hit_writeback(out,m->vertex_count*16);')]
    (out/'pve_preparation_reference.inc').write_text('static int16_t pve_decoded[8192][3];\nstatic void reference_apply(const bg_pve_animation*clip,const uint16_t*samples,unsigned f0,unsigned f1,int mix,unsigned kind,unsigned lod,float shield,T3DVertPacked*out){struct {unsigned kind;} actor={kind},*a=&actor;struct {float shield;} player={shield},*p=&player;\n'+loops+'}\n')
    source=(ROOT/'port/n64/pve_draw.inc').read_text()
    (out/'pve_preparation_share.inc').write_text('static unsigned pve_shared_pose(unsigned i,unsigned lod,uint32_t key){'+function(source,'pve_shared_pose')+'}\n')
    prepare=function(source,'pve_prepare');assert prepare.index('memset(pve_frame_keys,0')<prepare.index('if(!bg_pve_is_active())return;')
    banks=a.bank or [ROOT/'halo64-assets/generated/pve',ROOT/'halo64-assets/assets/covenant-model-appraisal/bank']
    for i,bank in enumerate(banks):
        binary=out/f'test-{i}'
        command=['clang','-std=c17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-variable','-fsanitize=address,undefined','-I'+str(out),'-I'+str(ROOT/'port/n64'),str(ROOT/'port/n64/test_pve_preparation.c'),str(bank/'pve_data.c'),'-o',str(binary)]
        subprocess.run(command,check=True);print('BANK',bank,flush=True);subprocess.run([str(binary),str(bank/'pve-motion.bin')],check=True)
if __name__=='__main__':main()
