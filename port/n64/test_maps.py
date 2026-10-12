"""Exercise the production map loader and game against both private ROM banks."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def run(output, blam_bsp=False):
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
    sources=['port/n64/test_maps.c','port/n64/map.c','halo64-assets/generated/maps/common_data.c',
             'port/n64/game.c','port/n64/terrain.c','port/n64/movement.c','port/n64/combat_geometry.c',
             'build/n64/generated/combat_data.c','build/n64/generated/movement_data.c',
             'build/n64/generated/interaction_defs.c','port/n64/blam/runtime.c','port/n64/blam/core.c',
             'port/n64/blam/vehicle_physics.c','port/n64/replay.c','port/n64/frontend_qa.c',
             str(solver/'vehicle_data.c')]
    if blam_bsp:
        flags.append('-DBG_BLAM_BSP')
        sources += ['port/n64/blam/collision.c', 'build/n64/generated/blam_collision_data.c']
    binary=output/'maps'
    subprocess.run(['clang',*flags,*sources,'-lm','-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,env={**os.environ,'BG_MAP_DIRECTORY':str(ROOT/'halo64-assets/generated/maps')},check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-wizard-audit/maps-tests')
    parser.add_argument('--blam-bsp', action='store_true', help='Also exercise the optional Blood Gulch source BSP')
    args = parser.parse_args()
    run(args.output_dir, args.blam_bsp)
