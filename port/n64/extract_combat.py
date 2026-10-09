#!/usr/bin/env python3
"""Extract owned Xbox direct-weapon damage/material and range definitions."""
from pathlib import Path
import contextlib,hashlib,json
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]
PROFILES=[('AR','assault rifle','bullet'),('PISTOL','pistol','bullet'),
 ('PLASMA_PISTOL','plasma pistol','bolt'),('PLASMA_RIFLE','plasma rifle','bolt'),
 ('SHOTGUN','shotgun','pellet'),('SNIPER','sniper rifle','sniper bullet'),
 ('OVERCHARGE','plasma rifle','charged bolt'),('MELEE','pistol','melee'),('FRAG','frag grenade','explosion'),('PLASMA_GRENADE','plasma grenade','explosion'),('ROCKET','rocket launcher','explosion'),('NEEDLE','needler','detonation damage'),('SUPERCOMBINE','needler','explosion'),('STICK','plasma grenade','attached'),('FALL',None,'falling'),('DISTANCE',None,'distance'),('COLLISION',None,'vehicle_collision'),('VEHICLE_KILL',None,'vehicle_killed_unit')]
def main():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 out=ROOT/'build/n64/generated';cache=ROOT/'build/n64/assets/bloodgulch-decompressed.map'
 with (out/'combat-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(cache);es=h.tag_index.tag_index
  campaign=Halo1Map();campaign.load_map(ROOT/'build/n64/assets/a30-decompressed.map')
  def get(path,kind):return tag_values(h.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)))
  unit=get(r'characters\cyborg_mp\cyborg_mp','biped')
  collision=get(unit['obje_attrs']['collision_model'],'model_collision_geometry')
  rows=[];sources={}
  mounted_specs=[('HOG','warthog','warthog gun','bullet','bullet',0),('GHOST','ghost','ghost gun','ghost bolt','ghost bolt',0),('TANK','scorpion','scorpion cannon','shell explosion','tank shell',0),('TANK_MG','scorpion','scorpion cannon','bullet','bullet',1),('BANSHEE','banshee','banshee gun','banshee bolt','banshee bolt',0),('FUEL_ROD','banshee','banshee gun','fuel rod explosion','banshee fuel rod',1)]
  mounted=[]
  for name,weapon,leaf in PROFILES+[(n,v,l) for n,v,w,l,p,t in mounted_specs]:
   spec=next((v for v in mounted_specs if v[0]==name),None)
   es=(campaign if spec and spec[1]=='banshee' else h).tag_index.tag_index
   def get(path,kind):
    source=campaign if spec and spec[1]=='banshee' else h
    return tag_values(source.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)))
   path=(('vehicles\\' if spec else 'weapons\\')+weapon+'\\'+leaf) if weapon else 'globals\\'+leaf;tag=get(path,'damage_effect');damage=tag['damage'];mods=tag['damage_modifiers']
   flags=(bool(damage['flags']['headshot'])+2*bool(damage['flags']['multiplayer_headshot'])+4*(damage['priority']=='emp')+8*(damage['priority']=='backstab')+16*bool(damage['flags']['skips_shields'])+32*bool(damage['flags']['does_not_hurt_owner'])+64*bool(damage['flags']['detonates_explosives']))
   row=dict(minimum=damage['damage_lower_bound'],lower=damage['damage_upper_bound']['from'],upper=damage['damage_upper_bound']['to'],body=mods['cyborg_armor'],shield=mods['cyborg_energy_shield'],range_start=0,range_end=0,speed_start=0,speed_end=0,range=0,falloff=tag['radius']['from'],cutoff=tag['radius']['to'],core=damage['aoe_core_radius'],stun=damage['stun'],stun_max=damage['maximum_stun'],stun_time=damage['stun_time'],flags=flags,passthrough=damage['vehicle_passthrough_penalty'],acceleration=damage['instantaneous_acceleration'])
   if spec or name in ['AR','PISTOL','PLASMA_PISTOL','PLASMA_RIFLE','SHOTGUN','SNIPER','OVERCHARGE']:
    projectile=get(('vehicles\\'+weapon+'\\'+spec[4]) if spec else path,'projectile')['proj_attrs'];physics=projectile['physics']
    row.update(gravity=physics['air_gravity_scale'],range_start=physics['air_damage_range']['from'],range_end=physics['air_damage_range']['to'],speed_start=physics['initial_velocity'],speed_end=physics['final_velocity'],range=projectile['detonation']['maximum_range'])
    if row['range']<=0:row['range']=max(row['range_end'],100)
    sources[path+'|projectile']={k:v for k,v in projectile.items() if k!='material_responses'}
   row['vehicle_material']=[mods[k] for k in ['metal_thick','metal_thin','rubber','glass']]
   sources[path+'|damage_effect']=tag;rows.append((name,row))
   if spec:
    w=get('vehicles\\'+weapon+'\\'+spec[2],'weapon')['weap_attrs'];t=w['triggers'][spec[5]];r=t['misc_rates'];pr=t['projectile']
    tr=dict(rate_min=t['firing']['rounds_per_second']['from'],rate_max=t['firing']['rounds_per_second']['to'],rate_up=r['acceleration_rate'],rate_down=r['deceleration_rate'],error_up=r['error_acceleration_rate'],error_down=r['error_deceleration_rate'],cone_min=pr['error_angle']['from'],cone_max=pr['error_angle']['to'],cone_inner=pr['minimum_error'])
    mounted.append(dict(profile=name,trigger=tr,chamber=w['magazines'][0]['chamber_time'] if t['firing']['magazine']!='NONE' and w['magazines'] and w['magazines'][0]['flags']['every_round_must_be_chambered'] else 0))
    sources['vehicles\\'+weapon+'|trigger'+str(spec[5])]=t
  es=h.tag_index.tag_index;spec=None
  children=[]
  for vehicle,path in [('warthog',r'vehicles\warthog\warthog'),('ghost',r'vehicles\ghost\ghost_mp'),('scorpion',r'vehicles\scorpion\scorpion_mp'),('banshee',r'vehicles\banshee\banshee')]:
   source=campaign if vehicle=='banshee' else h
   v=tag_values(source.get_meta(next(i for i,e in enumerate(source.tag_index.tag_index) if e.path==path and e.class_1.enum_name=='vehicle')))
   children.append(v['unit_attrs']['rider_damage_fraction'])
  globals_=get(r'globals\globals','globals');fall=globals_['falling_damages'][0];stun=globals_['player_informations'][0]
  fall_distances=[fall['harmful_falling_distance']['from'],fall['harmful_falling_distance']['to'],fall['maximum_falling_distance']]
  stun_config=[stun[k] for k in ['stun_movement_penalty','stun_turning_penalty','stun_jumping_penalty','minimum_stun_time','maximum_stun_time']]
  grenades=[]
  for name in ['frag grenade','plasma grenade']:
   path='weapons\\'+name+'\\'+name;v=get(path,'projectile')['proj_attrs'];m=v['material_responses'][0]
   grenades.append(dict(arming=v['detonation']['arming_time'],fuse=v['detonation']['timer']['from'],gravity=v['physics']['air_gravity_scale'],parallel=m['parallel_refriction'],perpendicular=m['perpendicular_friction']))
   sources[path+'|projectile']=v
  needle=get(r'weapons\needler\needle','projectile')['proj_attrs'];sources[r'weapons\needler\needle|projectile']=needle
  from extract_combat_geometry import vehicle_meshes
  geometry_lines,geometry_report=vehicle_meshes(h,campaign,ROOT)
  from extract_player_hits import player_hits
  player_lines,player_report=player_hits(h,campaign,ROOT)
  triggers=[]
  names=['assault rifle','pistol','plasma pistol','plasma rifle','needler','shotgun','sniper rifle','rocket launcher','flamethrower']
  for name in names:
   path='weapons\\'+name+'\\'+name;weapon=get(path,'weapon')['weap_attrs'];t=weapon['triggers'][0];r=t['misc_rates'];pr=t['projectile']
   anim=get(weapon['interface']['first_person_animations'],'model_animations');refs=anim['fp_animations'][0]['animations']
   def clip(index):
    i=refs[index]['animation'] if index<len(refs) else -1
    return anim['animations'][i] if i>=0 else {'frame_count':0,'key_frame_index':0}
   melee=clip(13)
   row=dict(rate_min=t['firing']['rounds_per_second']['from'],rate_max=t['firing']['rounds_per_second']['to'],rate_up=r['acceleration_rate'],rate_down=r['deceleration_rate'],error_up=r['error_acceleration_rate'],error_down=r['error_deceleration_rate'],cone_min=pr['error_angle']['from'],cone_max=pr['error_angle']['to'],cone_inner=pr['minimum_error'],charge_time=t['charging']['charging_time'],reload_full=clip(8)['frame_count'],reload_empty=clip(7)['frame_count'],reload_enter=clip(23)['frame_count'],melee_frames=melee['frame_count'],melee_key=melee['key_frame_index'],zoom_accurate=bool(t['flags']['use_error_when_unzoomed']),automatic=not bool(t['flags']['does_not_repeat_automatically']))
   triggers.append(row);sources[path+'|trigger']=t
   sources[path+'|animation_events']={str(i):{k:clip(i)[k] for k in ['frame_count','key_frame_index']} for i in [7,8,13,23]}
 def f(v):return f'{v:.9e}f'
 lines=['/* Generated from owned Xbox tags. */','#include "combat.h"',
  'const float bg_player_acceleration_scale='+f(unit['obje_attrs']['acceleration_scale'])+';',
  'const float bg_combat_body_max='+f(collision['body']['maximum_body_vitality'])+';',
  'const float bg_combat_shield_max='+f(collision['shield']['maximum_shield_vitality'])+';',
  'const float bg_combat_leg_scale='+f(next(m for m in collision['materials'] if m['name']=='legs')['body_damage_multiplier'])+';',
  'const bg_damage_profile bg_damage_profiles[BG_D_COUNT]={']
 for name,row in rows:lines.append('[BG_D_'+name+']={'+','.join('.'+k+'='+ (str(v) if k=='flags' else '{'+','.join(map(f,v))+'}' if isinstance(v,list) else f(v)) for k,v in row.items())+'},')
 lines+=['};','const bg_trigger_profile bg_trigger_profiles[9]={']
 for row in triggers:lines.append('{'+','.join('.'+k+'='+ (str(int(v)) if isinstance(v,(int,bool)) else f(v)) for k,v in row.items())+'},')
 lines+=['};','const bg_grenade_profile bg_grenade_profiles[2]={']
 for row in grenades:lines.append('{'+','.join('.'+k+'='+f(v) for k,v in row.items())+'},')
 lines+=['};','const float bg_fall_distances[3]={'+','.join(map(f,fall_distances))+'};','const float bg_stun_config[5]={'+','.join(map(f,stun_config))+'};']
 for key,val in [('fuse',needle['detonation']['timer']['from']),('turn',needle['physics']['guided_angular_velocity']),('range',needle['detonation']['maximum_range'])]:lines.append('const float bg_needle_'+key+'='+f(val)+';')
 lines+=['const float bg_vehicle_child_damage[4]={'+','.join(map(f,children))+'};','const bg_mounted_profile bg_mounted_profiles[6]={']
 for row in mounted:lines.append('{.profile=BG_D_'+row['profile']+',.chamber='+f(row['chamber'])+',.trigger={'+','.join('.'+k+'='+f(v) for k,v in row['trigger'].items())+'}},')
 lines+=['};']
 lines+=geometry_lines+player_lines
 target=out/'combat_data.c';target.write_text('\n'.join(lines)+'\n')
 report={'player_geometry':player_report,'mounted':mounted,'child_damage':children,'geometry':geometry_report,'profiles':dict(rows),'triggers':triggers,'grenades':grenades,'fall_distances':fall_distances,'stun_config':stun_config,'collision':{k:collision[k] for k in ('body','shield','materials')},'sources':sources,'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'port/n64/extract_combat_geometry.py',ROOT/'port/n64/extract_player_hits.py',ROOT/'port/n64/pack_fp_ammo.py',ROOT/'port/n64/vehicle_parts.py',ROOT/'build/n64/assets/extended-reduced.json',ROOT/'build/n64/assets/extended-raw.json',ROOT/'build/n64/assets/a30-decompressed.map',cache,ROOT/'source/objects/damage.c',ROOT/'source/items/projectiles.c',ROOT/'source/units/units.c',ROOT/'source/items/weapons.c',ROOT/'source/units/bipeds.c']},'files':{'build/n64/frontend-files/player-hits.bin':hashlib.sha256((ROOT/'build/n64/frontend-files/player-hits.bin').read_bytes()).hexdigest()},'generated_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (out/'combat-report.json').write_text(json.dumps(report,indent=2)+'\n');print('Extracted combat, trigger, grenade, stun and fall profiles.')
if __name__=='__main__':main()
