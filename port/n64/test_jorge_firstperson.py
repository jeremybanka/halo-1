"""Exercise the actual C armor binding over core, ready and service ROM poses."""
from pathlib import Path
import json,re,struct,subprocess,tempfile
import numpy as np
from pack_firstperson import prepare_model,split_details
from pack_assets import position

ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-personal'

def run():
    binding=np.load(OUT/'firstperson-binding.npz')
    reduced=json.loads((A/'assets/firstperson-reduced.json').read_text());names=list(reduced['weapons'])
    aliases=json.loads((A/'generated/firstperson-report.json').read_text())['aliases']
    count=len(binding['local']);fixtures=[];area_min=1e9;area_max=0
    def check(name,points,label):
        nonlocal area_min,area_max
        actual=aliases.get(name,name)
        frames=np.array([binding[f'coeff_{b}']@points[binding[f'{actual}_indices_{b}']] for b in range(2)])
        expected=np.einsum('ij,ijk->ik',binding['local'],frames[binding['bones']])
        assert np.isfinite(expected).all() and np.max(np.abs(expected))<512,label
        # Rigid plate edges may move by a few quantization steps, but cannot
        # stretch into spikes or collapse through the glove during a service.
        for b in range(2):
            axes=(frames[b,1:]-frames[b,0])/(.08*256)
            singular=np.linalg.svd(axes,compute_uv=False)
            area_min=min(area_min,float(singular.min()));area_max=max(area_max,float(singular.max()))
            assert singular.min()>.70 and singular.max()<1.30,(label,singular)
        fixtures.append((names.index(name),np.asarray(points,dtype=np.int16),expected.astype(np.float32)))
    for name,w in reduced['weapons'].items():
        actual=aliases.get(name,name);w=reduced['weapons'][actual]
        if actual in ('sniper','plasma_pistol','plasma_rifle'):w=split_details(w,actual)[0]
        mesh,clips,_=prepare_model(w,actual)
        for clip,c in clips.items():
            for fi,frame in enumerate(c['frames']):
                check(name,np.rint(np.array([position(p,(0,0,0)) for p in frame])*256),f'{name}/{clip}/{fi}')
    core_count=len(fixtures)
    source=(A/'generated/interaction_assets.c').read_text();bank=(A/'frontend-files/interactions.bin').read_bytes()
    service_names=[m[1] for m in re.findall(r'BG_SERVICE\((\d+),\s*\w+,\s*"([^"]+)"', (ROOT/'port/n64/interaction_services.def').read_text())]
    for symbol,order in [('bg_ready_poses',names),('bg_service_poses',service_names)]:
        line=next(l for l in source.splitlines() if l.startswith('const bg_rom_pose '+symbol+'['))
        entries=re.findall(r'\{(\d+),(\d+),(\d+),(\d+),([0-9.]+)f,',line)
        assert len(entries)==len(order)
        for name,(offset,stride,n,frames,duration) in zip(order,entries):
            offset,stride,n,frames=map(int,(offset,stride,n,frames))
            for i in range(frames):
                points=np.frombuffer(bank,dtype='>i2',count=n*3,offset=offset+i*stride).reshape(n,3)
                check(name,points,f'{symbol}/{name}/{i}')
    with tempfile.TemporaryDirectory(prefix='jorge-fp-') as tmp:
        tmp=Path(tmp);(tmp/'t3d').mkdir()
        (tmp/'t3d/t3d.h').write_text('''#pragma once
#include <stdint.h>
typedef struct { int16_t a[3]; uint16_t na; int16_t b[3]; uint16_t nb; uint32_t ca,cb; int16_t ua[2],ub[2]; } T3DVertPacked;
static inline int16_t *t3d_vertbuffer_get_pos(T3DVertPacked *p,unsigned i){return i&1?p[i/2].b:p[i/2].a;}
static inline uint32_t *t3d_vertbuffer_get_color(T3DVertPacked *p,unsigned i){return i&1?&p[i/2].cb:&p[i/2].ca;}
''')
        with (tmp/'fixtures.bin').open('wb') as out:
            for weapon,points,expected in fixtures:
                out.write(struct.pack('=2I',weapon,len(points)));out.write(points.astype('=i2').tobytes());out.write(expected.astype('=f4').tobytes())
        (tmp/'test.c').write_text('''#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jorge_firstperson.h"
int main(int argc,char**argv){assert(argc==2);FILE*f=fopen(argv[1],"rb");assert(f);unsigned header[2],tested=0;bool seen[9]={0};
while(fread(header,sizeof(header),1,f)==1){unsigned w=header[0],n=header[1];assert(n==bg_fp_models[w].vertex_count);
T3DVertPacked *in=malloc(((n+1)/2)*sizeof(*in)),*out=malloc(((bg_jorge_fp_model.vertex_count+1)/2)*sizeof(*out));
memcpy(in,bg_fp_models[w].vertices,((n+1)/2)*sizeof(*in));memcpy(out,bg_jorge_fp_model.vertices,((bg_jorge_fp_model.vertex_count+1)/2)*sizeof(*out));
for(unsigned i=0;i<n;i++){int16_t point[3];assert(fread(point,sizeof(int16_t),3,f)==3);if(!seen[w])assert(memcmp(point,t3d_vertbuffer_get_pos(in,i),sizeof(point))==0);memcpy(t3d_vertbuffer_get_pos(in,i),point,sizeof(point));}seen[w]=true;
bg_jorge_firstperson_pose(out,in,w);
for(unsigned profile=0;profile<BG_PROFILE_COUNT;profile++){
for(unsigned i=0;i<n;i++)*t3d_vertbuffer_get_color(in,i)=*t3d_vertbuffer_get_color(bg_fp_models[w].vertices,i);
bg_jorge_firstperson_tint(in,w,profile);
for(unsigned i=0;i<n;i++)if(!bg_jorge_fp_colors[w][i])assert(*t3d_vertbuffer_get_color(in,i)==*t3d_vertbuffer_get_color(bg_fp_models[w].vertices,i));}
for(unsigned i=0;i<bg_jorge_fp_model.vertex_count;i++){float expected[3];assert(fread(expected,sizeof(float),3,f)==3);
for(unsigned a=0;a<3;a++)assert(fabsf(t3d_vertbuffer_get_pos(out,i)[a]-expected[a])<.502f);}
for(unsigned i=0;i<n;i++)if(!bg_jorge_fp_colors[w][i])assert(*t3d_vertbuffer_get_color(in,i)==*t3d_vertbuffer_get_color(bg_fp_models[w].vertices,i));
free(in);free(out);tested++;}fclose(f);printf("PASS: %u actual production poses, four profile palettes, C runtime binding and untouched weapon colors\\n",tested);return 0;}
''')
        subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'port/n64'),str(tmp/'test.c'),str(A/'generated/firstperson_data.c'),str(A/'generated/jorge_firstperson_data.c'),'-o',str(tmp/'test')],check=True)
        subprocess.run([str(tmp/'test'),str(tmp/'fixtures.bin')],check=True)
    old=np.load(A/'assets/jorge/playable-refined/gameplay-poses.npz');body=np.load(OUT/'gameplay-poses.npz');n=len(old['rest'])
    assert np.array_equal(old['rest'],body['rest'][:n])
    for i in range(39):assert np.array_equal(old[f'frames_{i}'],body[f'frames_{i}'][:,:n])
    report={'core_pose_frames':core_count,'ready_and_service_pose_frames':len(fixtures)-core_count,
            'total_pose_frames':len(fixtures),'runtime_sanitizers_passed':True,'weapon_colors_unchanged':True,
            'plate_axis_scale_range':[area_min,area_max],'accepted_body_vertices_and_39_pose_arrays_exact':True}
    (OUT/'firstperson-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':run()
