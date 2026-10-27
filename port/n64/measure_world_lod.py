"""SDK-matched pose replay of the shared native world-LOD selector."""
import csv,json,os,re,statistics,subprocess
from sidewinder_world_lod import ROOT,OUT,BASE
PREVIOUS=ROOT/'build/n64-sidewinder-cluster-terrain'

def measure():
    sdk=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src';solver=PREVIOUS/'cameras/solver';results={}
    for name,directory in [('replay',PREVIOUS/'cameras'),('photos',PREVIOUS/'after-census')]:
        output=OUT/name;output.mkdir(exist_ok=True);driver=(directory/'camera.c').read_text()
        if name=='replay':driver,n=re.subn(r'const unsigned maps\[\]=\{[^}]+\};','const unsigned maps[]={1};',driver);assert n==1
        driver=driver.replace('#include "render_pvs.h"','#include "render_pvs.h"\n#include "render_world_lod.h"\n#include <stdio.h>\n#include <stdlib.h>\n#include <t3d/t3dmath.h>\nstatic T3DMat4 last_view,last_projection;static float last_near,last_w,last_h;\nstatic FILE *lod_trace;')
        driver=driver.replace('t3d_mat4_mul(out_matrix,&projection,&view);','last_view=view;last_projection=projection;last_near=near;last_w=w;last_h=h;\n t3d_mat4_mul(out_matrix,&projection,&view);')
        anchor=' camera(p,&eye,&matrix,&f);'
        driver=driver.replace(anchor,anchor+'''\n uint8_t levels[BG_WORLD_LOD_MAX_GROUPS];
 fprintf(lod_trace,"%u,%u",tick,p);
 for(unsigned col=0;col<4;col++)for(unsigned row=0;row<4;row++)fprintf(lod_trace,",%.9g",matrix.m[col][row]);
 for(unsigned g=0;g<bg_world_lod.group_count;g++){
 levels[g]=!getenv("BG_WORLD_LOD_FORCE_NEAR")&&bg_world_lod_far(&bg_world_lod.groups[g],last_view.m,last_projection.m,last_w,last_h,last_near,eye.v);
 fprintf(lod_trace,",%u",levels[g]);}fputc(10,lod_trace);
''')
        driver=driver.replace('  const bg_chunk*k=&bg_chunks[b];','  const bg_chunk*k=&bg_chunks[b];\n  if(!bg_world_lod_keep(&bg_world_lod,levels,b))continue;')
        driver=driver.replace(' assert(argc==2);',' assert(argc==3);lod_trace=fopen(argv[2],"w");assert(lod_trace);')
        driver=driver.replace('assert(fclose(out)==0);','assert(fclose(out)==0);assert(fclose(lod_trace)==0);')
        (output/'camera.c').write_text(driver)
        flags=['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off','-fno-fast-math','-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-unused-function','-Wno-incompatible-pointer-types','-DBG_WORLD_LOD','-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES','-I'+str(PREVIOUS/'cameras'),'-I'+str(sdk),'-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
        sources=['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','render_pvs.c']
        generated=['combat_data.c','movement_data.c','interaction_defs.c','camera_data.c']
        cmd=['clang',*flags,str(output/'camera.c'),str(OUT/'visibility-data.c'),str(sdk/'t3d/t3dmath.c'),*(str(ROOT/'port/n64'/s) for s in sources),*(str(ROOT/'build/n64/generated'/s) for s in generated),str(ROOT/'halo64-assets/generated/maps/common_data.c'),str(solver/'vehicle_data.c'),'-lm','-o',str(output/'probe')]
        subprocess.run(cmd,cwd=ROOT,check=True)
        with (output/'poses.json').open('w') as stdout:subprocess.run([str(output/'probe'),str(output/'cameras.csv'),str(output/'lod-trace.csv')],cwd=ROOT,check=True,stdout=stdout,env={**os.environ,'BG_MAP_DIRECTORY':str(OUT/'candidate-maps')})
        with (output/'control-poses.json').open('w') as stdout:subprocess.run([str(output/'probe'),str(output/'control-cameras.csv'),str(output/'control-lod-trace.csv')],cwd=ROOT,check=True,stdout=stdout,env={**os.environ,'BG_MAP_DIRECTORY':str(OUT/'candidate-maps'),'BG_WORLD_LOD_FORCE_NEAR':'1'})
        before=[r for r in csv.DictReader((BASE/name/'cameras.csv').open()) if r['map']=='1' and r['candidate']=='1'];after=[r for r in csv.DictReader((output/'cameras.csv').open()) if r['candidate']=='1']
        assert len(before)==len(after)
        for a,b in zip(before,after):assert all(a[k]==b[k] for k in ['map','tick','camera','eye_x','eye_y','eye_z','alive','zoom','pvs_mask'])
        if name=='photos':assert json.loads((output/'poses.json').read_text())==json.loads((BASE/name/'poses.json').read_text())
        control=[r for r in csv.DictReader((output/'control-cameras.csv').open()) if r['candidate']=='1']
        results[name]=dict(control_near_mean=statistics.mean(int(r['vertices']) for r in control),samples=len(after),before_mean=statistics.mean(int(r['vertices']) for r in before),after_mean=statistics.mean(int(r['vertices']) for r in after),after_worst=max(int(r['vertices']) for r in after),below_1500=sum(int(r['vertices'])<1500 for r in after),matching_poses=True)
    (OUT/'measurements.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
if __name__=='__main__':measure()
