#!/usr/bin/env python3
"""Pack locally extracted Xbox models, baked animation, audio and HUD for libdragon."""
import argparse,json,math
from pathlib import Path
from pack_assets import position, floats
from extract_extended import MODEL_PATHS, AUDIO_TAGS, ANIM_NAMES
from vehicle_parts import VEHICLES, split_vehicle
from pack_animation import emit_clip, clip_initializer
from model_colors import load_images, bake_triangle, bake_team_mask, is_visor
from pack_mesh import indexed_mesh, emit_batches, trajectory_keys, remap_clip, MODEL_COLOR_TOLERANCE, model_color_tolerance
import pack_bounds


def pack(source,out,pc_extras=False):
 data=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True)
 raw=json.loads((source.parent/'extended-raw.json').read_text());rigs={}
 # Original low/superlow Spartan LODs merge the visor into the armor shader.
 # Recover those broad face panels using the highest source visor's bounds.
 spartan=raw['models']['spartan']
 visor_material=next(i for i in range(len(spartan['material_metadata'])) if is_visor(spartan,i))
 visor_points=[spartan['vertices'][v] for face,material in zip(spartan['faces'],spartan['materials']) if material==visor_material for v in face]
 visor_bounds=[[fn(p[a] for p in visor_points) for a in range(3)] for fn in (min,max)]
 for model in (data['models']['spartan'],data['spartan_lod']):
  for tri in model['triangles']:
   center=[sum(p[a] for p in tri['p'])/3 for a in range(3)]
   if all(visor_bounds[0][a]<=center[a]<=visor_bounds[1][a] for a in range(3)):
    tri['material']=visor_material
 for name in VEHICLES:
  data['models'][name],rigs[name]=split_vehicle(name,data['models'][name],raw['models'][name])
 def rgba(rgb):return (rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
 def xyz(v):return '{'+','.join(map(str,v))+'}'
 lines=['/* Generated from local game data; do not commit. */','#include "asset_models.h"']
 model_sizes={};previews={};scales={};meshes={};triangle_counts={};packed_animations={};cull_bounds={};cull_radii={}
 all_models=(list(data['models'].items())
             +[(name+'_lod',model) for name,model in data.get('vehicle_lods',{}).items()]
             +[('spartan_lod',data['spartan_lod'])]
             +[(name+'_pickup_lod',model) for name,model in data.get('pickup_lods',{}).items()
               if pc_extras or name!='flamethrower'])
 for name,model in all_models:
  if name=='flamethrower' and not pc_extras:continue
  scale=128 if name.startswith('spartan') else 1024;scales[name]=scale
  cull_bounds[name],cull_radii[name]=pack_bounds.model_bounds(model,scale)
  verts=[];team_mask=[]
  images=load_images(model['textures'])
  masks=load_images(model.get('team_masks',[]));channels=model.get('team_mask_channels',[])
  for tri in model['triangles']:
   points=[position(p,(0,0,0)) for p in tri['p']]
   colors=bake_triangle(tri,images,model)
   team_mask.extend([0,0,0] if is_visor(model,tri['material']) else bake_team_mask(tri,masks,channels))
   for p,rgb in zip(points,colors):
    if name in ('overshield','overshield_pickup_lod'):rgb=[238,92,52]
    if name in ('camouflage','camouflage_pickup_lod'):rgb=[57,151,234]
    verts.append(([round(x*scale) for x in p],rgb))
  clips=data['animations'] if name=='spartan' else data['animations_lod'] if name=='spartan_lod' else None
  segments=[(p['first'],p['count']) for p in rigs[name]['parts']] if name in rigs else None
  mesh=indexed_mesh([p for p,rgb in verts],[rgb for p,rgb in verts],team_mask,
                    trajectory_keys(clips,scale) if clips else None,segments,reorder_static=clips is None,
                    color_tolerance=model_color_tolerance('world',name),
                    material_keys=[t['material'] for t in model['triangles'] for _ in range(3)])
  meshes[name]=mesh;triangle_counts[name]=len(model['triangles'])
  corners=[triangle*3+corner for triangle in mesh['triangle_order'] for corner in range(3)]
  previews[name]={'positions':[[c/scale for c in verts[i][0]] for i in corners],
                  'colors':[mesh['colors'][i] for i in corners],'triangle_count':len(model['triangles']),
                  'team_mask':[team_mask[i]/255 for i in corners]}
  if clips:packed_animations[name]={n:remap_clip(c,mesh['sources']) for n,c in clips.items()}
  if name in ('spartan','spartan_lod'):
   lines.append(f'const uint8_t bg_{name}_team_mask[]={{'+','.join(str(v[2]) for v in mesh['vertices'])+'};')
  verts=mesh['vertices'];model_sizes[name]=len(verts)
  lines.append(f'static T3DVertPacked model_{name}[] __attribute__((aligned(16)))={{')
  for i in range(0,len(verts),2):
   a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{{0,0}},{{0,0}}'+'},')
  lines.append('};')
  emit_batches(lines,'model_'+name,mesh)
 def initializer(name,radius):
  return (f'{{model_{name},{model_sizes[name]},{radius:.6f}f,model_{name}_batches,'
          f'model_{name}_indices,{len(meshes[name]["batches"])},{triangle_counts[name]}}},')
 lines.append('const bg_model_asset bg_model_assets[BG_M_COUNT]={')
 for name in MODEL_PATHS:
  if name=='flamethrower' and not pc_extras:name='ar'
  radius=max(math.sqrt(sum(v*v for v in p)) for t in data['models'][name]['triangles'] for p in t['p'])
  lines.append(initializer(name,radius))
 lines.append('};')
 lines.append('const bg_bounds bg_model_cull_bounds[BG_M_COUNT]={')
 for name in MODEL_PATHS:
  if name=='flamethrower' and not pc_extras:name='ar'
  lod=name+'_pickup_lod'
  lines.append(pack_bounds.initializer(pack_bounds.union(cull_bounds[name],cull_bounds.get(lod,cull_bounds[name])))+',')
 lines.append('};')
 lines.append('const float bg_model_cull_radii[BG_M_COUNT]={')
 for name in MODEL_PATHS:
  if name=='flamethrower' and not pc_extras:name='ar'
  radius=max(cull_radii[name],cull_radii.get(name+'_pickup_lod',0))
  lines.append(f'{radius+1e-6:.7f}f,')
 lines.append('};')
 lines.append('const bg_model_asset bg_pickup_lods[BG_M_COUNT]={')
 for name in MODEL_PATHS:
  if name=='flamethrower' and not pc_extras:name='ar'
  lod=name+'_pickup_lod' if name in data.get('pickup_lods',{}) else name
  radius=max(math.sqrt(sum(v*v for v in p)) for t in data['models'][name]['triangles'] for p in t['p'])
  lines.append(initializer(lod,radius))
 lines.append('};')
 for name in VEHICLES:
  lines.append(f'static const bg_vehicle_part parts_{name}[]={{')
  for part,segment in zip(rigs[name]['parts'],meshes[name]['segments']):
   triangles=data['models'][name]['triangles'][part['first']//3:(part['first']+part['count'])//3]
   box,_=pack_bounds.model_bounds({'triangles':triangles},1024)
   lines.append('{'+f'{part["first"]},{part["count"]},{part["kind"]},{floats(part["pivot"])},{segment[0]},{segment[1]},'+pack_bounds.initializer(box)+'},')
  lines.append('};')
 lines.append('const bg_vehicle_rig bg_vehicle_rigs[4]={')
 for name in VEHICLES:
  rig=rigs[name];lines.append('{'+f'parts_{name},{len(rig["parts"])},{floats(rig["turret_pivot"])}'+'},')
 lines.append('};')
 lines.append('const bg_bounds bg_vehicle_lod_bounds[4]={')
 for name in VEHICLES:lines.append(pack_bounds.initializer(cull_bounds[name+'_lod'])+',')
 lines.append('};')
 lines.append('const bg_bounds bg_body_cull_bounds[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  lines.append(pack_bounds.initializer(pack_bounds.animation_bounds(data['animations'][name],data['animations_lod'][name]))+',')
 lines.append('};')
 lines.append('const bg_bounds bg_attachment_cull_bounds[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  lines.append(pack_bounds.initializer(pack_bounds.bounds(p['pos'] for p in data['weapon_attachment'][name]['poses']))+',')
 lines.append('};')
 lines.append('const bg_model_asset bg_vehicle_lods[4]={')
 for name in ('warthog','ghost','scorpion','banshee'):
  lod=name+'_lod';radius=max(math.sqrt(sum(v*v for v in p)) for t in data['models'][name]['triangles'] for p in t['p'])
  lines.append(initializer(lod,radius))
 lines.append('};')
 anim_bytes=0;animation_packing={}
 for name in ANIM_NAMES:
  clip=packed_animations['spartan'][name];packed=emit_clip(lines,'anim_'+name,clip,128)
  animation_packing[name]=packed;anim_bytes+=packed['bytes']
 lines.append('const bg_anim_asset bg_animations[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  lines.append(clip_initializer('anim_'+name,data['animations'][name],animation_packing[name]))
 lines.append('};')
 lines.append('const bg_model_asset bg_spartan_lod='+initializer('spartan_lod',1.0).rstrip(',')+';')
 for name in ANIM_NAMES:
  clip=packed_animations['spartan_lod'][name];packed=emit_clip(lines,'anim_lod_'+name,clip,128)
  animation_packing['lod_'+name]=packed;anim_bytes+=packed['bytes']
 lines.append('const bg_anim_asset bg_spartan_lod_animations[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  lines.append(clip_initializer('anim_lod_'+name,data['animations_lod'][name],animation_packing['lod_'+name]))
 lines.append('};')
 for name in ANIM_NAMES:
  lines.append(f'static const bg_attachment_pose attachment_{name}[]={{')
  for pose in data['weapon_attachment'][name]['poses']:
   lines.append('{'+floats(pose['pos'])+','+floats(pose['quat'])+'},')
  lines.append('};')
 lines.append('const bg_attachment_clip bg_weapon_attachment[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  a=data['weapon_attachment'][name];lines.append(f'{{attachment_{name},{len(a["poses"])},{a["duration"]:.6f}f}},')
 lines.append('};');(out/'models_data.c').write_text('\n'.join(lines)+'\n')
 (out/'model-preview.json').write_text(json.dumps(previews))
 lines=['/* Generated from local game audio; do not commit. */','#include "asset_models.h"']
 for name in AUDIO_TAGS:
  if name=='flamethrower' and not pc_extras:continue
  if 'alias' in data['audio'][name]:continue
  samples=Path(data['audio'][name]['file']).read_bytes()
  lines.append(f'static const int8_t audio_{name}[]={{'+','.join(str(x if x<128 else x-256) for x in samples)+'};')
 lines.append('const bg_audio_asset bg_audio_assets[BG_S_COUNT]={')
 for name in AUDIO_TAGS:
  if name=='flamethrower' and not pc_extras:
   lines.append('{0,0,11025,false},');continue
  a=data['audio'][name];buffer=a.get('alias',name)
  lines.append(f'{{audio_{buffer},{a["count"]},{a["rate"]},{str(a["loop"]).lower()}}},')
 lines.append('};');(out/'audio_data.c').write_text('\n'.join(lines)+'\n')
 hud_bytes,scope_bytes=pack_hud(raw['hud'],out,source.parent/'hud-sprites')
 report={'position_scale':1024,'model_position_scales':scales,'team_mask_bytes':sum(model_sizes[n] for n in ('spartan','spartan_lod')),'models':triangle_counts,'model_bytes':sum(v*16 for v in model_sizes.values()),
 'cull_bounds_bytes':len(MODEL_PATHS)*28+len(VEHICLES)*24+len(ANIM_NAMES)*48+sum(len(r['parts'])*24 for r in rigs.values()),
 'vertices':model_sizes,'batches':{n:len(m['batches']) for n,m in meshes.items()},
 'triangle_order':{n:m['triangle_order'] for n,m in meshes.items()},'static_cache_reorder':True,'unindexed_vertices':{n:count*3 for n,count in triangle_counts.items()},
 'mesh_index_bytes':sum(len(m['indices'])*2+len(m['batches'])*8 for m in meshes.values()),'color_weld_max_channel_delta':MODEL_COLOR_TOLERANCE,'material_boundaries_preserved':True,
 'color_weld_tolerances':{name:model_color_tolerance('world',name) for name in model_sizes},
 'animation_bytes':anim_bytes,'animation_uncompressed_bytes':sum(p['uncompressed_bytes'] for p in animation_packing.values()),'audio_bytes':sum(v['count'] for k,v in data['audio'].items() if 'alias' not in v and (pc_extras or k!='flamethrower')),'hud_bytes':hud_bytes,
 'scope_bytes':scope_bytes,'pc_extras':pc_extras,'audio_events':len(data['audio'])-(not pc_extras),'audio_unique_clips':sum('alias' not in v for k,v in data['audio'].items() if pc_extras or k!='flamethrower'),
 'vehicle_rigs':rigs}
 (out/'extended-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

def pack_hud(hud,out,preview):
 from PIL import Image
 # Individual original Xbox bitmap sequences, retaining transparent pixels.
 def bitmap(name,index):
  h=hud[name];suffix=f'__{index}.png';files=h['files']
  p=next((p for p in files if p.endswith(suffix)),files[0] if len(files)==1 else None)
  if p is None:raise ValueError(f'Missing bitmap {name}:{index}')
  return Image.open(p).convert('RGBA')
 def sprite(name,seq,index=0):
  h=hud[name];s=h['sequences'][seq]
  if s['sprites']:
   sp=s['sprites'][index];im=bitmap(name,sp['bitmap']);l,t,r,b=sp['bounds']
   return im.crop((round(l*im.width),round(t*im.height),round(r*im.width),round(b*im.height)))
  return bitmap(name,s['first_bitmap']+index)
 requests=[('shield_bg','unit_backgrounds',1),('health_bg','unit_backgrounds',3),('motion_bg','weapon_backgrounds',4),
 ('shield_meter','unit_meters',1),('health_meter','unit_meters',3),('ammo_bg','weapon_backgrounds',0)]
 for name,seq in [('ar',0),('pistol',8),('plasma_pistol',3),('plasma_rifle',4),('needler',6),('shotgun',10),('sniper',0),('rocket',9)]:requests.append(('reticle_'+name,'sniper_reticles' if name=='sniper' else 'reticles',seq))
 for name,seq in [('ar',1),('pistol',0),('needler',3),('shotgun',4),('sniper',2),('rocket',5)]:requests.append(('ammo_'+name,'ammo_alphas',seq))
 images=[(name,sprite(asset,seq)) for name,asset,seq in requests]
 # cyborg_mp has no health background reference; retain a transparent API
 # entry rather than substituting a single-player shield texture.
 images[1]=('health_bg',Image.new('RGBA',(1,1),(0,0,0,0)))
 images.extend((f'digit_{i}',sprite('numbers',0,i)) for i in range(10))
 images.extend((name,sprite(asset,seq)) for name,asset,seq in
               [('grenade_frag','ammo_icons',2),('grenade_plasma','ammo_icons',3),('blip','blip',0),('radar_sweep','radar',0),('motion_fg','unit_backgrounds',7)])
 images.extend((f'reticle_{name}',sprite('reticles',seq)) for name,seq in
               [('warthog',2),('ghost',13),('scorpion',11),('banshee',1)])
 images.extend((f'zoom_{name}',sprite('sniper_reticles',1,i)) for i,name in enumerate(('2x','10x')))
 lines=['/* Generated original Xbox HUD imagery; do not commit. */','#include "asset_hud.h"'];hud_bytes=0;rects={}
 preview.mkdir(exist_ok=True)
 for name,im in images:
  im.save(preview/(name+'.png'));pixels=[]
  # Keep all visible pixels and their exact filter neighbours, but omit the
  # unused transparent rectangle. Original dimensions still drive the layout
  # and meter amounts. Digits retain their source cells for atlas extraction.
  box=im.getchannel('A').point(lambda a:255 if a>=64 else 0).getbbox()
  if name.startswith('digit_'):box=(0,0,im.width,im.height)
  elif box:
   box=(max(0,box[0]-1),max(0,box[1]-1),min(im.width,box[2]+1),min(im.height,box[3]+1))
  else:box=(0,0,1,1)
  rects[name]=box
  stored=im.crop(box)
  tint=(42,148,255) if name.startswith(('reticle','digit','shield_meter','ammo_','zoom_')) else (93,155,219)
  if name=='health_meter':tint=(71,219,147)
  for r,g,b,a in stored.get_flattened_data():
   # Halo uses white bitmap intensity and tag colors. Bake that modulation
   # so the runtime can use a single ordinary RGBA16 blit per HUD element.
   intensity=max(r,g,b)/255;r,g,b=[round(c*intensity) for c in tint]
   pixels.append(((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|(1 if a>=64 else 0))
  hud_bytes+=len(pixels)*2
  lines.append(f'static const uint16_t hud_{name}[] __attribute__((aligned(16)))={{'+','.join(hex(v) for v in pixels)+'};')
 lines.append('const bg_hud_image bg_hud_images[BG_H_COUNT]={')
 for name,im in images:
  x,y,r,b=rects[name]
  lines.append(f'{{hud_{name},{im.width},{im.height},{r-x},{b-y},{x},{y}}},')
 lines.append('};')
 # Monochrome original screen masks retain eight-bit alpha; they are not
 # ordinary RGBA16 HUD sprites. Scale the source split-screen art offline.
 scope=[]
 for name in ('scope_pistol_mask','scope_sniper_mask'):
  scope.append((name,sprite(name,0).getchannel('A').resize((64,64),Image.Resampling.BOX)))
 for i in range(5):
  im=sprite('scope_sniper_ticks',i).getchannel('A')
  scope.append((f'scope_sniper_tick_{i}',im.resize((im.width//2,im.height//2),Image.Resampling.BOX)))
 scope_bytes=0
 for name,im in scope:
  # RDP rows require an eight-byte stride; preserve the image's logical size.
  stride=(im.width+7)&~7;pixels=[]
  for y in range(im.height):pixels.extend([im.getpixel((x,y)) for x in range(im.width)]+[0]*(stride-im.width))
  scope_bytes+=len(pixels);im.save(preview/(name+'.png'))
  lines.append(f'static const uint8_t {name}[] __attribute__((aligned(16)))={{'+','.join(map(str,pixels))+'};')
 lines.append('const bg_scope_image bg_scope_images[BG_SCOPE_COUNT]={')
 for name,im in scope:lines.append(f'{{{name},{im.width},{im.height},{(im.width+7)&~7}}},')
 lines.append('};');(out/'hud_data.c').write_text('\n'.join(lines)+'\n')
 return hud_bytes+scope_bytes,scope_bytes


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path,nargs='?',default=Path('build/n64/assets/extended-reduced.json'))
 p.add_argument('--output',type=Path,default=Path('build/n64/generated'))
 p.add_argument('--hud-only',action='store_true',help='Regenerate HUD arrays from current raw metadata without repacking models/audio')
 p.add_argument('--pc-extras',action='store_true',help='Include unused PC-only flamethrower model/audio arrays')
 a=p.parse_args()
 if a.hud_only:
  raw=json.loads((a.source.parent/'extended-raw.json').read_text())
  total,scope=pack_hud(raw['hud'],a.output,a.source.parent/'hud-sprites')
  report_path=a.output/'extended-report.json';report=json.loads(report_path.read_text())
  report.update(hud_bytes=total,scope_bytes=scope);report_path.write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps({'hud_bytes':total,'scope_bytes':scope}))
 else:pack(a.source,a.output,a.pc_extras)
