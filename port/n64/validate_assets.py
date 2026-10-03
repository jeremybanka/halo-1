#!/usr/bin/env python3
"""Validate the generated multiplayer asset contract, including genuine motion."""
import json,math,re,struct
from pathlib import Path
from vehicle_parts import split_vehicle
from extract_extended import AUDIO_TAGS,AUDIO_ALIASES,MODEL_PATHS,ANIM_NAMES
from pack_animation import compact_clip
from pack_assets import position
from model_colors import load_images, bake_triangle, bake_team_mask
from pack_mesh import MODEL_COLOR_TOLERANCE, model_color_tolerance
from PIL import Image

def validate_material_sharing(corners,materials):
 """A loaded vertex may never serve two original shader materials."""
 groups={}
 for vertex,material in zip(corners,materials):
  if vertex in groups:assert groups[vertex]==material,('material seam',vertex)
  groups[vertex]=material

def validate_preview(preview,vertices,colors,masks,corners,scale):
 """Preview evidence must describe the actual emitted C index expansion."""
 assert preview['positions']==[[v/scale for v in vertices[i]] for i in corners]
 assert preview['colors']==[list(colors[i]) for i in corners]
 assert preview['team_mask']==[masks[i]/255 for i in corners]

def validate_animation(text,prefix,clip,scale,corners,vertex_count):
 """Independently decode every indexed animation endpoint from emitted C."""
 def numbers(kind,name):
  match=re.search(r'static (?:const )?'+kind+r' '+re.escape(name)+r'\[\][^=]*=\{(.*?)\};',text,re.S)
  assert match,name
  return [int(v) for v in re.findall(r'-?\d+',match[1])]
 values=numbers('uint8_t',prefix);tracks=numbers('uint16_t',prefix+'_indices')
 record=re.search(r'\{'+prefix+','+prefix+r'_indices,(\d+),(\d+),(\d+),([\d.]+)f,\{(-?\d+),(-?\d+),(-?\d+)\}\}',text);assert record,prefix
 frames,stored_vertices,track_count=map(int,record.group(1,2,3));origin=tuple(map(int,record.group(5,6,7)))
 assert frames==len(clip['frames']) and stored_vertices==vertex_count==len(tracks),prefix
 assert abs(float(record[4])-clip['duration'])<.000001 and len(values)==frames*track_count*3,prefix
 assert all(0<=v<=255 for v in values) and all(0<=t<track_count for t in tracks),prefix
 for frame,source in enumerate(clip['frames']):
  for corner,index in enumerate(corners):
   offset=(frame*track_count+tracks[index])*3
   actual=tuple(origin[a]+values[offset+a] for a in range(3))
   expected=tuple(round(v*scale) for v in position(source[corner],(0,0,0)))
   assert actual==expected,(prefix,frame,corner)
 return len(values)+len(tracks)*2

def validate_firstperson(fp,report,text,preview=None):
 """Decode the emitted indices and animation bytes independently of packing."""
 def numbers(kind,name):
  match=re.search(r'static (?:const )?'+kind+r' '+re.escape(name)+r'\[\][^=]*=\{(.*?)\};',text,re.S)
  assert match,name
  return [int(v) for v in re.findall(r'-?\d+',match[1])]
 pair=re.compile(r'\{\{(-?\d+),(-?\d+),(-?\d+)\},0,\{(-?\d+),(-?\d+),(-?\d+)\},0,0x([0-9a-fA-F]+),0x([0-9a-fA-F]+),')
 assert report['color_weld_tolerance']==MODEL_COLOR_TOLERANCE and report['material_boundaries_preserved']
 assert report['color_weld_tolerances']=={n:model_color_tolerance('firstperson',n) for n in report['vertices']}
 total=animation_bytes=0
 for name,expected_count in report['vertices'].items():
  tolerance=model_color_tolerance('firstperson',name)
  weapon=fp['weapons'][name];prefix='fp_'+name
  body=re.search(r'static T3DVertPacked '+prefix+r'\[\].*?=\{(.*?)\n\};',text,re.S);assert body,name
  vertices=[];colors=[]
  for item in pair.findall(body[1]):
   vertices.extend((tuple(map(int,item[:3])),tuple(map(int,item[3:6]))))
   for rgba in item[6:]:
    value=int(rgba,16);assert value&255==255
    colors.append(tuple((value>>shift)&255 for shift in (24,16,8)))
  assert len(vertices)==expected_count and expected_count%2==0,name
  masks=numbers('uint8_t',prefix+'_team_mask');assert len(masks)==expected_count,name
  indices=numbers('int16_t',prefix+'_indices')
  batch_text=re.search(r'static const bg_mesh_batch '+prefix+r'_batches\[\]=\{(.*?)\};',text,re.S);assert batch_text,name
  batches=[tuple(map(int,b)) for b in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}',batch_text[1])]
  assert len(batches)==report['batches'][name],name
  corners=[];end=0
  for first,count,index_first,index_count in batches:
   assert first==end and first%2==0 and 0<count<=60 and count%2==0
   assert index_first%4==0 and 0<index_count<=120 and index_count%3==0
   local=indices[index_first:index_first+index_count]
   assert len(local)==index_count and all(0<=i<count for i in local)
   corners.extend(first+i for i in local);end=first+count
  assert end==len(vertices) and len(corners)==len(weapon['triangles'])*3,name
  expected_positions=[tuple(round(v*256) for v in position(p,(0,0,0))) for tri in weapon['triangles'] for p in tri['p']]
  assert [vertices[i] for i in corners]==expected_positions,name
  images=load_images(weapon['textures']);source_colors=[rgb for tri in weapon['triangles'] for rgb in bake_triangle(tri,images,weapon,firstperson=True)]
  assert all(max(abs(a-b) for a,b in zip(source,colors[index]))<=tolerance for source,index in zip(source_colors,corners)),name
  validate_material_sharing(corners,[tri['material'] for tri in weapon['triangles'] for _ in range(3)])
  source_masks=load_images(weapon.get('material_multipurpose',[]))
  channels=[2 if source==3 else None for source in weapon.get('material_change_source',[])]
  expected_masks=[m for tri in weapon['triangles'] for m in bake_team_mask(tri,source_masks,channels)]
  assert [masks[i] for i in corners]==expected_masks,name
  if preview is not None:validate_preview(preview[name],vertices,colors,masks,corners,256)
  total+=len(vertices)*16+len(masks)+len(indices)*2+len(batches)*8
  for clipname,clip in weapon['clips'].items():
   count=validate_animation(text,prefix+'_'+clipname,clip,256,corners,len(vertices))
   total+=count;animation_bytes+=count
 assert animation_bytes==report['animation_bytes'] and total==report['total_bytes']
 assert total==sum(report[k] for k in ('vertex_bytes','team_mask_bytes','index_bytes','batch_bytes','animation_bytes'))
 maximum=re.search(r'bg_fp_max_vertices=(\d+);',text);assert maximum
 assert int(maximum[1])==max(report['vertices'].values())


def validate_world(raw,reduced,report,text,preview=None):
 """Expand emitted indexed static geometry against immutable source corners."""
 models=dict(reduced['models'])
 for name in ('warthog','ghost','scorpion','banshee'):
  models[name],_=split_vehicle(name,models[name],raw['models'][name])
 models.update({name+'_lod':m for name,m in reduced['vehicle_lods'].items()})
 models['spartan_lod']=reduced['spartan_lod']
 models.update({name+'_pickup_lod':m for name,m in reduced.get('pickup_lods',{}).items()})
 pair=re.compile(r'\{\{(-?\d+),(-?\d+),(-?\d+)\},0,\{(-?\d+),(-?\d+),(-?\d+)\},0,0x([0-9a-fA-F]+),0x([0-9a-fA-F]+),')
 assert report['color_weld_max_channel_delta']==MODEL_COLOR_TOLERANCE and report['material_boundaries_preserved']
 assert report['color_weld_tolerances']=={n:model_color_tolerance('world',n) for n in report['vertices']}
 packed_positions={};animation_bytes=0
 for name,expected_count in report['vertices'].items():
  tolerance=model_color_tolerance('world',name)
  model=models[name];prefix='model_'+name
  body=re.search(r'static T3DVertPacked '+prefix+r'\[\].*?=\{(.*?)\n\};',text,re.S);assert body,name
  vertices=[];colors=[]
  for item in pair.findall(body[1]):
   vertices.extend((tuple(map(int,item[:3])),tuple(map(int,item[3:6]))))
   for rgba in item[6:]:
    value=int(rgba,16);assert value&255==255
    colors.append(tuple((value>>shift)&255 for shift in (24,16,8)))
  assert len(vertices)==expected_count and expected_count%2==0,name
  index_text=re.search(r'static int16_t '+prefix+r'_indices\[\][^=]*=\{(.*?)\};',text,re.S);assert index_text,name
  indices=[int(v) for v in re.findall(r'-?\d+',index_text[1])]
  batch_text=re.search(r'static const bg_mesh_batch '+prefix+r'_batches\[\]=\{(.*?)\};',text,re.S);assert batch_text,name
  batches=[tuple(map(int,b)) for b in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}',batch_text[1])]
  corners=[];end=0
  for first,count,ii,ic in batches:
   assert first==end and first%2==0 and 0<count<=60 and count%2==0
   assert ii%4==0 and 0<ic<=120 and ic%3==0
   local=indices[ii:ii+ic];assert len(local)==ic and all(0<=i<count for i in local)
   corners.extend(first+i for i in local);end=first+count
  assert end==len(vertices) and len(corners)==len(model['triangles'])*3,name
  order=report.get('triangle_order',{}).get(name,list(range(len(model['triangles']))))
  assert sorted(order)==list(range(len(model['triangles']))),name
  if name in ('spartan','spartan_lod'):assert order==list(range(len(order))),name
  scale=report['model_position_scales'][name]
  positions=[tuple(round(v*scale) for v in position(p,(0,0,0))) for t in model['triangles'] for p in t['p']]
  packed_positions[name]=[tuple(v/scale for v in p) for p in positions]
  assert max((sum(abs(v) for v in p)+1)/65536 for p in positions)<.5,name
  images=load_images(model['textures']);source_colors=[rgb for t in model['triangles'] for rgb in bake_triangle(t,images,model)]
  if name in ('overshield','overshield_pickup_lod'):source_colors=[[238,92,52]]*len(positions)
  if name in ('camouflage','camouflage_pickup_lod'):source_colors=[[57,151,234]]*len(positions)
  source_corners=[triangle*3+corner for triangle in order for corner in range(3)]
  assert [vertices[index] for index in corners]==[positions[i] for i in source_corners],name
  assert all(max(abs(a-b) for a,b in zip(colors[index],source_colors[source]))<=tolerance
             for source,index in zip(source_corners,corners)),name
  validate_material_sharing(corners,[model['triangles'][source//3]['material'] for source in source_corners])
  source_masks=load_images(model.get('team_masks',[]))
  expected_masks=[m for tri in model['triangles'] for m in bake_team_mask(tri,source_masks,model.get('team_mask_channels',[]))]
  if name in ('spartan','spartan_lod'):
   mask_text=re.search(r'\buint8_t bg_'+name+r'_team_mask\[\]=\{(.*?)\};',text,re.S);assert mask_text,name
   masks=[int(v) for v in re.findall(r'\d+',mask_text[1])]
   clips=reduced['animations' if name=='spartan' else 'animations_lod']
   for clipname,clip in clips.items():
    animation_bytes+=validate_animation(text,('anim_' if name=='spartan' else 'anim_lod_')+clipname,clip,128,corners,len(vertices))
  else:
   assert not any(expected_masks),name
   masks=[0]*len(vertices)
  assert len(masks)==len(vertices) and [masks[i] for i in corners]==[expected_masks[i] for i in source_corners],name
  if preview is not None:validate_preview(preview[name],vertices,colors,masks,corners,scale)
  if name in report['vehicle_rigs']:
   offset=0
   for part in report['vehicle_rigs'][name]['parts']:
    count=part['count']//3;first=part['first']//3
    assert sorted(order[offset:offset+count])==list(range(first,first+count)),name
    offset+=count
 assert animation_bytes==report['animation_bytes']
 validate_cull_bounds(reduced,report,text,packed_positions)


def validate_cull_bounds(reduced,report,text,positions):
 """Every generated culling bound must enclose the actual rendered bank."""
 def values(name):
  record=re.search(r'\b'+re.escape(name)+r'\[[^]]*\]=\{(.*?)\};',text,re.S);assert record,name
  return [struct.unpack('f',struct.pack('f',float(v)))[0]
          for v in re.findall(r'(-?\d+\.\d+)f',record[1])]
 def contains(box,p):return all(box[a]<=p[a]<=box[a+3] for a in range(3))
 boxes=values('bg_model_cull_bounds');radii=values('bg_model_cull_radii')
 assert len(boxes)==len(MODEL_PATHS)*6 and len(radii)==len(MODEL_PATHS)
 for i,name in enumerate(MODEL_PATHS):
  if name=='flamethrower' and not report['pc_extras']:name='ar'
  names=[name]+([name+'_pickup_lod'] if name+'_pickup_lod' in positions else [])
  for key in names:
   for p in positions[key]:
    assert contains(boxes[i*6:i*6+6],p),(name,'bounds')
    assert sum(v*v for v in p)<=radii[i]**2,(name,'radius')
 vehicle_boxes=values('bg_vehicle_lod_bounds');assert len(vehicle_boxes)==24
 for i,name in enumerate(('warthog','ghost','scorpion','banshee')):
  assert all(contains(vehicle_boxes[i*6:i*6+6],p) for p in positions[name+'_lod']),name
  record=re.search(r'\bparts_'+name+r'\[\]=\{(.*?)\};',text,re.S);assert record,name
  records=record[1].strip().splitlines();parts=report['vehicle_rigs'][name]['parts']
  assert len(records)==len(parts),name
  for record,part in zip(records,parts):
   box=[struct.unpack('f',struct.pack('f',float(v)))[0] for v in re.findall(r'(-?\d+\.\d+)f',record)][-6:]
   assert all(contains(box,p) for p in positions[name][part['first']:part['first']+part['count']]),name
 bodies=values('bg_body_cull_bounds');markers=values('bg_attachment_cull_bounds')
 assert len(bodies)==len(markers)==len(ANIM_NAMES)*6
 for i,name in enumerate(ANIM_NAMES):
  box=bodies[i*6:i*6+6]
  for key in ('animations','animations_lod'):
   for frame in reduced[key][name]['frames']:
    assert all(contains(box,[round(v*128)/128 for v in position(p,(0,0,0))]) for p in frame),(name,key)
  assert all(contains(markers[i*6:i*6+6],p['pos']) for p in reduced['weapon_attachment'][name]['poses']),name


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
 validate_firstperson(fp,fp_report,fp_c,json.loads((root/'generated/firstperson-preview.json').read_text()))
 world_report=json.loads((root/'generated/extended-report.json').read_text())
 validate_world(raw,reduced,world_report,(root/'generated/models_data.c').read_text(),json.loads((root/'generated/model-preview.json').read_text()))
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
 # HUD padding removal must preserve the original layout and every visible
 # texel. Digits still use complete source cells to build the runtime atlas.
 hud=(root/'generated/hud_data.c').read_text()
 pixels={name:[int(v,16) for v in values.split(',')]
         for name,values in re.findall(r'uint16_t hud_(\w+)\[\].*?=\{(.*?)\};',hud)}
 records=re.findall(r'\{hud_(\w+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\}',hud)
 assert len(records)==41
 for name,w,h,tw,th,x,y in records:
  w,h,tw,th,x,y=map(int,(w,h,tw,th,x,y))
  image=Image.open(root/'assets/hud-sprites'/f'{name}.png').convert('RGBA')
  assert image.size==(w,h) and len(pixels[name])==tw*th,name
  if name.startswith('digit_'):assert (tw,th,x,y)==(w,h,0,0),name
  for py in range(h):
   for px in range(w):
    present=x<=px<x+tw and y<=py<y+th
    packed=bool(pixels[name][(py-y)*tw+px-x]&1) if present else False
    assert packed==(image.getpixel((px,py))[3]>=64),(name,px,py)
 print(f'Asset contracts pass: 19 source models, 4 vehicle LODs, vehicle part ranges, 2 Spartan LODs, {len(reduced["animations"])} clips, {len(fp_report["vertices"])} packed first-person rigs, 39 sound events / 36 source clips.')
if __name__=='__main__':main()
