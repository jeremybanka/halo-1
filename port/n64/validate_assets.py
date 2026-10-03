#!/usr/bin/env python3
"""Validate the generated multiplayer asset contract, including genuine motion."""
import json,math
from pathlib import Path
from vehicle_parts import split_vehicle
from extract_extended import AUDIO_TAGS,AUDIO_ALIASES
from pack_animation import compact_clip


def main():
 root=Path('build/n64');raw=json.loads((root/'assets/extended-raw.json').read_text())
 reduced=json.loads((root/'assets/extended-reduced.json').read_text())
 fp=json.loads((root/'assets/firstperson-reduced.json').read_text())
 assert len(reduced['models'])==19
 assert len(reduced['vehicle_lods'])==4
 assert all(0<len(m['triangles'])<=450 for m in reduced['vehicle_lods'].values())
 assert len(reduced['spartan_lod']['triangles'])<=240
 assert all(len(reduced['models'][name]['triangles'])<=80 for name in ('frag','plasma_grenade'))
 assert raw['models']['banshee']['baked_vehicle_pose']=='stand closing:terminal'
 for mesh in (reduced['models']['banshee'],reduced['vehicle_lods']['banshee']):
  points=[p for t in mesh['triangles'] for p in t['p']]
  assert max(p[2] for p in points)-min(p[2] for p in points)<1.1
 for name,expected in [('warthog',7),('scorpion',3)]:
  model,rig=split_vehicle(name,reduced['models'][name],raw['models'][name])
  assert len(rig['parts'])==expected,name
  offset=0
  for part in rig['parts']:
   assert part['first']==offset and part['first']%2==0 and part['count']%6==0,(name,part)
   offset+=part['count']
  assert offset==len(model['triangles'])*3,name
 for name,model in reduced['models'].items():
  assert model['triangles'],name
  for t in model['triangles']:
   assert len(t['p'])==3 and len(t['uv'])==3
   assert all(math.isfinite(x) for p in t['p'] for x in p)
   assert 0<=t['material']<len(model['textures'])
 assert all(0<=v[0]<len(raw['models']['spartan']['nodes']) for v in raw['models']['spartan']['weights'])
 death=raw['animations']['death']
 assert len(death['frames'])==death['source_frame_count']
 assert death['duration']==death['source_frame_count']/30 and death['frames'][-1]!=death['frames'][0]
 count=len(reduced['models']['spartan']['triangles'])*3
 for name,a in reduced['animations'].items():
  assert a['duration']>0 and len(a['frames'])>=2,name
  assert all(len(f)==count for f in a['frames']),name
  assert a['frames'][0]!=a['frames'][len(a['frames'])//2],name
  for f in a['frames']:
   assert all(math.isfinite(v) and abs(v)<3 for p in f for v in p),name
  low=reduced['animations_lod'][name]
  assert low['duration']==a['duration'] and len(low['frames'])==len(a['frames']),name
  assert all(len(f)==len(reduced['spartan_lod']['triangles'])*3 for f in low['frames']),name
  assert low['frames'][0]!=low['frames'][len(low['frames'])//2],name
  attachment=reduced['weapon_attachment'][name]
  assert attachment['duration']==a['duration'] and len(attachment['poses'])==len(a['frames']),name
  for pose in attachment['poses']:
   assert all(math.isfinite(v) and abs(v)<3 for v in pose['pos']),name
   assert abs(sum(v*v for v in pose['quat'])-1)<.001,name
 # Death is a clamped one-shot, unlike the repeating run/idle clips. Both LODs
 # must retain the real prone terminal pose rather than JMA's loop sentinel.
 for key in ('animations','animations_lod'):
  death=reduced[key]['death'];terminal=death['frames'][-1]
  assert death['duration']==raw['animations']['death']['duration']
  assert max(p[2] for p in terminal)<.25
  assert max(p[2] for p in terminal)-min(p[2] for p in terminal)<.25
  for name in ('passenger','gunner'):
   assert len(reduced[key][name]['frames'])==4
 assert raw['animations']['passenger']['tag_name']=='W-passenger rifle idle'
 assert raw['animations']['gunner']['tag_name']=='W-gunner fixed idle'
 assert len(fp['weapons'])==9
 for name,weapon in fp['weapons'].items():
  count=len(weapon['triangles'])*3
  assert count<=1800,name
  for cn,clip in weapon['clips'].items():
   assert all(len(frame)==count for frame in clip['frames']),(name,cn)
   assert all(math.isfinite(v) and abs(v)<3 for frame in clip['frames'] for p in frame for v in p),(name,cn)
   if cn in ('reload','melee'):
    assert clip['frames'][0]!=clip['frames'][len(clip['frames'])//2],(name,cn)
  if name!='flamethrower':assert 'fire' in weapon['clips']['fire']['tag_name'] or 'firing' in weapon['clips']['fire']['tag_name']
 fp_report=json.loads((root/'generated/firstperson-report.json').read_text())
 fp_c=(root/'generated/firstperson_data.c').read_text()
 if fp_report['pc_extras']:
  assert len(fp_report['vertices'])==9 and not fp_report['aliases']
  assert 'static T3DVertPacked fp_flamethrower[]' in fp_c
 else:
  assert len(fp_report['vertices'])==8 and fp_report['aliases']=={'flamethrower':'ar'}
  assert 'fp_flamethrower' not in fp_c
  assert fp_report['total_bytes']==sum(
      ((len(w['triangles'])*3+1)//2)*32+len(w['triangles'])*3+
      sum(compact_clip(a,256)['bytes'] for a in w['clips'].values())
      for n,w in fp['weapons'].items() if n!='flamethrower')
 for key in ('animations','animations_lod'):
  for clip in reduced[key].values():compact_clip(clip,128)
 for name,sound in raw['audio'].items():
  samples=Path(sound['file']).read_bytes()
  assert sound['count']==len(samples)>0 and sound['rate']==11025,name
  assert len(set(samples))>10,name
 assert list(raw['audio'])==list(AUDIO_TAGS)
 for name,canonical in AUDIO_ALIASES.items():
  assert raw['audio'][name]['alias']==canonical
  assert Path(raw['audio'][name]['file']).read_bytes()==Path(raw['audio'][canonical]['file']).read_bytes()
 added=sum(raw['audio'][name]['count'] for name in ('banshee','warthog_gun','banshee_bomb'))
 assert added<=60000,added
 for file in ('models_data.c','audio_data.c','hud_data.c','firstperson_data.c'):
  assert (root/'generated'/file).stat().st_size>1000,file
 print(f'Asset contracts pass: 19 source models, 4 vehicle LODs, vehicle part ranges, 2 Spartan LODs, {len(reduced["animations"])} clips, {len(fp_report["vertices"])} packed first-person rigs, 39 sound events / 36 source clips.')
if __name__=='__main__':main()
