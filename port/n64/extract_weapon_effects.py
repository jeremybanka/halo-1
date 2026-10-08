#!/usr/bin/env python3
"""Pack owned Xbox firing sprites, effect values and animated muzzle markers.

Billboard effects intentionally collapse the original multiparticle emitters.
No extracted game data is checked in. Run after the first-person asset pipeline.
"""
import contextlib, hashlib, json
from pathlib import Path
from PIL import Image
from extract_extended import MODEL_PATHS
from pack_fp_ammo import globals_for, transform_point, CLIPS
from pack_assets import position

ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets'; OUT=ROOT/'build/n64/generated'
NAMES=list(MODEL_PATHS)[:8]
PARTICLES=['flash h ar','flash h pistol muzzle','flash c generic','flash c generic',
           'flash c generic','flash h generic','flash h sniper muzzle break','flash h ar']

def extract():
 textures=[];texture_keys={};report={'weapons':{},'textures':[]};poses=[];offsets=[];world=[];defs=[]
 raw=json.loads((A/'firstperson-raw.json').read_text())
 reduced=json.loads((A/'firstperson-reduced.json').read_text())
 models=json.loads((A/'extended-raw.json').read_text())['models']
 directory=A/'weapon-effects';directory.mkdir(exist_ok=True)
 with (directory/'extract.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
  from reclaimer.meta.wrappers.halo1_map import Halo1Map
  from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
  h=Halo1Map();h.load_map(A/'bloodgulch-decompressed.map');entries=h.tag_index.tag_index
  def tag(path,kind):
   ix=next(i for i,e in enumerate(entries) if e.path==path and e.class_1.enum_name==kind)
   return ix,h.get_meta(ix)
  def texture(ref,sequence=0,sprite_index=0,additive=True,bitmap_override=None):
   key=(ref.id&65535,sequence,sprite_index,additive,bitmap_override)
   if key in texture_keys:return texture_keys[key]
   ix=ref.id&65535;m=h.get_meta(ix)
   seq=m.sequences.STEPTREE[min(sequence,len(m.sequences.STEPTREE)-1)] if m.sequences.STEPTREE else None
   sprite=seq.sprites.STEPTREE[min(sprite_index,len(seq.sprites.STEPTREE)-1)] if seq and seq.sprites.STEPTREE else None
   bitmap=sprite.bitmap_index if sprite else (seq.first_bitmap_index if seq else 0)
   crop=[sprite.left_side,sprite.top_side,sprite.right_side,sprite.bottom_side] if sprite else None
   if bitmap_override is not None:bitmap=bitmap_override;crop=None
   h.meta_to_tag_data(m,'bitm',entries[ix]);prefix='bitmap-'+str(ix)
   extract_bitmaps(m,prefix,out_dir=directory,bitmap_ext='png',halo_map=h)
   files=sorted(directory.glob(prefix+'*.png'));im=Image.open(files[bitmap]).convert('RGBA')
   if crop:im=im.crop(tuple(round(v*(im.width if n%2==0 else im.height)) for n,v in enumerate(crop)))
   im=im.resize((16,16),Image.Resampling.BOX)
   if additive:
    # Bounded-alpha approximation preserves the source colored energy silhouette
    # while avoiding the N64 blender's overflowing additive mode.
    im.putdata([(round(r*255/peak),round(g*255/peak),round(b*255/peak),round(a*peak/255)) if (peak:=max(r,g,b)) else (0,0,0,0) for r,g,b,a in im.getdata()])
   index=len(textures);texture_keys[key]=index;textures.append(im)
   im.save(directory/f'packed-{index}.png')
   report['textures'].append({'tag':ix,'path':entries[ix].path,'sequence':sequence,'sprite':sprite_index,'bitmap_index':bitmap,'crop':crop,'additive_approximation':additive})
   return index
  for name,particle_name in zip(NAMES,PARTICLES):
   wi,weapon=tag(MODEL_PATHS[name],'weapon');effect=weapon.weap_attrs.triggers.STEPTREE[0].firing_effects.STEPTREE[0].firing_effect
   em=h.get_meta(effect.id);candidates=[p for ev in em.events.STEPTREE for p in ev.particles.STEPTREE if p.particle_type.filepath.endswith('\\'+particle_name)]
   candidates.sort(key=lambda p:p.create_in_camera.enum_name!='first_person_only');p=candidates[0];pm=h.get_meta(p.particle_type.id)
   tex=texture(pm.bitmap,pm.rendering.first_sequence_index)
   tint=[round(float(getattr(p.tint_lower_bound,c))*255) for c in 'rgb'];radius=sum(p.radius)/2;life=max(1/30,min(.15,sum(pm.lifespan)/2))
   defs.append([radius,life,tex,*tint]);marker_names=['primary trigger','secondary trigger' if name=='plasma_pistol' else 'primary trigger1' if name=='plasma_rifle' else 'primary trigger']
   fp_path=MODEL_PATHS[name].rsplit('\\',1)[0]+r'\fp\fp';mi,model=tag(fp_path,'model')
   markers={m.name:m.marker_instances.STEPTREE[0] for m in model.markers.STEPTREE}
   src=raw['weapons'][name];lookup={n['name']:i for i,n in enumerate(src['nodes'])}
   chosen=[markers[n] for n in marker_names];weapon_offsets=[]
   for clip in CLIPS:
    weapon_offsets.append(len(poses));frames=src['clips'][clip]['frames'];count=len(reduced['weapons'][name]['clips'][clip]['frames'])
    for fi in range(count):
     states=frames[round(fi*(len(frames)-1)/max(1,count-1))];pose=globals_for(states,src['nodes']);points=[]
     for marker in chosen:
      node=lookup[src['gun']['nodes'][marker.node_index]['name']]
      point=transform_point(pose[node],list(marker.translation))
      points.append([round(v*4096) for v in position(point,(0,0,0))])
     poses.append(points)
   offsets.append(weapon_offsets)
   wm=models[name];bind=globals_for(wm['nodes'],wm['nodes']);world_points=[]
   for marker_name in marker_names:
    marker=wm['markers'][marker_name][0]
    world_points.append(position(transform_point(bind[marker['node']],marker['p']),(0,0,0)))
   world.append(world_points)
   report['weapons'][name]={'weapon_tag':wi,'effect':effect.filepath,'particle':p.particle_type.filepath,'bitmap':pm.bitmap.filepath,'life':life,'source_radius':radius,'color':tint,'markers':marker_names,'firstperson_model':mi,'marker_offsets':weapon_offsets}
  _,charge=tag(r'weapons\plasma rifle\overcharge','lens_flare');reflection=charge.reflections.STEPTREE[0]
  charge_texture=texture(charge.bitmaps.bitmap,bitmap_override=reflection.bitmap_index)
  glow_texture=texture(charge.bitmaps.bitmap,bitmap_override=0)
  _,contrail=tag(r'weapons\sniper rifle\sniper','contrail');trail_texture=texture(contrail.rendering.bitmap,0,0,False)
  report['charge']={'source':r'weapons\plasma rifle\overcharge','texture':charge_texture,'glow_texture':glow_texture,'radius':list(reflection.radius),'attachment':'secondary trigger flare1','note':'Sustained green candle uses the original corona sprite at the secondary muzzle with a tapered rising copy.'}
  report['trail']={'source':r'weapons\sniper rifle\sniper','texture':trail_texture,'states':[{'width':s.width,'duration':list(s.state_duration),'transition':list(s.state_transition_duration),'color':list(s.color_lower_bound)} for s in contrail.point_states.STEPTREE]}
 def array(v):return '{'+','.join(array(x) if isinstance(x,list) else str(x) for x in v)+'}'
 lines=['/* Generated owned Xbox effects; do not commit. */','#include "weapon_effects.h"',f'const unsigned bg_fx_texture_count={len(textures)};',f'const unsigned bg_fx_charge_texture={charge_texture},bg_fx_glow_texture={glow_texture},bg_fx_trail_texture={trail_texture};', 'const uint32_t bg_fx_textures[][256] __attribute__((aligned(8)))={']
 for im in textures:lines.append('{'+','.join(f'0x{r:02x}{g:02x}{b:02x}{a:02x}' for r,g,b,a in im.getdata())+'},')
 lines+=['};','const bg_fx_definition bg_fx_definitions[9]={']
 for radius,life,tex,r,g,b in defs+[defs[0]]:lines.append(f'{{{radius:.7f}f,{life:.7f}f,{tex},{{{r},{g},{b}}}}},')
 lines+=['};','const float bg_fx_world_markers[9][2][3]='+array(world+[world[0]])+';','const uint16_t bg_fx_marker_offsets[9][4]='+array(offsets+[offsets[0]])+';','const int16_t bg_fx_marker_poses[][2][3]='+array(poses)+';']
 assert all(-32768<=v<=32767 for frame in poses for point in frame for v in point)
 target=OUT/'weapon_effects_data.c';target.write_text('\n'.join(lines)+'\n')
 inputs=[Path(__file__),A/'bloodgulch-decompressed.map',A/'firstperson-raw.json',A/'firstperson-reduced.json',A/'extended-raw.json',OUT/'firstperson_data.c']
 report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs};report['generated_sha256']=hashlib.sha256(target.read_bytes()).hexdigest();report['texture_bytes']=len(textures)*1024;report['marker_bytes']=len(poses)*12
 (OUT/'weapon-effects-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(f'Packed {len(textures)} source sprites ({len(textures)*1024} bytes), {len(poses)} animated muzzle marker frames.')
if __name__=='__main__':extract()
