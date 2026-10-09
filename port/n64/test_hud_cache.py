"""Compare the actual indexed HUD cache with its original linear implementation.

The host SDK shim records every begin/blit/end/run and the selected stable block
identity. It does not measure N64 time or stand in for target pixel validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]

# Original implementation, retained as an independent command-stream oracle.
LINEAR = r'''
    const bg_hud_image *im=&bg_hud_images[id];
    x+=im->x*scale;y+=im->y*scale;
    if (id!=BG_H_BLIP) {
        for (unsigned i=0;i<old_count;i++) {
            const hud_blit *b=&old_blits[i];
            ++visits[0];
            if(b->id==id&&b->x==x&&b->y==y&&b->scale==scale) {
                rspq_block_run(b->block);return;
            }
        }
        if(old_count<sizeof(old_blits)/sizeof(old_blits[0])) {
            hud_blit *b=&old_blits[old_count++];
            *b=(hud_blit){.id=id,.x=x,.y=y,.scale=scale};
            rspq_block_begin();
            rdpq_tex_blit(&images[id],x,y,&(rdpq_blitparms_t){
                .scale_x=scale,.scale_y=scale,.filtering=true});
            b->block=rspq_block_end();rspq_block_run(b->block);return;
        }
    }
    rdpq_tex_blit(&images[id],x,y,&(rdpq_blitparms_t){
        .scale_x=scale,.scale_y=scale,.filtering=true});
'''

HARNESS = r'''
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "asset_hud.h"
typedef struct { unsigned id; } surface_t;
typedef struct { unsigned serial; } rspq_block_t;
typedef struct { float scale_x,scale_y; bool filtering; } rdpq_blitparms_t;
static surface_t images[BG_H_COUNT];
const bg_hud_image bg_hud_images[BG_H_COUNT]={@IMAGES@};
typedef struct { uint32_t kind,id,x,y,sx,sy,filtering; } event;
static struct { event events[4]; unsigned count,blocks; rspq_block_t pool[192]; bool recording; } commands[2];
static unsigned active;
static uint64_t visits[2],requests,hits,misses,fallbacks;
static uint32_t float_bits(float f) { uint32_t bits;memcpy(&bits,&f,4);return bits; }
static void emit(event e) {
    assert(commands[active].count<4);
    commands[active].events[commands[active].count++]=e;
}
static void rspq_block_begin(void) {
    assert(!commands[active].recording);commands[active].recording=true;
    emit((event){.kind=1});
}
static void rdpq_tex_blit(surface_t *im,float x,float y,const rdpq_blitparms_t *p) {
    assert(im>=images&&im<images+BG_H_COUNT);
    emit((event){.kind=2,.id=im->id,.x=float_bits(x),.y=float_bits(y),
        .sx=float_bits(p->scale_x),.sy=float_bits(p->scale_y),.filtering=p->filtering});
}
static rspq_block_t *rspq_block_end(void) {
    assert(commands[active].recording);commands[active].recording=false;
    unsigned index=commands[active].blocks++;
    assert(index<192);
    rspq_block_t *b=&commands[active].pool[index];b->serial=index;
    emit((event){.kind=3,.id=index});return b;
}
static void rspq_block_run(rspq_block_t *b) {
    assert(b>=commands[active].pool&&b<commands[active].pool+commands[active].blocks);
    emit((event){.kind=4,.id=b->serial});
}
@DECLS@
static hud_blit old_blits[192];
static unsigned old_count;
static void linear(unsigned id,float x,float y,float scale) {@LINEAR@}
static void indexed(unsigned id,float x,float y,float scale) {@INDEXED@}

static uint32_t rng=0x48ce1064;
static unsigned random_u32(void) { rng=rng*1664525u+1013904223u;return rng; }
static void verify(void) {
    assert(blit_count==old_count&&blit_count<=192);
    assert(commands[0].blocks==commands[1].blocks&&commands[0].blocks==blit_count);
    assert(!commands[0].recording&&!commands[1].recording);
    bool seen[192]={0};unsigned linked=0;
    for (unsigned id=0;id<BG_H_COUNT;id++) {
        unsigned previous=0;
        for (unsigned link=blit_heads[id];link;link=blit_next[link-1]) {
            assert(link<=blit_count&&link>previous&&!seen[link-1]);
            previous=link;seen[link-1]=true;linked++;
            assert(blits[link-1].id==id&&id!=BG_H_BLIP);
        }
    }
    assert(linked==blit_count);
    for (unsigned i=0;i<blit_count;i++) {
        const hud_blit *a=&blits[i],*b=&old_blits[i];
        assert(a->id==b->id&&float_bits(a->x)==float_bits(b->x));
        assert(float_bits(a->y)==float_bits(b->y)&&float_bits(a->scale)==float_bits(b->scale));
        assert(a->block==&commands[1].pool[i]&&b->block==&commands[0].pool[i]);
    }
}
static void request(unsigned id,float x,float y,float scale) {
    unsigned before=blit_count;
    active=0;commands[0].count=0;linear(id,x,y,scale);
    active=1;commands[1].count=0;indexed(id,x,y,scale);
    assert(commands[0].count==commands[1].count);
    assert(memcmp(commands[0].events,commands[1].events,commands[0].count*sizeof(event))==0);
    requests++;
    if (commands[1].count==4) { misses++;assert(blit_count==before+1); }
    else if (commands[1].events[0].kind==4) { hits++;assert(blit_count==before); }
    else { fallbacks++;assert(blit_count==before); }
    verify();
}
static void reset(void) {
    memset(blits,0,sizeof(blits));memset(old_blits,0,sizeof(old_blits));
    memset(blit_heads,0,sizeof(blit_heads));memset(blit_next,0,sizeof(blit_next));
    memset(commands,0,sizeof(commands));blit_count=old_count=0;
}
static void layout(unsigned views,unsigned frame) {
    static const unsigned fixed[]={BG_H_SHIELD_BG,BG_H_SHIELD_METER,BG_H_HEALTH_METER,
        BG_H_AMMO_BG,BG_H_GRENADE_FRAG,BG_H_GRENADE_PLASMA,BG_H_MOTION_BG,BG_H_MOTION_FG};
    for (unsigned p=0;p<views;p++) {
        float x=views==4?(p&1)*160.f:0,y=views==1?0:(p/(views==4?2:1))*120.f;
        float scale=views==4?.45f:.5f;
        for (unsigned i=0;i<sizeof(fixed)/sizeof(*fixed);i++) {
            request(fixed[i],x+5+i*3,y+5+i*2,scale);
            if (i==1||i==2) request(fixed[i],x+5+i*3,y+5+i*2,scale); /* Full meter overlay. */
        }
        request(BG_H_RETICLE_AR+frame%8,x+80,y+60,scale);
        request(BG_H_AMMO_AR+frame%6,x+5,y+21,scale);
        request(BG_H_BLIP,x+random_u32()%40,y+random_u32()%40,.125f);
    }
}
int main(void) {
    for (unsigned id=0;id<BG_H_COUNT;id++) images[id].id=id;
    /* Repeated warm fixed layouts, then switch sizes without resetting blocks. */
    for (unsigned frame=0;frame<120;frame++) layout(4,frame);
    for (unsigned frame=0;frame<120;frame++) layout((unsigned[]){1,2,4}[frame%3],frame);
    while (blit_count<192) request(BG_H_RETICLE_AR,2000.f+blit_count,2000,1);
    assert(blit_count==192);
    /* Full cache still finds any old slot, retains pointers, falls back for new keys. */
    for (unsigned n=0;n<12000;n++) {
        unsigned i=random_u32()%blit_count;
        const hud_blit *b=&blits[i];const bg_hud_image *im=&bg_hud_images[b->id];
        request(b->id,b->x-im->x*b->scale,b->y-im->y*b->scale,b->scale);
        if (!(n%7)) request(random_u32()%BG_H_COUNT,10000.f+n,-10000.f-n,1.125f);
    }
    /* Directed IEEE comparison cases: equality uses floats, never byte keys. */
    reset();
    request(BG_H_RETICLE_AR,0.f,-0.f,0.f);request(BG_H_RETICLE_AR,-0.f,0.f,-0.f);
    assert(blit_count==1);
    request(BG_H_RETICLE_AR,nextafterf(0.f,1.f),0.f,1.f);
    request(BG_H_RETICLE_AR,1.f,1.f,.45f);request(BG_H_RETICLE_AR,nextafterf(1.f,2.f),1.f,.45f);
#if !defined(__FINITE_MATH_ONLY__) || !__FINITE_MATH_ONLY__
    request(BG_H_RETICLE_AR,INFINITY,-INFINITY,1.f);
    request(BG_H_RETICLE_AR,INFINITY,-INFINITY,1.f);
    request(BG_H_RETICLE_AR,NAN,1.f,1.f);request(BG_H_RETICLE_AR,NAN,1.f,1.f);
#endif
    /* Fill every slot under one image: ascending order, tail insertion and last hit. */
    reset();
    for (unsigned n=0;n<192;n++) request(BG_H_SHIELD_BG,n*.5f,n*.25f,1.f);
    assert(blit_count==192);
    for (unsigned n=192;n-->0;) request(BG_H_SHIELD_BG,n*.5f,n*.25f,1.f);
    request(BG_H_SHIELD_BG,1000,1000,1);request(BG_H_BLIP,0,0,1);
    /* Every image except the moving blip participates, across four distinct scales. */
    reset();
    for (unsigned repeat=0;repeat<100;repeat++)
        for (unsigned id=0;id<BG_H_COUNT;id++)
            for (unsigned view=0;view<4;view++) request(id,view*80.f,view*40.f,.25f*(view+1));
    assert(visits[1]<visits[0]/4);
    printf("PASS: %llu exact command traces; hits=%llu misses=%llu fallback=%llu; "
        "entry visits linear=%llu indexed=%llu; link bytes=%zu\n",
        (unsigned long long)requests,(unsigned long long)hits,(unsigned long long)misses,
        (unsigned long long)fallbacks,(unsigned long long)visits[0],(unsigned long long)visits[1],
        sizeof(blit_heads)+sizeof(blit_next));
}
'''


def run(output, cc):
    source = (ROOT/'port/n64/hud.c').read_text()
    declarations = re.search(r'typedef struct \{ unsigned id; float x,y,scale; rspq_block_t \*block; \} hud_blit;.*?static uint16_t blit_heads\[BG_H_COUNT\],blit_next\[192\];', source, re.S)
    assert declarations, 'Update the test extraction if the actual cache representation changes'
    indexed = function(source, 'blit_picture')
    needle = 'const hud_blit *b=&blits[i];'
    assert indexed.count(needle) == 1
    indexed = indexed.replace(needle, needle+'++visits[1];')
    header = (ROOT/'port/n64/asset_hud.h').read_text()
    count = len(re.findall(r'\bBG_H_\w+', header.split('BG_H_COUNT')[0]))
    images = ','.join('{.x=%d,.y=%d}' % (i%5,i%7) for i in range(count))
    harness = HARNESS.replace('@IMAGES@', images).replace('@DECLS@', declarations.group())
    harness = harness.replace('@LINEAR@', LINEAR).replace('@INDEXED@', indexed)
    output.mkdir(parents=True,exist_ok=True)
    c = output/'actual-hud-cache.c';c.write_text(harness)
    results = []
    for name, extra in (('strict',[]),('fast',['-ffast-math','-ftrapping-math','-fno-associative-math'])):
        binary = output/('test-hud-cache-'+name)
        command = [cc,'-std=c11','-O2','-g','-Wall','-Wextra','-Werror',
                   '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                   '-I'+str(ROOT/'port/n64'),*extra,str(c),'-lm','-o',str(binary)]
        subprocess.run(command,check=True)
        result = subprocess.run([str(binary)],capture_output=True,text=True)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        print(name+': '+result.stdout.strip())
        results.append({'configuration':name,'command':command,'output':result.stdout.strip()})
    (output/'results.json').write_text(json.dumps({'hud_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results},indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64/visibility-weapon-qa/hud-cache')
    parser.add_argument('--cc',default='clang')
    args = parser.parse_args()
    run(args.output.resolve(),args.cc)
