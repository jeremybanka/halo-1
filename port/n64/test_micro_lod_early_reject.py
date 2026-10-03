"""Compare actual micro-LOD early rejection with the full eight-corner path.

Only the new early return is removed from the reference. If the local frozen
pre-change header exists, its full function must match that reference exactly.
This measures decisions and corner counts, not target execution time.
"""
from pathlib import Path
import hashlib
import json
import subprocess
from test_render_matrix import function, compact

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64/visibility-weapon-qa/micro-early-reject'
OUT.mkdir(parents=True,exist_ok=True)
header=ROOT/'port/n64/render_micro_lod.h'
source=header.read_text();body=function(source,'bg_micro_lod_below')
early='if(maxx-minx>=limit||maxy-miny>=limit)return false;'
assert body.count(early)==1
reference=body.replace(early,'')
before=OUT/'render_micro_lod-before.h'
if before.exists():assert compact(reference)==compact(function(before.read_text(),'bg_micro_lod_below'))
args='const bg_micro_sphere*s,const float camera[4][4],const float projection[4][4],unsigned width,unsigned height,float near_plane,float pixels,bool already_far,bool zoom,unsigned views'
c=r'''
#include <assert.h>
#include <stdio.h>
#include "render_micro_lod.h"
static unsigned old_corners,new_corners;
'''
for name,text,counter in [('reference',reference,'old_corners'),('counted',body,'new_corners')]:
    text=text.replace('for(unsigned corner=0;corner<8;corner++){',
                      'for(unsigned corner=0;corner<8;corner++){'+counter+'++;')
    c+='\nstatic bool '+name+'('+args+'){'+text+'}\n'
c+=r'''
static uint32_t seed=0xce064;
static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static float unit(void){return (rnd()>>8)*(1.f/16777216.f);}
static float bits(uint32_t raw){volatile uint32_t v=raw;uint32_t x=v;float f;memcpy(&f,&x,4);return f;}
static unsigned cases,accepted,avoided,early_cases;
static void check(bg_micro_sphere*s,float camera[4][4],float projection[4][4],unsigned w,unsigned h,float near,float pixels,bool far,bool zoom,unsigned views){
    old_corners=new_corners=0;
    bool old=reference(s,camera,projection,w,h,near,pixels,far,zoom,views);
    bool actual=bg_micro_lod_below(s,camera,projection,w,h,near,pixels,far,zoom,views);
    bool counted_result=counted(s,camera,projection,w,h,near,pixels,far,zoom,views);
    assert(actual==old&&counted_result==old);assert(new_corners<=old_corners);
    cases++;accepted+=actual;avoided+=old_corners-new_corners;early_cases+=new_corners<old_corners;
}
int main(void){
    for(unsigned i=0;i<50000;i++){
        float camera[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
        float projection[4][4]={{1.25f,0,0,0},{0,1.6666667f,0,0},{.1375f,-.133333f,-1,-1},{0,0,-2.8f,0}};
        float angle=(unit()-.5f)*6.28f;
        camera[0][0]=cosf(angle);camera[2][0]=sinf(angle);camera[0][2]=-sinf(angle);camera[2][2]=cosf(angle);
        bg_cull_bounds b={.valid=true};
        for(unsigned a=0;a<3;a++){
            int center=(int)((unit()-.5f)*16000),extent=(int)(unit()*400);
            b.min[a]=(int16_t)(center-extent);b.max[a]=(int16_t)(center+extent);
        }
        bg_micro_sphere s;bg_micro_sphere_from_bounds(&s,&b);
        for(unsigned threshold=0;threshold<3;threshold++)
            check(&s,camera,projection,160,120,1.4f,4+threshold*2,true,false,4);
        /* Ordinary guards and adversarial float32 values are evaluated by
         * the same bitwise finite checks under both strict/target math. */
        switch(i%18){
        case 0:s.valid=false;break;
        case 1:b.valid=false;break;
        case 2:b.min[0]=b.max[0]+1;break;
        case 3:s.radius=bits(0x7fc00000u);break;
        case 4:s.center[0]=bits(0x7f800000u);break;
        case 5:camera[1][0]=bits(0xff800000u);break;
        case 6:camera[3][0]=65537.f;break;
        case 7:projection[0][0]=bits(0x7fc00000u);break;
        case 8:projection[1][1]=bits(0x7f7fffffu);break;
        case 9:s.bounds=NULL;break;
        case 10:s.radius=0;break;
        case 11:camera[0][0]=1.002f;break;
        default:break;
        }
        check(&s,camera,projection,i%23?160:0,i%29?120:0,i%31?1.4f:bits(0x7fc00000u),
              i%37?8:bits(0x7f800000u),i%41!=0,i%43==0,i%47?4:2);
    }
    /* Exact threshold/near-plane neighborhoods, including signed zeros. */
    float camera[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
    float projection[4][4]={{1,0,0,0},{0,1,0,0},{0,0,-1,-1},{0,0,-2.8f,0}};
    for(int depth=1;depth<256;depth++)for(unsigned e=0;e<16;e++){
        bg_cull_bounds b={.min={-(int16_t)e,-1,-depth-1},.max={(int16_t)e,1,-depth},.valid=true};
        bg_micro_sphere s;bg_micro_sphere_from_bounds(&s,&b);
        for(unsigned k=0;k<5;k++){
            float limit=2.f*(float)e*80/depth+.5f;
            if(k==0)limit=nextafterf(limit,-FLT_MAX);
            if(k==1)limit=nextafterf(limit,FLT_MAX);
            if(k==3)limit=0.f;
            if(k==4)limit=bits(0x80000000u);
            check(&s,camera,projection,160,120,1.4f,limit,true,false,4);
        }
    }
    assert(accepted&&early_cases&&avoided);
    printf("PASS: %u identical LOD decisions; %u eligible; %u early-rejected cases avoided %u corner projections; invalid/overflow/zoom/layout/near/exact-limit cases included.\n",cases,accepted,early_cases,avoided);
}
'''
test=OUT/'actual-functions.c';test.write_text(c);results=[]
for label,flags in [('strict',[]),('target-math',['-ffast-math','-ftrapping-math','-fno-associative-math'])]:
    binary=OUT/label
    cmd=['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
         *flags,'-I'+str(ROOT/'port/n64'),str(test),'-lm','-o',str(binary)]
    subprocess.run(cmd,check=True)
    result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
    print(result.stdout,end='');results.append({'mode':label,'command':cmd,'output':result.stdout})
(OUT/'equivalence-proof.json').write_text(json.dumps({'header_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),
    'before_header_sha256':hashlib.sha256(before.read_bytes()).hexdigest() if before.exists() else None,
    'reference':'Actual pre-optimization function; only early rejection removed; local before function comparison required when available.',
    'results':results,'performance_limit':'Synthetic corner counts are not representative replay counts or target timing.'},indent=2)+'\n')
