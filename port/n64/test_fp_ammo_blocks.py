"""Check actual counter recording, replay order and mutable-buffer ownership.

The host shim captures SDK calls and the documented PIPE tracking boundary;
it does not emulate RSP triangles or replace target RDP/pixel validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint8_t bytes[32]; } T3DVertPacked;
typedef struct { uint8_t bytes[64]; } T3DMat4FP;
typedef struct { void *pixels; int format,width,height,stride; } surface_t;
#define BG_FP_SCALE 256.f
#define BG_AR_AMMO_SCALE 4096.f
enum { FMT_RGBA16=2,
 BG_AR_AMMO_TEXTURE_WIDTH=100, BG_AR_AMMO_TEXTURE_HEIGHT=16,
 RDPQ_COMBINER_TEX=1, TLUT_NONE=0, FILTER_BILINEAR=2, TILE0=0,
 T3D_FLAG_TEXTURED=1,T3D_FLAG_CULL_BACK=2,T3D_FLAG_SHADED=4,T3D_FLAG_CULL_FRONT=8 };
static uint16_t bg_ar_ammo_texture[1600];
typedef struct { unsigned kind; uintptr_t pointer; int a,b; } command;
typedef struct { command commands[40]; unsigned count; bool pipe_tracking; } rspq_block_t;
typedef struct { command cmd; uint32_t vertex_contents; } event;
static rspq_block_t pool[8],*recording;
static unsigned allocated,trace_count,cpu_calls,runs;
static bool tracked,saved_tracking;
static event trace[40];
static void emit(command c) {
    if(recording) { assert(recording->count<40);recording->commands[recording->count++]=c;return; }
    assert(trace_count<40);event *e=&trace[trace_count++];memset(e,0,sizeof(*e));e->cmd=c;
    if(c.kind==14) { /* The DMA source is read on replay, not on recording. */
        const uint8_t *bytes=(const uint8_t *)c.pointer;
        for(int i=0;i<c.b*16;i++)e->vertex_contents=e->vertex_contents*31+bytes[i];
    }
}
static void rspq_block_begin(void){assert(!recording&&allocated<8);saved_tracking=tracked;tracked=true;recording=&pool[allocated++];}
static rspq_block_t *rspq_block_end(void){rspq_block_t*b=recording;assert(b);b->pipe_tracking=tracked;recording=NULL;tracked=saved_tracking;return b;}
static void rspq_block_run(rspq_block_t*b){assert(!recording&&b>=pool&&b<pool+allocated);runs++;tracked=b->pipe_tracking;for(unsigned i=0;i<b->count;i++)emit(b->commands[i]);}
static void rdpq_sync_pipe(void){cpu_calls++;tracked=false;emit((command){.kind=19});}
static void mode(unsigned kind,int value){cpu_calls++;if(tracked){tracked=false;emit((command){.kind=19});}emit((command){.kind=kind,.a=value});}
static void t3d_tri_sync(void){cpu_calls++;emit((command){.kind=1});}
static void rdpq_mode_push(void){cpu_calls++;emit((command){.kind=2});}
static void rdpq_mode_begin(void){mode(3,0);}
static void rdpq_mode_combiner(int v){mode(4,v);}
static void rdpq_mode_blender(int v){mode(5,v);}
static void rdpq_mode_alphacompare(int v){mode(6,v);}
static void rdpq_mode_tlut(int v){mode(7,v);}
static void rdpq_mode_filter(int v){mode(8,v);}
static void rdpq_mode_persp(bool v){mode(9,v);}
static void rdpq_mode_end(void){mode(10,0);}
static void rdpq_tex_upload(int tile,surface_t*s,void*p){assert(!p&&s->pixels==bg_ar_ammo_texture);cpu_calls++;emit((command){.kind=11,.pointer=(uintptr_t)s->pixels,.a=tile,.b=s->stride});}
static void t3d_state_set_drawflags(int f){cpu_calls++;emit((command){.kind=12,.a=f});}
static void t3d_matrix_push(void*p){cpu_calls++;emit((command){.kind=13,.pointer=(uintptr_t)p});}
static void t3d_vert_load(void*p,int first,int count){cpu_calls++;emit((command){.kind=14,.pointer=(uintptr_t)p,.a=first,.b=count});}
static void t3d_tri_draw_strip(void*p,int n){cpu_calls++;emit((command){.kind=15,.pointer=(uintptr_t)p,.a=n});}
static void t3d_matrix_pop(int n){cpu_calls++;emit((command){.kind=16,.a=n});}
static void rdpq_mode_pop(void){mode(17,0);}
static void t3d_mat4fp_from_srt_euler(T3DMat4FP*m,float*s,float*r,float*t){assert(s[0]>0&&r[0]==0&&t[0]==0);memset(m,0,sizeof(*m));}
static void data_cache_hit_writeback(void*p,unsigned n){assert(p&&n);}
static void t3d_indexbuffer_convert(int16_t*p,int n){assert(p&&n==12);}
static surface_t surface_make(void*p,int f,int w,int h,int stride){return(surface_t){p,f,w,h,stride};}
@DECLARATIONS@
static void draw_counter(unsigned slot,unsigned player){@BODY@}
void bg_fp_ammo_init(void){@INIT@}
void bg_fp_ammo_draw(unsigned slot,unsigned player){@DRAW@}
int main(void){
    tracked=false;bg_fp_ammo_init();assert(allocated==8&&!recording&&!trace_count&&!tracked);
    unsigned cases=0,direct_calls=0;
    for(unsigned repeat=0;repeat<128;repeat++)for(unsigned slot=0;slot<2;slot++)for(unsigned player=0;player<4;player++){
        memset(digits[slot][player],1+repeat+slot*4+player,sizeof(digits[slot][player]));
        event expected[40];tracked=true;trace_count=cpu_calls=0;draw_counter(slot,player);
        unsigned count=trace_count;direct_calls=cpu_calls;assert(!tracked);memcpy(expected,trace,sizeof(expected));
        tracked=true;trace_count=cpu_calls=0;unsigned old_runs=runs;bg_fp_ammo_draw(slot,player);
        assert(runs==old_runs+1&&cpu_calls==0&&!tracked&&trace_count==count);
        assert(!memcmp(expected,trace,count*sizeof(*trace)));
        unsigned loads=0,syncs=0;
        for(unsigned i=0;i<count;i++){
            if(trace[i].cmd.kind==14){loads++;assert(trace[i].cmd.pointer==(uintptr_t)digits[slot][player]&&trace[i].cmd.b==8&&trace[i].vertex_contents);}
            syncs+=trace[i].cmd.kind==19;
        }
        assert(loads==1&&syncs==2);cases++;
    }
    printf("PASS: %u exact direct/replayed traces; 8 unique slot/player buffers; updated bytes read on replay; setup calls %u->0 plus one block run; 2 PIPE syncs retained\n",cases,direct_calls);
}
'''


def run(output, sdk, cc):
    source_path = ROOT/'port/n64/firstperson_ammo.c'
    source = source_path.read_text()
    # Verify assumptions against the installed block implementation, rather
    # than treating the shim as an independent replacement for libdragon.
    rdpq = (sdk/'src/rdpq/rdpq.c').read_text()
    begin = compact(function(rdpq, '__rdpq_block_begin'))
    end = compact(function(rdpq, '__rdpq_block_end'))
    replay = compact(function(rdpq, '__rdpq_block_run'))
    assert '__rdpq_block_run(NULL);' in begin
    assert '.autosync=~0' in replay and 'rdpq_tracking=block->tracking;' in replay
    assert 'st->first_node->tracking=rdpq_tracking;' in end
    assert 'rdpq_tracking=st->previous_tracking;' in end
    draw = function(source, 'bg_fp_ammo_draw')
    assert compact(draw) == 'assert(slot<2&&player<4);rspq_block_run(counter_blocks[slot][player]);'
    declarations = source[source.index('static T3DVertPacked digits'):source.index('void bg_fp_ammo_init')]
    text = HARNESS.replace('@DECLARATIONS@', declarations)
    for marker, name in [('BODY','draw_counter'), ('INIT','bg_fp_ammo_init'), ('DRAW','bg_fp_ammo_draw')]:
        text = text.replace('@'+marker+'@', function(source, name))
    output.mkdir(parents=True, exist_ok=True)
    c = output/'counter-blocks.c';c.write_text(text)
    binary = output/'counter-blocks'
    command = [cc, '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', str(c), '-o', str(binary)]
    subprocess.run(command, check=True)
    result = subprocess.check_output([str(binary)], text=True).strip()
    print(result)
    proof = {'status':'pass', 'scope':__doc__, 'result':result, 'command':command,
             'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
             'sdk_rdpq_sha256':hashlib.sha256(rdpq.encode()).hexdigest(),
             'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/n64/visibility-weapon-qa/rdp-counter-blocks')
    parser.add_argument('--sdk-source', type=Path, default=ROOT.parent/'n64-2048/.build/libdragon-src')
    parser.add_argument('--cc', default='clang')
    args = parser.parse_args();run(args.output, args.sdk_source, args.cc)
