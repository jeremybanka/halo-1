"""Check immutable texture blocks reproduce the original bind commands.

The fake recorder owns copied commands, just as the target RSP block does.
SDK TMEM/auto-sync behavior must also pass the real ROM's RDP validator.
"""

from pathlib import Path
import subprocess
from runtime_source import validation_output
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
C = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct{int id,width,height,format;}surface_t;
typedef struct{struct{float repeats;}s,t;}rdpq_texparms_t;
enum{TILE0=0};
#define REPEAT_INFINITE 1024.f
typedef struct{unsigned kind;uintptr_t pointer;unsigned a,b;float s,t;}command;
typedef struct{unsigned count;command commands[2];}rspq_block_t;
static surface_t textures[32];static uint16_t bg_ground_palette[16];
static uint8_t bg_texture_ci4[32];
static rspq_block_t blocks[32],*recording;
static command queue[1024];static unsigned count,cpu_uploads;
static void emit(command c){if(recording)recording->commands[recording->count++]=c;else queue[count++]=c;}
static void rspq_block_begin(void){static unsigned n;recording=&blocks[n++];}
static rspq_block_t*rspq_block_end(void){rspq_block_t*b=recording;recording=NULL;return b;}
static void rspq_block_run(rspq_block_t*b){for(unsigned i=0;i<b->count;i++)emit(b->commands[i]);}
static void rdpq_tex_upload_tlut(uint16_t*p,unsigned at,unsigned n){cpu_uploads++;emit((command){1,(uintptr_t)p,at,n,0,0});}
static void rdpq_tex_upload(unsigned tile,surface_t*p,const rdpq_texparms_t*t){cpu_uploads++;emit((command){2,(uintptr_t)p,tile,0,t->s.repeats,t->t.repeats});}
RECORD
int main(void){
    rspq_block_t*cached[32];
    for(unsigned i=0;i<32;i++){textures[i]=(surface_t){i,i%4?32:64,32,i%3};bg_texture_ci4[i]=i%3==0;cached[i]=record_texture(i);}
    unsigned prepared_uploads=cpu_uploads;
    for(unsigned frame=0;frame<200;frame++){
        command expected[1024];count=0;
        for(unsigned i=0;i<128;i++){
            unsigned m=(frame*17+i*13)%32;
            if(bg_texture_ci4[m])rdpq_tex_upload_tlut(bg_ground_palette,0,16);
            rdpq_tex_upload(TILE0,&textures[m],&(rdpq_texparms_t){.s.repeats=REPEAT_INFINITE,.t.repeats=REPEAT_INFINITE});
        }
        unsigned n=count;memcpy(expected,queue,n*sizeof(*expected));count=0;unsigned before=cpu_uploads;
        for(unsigned i=0;i<128;i++)rspq_block_run(cached[(frame*17+i*13)%32]);
        assert(cpu_uploads==before);assert(count==n&&!memcmp(queue,expected,n*sizeof(*expected)));
    }
    printf("PASS: 25600 binds reproduce palette/image/parameter commands; %u texture setups run only during recording\n",prepared_uploads);
}
"""
out = validation_output("texture-blocks")
out.mkdir(parents=True, exist_ok=True)
source = out / "texture.c"
source.write_text(
    C.replace(
        "RECORD",
        "static rspq_block_t*record_texture(unsigned material){"
        + function((ROOT / "port/n64/scene.c").read_text(), "record_texture")
        + "}",
    )
)
binary = out / "texture"
subprocess.run(
    [
        "clang",
        "-std=c17",
        "-O2",
        "-g",
        "-fsanitize=address,undefined",
        str(source),
        "-o",
        str(binary),
    ],
    check=True,
)
subprocess.run([str(binary)], check=True)
