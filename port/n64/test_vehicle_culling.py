"""Exercise actual renderer part preparation with current packed rig bounds.

The harness compiles prepare_vehicle/pivot_rotation from main.c, the installed
Tiny3D matrix operations, and the generated part tables. It checks every box
corner at each actual pose, rather than approximating spinning wheels with a
finite pose envelope. Host trig replaces the SDK's N64 trig implementation;
both the bound and rendered matrix still consume exactly the same result.
"""
from runtime_source import read_runtime, validation_output
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

from test_render_matrix import compact, function


PRELUDE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "render_bounds.h"
#include "render_pose_cache.h"
#define BG_OBJECT_SCALE 1024.f
#define BG_FRAME_SLOTS 2
#define fm_cosf cosf
#define fm_sinf sinf
typedef struct {float v[3];} T3DVec3;
typedef struct {float v[4];} T3DVec4;
typedef struct {float m[4][4];} T3DMat4;
/* Model the exact SDK coefficient conversion without host byte-order packing.
 * The production macro is checked below before compiling this harness. */
typedef T3DMat4 T3DMat4FP;
typedef struct {T3DVec4 planes[6];} T3DFrustum;
typedef struct {T3DFrustum viewFrustum;} T3DViewport;
static void t3d_mat4_to_fixed_3x4(T3DMat4FP*out,const T3DMat4*in){
    for(unsigned c=0;c<4;c++)for(unsigned r=0;r<3;r++)
        out->m[c][r]=(int32_t)(in->m[c][r]*65536.f)/65536.f;
}
bg_vehicle bg_vehicles[BG_MAX_VEHICLES];
static unsigned slot;
static float wheel_rotation[BG_MAX_VEHICLES];
static bg_vehicle_pose_cache vehicle_pose_cache[BG_MAX_VEHICLES];
static T3DMat4FP vehicle_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES];
static T3DMat4FP part_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES][7];
static bg_cull_bounds vehicle_bounds[BG_MAX_VEHICLES];
static bg_cull_bounds vehicle_part_bounds[BG_MAX_VEHICLES][7];
'''

TEST = r'''
static uint32_t seed=0xCE064;
static float uniform(float low,float high){
    seed=seed*1664525u+1013904223u;
    return low+(high-low)*(float)(seed>>8)/16777215.f;
}
int main(void){
    unsigned poses=0,coordinates=0,rejected=0,wheels=0,changed_wheels=0;
    bg_cull_bounds old_wheel={{0},{0},false};
    for(unsigned trial=0;trial<4096;trial++){
        unsigned i=trial%BG_MAX_VEHICLES;slot=trial%BG_FRAME_SLOTS;
        bg_vehicle*v=&bg_vehicles[i];v->kind=trial%4;
        for(unsigned a=0;a<3;a++)v->pos[a]=uniform(-80,80);
        v->physics_valid=(trial%2)==0;float roll=uniform(-3.15f,3.15f);
        v->forward[0]=1;v->forward[1]=v->forward[2]=0;v->up[0]=0;v->up[1]=cosf(roll);v->up[2]=sinf(roll);
        v->steering=uniform(-.5,.5);for(unsigned a=0;a<8;a++)v->suspension[a]=uniform(-.3,-.1);
        v->yaw=uniform(-3.15f,3.15f);v->pitch=uniform(-3.15f,3.15f);
        v->turret_yaw=uniform(-3.15f,3.15f);v->turret_pitch=uniform(-3.15f,3.15f);
        /* Large and negative phases include long sessions and reverse travel.
         * They enter the unchanged runtime prepare function, not an envelope. */
        wheel_rotation[i]=uniform(-100000,100000);
        prepare_vehicle(i);
        const bg_vehicle_rig*rig=&bg_vehicle_rigs[v->kind];
        assert(rig->count>0&&rig->count<=7&&vehicle_bounds[i].valid);
        for(unsigned j=0;j<rig->count;j++){
            const bg_vehicle_part*part=&rig->parts[j];
            const bg_cull_bounds*b=&vehicle_part_bounds[i][j];
            const T3DMat4FP*m=&part_matrices[slot][i][j];
            assert(b->valid);poses++;
            if(part->kind==BG_PART_WHEEL){
                wheels++;
                changed_wheels+=memcmp(old_wheel.min,b->min,sizeof b->min)!=0;
                old_wheel=*b;
            }
            float points[8][3];
            for(unsigned mask=0;mask<8;mask++)for(unsigned a=0;a<3;a++){
                float value=m->m[3][a];
                for(unsigned c=0;c<3;c++)value+=m->m[c][a]*BG_OBJECT_SCALE*
                    (mask&(1u<<c)?part->bounds.max[c]:part->bounds.min[c]);
                points[mask][a]=value;
                assert(value>=b->min[a]&&value<=b->max[a]);
                assert(value>=vehicle_bounds[i].min[a]&&value<=vehicle_bounds[i].max[a]);
                coordinates++;
            }
            /* A random half-space through/near the current part, with five
             * inactive planes. If the SDK rejects its AABB, every transformed
             * corner must be outside that plane. Convexity then covers all
             * triangles/interior positions enclosed by the source part box. */
            for(unsigned probe=0;probe<8;probe++){
                T3DViewport vp={0};
                for(unsigned p=0;p<6;p++)vp.viewFrustum.planes[p].v[3]=1;
                float*plane=vp.viewFrustum.planes[0].v;
                plane[3]=uniform(-100,100);
                for(unsigned a=0;a<3;a++){
                    plane[a]=uniform(-1,1);
                    plane[3]-=plane[a]*(b->min[a]+b->max[a])*.5f;
                }
                if(!visible_bounds(&vp,b)){
                    rejected++;
                    for(unsigned c=0;c<8;c++){
                        float side=plane[3];
                        for(unsigned a=0;a<3;a++)side+=plane[a]*points[c][a];
                        assert(side<=0);
                    }
                }
                bg_cull_bounds invalid=*b;invalid.valid=false;
                assert(visible_bounds(&vp,&invalid));
            }
        }
    }
    fprintf(stderr,"CULL coverage poses=%u wheels=%u changed=%u rejected=%u\n",poses,wheels,changed_wheels,rejected);
    assert(poses>0&&wheels==4096&&changed_wheels>4000&&rejected>0);
    printf("Current-pose part bounds: %u poses, %u wheel poses, %u fixed corner "
           "coordinates, %u conservative plane rejections; invalid bounds remain visible.\n",
           poses,wheels,coordinates,rejected);
}
'''


def declaration(source, name):
    match = re.search(r'[^;{}\n]*\b' + name + r'(?:\[[^\]]*\])+\s*=\s*\{', source)
    assert match, name
    end = source.index(';',match.end())+1
    return source[match.start():end]


def run(root, sdk, generated, out):
    paths = [root/'port/n64/main.c', root/'port/n64/asset_models.h',
             sdk/'src/t3d/t3dmath.h', sdk/'src/t3d/t3dmath.c', generated,
             generated.with_name('micro_data.c')]
    texts = [read_runtime(p) for p in paths]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    main, assets, header, math, bank, micro_bank = texts
    assert '#define T3D_F32_TO_FIXED(val) (int32_t)((val) * (float)(1<<16))' in header
    prepare = compact(function(main, 'compute_vehicle_pose'))
    assert prepare.count('bg_bounds_quantize(&vehicle_part_bounds[i][j],&box);') == 1
    assert prepare.index('t3d_mat4_to_fixed_3x4(&part_matrices[slot][i][j],&world);') < \
        prepare.index('bg_bounds_transform(&box,&part->bounds,world.m,BG_OBJECT_SCALE);') < \
        prepare.index('bg_bounds_quantize(&vehicle_part_bounds[i][j],&box);')
    draw = compact(function(main, 'draw_view'))
    assert 'if(!visible_bounds(vp,&vehicle_part_bounds[i][j]))continue;' \
           't3d_matrix_set(&part_matrices[slot][i][j],true);' in draw
    assert 'return!bounds->valid||t3d_frustum_vs_aabb_s16' in compact(function(main, 'visible_bounds'))
    typedefs = assets[assets.index('enum { BG_PART_BODY'):assets.index('extern const bg_vehicle_rig')]
    c = PRELUDE + typedefs
    c += '\ntypedef struct {uint32_t offset,stride;uint16_t vertices,frames;float duration;bg_bounds bounds;} bg_rom_pose;\n'
    c += declaration((root/'build/n64/generated/interaction_assets.c').read_text(),'bg_hatch_poses')
    # Decode the actual immutable ROM marker bank, using the same adjacent-frame
    # interpolation as interaction_render.c. No synthetic hatch geometry.
    data=(root/'build/n64/frontend-files/interactions.bin').read_bytes()
    hatch=declaration((root/'build/n64/generated/interaction_assets.c').read_text(),'bg_hatch_poses')
    rows=re.findall(r'\{(\d+),(\d+),(\d+),(\d+),',hatch)
    extent=max(int(offset)+int(stride)*int(frames) for offset,stride,vertices,frames in rows)
    first=min(int(row[0]) for row in rows)
    data=data[first:extent]
    c += '\n#define POSE_BASE '+str(first)+'\nstatic const unsigned char pose_bank[]={'+','.join(map(str,data))+'};\n'
    c += r'''
static int16_t signed_short(const unsigned char *p){return (int16_t)((p[0]<<8)|p[1]);}
static void bg_interaction_points(int16_t (*out)[3],const bg_rom_pose *p,float seconds){
    float phase=fminf(1,fmaxf(0,seconds/p->duration)),frame=phase*(p->frames-1);
    unsigned a=frame,b=a+1<p->frames?a+1:a;int fraction=(frame-a)*256;
    for(unsigned i=0;i<p->vertices;i++)for(unsigned axis=0;axis<3;axis++){
        unsigned k=(i*3+axis)*2;
        int lo=signed_short(pose_bank+p->offset-POSE_BASE+a*p->stride+k);
        int hi=signed_short(pose_bank+p->offset-POSE_BASE+b*p->stride+k);
        out[i][axis]=lo+(hi-lo)*fraction/256;
    }
}
'''

    for name in ('parts_warthog','parts_ghost','parts_scorpion','parts_banshee',
                 'bg_vehicle_rigs','bg_vehicle_lod_bounds'):
        c += '\n' + declaration(bank, name)
    c += '\n' + declaration(micro_bank, 'bg_vehicle_micro_gate_bounds')
    c += '\n' + declaration((root/'build/n64/generated/vehicle_visuals_data.c').read_text(), 'bg_covenant_wreck_bounds')
    for source, result, name, args in (
        (math,'void','t3d_mat4_from_srt_euler','T3DMat4 *mat,const float scale[3],const float rot[3],const float translate[3]'),
        (header,'void','t3d_mat4_identity','T3DMat4 *mat'),
        (header,'void','t3d_mat4_mul','T3DMat4 *matRes,const T3DMat4 *matA,const T3DMat4 *matB'),
        (header,'void','t3d_mat3_mul_vec3','T3DVec3 *vecOut,const T3DMat4 *mat,const T3DVec3 *vec'),
        (math,'bool','t3d_frustum_vs_aabb_s16','const T3DFrustum *frustum,const int16_t min[3],const int16_t max[3]'),
        (main,'bool','visible_bounds','T3DViewport *vp,const bg_cull_bounds *bounds'),
        (main,'void','pivot_rotation','T3DMat4 *out,const float pivot[3],float yaw,float pitch'),
        (main,'void','compute_vehicle_pose','unsigned i'),
        (main,'void','prepare_vehicle','unsigned i')):
        c += f'\nstatic {result} {name}({args}){{{function(source,name)}}}\n'
    out.mkdir(parents=True,exist_ok=True)
    source = out/'current-part-bounds.c';source.write_text(c+TEST)
    binary = out/'current-part-bounds'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    '-I'+str(root/'port/n64'),str(source),'-lm','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths], 'Source/bank changed during test'


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tiny3d',type=Path,default=root.parent/'n64-3d-splitscreen/.build/tiny3d')
    p.add_argument('--generated',type=Path,default=root/'build/n64/generated/models_data.c')
    p.add_argument('--out',type=Path,default=validation_output('vehicle-culling'))
    args = p.parse_args()
    run(root,args.tiny3d,args.generated,args.out)
