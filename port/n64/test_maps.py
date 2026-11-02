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

def run(output, blam_bsp=False, frontend_cycle=False,export_spawn_clearance=False,maps_cycle=False,map_directory=None,world_cells=False,mode_tests=False,target_math=False,pve=False,with_pve=False,firefight=False,navigation=False,spartan_motion=False,collision=False,roster=False,enemy_vehicles=False,gungnir=False,bake_autonav=False,autonav_directory=None,gungnir_frontend=False,gungnir_showcase=False):
    output = output.resolve(); output.mkdir(parents=True, exist_ok=True)
    if gungnir_frontend:frontend_cycle=True;with_pve=True
    solver = output/'solver'; solver.mkdir(exist_ok=True)
    for script in ('prepare_vehicle.py','export_vehicle.py'):
        args=[str(ROOT/'port/n64/blam'/script),'--output',str(solver)]
        if script=='export_vehicle.py':args += ['--rom-files',str(solver)]+(['--enemy-vehicles'] if enemy_vehicles else [])
        subprocess.run([str(ROOT/'build/n64-python/bin/python'),*args],cwd=ROOT,check=True)
    from prepare_gungnir_strategy import run as prepare_strategy
    prepare_strategy(solver)
    flags=['-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-Wno-multichar',
           '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
           '-Wno-incompatible-pointer-types','-fno-fast-math','-ffp-contract=off',
           '-fno-strict-aliasing','-fwrapv','-DBG_BODY_CANDIDATES','-DBG_STREAM_MAPS',
           '-fsanitize=address,undefined','-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
    if world_cells:flags.append('-DBG_WORLD_CELLS')
    if gungnir_frontend:flags+=['-DBG_GUNGNIR_FRONTEND_QA','-DBG_FIREFIGHT']
    sources=['port/n64/test_maps.c','halo64-assets/generated/hud_damage_data.c','port/n64/map.c','halo64-assets/generated/maps/common_data.c',
             'port/n64/game.c','port/n64/terrain.c','port/n64/movement.c','port/n64/combat_geometry.c',
             'build/n64/generated/combat_data.c','build/n64/generated/movement_data.c',
             'build/n64/generated/interaction_defs.c','port/n64/blam/runtime.c','port/n64/blam/core.c',
             'port/n64/blam/vehicle_physics.c','port/n64/replay.c','port/n64/frontend_qa.c',
             str(solver/'vehicle_data.c'),'port/n64/gungnir_movement.c','port/n64/autopilot_nav.c','port/n64/autopilot_strategy.c','halo64-assets/generated/pve/pve_defs.c']
    if mode_tests:
        from spawn_source_reference import generate
        generate(solver/'spawn_reference.c')
        # The original routines remain strict even when testing the port with
        # the target compiler's math options.
        subprocess.run(['clang',*flags,'-c',str(solver/'spawn_reference.c'),'-o',str(solver/'spawn_reference.o')],cwd=ROOT,check=True)
        sources[0]='port/n64/test_modes.c'
        sources.remove('port/n64/game.c')
        sources.append(str(solver/'spawn_reference.o'))
        if target_math:
            # VR4300 has no fused multiply-add; disable host contraction too.
            flags+=['-ffast-math','-ftrapping-math','-fno-associative-math','-ffp-contract=off','-Wno-overriding-option']
    if pve:
        flags += ["-DBG_PVE","-DBG_PVE_QA=2","-DBG_PVE_NAV_BUILD","-Ihalo64-assets/generated/pve"]
        sources[0]="port/n64/test_pve.c";sources.remove("port/n64/game.c")
        sources += ["halo64-assets/generated/pve/pve_defs.c","halo64-assets/generated/pve/pve_collision.c"]
    if with_pve and not pve:
        flags += ["-DBG_PVE","-DBG_PVE_QA=0","-Ihalo64-assets/generated/pve"]
        sources += ["halo64-assets/generated/pve/pve_defs.c","halo64-assets/generated/pve/pve_nav.c","halo64-assets/generated/pve/pve_collision.c"]
    if roster:
        flags += ['-DBG_PVE_ROSTER']
        sources += ['build/firefight-roster/bank/pve_roster.c']
    if firefight or navigation:
        sources[0]="port/n64/test_navigation.c" if navigation else "port/n64/test_firefight.c";sources.remove("port/n64/game.c")
    if spartan_motion:
        sources[0]="port/n64/test_spartan_motion.c";sources.remove("port/n64/game.c")
    if collision:
        from collision_reference import generate
        generate(solver)
        flags += ['-DBG_COLLISION_PROFILE']
        if target_math:flags += ['-ffast-math','-ftrapping-math','-fno-associative-math','-ffp-contract=off','-Wno-overriding-option']
        sources[0]='port/n64/test_firefight_collision.c';sources.remove('port/n64/game.c')
        sources.append(str(solver/'collision_reference_terrain.c'))
    if enemy_vehicles:
        bank=ROOT/'build/pve-vehicles/bank'
        flags+=['-DBG_ENEMY_VEHICLES','-I'+str(bank)]
        sources=[str(bank/Path(n).name) if Path(n).name in ('combat_data.c','interaction_defs.c') else n for n in sources]
        sources += ['port/n64/vehicle_ai.c',str(bank/'enemy_vehicle_data.c'),str(bank/'enemy_pilot_hits.c')]
        if not firefight and not navigation and not mode_tests:
            sources[0]='port/n64/test_enemy_vehicles.c';sources.remove('port/n64/game.c')
    if blam_bsp:
        flags.append('-DBG_BLAM_BSP')
        sources += ['port/n64/blam/collision.c', 'build/n64/generated/blam_collision_data.c']
    if maps_cycle:flags.append("-DBG_MAPS_CYCLE");frontend_cycle=True
    if frontend_cycle:
        flags.append('-DBG_INITIAL_MAP=10')
        sources += ['port/n64/frontend.c', 'port/n64/menu.c', 'port/n64/controls.c']
    if gungnir:sources[0]='port/n64/test_gungnir.c';sources.remove('port/n64/game.c');sources.append('port/n64/controls.c')
    if gungnir_showcase:sources[0]='port/n64/test_gungnir_showcase.c'
    if bake_autonav:sources[0]='port/n64/bake_autopilot_nav.c'
    sources=list(dict.fromkeys(sources))
    binary=output/'maps'
    subprocess.run(['clang',*flags,*sources,'-lm','-o',str(binary)],cwd=ROOT,check=True)
    if bake_autonav:
        subprocess.run([str(binary),str(output)],cwd=ROOT,env={**os.environ,'BG_MAP_DIRECTORY':str(ROOT/'halo64-assets/generated/maps')},check=True)
    elif export_spawn_clearance:
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
        environment={**os.environ,'BG_MAP_DIRECTORY':str(directory)}
        if gungnir or gungnir_showcase:environment['BG_AUTONAV_DIRECTORY']=str(Path(autonav_directory).resolve() if autonav_directory else ROOT/'halo64-assets/generated/gungnir')
        if gungnir_frontend:environment['BG_AUTONAV_DIRECTORY']=str(Path(autonav_directory).resolve() if autonav_directory else ROOT/'halo64-assets/generated/gungnir')
        capture=gungnir or gungnir_frontend or gungnir_showcase
        result=subprocess.run([str(binary)],cwd=ROOT,env=environment,check=False,capture_output=capture,text=capture)
        if capture and result.returncode:
            log=result.stdout+result.stderr;print(log,end='');(output/'failed.log').write_text(log)
        result.check_returncode()
        if gungnir_frontend:
            log=result.stdout+result.stderr;print(log,end='');(output/'frontend.log').write_text(log)
        if gungnir_showcase:
            log=result.stdout+result.stderr;print(log,end='');(output/'showcases.log').write_text(log)
        if gungnir:
            import hashlib
            log=result.stdout+result.stderr;print(log,end='');(output/'gameplay.log').write_text(log)
            assert 'PASS: GUNGNIR gameplay and all-map movement autopilot' in log
            proof=dict(sanitizers_passed=True,maps=13,manual_firing_while_autopilot=True,log_sha256=hashlib.sha256(log.encode()).hexdigest(),test_sha256=hashlib.sha256((ROOT/'port/n64/test_gungnir.c').read_bytes()).hexdigest())
            (output/'gameplay-validation.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-wizard-audit/maps-tests')
    parser.add_argument('--blam-bsp', action='store_true', help='Also exercise the optional Blood Gulch source BSP')
    parser.add_argument('--gungnir',action='store_true')
    parser.add_argument('--gungnir-frontend',action='store_true')
    parser.add_argument('--gungnir-showcase',action='store_true')
    parser.add_argument('--autonav-directory',type=Path,help='GUNGNIR host-test navigation bank override')
    parser.add_argument('--bake-autonav',action='store_true')
    parser.add_argument('--navigation',action='store_true',help='Exact shortest-distance, scheduling and cache-lifecycle navigation checks')
    parser.add_argument("--collision",action="store_true",help="Exact terrain and animated hit oracles")
    parser.add_argument('--spartan-motion',action='store_true',help='Sustained-fire locomotion clocks and animated hit poses')
    parser.add_argument('--firefight',action='store_true',help='Finite Firefight lifecycle and formation-arrival tests')
    parser.add_argument('--with-pve', action='store_true', help='Run regressions with the NPC pool compiled in but inactive')
    parser.add_argument('--frontend-cycle', action='store_true', help='Run the real three-match menu/map/quit/resume fixture')
    parser.add_argument('--export-spawn-clearance',action='store_true',help='Bake only minimal map-specific offsets using the accepted capsule solver')
    parser.add_argument("--maps-cycle",action="store_true",help="Complete the fourteen-match/all-thirteen-map menu fixture")
    parser.add_argument('--map-directory',type=Path,help='Test an isolated candidate ROM map directory')
    parser.add_argument('--world-cells',action='store_true',help='Match the larger batch capacity of the world-cell/hierarchy renderer')
    parser.add_argument('--modes',action='store_true',help='Exercise every multiplayer preset and objective transition against all maps')
    parser.add_argument('--target-math',action='store_true',help='Exercise modes with target math flags against a separately compiled strict source reference')
    parser.add_argument("--pve",action="store_true")
    parser.add_argument("--roster",action="store_true",help="Test the isolated CE roster candidate")
    parser.add_argument('--enemy-vehicles',action='store_true')
    args = parser.parse_args()
    if args.enemy_vehicles:args.with_pve=True;args.roster=True
    if args.export_spawn_clearance and args.map_directory:parser.error('Spawn export uses only the canonical banks')
    if args.target_math and not (args.modes or args.collision):parser.error('--target-math requires --modes or --collision')
    run(args.output_dir, args.blam_bsp, args.frontend_cycle,args.export_spawn_clearance,args.maps_cycle,args.map_directory,args.world_cells,args.modes,args.target_math,args.pve,args.with_pve or args.firefight or args.navigation or args.collision,args.firefight,args.navigation,args.spartan_motion,args.collision,args.roster,args.enemy_vehicles,args.gungnir,args.bake_autonav,args.autonav_directory,args.gungnir_frontend,args.gungnir_showcase)
