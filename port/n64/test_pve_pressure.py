"""Exercise the production pre-draw pressure retry and mixed-view LOD plan."""
import argparse
from pathlib import Path
import subprocess
from test_render_matrix import function

ROOT=Path(__file__).resolve().parents[2]
HEADER=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define assertf(v,...) assert(v)
#define BG_FRAME_SLOTS 2
#define BG_PVE_MAX 12
#define BG_PVE_MODELS 5
#define BG_PVE_MODEL_CANDIDATE
#define BG_PVE_JACKAL_SHIELDS
typedef struct {unsigned frame;} T3DVertPacked;
typedef struct {unsigned unused;} rspq_block_t;
static T3DVertPacked*pve_vertices[2][13][BG_PVE_LODS];
static rspq_block_t*pve_blocks[5][BG_PVE_LODS],*pve_alpha_blocks[5][BG_PVE_LODS],*jackal_shield_block;
static unsigned jackal_shield_flashes[12],jackal_shield_flash_values[12];
static uint32_t pve_pose_keys[2][13][BG_PVE_LODS];
static uint8_t pve_lods[4][13];
static bool pve_shared_lod,pve_commands_ready,pve_initialized,busy[2];
static unsigned views,fences,freed,blocks_freed;
static void rspq_wait(void){fences++;busy[0]=busy[1]=false;}
static void free_uncached(T3DVertPacked*p){assert(!busy[p->frame]);freed++;free(p);}
static void rspq_block_free(rspq_block_t*p){assert(!busy[0]&&!busy[1]);blocks_freed++;free(p);}
#ifndef BG_PVE_PREP_BASELINE
typedef struct {unsigned unused;} bg_pve_motion_cache;
static bg_pve_motion_cache *pve_motion_cache;
static uint8_t *pve_motion_fallback;
static void *pve_decoded;
static unsigned pve_decoded_capacity,window_bytes;
static uint32_t pve_frame_keys[12][BG_PVE_LODS];
static void bg_pve_motion_cache_reset(bg_pve_motion_cache*c){memset(c,0,sizeof(*c));}
static void*memalign(unsigned alignment,unsigned bytes){
    window_bytes=bytes;return aligned_alloc(alignment,(bytes+alignment-1)&~(alignment-1));
}
#endif
'''
TEST=r'''
int main(void){
    unsigned plans=0;
    for(views=1;views<=4;views++){
        unsigned count=1;for(unsigned v=0;v<views;v++)count*=BG_PVE_LODS+1;
        for(unsigned state=0;state<count;state++){
            memset(pve_lods,0,sizeof(pve_lods));
            for(unsigned v=0;v<4;v++){pve_lods[v][2]=2;pve_lods[v][4]=1;}
            unsigned code=state,wanted=0,best=BG_PVE_LODS;
            for(unsigned v=0;v<views;v++){
                unsigned request=code%(BG_PVE_LODS+1);code/=BG_PVE_LODS+1;pve_lods[v][3]=request;
                if(request){wanted|=1u<<(request-1);if(request-1<best)best=request-1;}
            }
            uint8_t before[4][13];memcpy(before,pve_lods,sizeof(before));
            pve_shared_lod=false;assert(pve_actor_lods(3,wanted)==wanted);assert(!memcmp(before,pve_lods,sizeof(before)));
            pve_shared_lod=true;unsigned actual=pve_actor_lods(3,wanted);
            assert(actual==(wanted?1u<<best:0));
            for(unsigned v=0;v<4;v++)for(unsigned i=0;i<13;i++){
                unsigned expected=i==3&&v<views&&before[v][i]?best+1:before[v][i];
                assert(pve_lods[v][i]==expected);
            }
            plans++;
        }
    }
    /* Nothing from the current preparation has been queued for drawing yet.
     * Previous-slot readers must finish before either slot can be reclaimed. */
    pve_shared_lod=false;busy[0]=busy[1]=true;
#ifndef BG_PVE_PREP_BASELINE
    pve_decoded_capacity=680;pve_decoded=malloc(680*8);assert(pve_decoded);
    pve_motion_cache=malloc(sizeof(*pve_motion_cache));assert(pve_motion_cache);
#endif
    for(unsigned s=0;s<2;s++)for(unsigned i=0;i<13;i++)for(unsigned l=0;l<BG_PVE_LODS;l++){
        pve_vertices[s][i][l]=malloc(sizeof(T3DVertPacked));assert(pve_vertices[s][i][l]);
        pve_vertices[s][i][l]->frame=s;pve_pose_keys[s][i][l]=123;
    }
    assert(pve_retry_shared_lod()&&pve_shared_lod&&fences==1);
#ifndef BG_PVE_PREP_BASELINE
    assert(!pve_motion_cache&&pve_motion_fallback&&window_bytes==8192);
#endif
    for(unsigned s=0;s<2;s++)for(unsigned i=0;i<13;i++)for(unsigned l=0;l<BG_PVE_LODS;l++)
        assert(!pve_vertices[s][i][l]&&!pve_pose_keys[s][i][l]);
    assert(freed==2*13*BG_PVE_LODS);
    /* A second failure may not recurse again or discard the retry's owners. */
    pve_vertices[1][0][0]=malloc(sizeof(T3DVertPacked));assert(pve_vertices[1][0][0]);pve_vertices[1][0][0]->frame=1;
    pve_pose_keys[1][0][0]=456;
    assert(!pve_retry_shared_lod()&&fences==1&&pve_vertices[1][0][0]&&pve_pose_keys[1][0][0]==456);
    pve_drop_buffer(1,0,0);
    /* Teardown must clear the latched policy and attachment commands, while
     * retaining the one-time index conversion marker across match restarts. */
    pve_initialized=pve_commands_ready=true;busy[0]=busy[1]=true;
    memset(pve_lods,1,sizeof(pve_lods));
    memset(jackal_shield_flashes,1,sizeof(jackal_shield_flashes));
    memset(jackal_shield_flash_values,1,sizeof(jackal_shield_flash_values));
    for(unsigned k=0;k<5;k++)for(unsigned l=0;l<BG_PVE_LODS;l++){
        pve_blocks[k][l]=malloc(sizeof(rspq_block_t));pve_alpha_blocks[k][l]=malloc(sizeof(rspq_block_t));
        assert(pve_blocks[k][l]&&pve_alpha_blocks[k][l]);
    }
    jackal_shield_block=malloc(sizeof(rspq_block_t));assert(jackal_shield_block);
    pve_release();
    assert(fences==2&&blocks_freed==10*BG_PVE_LODS+1&&!jackal_shield_block);
    assert(pve_initialized&&!pve_commands_ready&&!pve_shared_lod);
#ifndef BG_PVE_PREP_BASELINE
    assert(!pve_motion_cache&&!pve_motion_fallback&&!pve_decoded&&!pve_decoded_capacity);
#endif
    for(unsigned k=0;k<5;k++)for(unsigned l=0;l<BG_PVE_LODS;l++)assert(!pve_blocks[k][l]&&!pve_alpha_blocks[k][l]);
    for(unsigned v=0;v<4;v++)for(unsigned i=0;i<13;i++)assert(!pve_lods[v][i]);
    for(unsigned i=0;i<12;i++)assert(!jackal_shield_flashes[i]&&!jackal_shield_flash_values[i]);
    pve_release();assert(fences==3&&blocks_freed==10*BG_PVE_LODS+1&&pve_initialized);
    printf("PASS: %u LODs / %u view plans; unchanged normal selection, highest requested detail, hidden-view isolation, fenced whole-frame retirement, exactly one retry and idempotent residency teardown\n",BG_PVE_LODS,plans);
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'port/n64/pve_draw.inc').read_text()
    shield=(ROOT/'port/n64/pve_jackal_shield.inc').read_text()
    helpers='static void jackal_shield_reset(void){'+function(shield,'jackal_shield_reset')+'}\n'
    for name,args,kind in [
        ('pve_drop_buffer','unsigned frame,unsigned actor,unsigned lod','void'),
        ('pve_retry_shared_lod','void','bool'),('pve_detail_lod','unsigned wanted','unsigned'),
        ('pve_actor_lods','unsigned actor,unsigned wanted','unsigned'),('pve_release','void','void')]:
        helpers+='static '+kind+' '+name+'('+args+'){'+function(source,name)+'}\n'
    test=out/'pressure.c';test.write_text(HEADER+helpers+TEST)
    for lods in (2,3):
        binary=out/f'pressure-{lods}'
        subprocess.run(['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
            f'-DBG_PVE_LODS={lods}','-DBG_PVE_PREP_BASELINE' if lods==2 else '-DBG_ENEMY_VEHICLES',
            str(test),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


if __name__=='__main__':main()
