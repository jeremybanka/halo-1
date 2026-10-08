#!/usr/bin/env python3
"""Extract owned Xbox direct-weapon damage/material and range definitions."""
from pathlib import Path
import contextlib,hashlib,json
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]
PROFILES=[('AR','assault rifle','bullet'),('PISTOL','pistol','bullet'),
 ('PLASMA_PISTOL','plasma pistol','bolt'),('PLASMA_RIFLE','plasma rifle','bolt'),
 ('SHOTGUN','shotgun','pellet'),('SNIPER','sniper rifle','sniper bullet'),
 ('OVERCHARGE','plasma rifle','charged bolt'),('MELEE','pistol','melee')]
def main():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 out=ROOT/'build/n64/generated';cache=ROOT/'build/n64/assets/bloodgulch-decompressed.map'
 with (out/'combat-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(cache);es=h.tag_index.tag_index
  def get(path,kind):return tag_values(h.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)))
  unit=get(r'characters\cyborg_mp\cyborg_mp','biped')
  collision=get(unit['obje_attrs']['collision_model'],'model_collision_geometry')
  rows=[];sources={}
  for name,weapon,leaf in PROFILES:
   path='weapons\\'+weapon+'\\'+leaf;tag=get(path,'damage_effect');damage=tag['damage'];mods=tag['damage_modifiers']
   flags=(bool(damage['flags']['headshot'])+2*bool(damage['flags']['multiplayer_headshot'])+4*(damage['priority']=='emp')+8*(damage['priority']=='backstab'))
   row=dict(minimum=damage['damage_lower_bound'],lower=damage['damage_upper_bound']['from'],upper=damage['damage_upper_bound']['to'],body=mods['cyborg_armor'],shield=mods['cyborg_energy_shield'],range_start=0,range_end=0,speed_start=0,speed_end=0,range=0,flags=flags)
   if leaf!='melee':
    projectile=get(path,'projectile')['proj_attrs'];physics=projectile['physics']
    row.update(range_start=physics['air_damage_range']['from'],range_end=physics['air_damage_range']['to'],speed_start=physics['initial_velocity'],speed_end=physics['final_velocity'],range=projectile['detonation']['maximum_range'])
    sources[path+'|projectile']={k:v for k,v in projectile.items() if k!='material_responses'}
   sources[path+'|damage_effect']=tag;rows.append((name,row))
 def f(v):return f'{v:.9e}f'
 lines=['/* Generated from owned Xbox tags. */','#include "combat.h"',
  'const float bg_combat_body_max='+f(collision['body']['maximum_body_vitality'])+';',
  'const float bg_combat_shield_max='+f(collision['shield']['maximum_shield_vitality'])+';',
  'const float bg_combat_leg_scale='+f(next(m for m in collision['materials'] if m['name']=='legs')['body_damage_multiplier'])+';',
  'const bg_damage_profile bg_damage_profiles[BG_D_COUNT]={']
 for name,row in rows:lines.append('[BG_D_'+name+']={'+','.join('.'+k+'='+ (str(v) if k=='flags' else f(v)) for k,v in row.items())+'},')
 lines+=['};'];target=out/'combat_data.c';target.write_text('\n'.join(lines)+'\n')
 report={'profiles':dict(rows),'collision':{k:collision[k] for k in ('body','shield','materials')},'sources':sources,'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),cache,ROOT/'source/objects/damage.c',ROOT/'source/items/projectiles.c',ROOT/'source/units/units.c']},'generated_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (out/'combat-report.json').write_text(json.dumps(report,indent=2)+'\n');print('Extracted eight direct-weapon damage profiles.')
if __name__=='__main__':main()
