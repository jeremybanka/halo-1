#!/usr/bin/env python3
"""Pack locally extracted Xbox models, baked animation, audio and HUD for libdragon."""
import argparse,json,math
from pathlib import Path
from pack_assets import position, floats
from extract_extended import MODEL_PATHS, AUDIO_TAGS, ANIM_NAMES
from vehicle_parts import VEHICLES, split_vehicle
from pack_animation import emit_clip, clip_initializer
from model_colors import load_images, bake_triangle, bake_team_mask


def pack(source,out,pc_extras=False):
 data=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True)
 raw=json.loads((source.parent/'extended-raw.json').read_text());rigs={}
 for name in VEHICLES:
  data['models'][name],rigs[name]=split_vehicle(name,data['models'][name],raw['models'][name])
 def rgba(rgb):return (rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
 def xyz(v):return '{'+','.join(map(str,v))+'}'
 lines=['/* Generated from local game data; do not commit. */','#include "asset_models.h"']
 model_sizes={};previews={};scales={}
 all_models=list(data['models'].items())+[(name+'_lod',model) for name,model in data.get('vehicle_lods',{}).items()]+[('spartan_lod',data['spartan_lod'])]
 for name,model in all_models:
  if name=='flamethrower' and not pc_extras:continue
  scale=128 if name.startswith('spartan') else 1024;scales[name]=scale
  verts=[];team_mask=[]
  images=load_images(model['textures'])
  masks=load_images(model.get('team_masks',[]));channels=model.get('team_mask_channels',[])
  for tri in model['triangles']:
   points=[position(p,(0,0,0)) for p in tri['p']]
   colors=bake_triangle(tri,images,model)
   team_mask.extend(bake_team_mask(tri,masks,channels))
   for p,rgb in zip(points,colors):
    if name=='overshield':rgb=[238,92,52]
    if name=='camouflage':rgb=[57,151,234]
    verts.append(([round(x*scale) for x in p],rgb))
  previews[name]={'positions':[[c/scale for c in p] for p,rgb in verts],
                  'colors':[rgb for p,rgb in verts],'triangle_count':len(model['triangles']),
                  'team_mask':[m/255 for m in team_mask]}
  if name in ('spartan','spartan_lod'):
   lines.append(f'const uint8_t bg_{name}_team_mask[]={{'+','.join(map(str,team_mask))+'};')
  count=len(verts);model_sizes[name]=count
  if count%2:verts.append(verts[-1])
  lines.append(f'static T3DVertPacked model_{name}[] __attribute__((aligned(16)))={{')
  for i in range(0,len(verts),2):
   a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{{0,0}},{{0,0}}'+'},')
  lines.append('};')
 lines.append('const bg_model_asset bg_model_assets[BG_M_COUNT]={')
 for name in MODEL_PATHS:
  if name=='flamethrower' and not pc_extras:name='ar'
  radius=max(math.sqrt(sum(v*v for v in p)) for t in data['models'][name]['triangles'] for p in t['p'])
  lines.append(f'{{model_{name},{model_sizes[name]},{radius:.6f}f}},')
 lines.append('};')
 for name in VEHICLES:
  lines.append(f'static const bg_vehicle_part parts_{name}[]={{')
  for part in rigs[name]['parts']:
   lines.append('{'+f'{part["first"]},{part["count"]},{part["kind"]},{floats(part["pivot"])}'+'},')
  lines.append('};')
 lines.append('const bg_vehicle_rig bg_vehicle_rigs[4]={')
 for name in VEHICLES:
  rig=rigs[name];lines.append('{'+f'parts_{name},{len(rig["parts"])},{floats(rig["turret_pivot"])}'+'},')
 lines.append('};')
 lines.append('const bg_model_asset bg_vehicle_lods[4]={')
 for name in ('warthog','ghost','scorpion','banshee'):
  lod=name+'_lod';radius=max(math.sqrt(sum(v*v for v in p)) for t in data['models'][name]['triangles'] for p in t['p'])
  lines.append(f'{{model_{lod},{model_sizes[lod]},{radius:.6f}f}},')
 lines.append('};')
 anim_bytes=0;animation_packing={}
 for name in ANIM_NAMES:
  clip=data['animations'][name];packed=emit_clip(lines,'anim_'+name,clip,128)
  animation_packing[name]=packed;anim_bytes+=packed['bytes']
 lines.append('const bg_anim_asset bg_animations[BG_A_COUNT]={')
 for name in ANIM_NAMES:
  lines.append(clip_initializer('anim_'+name,data['animations'][name],animation_packing[name]))
 lines.append('};')
 lines.append(f'const bg_model_asset bg_spartan_lod={{model_spartan_lod,{model_sizes["spartan_lod"]},1.0f}};')
 for name in ANIM_NAMES:
  clip=data['animations_lod'][name];packed=emit_clip(lines,'anim_lod_'+name,clip,128)
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
 report={'position_scale':1024,'model_position_scales':scales,'team_mask_bytes':sum(len(previews[n]['team_mask']) for n in ('spartan','spartan_lod')),'models':{k:v//3 for k,v in model_sizes.items()},'model_bytes':sum((v+1)//2*32 for v in model_sizes.values()),
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
 lines=['/* Generated original Xbox HUD imagery; do not commit. */','#include "asset_hud.h"'];hud_bytes=0
 preview.mkdir(exist_ok=True)
 for name,im in images:
  im.save(preview/(name+'.png'));pixels=[]
  tint=(42,148,255) if name.startswith(('reticle','digit','shield_meter','ammo_','zoom_')) else (93,155,219)
  if name=='health_meter':tint=(71,219,147)
  for r,g,b,a in im.get_flattened_data():
   # Halo uses white bitmap intensity and tag colors. Bake that modulation
   # so the runtime can use a single ordinary RGBA16 blit per HUD element.
   intensity=max(r,g,b)/255;r,g,b=[round(c*intensity) for c in tint]
   pixels.append(((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|(1 if a>=64 else 0))
  hud_bytes+=len(pixels)*2
  lines.append(f'static const uint16_t hud_{name}[] __attribute__((aligned(16)))={{'+','.join(hex(v) for v in pixels)+'};')
 lines.append('const bg_hud_image bg_hud_images[BG_H_COUNT]={')
 for name,im in images:lines.append(f'{{hud_{name},{im.width},{im.height}}},')
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
