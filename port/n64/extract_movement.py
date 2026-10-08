#!/usr/bin/env python3
"""Extract Xbox retail movement, controller and weapon aim-assist parameters."""
import contextlib,hashlib,json,re
from pathlib import Path
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'build/n64/generated';A=ROOT/'build/n64/assets'

def main():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 with (G/'movement-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(A/'bloodgulch-decompressed.map');es=h.tag_index.tag_index
  def get(path):return h.get_meta(next(i for i,e in enumerate(es) if e.path==path))
  glob=get(r'globals\globals');biped=get(r'characters\cyborg_mp\cyborg_mp').bipd_attrs
  info=glob.player_informations.STEPTREE[0];control=glob.player_controls.STEPTREE[0];cam=biped.camera_collision_and_autoaim
  gravity=float(re.search(r'real global_gravity = ([0-9.e-]+)f;', (ROOT/'source/physics/physics.c').read_text())[1])
  vals=dict(run=[info.run_forward,info.run_backward,info.run_sideways],sneak=[info.sneak_forward,info.sneak_backward,info.sneak_sideways],accel=[info.run_acceleration*30,info.sneak_acceleration*30,info.airborne_acceleration*30],jump=biped.jumping_and_landing.jump_velocity*30,gravity=gravity*900,crouch_rate=1/cam.crouch_transition_time,camera=[cam.standing_camera_height,cam.crouching_camera_height],curve=[x.scale for x in control.look_functions.STEPTREE],yaw_rate=control.look_default_yaw_rate,pitch_rate=control.look_default_pitch_rate,peg_time=control.look_acceleration_time,peg_scale=control.look_acceleration_scale,peg_threshold=control.look_peg_threshold,friction=control.magnetism_friction,adhesion=control.magnetism_adhesion,aim_width=cam.autoaim_width,height=[cam.standing_collision_height,cam.crouching_collision_height])
  weapons=[]
  for name in ('assault rifle','pistol','plasma pistol','plasma rifle','needler','shotgun','sniper rifle','rocket launcher'):
   w=get('weapons\\'+name+'\\'+name).weap_attrs;a=w.aiming
   weapons.append([a.autoaim_angle,a.autoaim_range,a.magnetism_angle,a.magnetism_range,a.deviation_angle,int(bool(w.flags.aim_assists_only_when_zoomed))])
 def c(x):
  if isinstance(x,list):return '{'+','.join(c(v) for v in x)+'}'
  return f'{float(x):.9e}f'
 lines=['/* Generated from owned Xbox tags. */','#include "movement.h"','const bg_movement_config bg_movement={']
 lines += ['.'+k+'='+c(v)+',' for k,v in vals.items()]
 lines+=['};','const bg_aim_config bg_aim_configs[BG_WEAPON_COUNT]={']+[c(row[:-1])[:-1]+','+str(row[-1])+'},' for row in weapons]+['{0,0,0,0,0,false},','};']
 out=G/'movement_data.c';out.write_text('\n'.join(lines)+'\n')
 report={'movement':vals,'weapon_aim':weapons,'units':'world units/second; acceleration in world units/second squared; aim angles radians; look rates degrees/second', 'sources':{'globals':tag_values(glob.player_controls),'biped':tag_values(biped.camera_collision_and_autoaim)},'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),A/'bloodgulch-decompressed.map',ROOT/'source/physics/physics.c']},'generated_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
 (G/'movement-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(vals,indent=2))
if __name__=='__main__':main()
