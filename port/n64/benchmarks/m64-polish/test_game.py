"""Use the resident, verified vehicle banks; no source-map re-export required."""
import os,sys,subprocess,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/m64-polish/host'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'port/n64/blam'))
from prepare_collision import function
reference='031e79f57ba49ab32d507a1c97aee118cbf328d2'
old=subprocess.check_output(['git','show',reference+':port/n64/firefight_game.inc'],cwd=ROOT,text=True)
(OUT/'onslaught_reference.inc').write_text(function(old,'ff_packet_kind').replace('ff_packet_kind','onslaught_packet_kind'))
solver=ROOT/'build/vehicle-lods/after-8-4/blam-vehicle';bank=ROOT/'build/vehicle-lods/bank'
flags=['-std=c17','-O2','-g','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-fwrapv','-fsanitize=address,undefined','-Wno-multichar','-Wno-incompatible-pointer-types']
inc=[OUT,ROOT/'port/n64',ROOT/'port/n64/blam',ROOT/'build/n64/blam-core',solver,bank,ROOT/'halo64-assets/generated/pve']
flags+=['-I'+str(p) for p in inc]
for roster in (False,True):
 for test in ('test_firefight_frontend','test_frontend'):
  name=test+('-roster' if roster else '-base')
  cmd=['clang',*flags,'-DBG_FIREFIGHT',*(['-DBG_PVE_ROSTER'] if roster else []),*[str(ROOT/'port/n64'/n) for n in (test+'.c','frontend.c','menu.c','controls.c')],'-lm','-o',str(OUT/name)]
  subprocess.run(cmd,cwd=ROOT,check=True)
  with (HERE/(name+'.log')).open('w') as log:subprocess.run([str(OUT/name)],cwd=ROOT,stdout=log,check=True)
  print('PASS',name,flush=True)
sources=['map.c','terrain.c','movement.c','combat_geometry.c','blam/runtime.c','blam/core.c','replay.c','frontend_qa.c','vehicle_ai.c','blam/vehicle_physics.c']
generated=[ROOT/'halo64-assets/generated/hud_damage_data.c',ROOT/'halo64-assets/generated/maps/common_data.c',ROOT/'build/n64/generated/movement_data.c',*[bank/n for n in ('combat_data.c','interaction_defs.c','enemy_vehicle_data.c','enemy_pilot_hits.c','pve_roster.c')],*[ROOT/'halo64-assets/generated/pve'/n for n in ('pve_defs.c','pve_collision.c','pve_nav.c')],ROOT/'build/vehicle-lods/after-8-4/generated/vehicle_data.c']
flags+=['-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS','-DBG_PVE','-DBG_PVE_QA=0','-DBG_PVE_ROSTER','-DBG_ENEMY_VEHICLES']
mapdir=OUT/'maps';mapdir.mkdir(exist_ok=True)
for p in (ROOT/'halo64-assets/generated/maps').iterdir():
 if p.suffix in ('.map64','.bin','.modes64'):
  dest=mapdir/p.name
  if not dest.exists():dest.symlink_to(ROOT/'build/pve/ground/bloodgulch.map64' if p.name=='bloodgulch.map64' else p)
env={**os.environ,'BG_MAP_DIRECTORY':str(mapdir)}
for test in sys.argv[1:] or ('test_m64_game','test_firefight_fights','test_firefight','test_enemy_vehicles'):
 cmd=['clang',*flags,str(ROOT/'port/n64'/(test+'.c')),*[str(ROOT/'port/n64'/n) for n in sources],*[str(n) for n in generated],'-lm','-o',str(OUT/test)]
 subprocess.run(cmd,cwd=ROOT,check=True)
 with (HERE/(test+'.log')).open('w') as log:subprocess.run([str(OUT/test)],cwd=ROOT,env=env,stdout=log,check=True)
 print('PASS',test,flush=True)
report={'reference':reference,'sanitizers':['address','undefined'],'compiler_flags':flags,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'port/n64'/n for n in ('firefight_game.inc','firefight.h','firefight_fights.h','game.c','frontend.c','frontend.h','test_firefight_fights.c','test_firefight_frontend.c')]}}
(HERE/'host.json').write_text(json.dumps(report,indent=2)+'\n')
