"""Record reproducible single-player walk states and matched world submissions."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-photography'
SDK=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src'

MAIN=r'''
#include "photo_tour.h"
int main(int argc,char**argv){
 assert(argc==2);assert(bg_map_load(1));views=1;
 FILE*out=fopen(argv[1],"w");assert(out);
 fputs("map,tick,camera,candidate,eye_x,eye_y,eye_z,alive,zoom,pvs_mask,chunks,vertices,triangles,material_changes,float_clip_crossing_estimate,float_clip_rejected_estimate\n",out);
 puts("[");
 for(unsigned photo=0;photo<BG_PHOTO_COUNT;photo++){
  bg_photo_begin(photo);float time=0,walk_distance=0;
  for(unsigned tick=0;tick<bg_photo_ticks(photo);tick++){
   bg_input in[4];bg_photo_input(photo,tick,in);float old[3];memcpy(old,bg_players[0].pos,12);
   bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);time+=BLAM_TICK_SECONDS;
   walk_distance+=hypotf(bg_players[0].pos[0]-old[0],bg_players[0].pos[2]-old[2]);
  }
  const bg_player*q=&bg_players[0];assert(q->health>0);
  count_view(0,photo,out);
  printf("%s{\"photo\":%u,\"label\":\"%s\",\"start\":%u,\"ticks\":%u,\"time\":%.9g,\"position\":[%.9g,%.9g,%.9g],\"yaw\":%.9g,\"pitch\":%.9g,\"crouch_amount\":%.9g,\"crouched\":%s,\"grounded\":%s,\"velocity\":[%.9g,%.9g,%.9g],\"vy\":%.9g,\"gait\":%.9g,\"animation\":%d,\"animation_time\":%.9g,\"eye_height\":%.9g,\"weapon\":%d,\"zoom\":%d,\"walk_distance\":%.9g,\"player_bytes_hex\":\"",
   photo?",\n":"",photo,bg_photo_stations[photo/2].label,bg_photo_stations[photo/2].start,bg_photo_ticks(photo),time,
   q->pos[0],q->pos[1],q->pos[2],q->yaw,q->pitch,q->crouch_amount,q->crouched?"true":"false",q->grounded?"true":"false",
   q->velocity[0],q->velocity[1],q->velocity[2],q->vy,q->gait,q->animation,q->anim_time,bg_eye_height(q),q->weapon,q->zoom,walk_distance);
  const unsigned char*raw=(const unsigned char*)q;
  for(unsigned j=0;j<sizeof(*q);j++)printf("%02x",raw[j]);puts("\"}");
 }
 puts("]");assert(fclose(out)==0);bg_map_unload();
}
'''

def run(output,directory,sidecar=None,trace_photo=None):
    output.mkdir(parents=True,exist_ok=True)
    base=ROOT/'build/n64-visibility-rollout/sidewinder/cameras'
    source=(base/'camera.c').read_text();source=source[:source.index('int main(int argc')]+MAIN
    if trace_photo is not None:
        source=source.replace('tick==180&&p==0&&!keep',f'tick=={trace_photo}&&p==0&&!keep')
    (output/'camera.c').write_text(source)
    flags=['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off','-fno-fast-math',
           '-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-unused-function','-Wno-incompatible-pointer-types',
           '-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES','-I'+str(base),'-I'+str(SDK),'-Iport/n64','-Ibuild/n64/blam-core','-I'+str(base/'solver')]
    if trace_photo is not None:flags.append('-DBG_TRACE_PVS_CHUNKS')
    sources=['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','render_pvs.c']
    generated=['combat_data.c','movement_data.c','interaction_defs.c','camera_data.c']
    visibility_source=base/'visibility-data.c'
    if sidecar:
        from export_chiron_visibility import emit_c
        visibility_source=output/'visibility-data.c'
        emit_c(json.loads(sidecar.read_text()),visibility_source,directory/'sidewinder.map64')
    subprocess.run(['clang',*flags,str(output/'camera.c'),str(visibility_source),str(SDK/'t3d/t3dmath.c'),
        *(str(ROOT/'port/n64'/s) for s in sources),*(str(ROOT/'build/n64/generated'/s) for s in generated),
        str(ROOT/'halo64-assets/generated/maps/common_data.c'),str(base/'solver/vehicle_data.c'),'-lm','-o',str(output/'probe')],check=True,cwd=ROOT)
    result=subprocess.check_output([str(output/'probe'),str(output/'cameras.csv')],cwd=ROOT,
                                  env={**os.environ,'BG_MAP_DIRECTORY':str(directory.resolve())},text=True)
    poses=json.loads(result);(output/'poses.json').write_text(json.dumps(poses,indent=2)+'\n')
    rows=[r for r in csv.DictReader((output/'cameras.csv').open()) if r['candidate']==('1' if sidecar else '0')]
    summary={k:sum(int(r[k]) for r in rows)/len(rows) for k in ['chunks','vertices','triangles','material_changes']}
    summary.update(photos=len(poses),walked_distance=sum(p['walk_distance'] for p in poses),
                   map_sha256=hashlib.sha256((directory/'sidewinder.map64').read_bytes()).hexdigest())
    (output/'results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--maps',type=Path,default=ROOT/'halo64-assets/generated/maps');p.add_argument('--sidecar',type=Path);p.add_argument('--trace-photo',type=int);a=p.parse_args();run(a.output,a.maps,a.sidecar,a.trace_photo)
