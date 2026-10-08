#!/usr/bin/env python3
"""Regenerate native vehicle sources/data and run host sanitizer regressions.

Requires the extracted caches and generated demake collision bank from the ROM
asset build. Emulator timing and presentation must be verified separately.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/n64/vehicle-tests'


def run(args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for script in ('prepare_core.py', 'prepare_collision.py', 'prepare_vehicle.py',
                   'tags/export_collision.py', 'export_vehicle.py'):
        run([sys.executable, ROOT/'port/n64/blam'/script])
    flags = ['-std=c17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
             '-fno-fast-math', '-ffp-contract=off', '-fno-strict-aliasing', '-fwrapv',
             '-Wno-multichar', '-Wno-unused-function', '-Wno-unused-parameter',
             '-Wno-unused-variable', '-Wno-incompatible-pointer-types',
             '-Iport/n64', '-Ibuild/n64/blam-core', '-Ibuild/n64/blam-vehicle']
    shared = ['port/n64/game.c', 'port/n64/blam/runtime.c', 'port/n64/blam/core.c',
              'port/n64/blam/vehicle_physics.c', 'build/n64/generated/vehicle_data.c',
              'build/n64/generated/collision_data.c']
    suites = {
        'native': ['port/n64/blam/test_vehicle.c',
                   'port/n64/blam/test_vehicle_reference.c', 'port/n64/blam/collision.c',
                   'build/n64/generated/vehicle_data.c',
                   'build/n64/generated/blam_collision_data.c'],
        'game': ['port/n64/test_game.c', *shared],
        'weapon-effects': ['port/n64/test_weapon_effects.c', 'port/n64/weapon_effects.c',
                           'build/n64/generated/weapon_effects_data.c', *shared],
        'effects-staging': ['port/n64/test_effects_qa.c', 'port/n64/effects_qa.c',
                            'port/n64/weapon_effects.c', 'build/n64/generated/weapon_effects_data.c', *shared],
        'replay': ['port/n64/test_replay.c', 'port/n64/replay.c', *shared],
        'showcase': ['port/n64/test_showcase.c', 'port/n64/showcase.c', *shared],
    }
    for name, sources in suites.items():
        exe = OUT / name
        run(['clang', *flags, *sources, '-lm', '-o', exe])
        run([exe])
    print('PASS: native vehicle, game, replay and showcase sanitizer suites')


if __name__ == '__main__':
    main()
