"""Skin accepted Elite LODs and canonical hit surfaces with original CE seats.

Source hierarchy, weights and every one-shot frame are retained. Runtime meshes
are unchanged: sample the same packed vertex sources as the accepted bank.
"""
import gzip,json,math,shutil
from pathlib import Path
import numpy as np
from pack_enemy_vehicles import ROOT,OUT,BANK,F,B
from pack_fp_ammo import globals_for
from pack_pve import prepare_model,emit_rom_clip
from pack_animation import emit_clip,clip_initializer
from pack_mesh import remap_clip
import pack_bounds

def bake():
 base=ROOT/'halo64-assets/assets/jackal-shields/bank'
 for p in base.iterdir():
  if p.is_file():shutil.copyfile(p,BANK/p.name)
 raw=json.loads((ROOT/'halo64-assets/assets/covenant-symmetry/source/squad-source.json').read_text());model=raw['models']['elite'];nodes=model['nodes']
 baked=json.loads(gzip.decompress((ROOT/'halo64-assets/assets/firefight-roster/source/squad-baked.json.gz').read_bytes()))['elite']
 meta=json.loads((OUT/'metadata.json').read_text());source=meta['elite_clips']
 def matrices(states):
  result=[]
  for r,p in globals_for(states,nodes):
   m=np.eye(4);m[:3,:3]=r;m[:3,3]=p;result.append(m)
  return np.array(result)
 inverse=np.linalg.inv(matrices(nodes));collision=raw['actors']['elite']['collision'];hit_vertices=[]
 for node in collision['nodes']:
  ni=next(i for i,n in enumerate(nodes) if n['name']==node['name'])
  for bsp in node['bsps'][:1]:hit_vertices += [(ni,[*v[:3],1]) for v in bsp['vertices']]
 motion=bytearray((BANK/'pve-motion.bin').read_bytes());lines=['#include "asset_pve.h"','#include "enemy_pilots.h"'];hitlines=['#include "enemy_pilots.h"'];visualrows=['{0}']*6;hitrows=['{0}']*6;boundrows=['{0}']*6;record={}
 for kind,prefix in [(1,'G-driver'),(3,'B-driver'),(4,'wraith-driver'),(5,'GT-gunner')]:
  enter=source[prefix+' enter'];idle=source.get(prefix+' unarmed idle') or {'duration':1,'frames':[enter['frames'][-1]]};exit=source.get(prefix+' exit') or {'duration':enter['duration'],'frames':list(reversed(enter['frames']))}
  clips=[idle,enter,exit];lodrows=[];all_bounds=[];hitrow=[];record[prefix]=[]
  for lod,(w,lodname) in enumerate(zip(baked,model['n64_lods'])):
   geometry=model['source_geometry_lods'][lodname];corners=[i for face in geometry['faces'] for i in face];mesh,_=prepare_model(w,True)
   assert len(corners)==len(w['triangles'])*3
   rows=[];bounds=[]
   for ci,c in enumerate(clips):
    # Idle cycles use the same four sample policy as source Spartan seats.
    frames=c['frames'] if ci else [c['frames'][round(i*(len(c['frames'])-1)/3)] for i in range(min(4,len(c['frames'])))]
    result=[];hits=[]
    for states in frames:
     pose=matrices(states);skin=pose@inverse;points=[]
     for vi in corners:
      p=np.array([*geometry['vertices'][vi],1])
      if 'skin_weights' in geometry:weighted=geometry['skin_weights'][vi]
      else:
       a,b,weight=geometry['weights'][vi];weighted=[(a,1-weight),(b,weight)] if b>=0 and weight else [(a,1)]
      points.append(sum((skin[b]@p)*weight for b,weight in weighted)[:3].tolist())
     result.append(points)
     if lod==0:hits.append([(pose[ni]@np.array(p))[:3].tolist() for ni,p in hit_vertices])
    clip={'duration':c['duration'],'frames':result};prefixout=f'enemy_pilot_{kind}_{lod}_{ci}'
    remapped=remap_clip(clip,mesh['sources']);packed=emit_rom_clip(lines,prefixout,remapped,motion)
    rows.append(clip_initializer(prefixout,remapped,packed,'(const uint16_t*)(uintptr_t)'+str(packed['rom_offset'])).rstrip(','))
    box=pack_bounds.animation_bounds(clip,clip);bounds.append(box)
    if lod==0:
     hc={'duration':c['duration'],'frames':hits};hn=prefixout+'_hit'
     # Host tests retain the exact samples; native uses the same big-endian ROM
     # bank as visual motion with one small, synchronous collision DMA window.
     hitlines.append('#ifndef N64');hp=emit_clip(hitlines,hn,hc,128,16)
     hitlines.append('#else');hr=emit_rom_clip(hitlines,hn,hc,motion)
     hitlines.append('#define '+hn+' ((const uint16_t*)(uintptr_t)'+str(hr['rom_offset'])+')')
     hitlines.append('#endif');hitrow.append(clip_initializer(hn,hc,hp).rstrip(','))
     record[prefix].append({'frames':len(frames),'duration':c['duration'],'source':prefix+(' unarmed idle' if ci==0 else ' enter' if ci==1 else ' exit'),'fallback_hidden_wraith':kind==4 and ci!=1})
   lodrows.append(B(rows));all_bounds.append(bounds)
  visualrows[kind]=B(lodrows);hitrows[kind]=B(hitrow);boundrows[kind]=B(pack_bounds.initializer(pack_bounds.union(*[row[ci] for row in all_bounds])) for ci in range(3))
 lines.append('const bg_pve_animation bg_enemy_pilot_animations[BG_VEHICLE_COUNT][3][3]='+B('['+str(i)+']='+r for i,r in enumerate(visualrows) if r!='{0}')+';')
 lines.append('const bg_bounds bg_enemy_pilot_bounds[BG_VEHICLE_COUNT][3]='+B('['+str(i)+']='+r for i,r in enumerate(boundrows) if r!='{0}')+';')
 hitlines.append('const bg_pve_animation bg_enemy_pilot_hits[BG_VEHICLE_COUNT][3]='+B('['+str(i)+']='+r for i,r in enumerate(hitrows) if r!='{0}')+';')
 (BANK/'enemy_pilot_data.c').write_text('\n'.join(lines));(BANK/'enemy_pilot_hits.c').write_text('\n'.join(hitlines));(BANK/'pve-motion.bin').write_bytes(motion)
 report=json.loads((BANK/'pve-report.json').read_text());import hashlib;report['motion']['sha256']=hashlib.sha256(motion).hexdigest();report['motion']['bytes']=len(motion);(BANK/'pve-report.json').write_text(json.dumps(report,indent=2))
 (BANK/'pilot-report.json').write_text(json.dumps(record,indent=2));print('Pilot bank',len(motion),'bytes')
if __name__=='__main__':bake()
