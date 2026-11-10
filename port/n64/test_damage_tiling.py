"""Check production damage-image tiling, TMEM ownership and screen geometry."""
import argparse,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def run(output):
    output.mkdir(parents=True,exist_ok=False)
    path=ROOT/'port/n64/hud.c';source=path.read_text()
    function=source[source.index('static void damage_bitmap('):source.index('static void damage_indicators(')]
    harness=r'''
#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
typedef struct {unsigned width,height,stride;} surface_t;
#define TILE0 0
static const int TRIFMT_TEX=0;
static unsigned loaded_first,loaded_last,next_row,uploads,draws,syncs,tile_syncs,triangles;
static bool busy,tile_busy;
static surface_t image;
static float origin_x,origin_y,rotation;
static void fm_sincosf(float a,float *s,float *c){*s=sinf(a);*c=cosf(a);}
static void rdpq_sync_load(void){busy=false;syncs++;}
static void rdpq_sync_tile(void){tile_busy=false;tile_syncs++;}
static void rdpq_tex_upload_sub(unsigned tile,const surface_t *s,void *parms,unsigned x0,unsigned y0,unsigned x1,unsigned y1){
    (void)parms;assert(tile==0&&!busy&&!tile_busy&&x0==0&&x1==s->width&&y0<y1&&y1<=s->height);
    assert(((s->width+7)&~7u)*(y1-y0)<=4096);
    assert(y0==(next_row?next_row-1:0));loaded_first=y0;loaded_last=y1;uploads++;
}
static void point(float x,float y,float u,float v){
    float px=(u-(int)(image.width*.5f))*.5f,py=(v-(int)(image.height*.5f))*.5f;
    float ex=origin_x+cosf(rotation)*px+sinf(rotation)*py;
    float ey=origin_y-sinf(rotation)*px+cosf(rotation)*py;
    assert(isfinite(x)&&isfinite(y)&&fabsf(x-ex)<.0001f&&fabsf(y-ey)<.0001f);
}
static void strip(float top,float end){
    assert(top==next_row&&end>top&&end<=image.height&&end<=loaded_last);
    assert(loaded_first<=top&&loaded_last==(end==image.height?end:end+1));
    next_row=end;draws++;busy=tile_busy=true;
}
static void rdpq_texture_rectangle_scaled(unsigned tile,float x0,float y0,float x1,float y1,float u0,float v0,float u1,float v1){
    assert(tile==0&&rotation==0&&u0==0&&u1==image.width);
    point(x0,y0,u0,v0);point(x1,y1,u1,v1);strip(v0,v1);
}
static void rdpq_triangle(const void *format,const float *a,const float *b,const float *c){
    (void)format;assert(rotation!=0);point(a[0],a[1],a[2],a[3]);point(b[0],b[1],b[2],b[3]);point(c[0],c[1],c[2],c[3]);
    assert(a[4]==1&&b[4]==1&&c[4]==1);
    if(!(triangles++%2)){
        assert(a[2]==0&&b[2]==image.width&&c[2]==image.width&&a[3]==b[3]);strip(a[3],c[3]);
    }else assert(a[2]==0&&b[2]==image.width&&c[2]==0&&b[3]==c[3]&&c[3]==next_row);
}
'''
    harness+=function+r'''
int main(void){
    const float angles[]={0,1.57079633f,3.14159265f,4.71238898f};
    const float centers[][2]={{160,120},{160,60},{160,180},{80,60},{240,60},{240,180}};
    unsigned cases=0,total_uploads=0;
    for(unsigned size=0;size<2;size++)for(unsigned angle=0;angle<4;angle++)for(unsigned center=0;center<6;center++){
        image=size?(surface_t){165,29,168}:(surface_t){231,40,232};
        origin_x=centers[center][0];origin_y=centers[center][1];rotation=angles[angle];
        next_row=uploads=draws=syncs=tile_syncs=triangles=0;busy=tile_busy=true;
        damage_bitmap(&image,origin_x,origin_y,rotation);
        assert(next_row==image.height&&uploads==draws&&uploads==syncs&&uploads==tile_syncs&&busy&&tile_busy);
        assert(uploads==(size?2:3));assert(triangles==(angle?draws*2:0));
        total_uploads+=uploads;cases++;
    }
    printf("PASS: %u damage-image cases, %u synchronized uploads, continuous filtered coverage and unchanged source UV/screen geometry\n",cases,total_uploads);
}
'''
    c=output/'damage.c';c.write_text(harness)
    binary=output/'damage'
    subprocess.run(['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-ffp-contract=off',str(c),'-lm','-o',str(binary)],check=True)
    log=subprocess.check_output([str(binary)],text=True);print(log,end='');(output/'damage.log').write_text(log)
    result=dict(passed=True,sanitizers_passed=True,cases=48,uploads=120,hud_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),contract='Every original I8 image row is covered once, bilinear gutters are retained, each upload fits 4096 bytes and follows SYNC_TILE and SYNC_LOAD, all four rotations preserve source UVs and screen coordinates within 0.0001 pixel.',limits='Host checks do not replace native RDP validation or pixel inspection.')
    (output/'damage-validation.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args();run(args.output_dir)
