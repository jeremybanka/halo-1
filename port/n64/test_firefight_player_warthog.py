"""Check player transport and Firefight regressions using the pinned private bank."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bank = ROOT / 'halo64-assets'
    core, solver = output / 'core', output / 'solver'
    for script, dest in [('prepare_core.py', core), ('prepare_vehicle.py', solver)]:
        subprocess.run([sys.executable, str(ROOT / 'port/n64/blam' / script),
                        '--output', str(dest)], cwd=ROOT, check=True)
    from prepare_gungnir_strategy import run as prepare_strategy
    prepare_strategy(output / 'gungnir-source')
    # The versioned checkpoint retains the six-vehicle physics export verbatim.
    checkpoint = bank / 'assets/firefight-checkpoint'
    inputs = json.loads((checkpoint / 'compiler-inputs.json').read_text())['play']['sources']
    digest = next(sha for name, sha in inputs.items() if name.endswith('/generated/vehicle_data.c'))
    physics = gzip.decompress((checkpoint / 'inputs' / (digest + '.gz')).read_bytes())
    assert hashlib.sha256(physics).hexdigest() == digest
    (output / 'enemy_vehicle_physics.c').write_bytes(physics)
    sys.path.insert(0, str(ROOT / 'port/n64/blam'))
    from prepare_collision import function
    reference = subprocess.check_output(['git', 'show',
        '031e79f57ba49ab32d507a1c97aee118cbf328d2:port/n64/firefight_game.inc'], cwd=ROOT, text=True)
    (output / 'onslaught_reference.inc').write_text(function(reference, 'ff_packet_kind').replace('ff_packet_kind', 'onslaught_packet_kind'))
    base = bank / 'generated'
    enemy = bank / 'assets/enemy-vehicles/bank'
    sandbox = output / 'sandbox'
    (sandbox / 'build/n64').mkdir(parents=True)
    (sandbox / 'build/pve-vehicles').mkdir(parents=True)
    (sandbox / 'build/n64/frontend-files').symlink_to(bank / 'frontend-files', target_is_directory=True)
    (sandbox / 'build/pve-vehicles/bank').symlink_to(enemy, target_is_directory=True)
    sources = ['map.c', 'terrain.c', 'movement.c', 'combat_geometry.c',
               'blam/runtime.c', 'blam/core.c', 'blam/vehicle_physics.c',
               'replay.c', 'frontend_qa.c', 'autopilot_nav.c', 'gungnir_movement.c',
               'autopilot_strategy.c']
    common = [base / 'maps/common_data.c', base / 'movement_data.c', base / 'hud_damage_data.c',
              *[base / 'pve' / name for name in ('pve_defs.c', 'pve_collision.c', 'pve_nav.c')]]
    flags = ['-std=c17', '-O1', '-g', '-fno-fast-math', '-ffp-contract=off',
             '-fno-strict-aliasing', '-fwrapv', '-fsanitize=address,undefined',
             '-Wno-multichar', '-Wno-incompatible-pointer-types',
             '-DBG_BODY_CANDIDATES', '-DBG_STREAM_MAPS', '-DBG_PVE', '-DBG_PVE_QA=0']
    reports = []
    for expanded in (False, True):
        data = enemy if expanded else base
        includes = [output, ROOT / 'port/n64', ROOT / 'port/n64/blam', core,
                    solver, output / 'gungnir-source', data, base / 'pve']
        options = flags + ['-I' + str(path) for path in includes]
        generated = common + [data / name for name in ('combat_data.c', 'interaction_defs.c')]
        generated += [output / 'enemy_vehicle_physics.c' if expanded else base / 'vehicle_data.c']
        extra = []
        if expanded:
            options += ['-DBG_PVE_ROSTER', '-DBG_ENEMY_VEHICLES']
            generated += [enemy / name for name in ('enemy_vehicle_data.c', 'enemy_pilot_hits.c', 'pve_roster.c')]
            extra = [ROOT / 'port/n64/vehicle_ai.c']
        tests = ['test_firefight_player_warthog', 'test_firefight']
        if expanded:
            tests += ['test_firefight_fights', 'test_enemy_vehicles']
        for test in tests:
            name = test + ('-roster' if expanded else '-base')
            binary = output / name
            command = ['clang', *options, str(ROOT / 'port/n64' / (test + '.c')),
                       *[str(ROOT / 'port/n64' / source) for source in sources],
                       *map(str, extra + generated), '-lm', '-o', str(binary)]
            subprocess.run(command, cwd=ROOT, check=True)
            result = subprocess.run([str(binary)], cwd=sandbox, text=True, capture_output=True,
                env={**os.environ, 'BG_MAP_DIRECTORY': str(base / 'maps'),
                     'BG_AUTONAV_DIRECTORY': str(base / 'gungnir')})
            (output / (name + '.log')).write_text(result.stdout + result.stderr)
            result.check_returncode()
            print('PASS', name, flush=True)
            reports.append({'test': name, 'command': command})
    (output / 'checks.json').write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    run(parser.parse_args().output_dir)
