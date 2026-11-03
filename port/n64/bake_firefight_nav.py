"""Bake selected-map enemy walk graphs from the pinned collision banks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def bake(output,map_directory=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    base=ROOT/'halo64-assets/generated';maps=Path(map_directory).resolve() if map_directory else base/'maps'
    for script,name in [('prepare_core.py','core'),('prepare_vehicle.py','solver')]:
        subprocess.run([sys.executable,str(ROOT/'port/n64/blam'/script),'--output',str(output/name)],cwd=ROOT,check=True)
    from prepare_gungnir_strategy import run
    run(output/'gungnir-source')
    includes=[ROOT/'port/n64',ROOT/'port/n64/blam',output/'core',output/'solver',output/'gungnir-source',base,base/'pve']
    flags=['-std=c17','-O1','-g','-fsanitize=address,undefined','-fno-fast-math','-ffp-contract=off',
        '-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-incompatible-pointer-types',
        '-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS','-DBG_PVE','-DBG_PVE_QA=0',*['-I'+str(p) for p in includes]]
    names=['bake_firefight_nav.c','game.c','map.c','terrain.c','movement.c','combat_geometry.c',
        'blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','frontend_qa.c',
        'autopilot_nav.c','gungnir_movement.c','autopilot_strategy.c']
    generated=[base/'maps/common_data.c',*[base/n for n in ('movement_data.c','hud_damage_data.c','combat_data.c','interaction_defs.c','vehicle_data.c')],
        *[base/'pve'/n for n in ('pve_defs.c','pve_collision.c','pve_nav.c')]]
    binary=output/'bake-firefight-nav'
    command=['clang',*flags,*[str(ROOT/'port/n64'/n) for n in names],*map(str,generated),'-lm','-o',str(binary)]
    subprocess.run(command,cwd=ROOT,check=True);reports=[]
    for map_id,name in [(0,'beavercreek'),(3,'ratrace')]:
        subprocess.run([str(binary),str(map_id),str(output)],cwd=ROOT,env={**os.environ,'BG_MAP_DIRECTORY':str(maps)},check=True)
        path=output/f'firefight-nav-{map_id}.bin';raw=path.read_bytes();magic,id,count=struct.unpack_from('>4s2H',raw)
        assert magic==b'FNV1' and id==map_id and 0<count<=8192 and len(raw)==20+22*count
        for n in range(count):
            nexts=struct.unpack_from('>8H',raw,20+22*n+6)
            assert any(v!=65535 for v in nexts)
            for k,v in enumerate(nexts):
                if v!=65535:assert v<count and struct.unpack_from('>H',raw,20+22*v+6+2*[1,0,3,2,7,6,5,4][k])[0]==n
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        reports.append({'map':map_id,'nodes':count,'bytes':len(raw),'sha256':sha(path),
            'source_map_sha256':sha(maps/(name+'.map64')),'source_world_sha256':sha(maps/(name+'-world.bin'))})
    report={'schema':1,'capsule':{'radius':.24,'height':.8},'layers':6,'walk_only':True,
        'maps':reports,'baker_sha256':hashlib.sha256((ROOT/'port/n64/bake_firefight_nav.c').read_bytes()).hexdigest(),
        'command':command}
    (output/'firefight-nav-report.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--map-directory',type=Path);a=p.parse_args();bake(a.output_dir,a.map_directory)
