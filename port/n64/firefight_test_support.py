"""Real map/game sanitizer harness using versioned private inputs, without re-export."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


class FirefightHarness:
    def __init__(self,output):
        self.output=Path(output).resolve();self.output.mkdir(parents=True,exist_ok=True)
        self.bank=ROOT/'halo64-assets';self.base=self.bank/'generated'
        self.enemy=self.bank/'assets/enemy-vehicles/bank';self.records=[]
        self.nav=self.output/'nav';self.nav.mkdir()
        for script,name in [('prepare_core.py','core'),('prepare_vehicle.py','solver')]:
            subprocess.run([sys.executable,str(ROOT/'port/n64/blam'/script),'--output',str(self.output/name)],cwd=ROOT,check=True)
        from prepare_gungnir_strategy import run
        run(self.output/'gungnir-source')
        checkpoint=self.bank/'assets/firefight-checkpoint'
        inputs=json.loads((checkpoint/'compiler-inputs.json').read_text())['play']['sources']
        digest=next(sha for name,sha in inputs.items() if name.endswith('/generated/vehicle_data.c'))
        physics=gzip.decompress((checkpoint/'inputs'/(digest+'.gz')).read_bytes())
        assert hashlib.sha256(physics).hexdigest()==digest
        (self.output/'enemy_vehicle_physics.c').write_bytes(physics)
        sys.path.insert(0,str(ROOT/'port/n64/blam'))
        from prepare_collision import function
        reference=subprocess.check_output(['git','show','031e79f57ba49ab32d507a1c97aee118cbf328d2:port/n64/firefight_game.inc'],cwd=ROOT,text=True)
        (self.output/'onslaught_reference.inc').write_text(function(reference,'ff_packet_kind').replace('ff_packet_kind','onslaught_packet_kind'))
        self.sandbox=self.output/'sandbox'
        (self.sandbox/'build/n64').mkdir(parents=True);(self.sandbox/'build/pve-vehicles').mkdir(parents=True)
        (self.sandbox/'build/n64/frontend-files').symlink_to(self.bank/'frontend-files',target_is_directory=True)
        (self.sandbox/'build/pve-vehicles/bank').symlink_to(self.enemy,target_is_directory=True)
        self.environment={**os.environ,'BG_MAP_DIRECTORY':str(self.base/'maps'),
            'BG_AUTONAV_DIRECTORY':str(self.base/'gungnir'),'BG_FIREFIGHT_NAV_DIRECTORY':str(self.nav)}

    def compile(self,test,expanded=False,embedded=True):
        data=self.enemy if expanded else self.base
        includes=[self.output,ROOT/'port/n64',ROOT/'port/n64/blam',self.output/'core',
            self.output/'solver',self.output/'gungnir-source',data,self.base/'pve']
        flags=['-std=c17','-O1','-g','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing',
            '-fwrapv','-fsanitize=address,undefined','-Wno-multichar','-Wno-incompatible-pointer-types',
            '-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS','-DBG_PVE','-DBG_PVE_QA=0',*['-I'+str(p) for p in includes]]
        sources=['map.c','terrain.c','movement.c','combat_geometry.c','blam/runtime.c','blam/core.c',
            'blam/vehicle_physics.c','replay.c','frontend_qa.c','autopilot_nav.c','gungnir_movement.c','autopilot_strategy.c']
        if not embedded:sources.append('game.c')
        generated=[self.base/'maps/common_data.c',self.base/'movement_data.c',self.base/'hud_damage_data.c',
            *[self.base/'pve'/n for n in ('pve_defs.c','pve_collision.c','pve_nav.c')],
            *[data/n for n in ('combat_data.c','interaction_defs.c')],
            self.output/'enemy_vehicle_physics.c' if expanded else self.base/'vehicle_data.c']
        if expanded:
            flags+=['-DBG_PVE_ROSTER','-DBG_ENEMY_VEHICLES'];sources.append('vehicle_ai.c')
            generated += [self.enemy/n for n in ('enemy_vehicle_data.c','enemy_pilot_hits.c','pve_roster.c')]
        binary=self.output/(test+('-roster' if expanded else '-base'))
        command=['clang',*flags,str(ROOT/'port/n64'/(test+'.c')),*[str(ROOT/'port/n64'/n) for n in sources],*map(str,generated),'-lm','-o',str(binary)]
        subprocess.run(command,cwd=ROOT,check=True);self.records.append({'test':binary.name,'command':command})
        return binary

    def run(self,binary,args=(),log=None,environment=None):
        result=subprocess.run([str(binary),*map(str,args)],cwd=self.sandbox,env={**self.environment,**(environment or {})},text=True,capture_output=True)
        (self.output/(log or (binary.name+'.log'))).write_text(result.stdout+result.stderr)
        if result.returncode:print(result.stdout+result.stderr,file=sys.stderr)
        result.check_returncode();print('PASS',log or binary.name,flush=True);return result.stdout

    def finish(self):
        (self.output/'checks.json').write_text(json.dumps(self.records,indent=2)+'\n')
