"""Match per-camera static-world submissions at fixed production replay ticks.

Uses the renderer's actual camera construction, SDK float matrices and culling.
Host clipping estimates are separately labeled; native snapshots corroborate
submission counts, and quiet VI controls establish performance independently.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from asset_ids import map_ids
from export_chiron_visibility import emit_c

ROOT=Path(__file__).resolve().parents[2]
SDK=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src'
DRIVER=r'''
#include "game.h"
#include "map.h"
#include "world.h"
#include "movement.h"
#include "pickup_rules.h"
#include "view_camera.h"
#include "blam/vehicle_physics.h"
#include "hud_layout.h"
#include "render_cull.h"
#include "render_visibility.h"
#include "render_pvs.h"
#include "blam/vehicle_profile.h"
#include "blam/runtime.h"
#include "replay.h"
#include <t3d/t3dmath.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern const bg_pvs_data bg_chiron_pvs;
static unsigned views=4;
CAMERA
typedef struct{unsigned chunks,vertices,triangles,materials,crossing,rejected;} counts;
static void count_view(unsigned p,unsigned tick,FILE*out){
 T3DVec3 eye;T3DMat4 matrix;T3DFrustum f;
 camera(p,&eye,&matrix,&f);
 uint8_t selected[6][3];bg_frustum_prepare(selected,(const float(*)[4])f.planes);
 const float*o=bg_map_origin();float source_eye[3]={eye.x/BG_SCALE+o[0],-eye.z/BG_SCALE+o[1],eye.y/BG_SCALE+o[2]};
 float radius=bg_players[p].health>0&&bg_players[p].zoom?1.25f:.25f;
 uint16_t mask=bg_map_id()==BG_MAP_CHIRON_TL34?bg_pvs_camera_mask(&bg_chiron_pvs,source_eye,radius):UINT16_MAX;
 counts c[2]={{0}};unsigned material[2]={~0u,~0u};
 for(unsigned b=0;b<bg_chunk_count;b++){
  const bg_chunk*k=&bg_chunks[b];
  if(!bg_frustum_box_cached((const float(*)[4])f.planes,selected,k->bounds))continue;
  bool keep=bg_map_id()!=BG_MAP_CHIRON_TL34||bg_pvs_keep_chunk(&bg_chiron_pvs,mask,b);
  unsigned crossing=0,rejected=0;
  for(unsigned i=0;i<k->index_count;i+=3){
   unsigned either=0,both=63;
   for(unsigned a=0;a<3;a++){
    unsigned id=k->first+(uint16_t)bg_chunk_indices[k->index_first+i+a];assert(id<bg_vertex_count);
    const uint8_t*raw=(const uint8_t*)bg_map_vertex_data+(id/2)*32+(id%2)*8;
    int16_t point[3];memcpy(point,raw,6);T3DVec3 v={{point[0]*.125f,point[1]*.125f,point[2]*.125f}};T3DVec4 clip;
    t3d_mat4_mul_vec3(&clip,&matrix,&v);
    /* Float CPU homogeneous estimate; RSP fixed-point and guard-band results
     * are deliberately not represented as measured clipping operations. */
    unsigned flags=0;
    for(unsigned axis=0;axis<3;axis++){flags|=(clip.v[axis]<-clip.w)<<(axis*2);flags|=(clip.v[axis]>clip.w)<<(axis*2+1);}
    either|=flags;both&=flags;
   }
   crossing+=either!=0&&both==0;rejected+=both!=0;
  }
  for(unsigned candidate=0;candidate<2;candidate++){
   if(candidate&&!keep)continue;
   c[candidate].chunks++;c[candidate].vertices+=(k->count+1)&~1u;c[candidate].triangles+=k->index_count/3;
   c[candidate].crossing+=crossing;c[candidate].rejected+=rejected;
   if(material[candidate]!=k->material){c[candidate].materials++;material[candidate]=k->material;}
  }
 }
 for(unsigned candidate=0;candidate<2;candidate++)fprintf(out,"%u,%u,%u,%u,%.9g,%.9g,%.9g,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
  bg_map_id(),tick,p,candidate,eye.x/BG_SCALE,eye.y/BG_SCALE,eye.z/BG_SCALE,
  bg_players[p].health>0,bg_players[p].zoom,mask,c[candidate].chunks,c[candidate].vertices,c[candidate].triangles,
  c[candidate].materials,c[candidate].crossing,c[candidate].rejected);
}
int main(int argc,char**argv){
 assert(argc==2);FILE*out=fopen(argv[1],"w");assert(out);
 fputs("map,tick,camera,candidate,eye_x,eye_y,eye_z,alive,zoom,pvs_mask,chunks,vertices,triangles,material_changes,float_clip_crossing_estimate,float_clip_rejected_estimate\n",out);
 const unsigned maps[]={MAP_IDS};
 for(unsigned m=0;m<sizeof(maps)/sizeof(maps[0]);m++){
  assert(bg_map_load(maps[m]));bg_set_players(4);bg_reset();float time=0;
  for(unsigned tick=1;tick<=2250;tick++){
   bg_input input[4]={{0}};bg_replay_input(input,time);bg_clear_events();bg_tick(input,BLAM_TICK_SECONDS);time+=BLAM_TICK_SECONDS;
   if(tick%150==0||tick==180||tick==1148)for(unsigned p=0;p<4;p++)count_view(p,tick,out);
  }
  bg_map_unload();
 }
 assert(fclose(out)==0);
}
'''


def run(out,sidecar):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);solver=out/'solver'
    for name in ('prepare_vehicle.py','export_vehicle.py'):
        cmd=[sys.executable,str(ROOT/'port/n64/blam'/name),'--output',str(solver)]
        if name=='export_vehicle.py':cmd+=['--rom-files',str(solver)]
        subprocess.run(cmd,cwd=ROOT,check=True)
    scene=(ROOT/'port/n64/scene.c').read_text()
    start=scene.index('static void prepare_view(unsigned p) {')
    end=scene.index('    T3DViewport *vp =',start)
    camera=scene[start:end].replace('static void prepare_view(unsigned p) {','static void camera(unsigned p,T3DVec3*out_eye,T3DMat4*out_matrix,T3DFrustum*out_frustum){')
    camera+='''
 float fov=1.08f;bool scoped=player->health>0&&player->zoom;
 unsigned magnification=scoped?(player->weapon==BG_W_SNIPER&&player->zoom==2?10:2):0;
 if(scoped)fov=bg_camera_zoom_fov(fov,magnification);
 float near,far;bg_camera_depth(scoped,&near,&far);T3DMat4 projection,view;
 t3d_mat4_perspective(&projection,fov,(float)w/h,near,far);bg_hud_aim_projection(projection.m,views,p);
 t3d_mat4_look_at(&view,&eye,&target,&(T3DVec3){{0,1,0}});
 t3d_mat4_mul(out_matrix,&projection,&view);t3d_mat4_to_frustum(out_frustum,out_matrix);
 bg_visibility_side_planes((float(*)[4])out_frustum->planes,out_matrix->m,w,h);*out_eye=eye;
}
'''
    driver=out/'camera.c';driver.write_text(DRIVER.replace('CAMERA',camera).replace('MAP_IDS',','.join(map(str,map_ids().values()))))
    (out/'libdragon.h').write_text('#include <stdint.h>\n#include <stdbool.h>\n#include <math.h>\n#define fm_sinf sinf\n#define fm_cosf cosf\n')
    data=json.loads(sidecar.read_text());emit_c(data,out/'visibility-data.c')
    sources=['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','render_pvs.c']
    generated=['combat_data.c','movement_data.c','interaction_defs.c','camera_data.c']
    flags=['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off','-fno-fast-math','-fno-strict-aliasing','-fwrapv',
           '-Wno-multichar','-Wno-unused-function','-Wno-incompatible-pointer-types','-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES',
           '-I'+str(out),'-I'+str(SDK),'-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
    cmd=['clang',*flags,str(driver),str(out/'visibility-data.c'),str(SDK/'t3d/t3dmath.c'),
         *(str(ROOT/'port/n64'/s) for s in sources),*(str(ROOT/'build/n64/generated'/s) for s in generated),
         str(ROOT/'halo64-assets/generated/maps/common_data.c'),str(solver/'vehicle_data.c'),'-lm','-o',str(out/'probe')]
    subprocess.run(cmd,cwd=ROOT,check=True)
    subprocess.run([str(out/'probe'),str(out/'cameras.csv')],cwd=ROOT,
                   env={**os.environ,'BG_MAP_DIRECTORY':str(ROOT/'halo64-assets/generated/maps')},check=True)
    names={v:k for k,v in map_ids().items()};rows=list(csv.DictReader((out/'cameras.csv').open()))
    result={}
    for name in map_ids():
        selected=[r for r in rows if names[int(r['map'])]==name]
        result[name]={}
        for candidate in (0,1):
            subset=[r for r in selected if int(r['candidate'])==candidate]
            result[name]['pvs' if candidate else 'baseline']={
                'camera_samples':len(subset),**{key:sum(int(r[key]) for r in subset)/len(subset) for key in
                    ('chunks','vertices','triangles','material_changes','float_clip_crossing_estimate','float_clip_rejected_estimate')}}
    metadata=dict(scope='Matched host per-camera production replay poses, 17 fixed ticks per map. SDK float-camera/cull math; native counts must corroborate. Static world only; clipping columns are float estimates, not RSP measurements or timing.',
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  camera_source_sha256=hashlib.sha256(camera.encode()).hexdigest(),
                  sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),maps=result)
    (out/'results.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-chiron-visibility/camera-census')
    parser.add_argument('--sidecar',type=Path,default=ROOT/'build/n64-chiron-visibility/data/visibility.json')
    args=parser.parse_args();run(args.output_dir,args.sidecar.resolve())
