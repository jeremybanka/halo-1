"""Add owned CE Wraith/Shade assets without modifying the accepted base banks."""
import contextlib,copy,gzip,hashlib,json,math,re,sys
from pathlib import Path
import numpy as np
from extract_enemy_vehicles import ROOT,OUT,PATHS
from pack_assets import position
from pack_mesh import indexed_mesh,emit_batches
from model_colors import load_images,bake_triangle
from pack_fp_ammo import globals_for
from vehicle_parts import split_vehicle
import pack_bounds
F=lambda x:float(x).hex()+'f'
B=lambda xs:'{'+','.join(map(str,xs))+'}'
BANK=ROOT/'build/pve-vehicles/bank'
BASE=ROOT/'halo64-assets/generated'
def append_array(text,symbol,rows,dim=None):
 m=re.search(r'\b'+symbol+r'(?:\[[^\]]*\])+\s*=\s*\{',text);assert m,symbol
 start=m.end()-1;depth=0
 for i in range(start,len(text)):
  if text[i]=='{':depth+=1
  elif text[i]=='}':
   depth-=1
   if depth==0:break
 prefix=text[:i].rstrip();prefix+=',' if prefix[-1]!='{' and prefix[-1]!=',' else ''
 text=prefix+'\n'+',\n'.join(rows)+'\n'+text[i:]
 if dim is not None:text=re.sub(r'(\b'+symbol+r'\[)[^\]]*',lambda m:m[1]+str(dim),text,count=1)
 return text

def pack_models(raw):
 lines=['#include "asset_models.h"'];rows=[];rigrows=[];bounds=[];report={}
 for name,model in raw['models'].items():
  w={**model,'triangles':[{'p':[model['vertices'][i] for i in face],'uv':[model['uv'][i] for i in face],'material':mat} for face,mat in zip(model['faces'],model['materials'])]}
  w,rig=split_vehicle(name,w,model);verts=[];colors=[];materials=[];images=load_images(w['textures'])
  for t in w['triangles']:
   verts += [[round(v*1024) for v in position(p,(0,0,0))] for p in t['p']];colors+=bake_triangle(t,images,w);materials += [t['material']]*3
  mesh=indexed_mesh(verts,colors,[0]*len(verts),segments=[(p['first'],p['count']) for p in rig['parts']],reorder_static=True,color_tolerance=8,material_keys=materials)
  sym='enemy_'+name;lines.append('static T3DVertPacked '+sym+'[] __attribute__((aligned(16)))={')
  for a,b in zip(mesh['vertices'][::2],mesh['vertices'][1::2]):
   rgba=lambda c:hex((c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255)
   lines.append(B([B(a[0]),0,B(b[0]),0,rgba(a[1]),rgba(b[1]),'{0,0}','{0,0}'])+',')
  lines.append('};');emit_batches(lines,sym,mesh)
  box,radius=pack_bounds.model_bounds(w,1024);bounds.append(pack_bounds.initializer(box))
  rows.append(B([sym,len(mesh['vertices']),F(radius),sym+'_batches',sym+'_indices',len(mesh['batches']),len(w['triangles'])]))
  lines.append('static const bg_vehicle_part '+sym+'_parts[]={')
  for part,seg in zip(rig['parts'],mesh['segments']):
   partbox,_=pack_bounds.model_bounds({'triangles':w['triangles'][part['first']//3:(part['first']+part['count'])//3]},1024)
   lines.append(B([part['first'],part['count'],part['kind'],B(map(F,part['pivot'])),*seg,pack_bounds.initializer(partbox)])+',')
  lines.append('};');rigrows.append(B([sym+'_parts',len(rig['parts']),B(map(F,rig['turret_pivot']))]))
  report[name]={'triangles':len(w['triangles']),'vertex_loads':len(mesh['vertices']),'bounds':box,'radius':radius,'rig':rig}
 text=(BASE/'models_data.c').read_text();extra='\n'.join(lines)+'\n';text=extra+text
 for symbol,r,dim in [('bg_model_assets',rows,None),('bg_pickup_lods',rows,None),('bg_model_cull_bounds',bounds,None),('bg_model_cull_radii',[F(report[n]['radius']) for n in raw['models']],None),('bg_vehicle_lods',rows,6),('bg_vehicle_rigs',rigrows,6),('bg_vehicle_lod_bounds',bounds,6)]:text=append_array(text,symbol,r,dim)
 (BANK/'models_data.c').write_text(text)
 text=(BASE/'micro_data.c').read_text()
 for sym,r,dim in [('bg_vehicle_micro_lods',['&bg_vehicle_lods[4]','&bg_vehicle_lods[5]'],6),('bg_pickup_micro_lods',['&bg_pickup_lods[BG_M_WRAITH]','&bg_pickup_lods[BG_M_SHADE]'],None),('bg_vehicle_micro_gate_bounds',bounds,6),('bg_pickup_micro_gate_bounds',bounds,None)]:text=append_array(text,sym,r,dim)
 (BANK/'micro_data.c').write_text(text)
 return report

def marker(model,name):
 transforms=globals_for(model['nodes'],model['nodes']);m=model['markers'].get(name,[{'node':0,'p':[0,0,0],'q':[0,0,0,1]}])[0]
 r,p=transforms[m['node']];q=r@np.array(m['p'])+p
 return position(q,(0,0,0))

def pack_seats(raw,h):
 from extract_extended import tag_values
 rows=[];counts=[];tracks=[];camrows=[];meta=json.loads((OUT/'metadata.json').read_text());source={}
 for name,path in PATHS.items():
  v=meta[name];s=v['unit_attrs']['seats'][0];model=raw['models'][name]
  anchor=marker(model,s['marker_name']);entry=marker(model,s['marker_name']+' enter') if s['marker_name']+' enter' in model['markers'] else anchor
  camera=marker(model,s['camera_marker_name']);flags=sum(s['flags'].values())
  # Wraith has no original human animation and hides its driver. Shade's
  # Spartan pose is appended separately; it must not alias a Warthog pose.
  enter=meta['elite_clips'][s['label']+' enter'];exit=meta['elite_clips'].get(s['label']+' exit')
  rows.append(B([B([B(map(F,anchor)),B(map(F,entry)),B(map(F,camera)),F(0),B(map(F,[0,0,0])),B(map(F,[0,0,0])),B(map(F,[0,0,0])),F(enter['duration']),F(exit['duration'] if exit else enter['duration']),flags,0])]))
  counts.append('1');source[name]={'seat':s,'anchor':anchor,'entry':entry}
  path=s['camera_tracks'][0]['track'] if s['camera_tracks'] else r'globals\default unit camera track'
  t=h.get_meta(next(i for i,e in enumerate(h.tag_index.tag_index) if e.path==path and e.class_1.enum_name=='camera_track'))
  points=[[float(x) for x in p.position] for p in t.control_points.STEPTREE];assert len(points)>=4
  sym='enemy_camera_'+name;tracks.append('static const float '+sym+'[][3]='+B(B(map(F,p)) for p in points)+';')
  camrows.append(B([B([sym,len(points),B(map(F,camera))])]))
 text=(BASE/'interaction_defs.c').read_text();text=append_array(text,'bg_seat_counts',counts,6);text=append_array(text,'bg_seat_definitions',rows,6);(BANK/'interaction_defs.c').write_text(text)
 text='\n'.join(tracks)+'\n'+(BASE/'camera_data.c').read_text();text=append_array(text,'bg_camera_tracks',camrows,6);(BANK/'camera_data.c').write_text(text)
 return source

def pack_weapons(h,text):
 from extract_extended import tag_values
 from reclaimer.enums import materials_list
 meta=json.loads((OUT/'metadata.json').read_text());rows=[];mounted=[];children=[];mods=[];report={}
 def tag(path,kind):return tag_values(h.get_meta(next(i for i,e in enumerate(h.tag_index.tag_index) if e.path==path and e.class_1.enum_name==kind),disable_tag_cleaning=True))
 for name in PATHS:
  v=meta[name];wp=v['unit_attrs']['weapons'][0]['weapon'];weapon=tag(wp,'weapon')['weap_attrs'];t=weapon['triggers'][0];projectile=tag(t['projectile']['projectile'],'projectile')['proj_attrs']
  fxpath=projectile['detonation']['effect'];fx=tag(fxpath,'effect') if fxpath else {'events':[]}
  damagepath=next((part['type'] for event in fx['events'] for part in event['parts'] if part['effect_class']=='damage_effect'),None)
  if not damagepath:damagepath=projectile['physics']['attached_detonation_damage'] or projectile['physics']['impact_damage']
  dtag=tag(damagepath,'damage_effect');d=dtag['damage'];m=dtag['damage_modifiers'];physics=projectile['physics'];f=d['flags']
  flags=int(bool(f['headshot']))+2*int(bool(f['multiplayer_headshot']))+4*(d['priority']=='emp')+8*(d['priority']=='backstab')+16*bool(f['skips_shields'])+32*bool(f['does_not_hurt_owner'])+64*bool(f['detonates_explosives'])
  row=dict(minimum=d['damage_lower_bound'],lower=d['damage_upper_bound']['from'],upper=d['damage_upper_bound']['to'],body=m['cyborg_armor'],shield=m['cyborg_energy_shield'],range_start=physics['air_damage_range']['from'],range_end=physics['air_damage_range']['to'],speed_start=physics['initial_velocity'],speed_end=physics['final_velocity'],range=projectile['detonation']['maximum_range'] or 100,falloff=dtag['radius']['from'],cutoff=dtag['radius']['to'],core=d['aoe_core_radius'],stun=d['stun'],stun_max=d['maximum_stun'],stun_time=d['stun_time'],passthrough=d['vehicle_passthrough_penalty'],acceleration=d['instantaneous_acceleration'],gravity=physics['air_gravity_scale'])
  symbol='BG_D_'+name.upper();rows.append('['+symbol+']='+B(['.'+k+'='+F(v) for k,v in row.items()]+['.flags='+str(flags),'.vehicle_material='+B(F(m[k]) for k in ['metal_thick','metal_thin','rubber','glass'])]))
  r=t['misc_rates'];pr=t['projectile'];trigger=dict(rate_min=t['firing']['rounds_per_second']['from'],rate_max=t['firing']['rounds_per_second']['to'],rate_up=r['acceleration_rate'],rate_down=r['deceleration_rate'],error_up=r['error_acceleration_rate'],error_down=r['error_deceleration_rate'],cone_min=pr['error_angle']['from'],cone_max=pr['error_angle']['to'],cone_inner=pr['minimum_error'],charge_time=t['charging']['charging_time'])
  chamber=weapon['magazines'][0]['chamber_time'] if weapon['magazines'] and weapon['magazines'][0]['flags']['every_round_must_be_chambered'] else 0
  mounted.append('{.profile='+symbol+',.chamber='+F(chamber)+',.trigger='+B('.'+k+'='+F(v) for k,v in trigger.items())+'}')
  children.append(F(v['unit_attrs']['rider_damage_fraction']));mods.append(B(F(m[k]) for k in materials_list))
  report[name]={'weapon':wp,'trigger':t,'projectile':projectile,'damage':dtag,'damage_path':damagepath}
 text=append_array(text,'bg_damage_profiles',rows);text=append_array(text,'bg_mounted_profiles',mounted,8);text=append_array(text,'bg_vehicle_child_damage',children,6)
 text+='\nconst float bg_enemy_vehicle_damage[2][33]='+B(mods)+';\n'
 return text,report

def pack_ai(raw):
 meta=json.loads((OUT/'metadata.json').read_text());pilots=json.loads((OUT/'pilots.json').read_text())
 base=json.loads((ROOT/'halo64-assets/assets/covenant-symmetry/source/squad-source.json').read_text());begin=json.loads((OUT/'details.json').read_text())['begin_angle_cosine']
 rows=['{0}']*6;seats=['{0}']*6;muzzles=['{0}']*6;muzzle_parts=[0]*6;original=json.loads((ROOT/'build/n64/assets/extended-raw.json').read_text())
 for kind,name in [(1,'ghost'),(3,'banshee'),(4,'wraith'),(5,'shade')]:
  v=meta[name];va=v['vehi_attrs'];a=va['ai'];r=pilots[name]['variant']['ranged_combat'];b=pilots[name]['variant']['burst_geometry']
  fields=dict(sideslip=a['sidestep_distance'],destination=a['destination_radius'],avoidance=a['avoidance_distance'],radius=a['pathfinding_radius'],repeat=a['charge_repeat_timeout'],abort_range=a['strafing_abort_range'],steering=a['steering_maximum'],throttle=a['throttle_maximum'],speed=va['maximum_forward_speed'],acceleration=va['speed_acceleration'],begin_angle=begin,fixed_pitch=va['fixed_gun_pitch'],health=v['collision_model']['body']['maximum_body_vitality'],range=r['maximum_firing_distance'],rate=r['rate_of_fire'],error=r['projectile_error'],leading=r['target_leading'],damage=r['weapon_damage_modifier'])
  special=pilots[name]['variant']['special_case_firing_patterns'];pattern=pilots[name]['variant']['firing_patterns']
  fields.update(new_target_time=r['new_target_firing_pattern_time'],new_target=[pattern['new_target_burst_duration'],pattern['new_target_burst_separation'],pattern['new_target_rate_of_fire'],pattern['new_target_projectile_error']],special_delay=special['special_fire_delay'],special_chance=special['special_fire_chance'],superballistic=special['super_ballistic_range'])
  fields.update(oversteer=list(a['oversteering_bounds'].values()),desired=list(r['desired_combat_range'].values()),first_delay=list(r['first_burst_delay_time'].values()),burst=list(b['burst_duration'].values()),pause=list(b['burst_separation'].values()))
  rows[kind]=B(['.'+k+'='+(B(map(F,v)) if isinstance(v,list) else F(v)) for k,v in fields.items()]+['.flags='+str(sum(va['flags'].values())),'.special_mode='+str(2 if special['special_fire_mode']=='secondary_trigger' else 0)])
  model=raw['models'].get(name) or original['models'][name];s=v['unit_attrs']['seats'][-1] if name=='ghost' else v['unit_attrs']['seats'][0];anchor=marker(model,s['marker_name']);entry=marker(model,s['marker_name']+' enter') if s['marker_name']+' enter' in model['markers'] else anchor;camera=marker(model,s['camera_marker_name']);prefix=s['label'].replace(' elite','')
  idle=meta['elite_clips'].get(prefix+' unarmed idle');enter=meta['elite_clips'][prefix+' enter'];exit=meta['elite_clips'].get(prefix+' exit')
  root=np.array(base['models']['elite']['nodes'][0]['p']);enter_start=position(np.array(enter['frames'][0][0]['p'])-root,(0,0,0))
  exit_offset=position(np.array(exit['frames'][-1][0]['p'])-root,(0,0,0)) if exit else [0,0,0]
  velocity=position((np.array(exit['frames'][-1][0]['p'])-np.array(exit['frames'][-2][0]['p']))*30,(0,0,0)) if exit else [0,0,0]
  seats[kind]=B([B(map(F,anchor)),B(map(F,entry)),B(map(F,camera)),F(0),B(map(F,exit_offset)),B(map(F,velocity)),B(map(F,enter_start)),F(enter['duration']),F(exit['duration'] if exit else enter['duration']),sum(s['flags'].values()),0])
  mu=marker(model,'primary trigger');muzzles[kind]=B(map(F,mu))
  if name in PATHS:
   from vehicle_parts import _layout
   muzzle_parts[kind]=_layout(name,model)[3](model['markers']['primary trigger'][0]['node'])
 text='#include "vehicle_ai.h"\n#include "interaction.h"\nconst bg_vehicle_ai_definition bg_vehicle_ai_defs[BG_VEHICLE_COUNT]='+B('['+str(i)+']='+r for i,r in enumerate(rows) if r!='{0}')+';\nconst bg_seat_definition bg_enemy_vehicle_seats[BG_VEHICLE_COUNT]='+B('['+str(i)+']='+r for i,r in enumerate(seats) if r!='{0}')+';\nconst float bg_vehicle_muzzles[BG_VEHICLE_COUNT][3]='+B(muzzles)+';\n'
 text+='const unsigned bg_vehicle_muzzle_parts[BG_VEHICLE_COUNT]='+B(muzzle_parts)+';\n'
 (BANK/'enemy_vehicle_data.c').write_text(text)

def main():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from extract_combat_geometry import vehicle_meshes
 BANK.mkdir(parents=True,exist_ok=True);raw=json.loads((OUT/'extended-raw.json').read_text())
 report={'models':pack_models(raw)};pack_ai(raw)
 with (BANK/'pack.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets/b40-decompressed.map')
  report['seats']=pack_seats(raw,h)
  lines,report['collision']=vehicle_meshes(h,h,ROOT,raw=raw,names=list(PATHS),paths=PATHS,hatches=False)
  text='\n'.join(lines);m=re.search(r'const bg_hit_mesh bg_vehicle_hit_meshes\[2\]=\{(.*?)\n\};',text,re.S);assert m
  geometry=text[:m.start()];rows=m[1].strip().rstrip(',')
  text=append_array(geometry+'\n'+(BASE/'combat_data.c').read_text(),'bg_vehicle_hit_meshes',[rows],6)
  text,report['weapons']=pack_weapons(h,text)
  (BANK/'combat_data.c').write_text(text)
 from pack_vehicle_details import pack as pack_details
 pack_details()
 from pack_vehicle_hud import pack as pack_hud
 pack_hud()
 (BANK/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['collision'],indent=2))
if __name__=='__main__':main()
