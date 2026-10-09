#!/usr/bin/env python3
"""Extract original Xbox seat camera tracks and rocket guidance evidence."""
import contextlib,hashlib,json
from pathlib import Path
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets';G=ROOT/'build/n64/generated'
def main():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from pack_fp_ammo import globals_for
 import numpy as np
 raw=json.loads((A/'extended-raw.json').read_text())
 tracks=[];rows=[];report={'seats':[],'rocket':{}}
 with (G/'camera-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  maps=[]
  for name in ('bloodgulch','a30'):
   h=Halo1Map();h.load_map(A/(name+'-decompressed.map'));maps.append(h)
  def tag(h,path,kind):
   return h.get_meta(next(i for i,e in enumerate(h.tag_index.tag_index) if e.path==path and e.class_1.enum_name==kind))
  for name,path in [('warthog',r'vehicles\warthog\warthog'),('ghost',r'vehicles\ghost\ghost_mp'),('scorpion',r'vehicles\scorpion\scorpion_mp'),('banshee',r'vehicles\banshee\banshee')]:
   h=maps[name=='banshee'];v=tag(h,path,'vehicle');seats=list(v.unit_attrs.seats.STEPTREE)
   if name=='warthog':seats=[seats[i] for i in (0,2,1)]
   model=raw['models'][name];transforms=globals_for(model['nodes'],model['nodes'])
   row=[]
   for seat in seats:
    path=seat.camera_tracks.STEPTREE[0].track.filepath if seat.camera_tracks.size else r'globals\default unit camera track'
    t=tag(h,path,'camera_track');points=[[float(p.position[i]) for i in range(3)] for p in t.control_points.STEPTREE]
    assert len(points)>=4
    if points not in tracks:tracks.append(points)
    origin=[0,0,0]
    if seat.camera_marker_name:
     marker=model['markers'].get(seat.camera_marker_name)
     if marker:
      marker=marker[0];r,p=transforms[marker['node']];pos=r@np.array(marker['p'])+p
     else:
      # objects.c:object_get_marker_by_name falls back to node zero.
      pos=transforms[0][1]
     origin=[float(pos[0]),float(pos[2]),float(-pos[1])]
    row.append((tracks.index(points),len(points),origin))
    report['seats'].append({'vehicle':name,'seat':seat.label,'marker':seat.camera_marker_name,'origin_y_up':origin,'track':path,'points':points})
   rows.append(row)
  rocket=tag(maps[0],r'weapons\rocket launcher\rocket','projectile')
  weapon=tag(maps[0],r'weapons\rocket launcher\rocket launcher','weapon')
  report['rocket']={'guided_angular_velocity':rocket.proj_attrs.physics.guided_angular_velocity,
   'tracks_fired_projectile':bool(weapon.weap_attrs.triggers.STEPTREE[0].flags.tracks_fired_projectile),
   'zoom':tag_values(weapon.weap_attrs.aiming)}
 lines=['/* Generated from owned Xbox camera tags. */','#include "view_camera.h"']
 for i,pts in enumerate(tracks):lines.append(f'static const float track{i}[{len(pts)}][3]={{'+','.join('{'+','.join(f'{x:.9g}f' if '.' in f'{x:.9g}' or 'e' in f'{x:.9g}' else f'{x:.1f}f' for x in p)+'}' for p in pts)+'};')
 lines.append('const bg_camera_track bg_camera_tracks[4][5]={')
 for row in rows:lines.append('{'+','.join('{track%d,%d,{%s}}'%(i,n,','.join(f'{x:.9f}f' for x in origin)) for i,n,origin in row)+'},')
 lines.append('};');out=G/'camera_data.c';out.write_text('\n'.join(lines)+'\n')
 report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),A/'bloodgulch-decompressed.map',A/'a30-decompressed.map',A/'extended-raw.json']}
 report['generated_sha256']=hashlib.sha256(out.read_bytes()).hexdigest();(G/'camera-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Extracted',len(tracks),'camera tracks; rocket guidance:',report['rocket']['guided_angular_velocity'])
if __name__=='__main__':main()
