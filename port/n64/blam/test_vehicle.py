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
    shared = ['build/n64/generated/pickup_data.c','port/n64/combat_geometry.c','build/n64/generated/combat_data.c', 'port/n64/terrain.c', 'port/n64/movement.c', 'build/n64/generated/movement_data.c', 'port/n64/game.c', 'build/n64/generated/interaction_defs.c', 'port/n64/blam/runtime.c', 'port/n64/blam/core.c',
              'port/n64/blam/vehicle_physics.c', 'build/n64/generated/vehicle_data.c',
              'build/n64/generated/terrain_data.c']
    suites = {
        'terrain-source': ['port/n64/test_terrain_source.c','port/n64/blam/collision.c','build/n64/generated/blam_collision_data.c',*shared],
        'terrain-cache': ['build/n64/generated/combat_data.c','port/n64/test_terrain_cache.c','port/n64/movement.c','build/n64/generated/movement_data.c','build/n64/generated/terrain_data.c'],
        'terrain': ['build/n64/generated/combat_data.c','port/n64/test_terrain.c','port/n64/terrain.c','port/n64/movement.c','build/n64/generated/movement_data.c'],
        'interaction-cache': ['port/n64/test_interaction_cache.c'],
        'native': ['port/n64/blam/test_vehicle.c',
                   'port/n64/blam/test_vehicle_reference.c', 'port/n64/blam/collision.c',
                   'build/n64/generated/vehicle_data.c',
                   'build/n64/generated/blam_collision_data.c'],
        'movement': ['port/n64/test_movement.c', 'port/n64/controls.c', *shared],
        'interactions': ['port/n64/test_interactions.c', *shared],
        'sound-mix': ['port/n64/test_sound_mix.c', 'port/n64/sound_mix.c'],
        'shield-audio': ['port/n64/test_shield_audio.c', 'port/n64/sound_mix.c', 'build/n64/generated/shield_data.c'],
        'shields': ['port/n64/test_shields.c', *shared],
        'powerups': ['port/n64/test_powerups.c', *shared],
        'vehicle-edges': ['port/n64/test_vehicle_edges.c', *shared],
        'view-camera': ['port/n64/test_view_camera.c', 'build/n64/generated/camera_data.c'],
        'game': ['port/n64/test_game.c', *shared],
        'combat-geometry': ['port/n64/test_combat_geometry.c', *shared],
        'combat': ['port/n64/test_combat.c', *shared],
        'pickups': ['port/n64/test_pickups.c', *shared],
        'weapon-effects': ['port/n64/test_weapon_effects.c', 'port/n64/weapon_effects.c',
                           'build/n64/generated/weapon_effects_data.c', *shared],
        'effects-staging': ['port/n64/test_effects_qa.c', 'port/n64/effects_qa.c',
                            'port/n64/weapon_effects.c', 'build/n64/generated/weapon_effects_data.c', *shared],
        'destruction': ['port/n64/test_destruction.c', 'port/n64/destruction_qa.c', 'port/n64/weapon_effects.c',
                        'build/n64/generated/weapon_effects_data.c', *shared],
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
