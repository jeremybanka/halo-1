"""Actual-map packet oracles, frozen pre-change firing oracle and full tick traces."""
import sys,subprocess,hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/vehicle-simulation/host'
OUT.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(ROOT/'port/n64/blam'))
from prepare_collision import function
reference='031e79f57ba49ab32d507a1c97aee118cbf328d2'
def old(n):return subprocess.check_output(['git','show',reference+':port/n64/'+n],cwd=ROOT,text=True)
arc=old('pve_actions.inc');vehicles=old('pve_vehicles.inc')
oracle=function(arc,'pve_ballistic_arc')+function(vehicles,'pve_vehicle_clearance')+function(vehicles,'pve_vehicle_inputs')
for a,b in [('pve_ballistic_arc','oracle_arc'),('pve_vehicle_clearance','oracle_clearance'),('pve_vehicle_inputs','oracle_inputs')]:oracle=oracle.replace(a,b)
(OUT/'query_reference.inc').write_text(oracle)
base=OUT/'reference';base.mkdir(exist_ok=True)
for n in ('game.c','pve_game.inc','pve_actions.inc','pve_vehicles.inc'):(base/n).write_text(old(n))
(base/'vehicle_physics.c').write_text(old('blam/vehicle_physics.c'))
solver=ROOT/'build/vehicle-lods/after-8-4/blam-vehicle';bank=ROOT/'build/vehicle-lods/bank'
flags=['-std=c17','-O2','-g','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-fwrapv','-fsanitize=address,undefined','-Wno-multichar','-Wno-incompatible-pointer-types','-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS','-DBG_PVE','-DBG_PVE_QA=0','-DBG_PVE_ROSTER','-DBG_ENEMY_VEHICLES']
if '--target-math' in sys.argv:flags+=['-ffast-math','-ftrapping-math','-fno-associative-math','-ffp-contract=off','-Wno-overriding-option']
sources=['map.c','terrain.c','movement.c','combat_geometry.c','blam/runtime.c','blam/core.c','replay.c','frontend_qa.c','vehicle_ai.c']
generated=[ROOT/'halo64-assets/generated/maps/common_data.c',*[ROOT/'build/n64/generated'/n for n in ('movement_data.c',)],*[bank/n for n in ('combat_data.c','interaction_defs.c','enemy_vehicle_data.c','enemy_pilot_hits.c','pve_roster.c')],*[ROOT/'halo64-assets/generated/pve'/n for n in ('pve_defs.c','pve_collision.c','pve_nav.c')],ROOT/'build/vehicle-lods/after-8-4/generated/vehicle_data.c']
mapdir=OUT/'maps';mapdir.mkdir(exist_ok=True)
for p in (ROOT/'halo64-assets/generated/maps').iterdir():
 if p.suffix in ('.map64','.bin'):
  dest=mapdir/p.name
  if not dest.exists():dest.symlink_to(ROOT/'build/pve/ground/bloodgulch.map64' if p.name=='bloodgulch.map64' else p)
env={**os.environ,'BG_MAP_DIRECTORY':str(mapdir)}
for name in ('candidate','reference'):
 inc=[base] if name=='reference' else []
 inc += [OUT,ROOT/'port/n64',ROOT/'port/n64/blam',ROOT/'build/n64/blam-core',solver,bank,ROOT/'halo64-assets/generated/pve']
 physics=base/'vehicle_physics.c' if name=='reference' else ROOT/'port/n64/blam/vehicle_physics.c'
 cmd=['clang',*flags,*(['-DQUERY_REFERENCE'] if name=='reference' else []),*['-I'+str(n) for n in inc],str(HERE/'test.c'),str(physics),*[str(ROOT/'port/n64'/n) for n in sources],*[str(n) for n in generated],'-lm','-o',str(OUT/(name+'-test'))]
 subprocess.run(cmd,cwd=ROOT,check=True)
 if name=='candidate':
  with (OUT/'queries.log').open('w') as f:subprocess.run([str(OUT/(name+'-test')),'queries'],cwd=ROOT,env=env,stdout=f,check=True)
 with (OUT/(name+'.log')).open('w') as f:subprocess.run([str(OUT/(name+'-test')),'trace'],cwd=ROOT,env=env,stdout=f,check=True)
if '--regressions' in sys.argv:
 inc=[OUT,ROOT/'port/n64',ROOT/'port/n64/blam',ROOT/'build/n64/blam-core',solver,bank,ROOT/'halo64-assets/generated/pve']
 cmd=['clang',*flags,*['-I'+str(n) for n in inc],str(ROOT/'port/n64/test_enemy_vehicles.c'),str(ROOT/'port/n64/blam/vehicle_physics.c'),*[str(ROOT/'port/n64'/n) for n in sources],*[str(n) for n in generated],'-lm','-o',str(OUT/'regressions')]
 subprocess.run(cmd,cwd=ROOT,check=True)
 with (OUT/'regressions.log').open('w') as f:subprocess.run([str(OUT/'regressions')],cwd=ROOT,env=env,stdout=f,check=True)
a=(OUT/'candidate.log').read_bytes();b=(OUT/'reference.log').read_bytes();assert a==b,'Per-tick gameplay divergence; inspect trace logs'
result={'reference':reference,'target_math':'--target-math' in sys.argv,'ticks':9600,'trace_sha256':hashlib.sha256(a).hexdigest(),'queries':(OUT/'queries.log').read_text(),'exact':True,'candidate_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'port/n64/pve_actions.inc',ROOT/'port/n64/pve_vehicles.inc',ROOT/'port/n64/blam/vehicle_physics.c',HERE/'test.c')},'compiler_flags':flags}
(HERE/('host-target.json' if '--target-math' in sys.argv else 'host-strict.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
