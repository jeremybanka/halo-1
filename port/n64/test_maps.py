"""Exercise the production map loader and game against both private ROM banks."""
import argparse
import os
import json
import struct
import tempfile
import shutil
from pathlib import Path
import subprocess
from asset_ids import map_ids

ROOT = Path(__file__).resolve().parents[2]

def run(output, blam_bsp=False, frontend_cycle=False,export_spawn_clearance=False,maps_cycle=False,map_directory=None,world_cells=False):
    output = output.resolve(); output.mkdir(parents=True, exist_ok=True)
    solver = output/'solver'; solver.mkdir(exist_ok=True)
    for script in ('prepare_vehicle.py','export_vehicle.py'):
        args=[str(ROOT/'port/n64/blam'/script),'--output',str(solver)]
        if script=='export_vehicle.py':args += ['--rom-files',str(solver)]
        subprocess.run([str(ROOT/'build/n64-python/bin/python'),*args],cwd=ROOT,check=True)
    flags=['-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-Wno-multichar',
           '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
           '-Wno-incompatible-pointer-types','-fno-fast-math','-ffp-contract=off',
           '-fno-strict-aliasing','-fwrapv','-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS',
           '-fsanitize=address,undefined','-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
    if world_cells:flags.append('-DBG_WORLD_CELLS')
    sources=['port/n64/test_maps.c','port/n64/map.c','halo64-assets/generated/maps/common_data.c',
             'port/n64/game.c','port/n64/terrain.c','port/n64/movement.c','port/n64/combat_geometry.c',
             'build/n64/generated/combat_data.c','build/n64/generated/movement_data.c',
             'build/n64/generated/interaction_defs.c','port/n64/blam/runtime.c','port/n64/blam/core.c',
             'port/n64/blam/vehicle_physics.c','port/n64/replay.c','port/n64/frontend_qa.c',
             str(solver/'vehicle_data.c')]
    if blam_bsp:
        flags.append('-DBG_BLAM_BSP')
        sources += ['port/n64/blam/collision.c', 'build/n64/generated/blam_collision_data.c']
    if maps_cycle:flags.append("-DBG_MAPS_CYCLE");frontend_cycle=True
    if frontend_cycle:
        flags.append('-DBG_INITIAL_MAP=10')
        sources += ['port/n64/frontend.c', 'port/n64/menu.c', 'port/n64/controls.c']
    binary=output/'maps'
    subprocess.run(['clang',*flags,*sources,'-lm','-o',str(binary)],cwd=ROOT,check=True)
    if export_spawn_clearance:
        directory=ROOT/'halo64-assets/generated/maps';report=json.loads((directory/'maps-report.json').read_text())
        with tempfile.TemporaryDirectory(prefix='halo-map-starts-') as tmp:
            tmp=Path(tmp)
            for source in directory.iterdir():
                if source.suffix in ('.map64','.bin'):shutil.copyfile(source,tmp/source.name)
            names=[n for n in map_ids() if n not in ('bloodgulch','wizard')]
            for name in names:
                info=report['maps'][name];path=tmp/(name+'.map64');data=bytearray(path.read_bytes())
                offset,count,stride=struct.unpack_from('>3I',data,16+14*12)
                assert count==len(info['authored_spawns']) and stride==20
                for i,row in enumerate(info['authored_spawns']):struct.pack_into('>4fi',data,offset+i*stride,*row)
                path.write_bytes(data)
            result=subprocess.check_output([str(binary)],cwd=ROOT,env={**os.environ,'BG_MAP_DIRECTORY':str(tmp),'BG_EXPORT_SPAWN_CLEARANCE':'1'},text=True)
        corrections={'corrections':json.loads(result),'source_sha256':{n:report['maps'][n]['source_sha256'] for n in names},
            'description':'Minimum offsets resolved by the unchanged N64 capsule solver for authored starts with initial penetration. Accepted maps retain their 0.075-world-unit bound; newly imported maps use a 0.2-unit bound.'}
        (directory/'spawn-clearance.json').write_text(json.dumps(corrections,indent=2)+'\n')
        print(result)
    else:
        directory=Path(map_directory).resolve() if map_directory else ROOT/'halo64-assets/generated/maps'
        subprocess.run([str(binary)],cwd=ROOT,env={**os.environ,'BG_MAP_DIRECTORY':str(directory)},check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-wizard-audit/maps-tests')
    parser.add_argument('--blam-bsp', action='store_true', help='Also exercise the optional Blood Gulch source BSP')
    parser.add_argument('--frontend-cycle', action='store_true', help='Run the real three-match menu/map/quit/resume fixture')
    parser.add_argument('--export-spawn-clearance',action='store_true',help='Bake only minimal map-specific offsets using the accepted capsule solver')
    parser.add_argument("--maps-cycle",action="store_true",help="Complete the fourteen-match/all-thirteen-map menu fixture")
    parser.add_argument('--map-directory',type=Path,help='Test an isolated candidate ROM map directory')
    parser.add_argument('--world-cells',action='store_true',help='Match the larger batch capacity of the world-cell/hierarchy renderer')
    args = parser.parse_args()
    if args.export_spawn_clearance and args.map_directory:parser.error('Spawn export uses only the canonical banks')
    run(args.output_dir, args.blam_bsp, args.frontend_cycle,args.export_spawn_clearance,args.maps_cycle,args.map_directory,args.world_cells)
