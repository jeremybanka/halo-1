#!/usr/bin/env python3
"""Translate the reconstructed Xbox preset builders into the N64 rule table.

Only public source constants are emitted here. Map/objective payloads are
exported separately into the private asset bank by extract_mode_maps.py.
"""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PRESETS = (
    ('slayer', 'Slayer'), ('slayer_pro', 'Slayer Pro'),
    ('elimination', 'Elimination'), ('phantoms', 'Phantoms'),
    ('endurance', 'Endurance'), ('rockets', 'Rockets'), ('snipers', 'Snipers'),
    ('oddball', 'Oddball'), ('reverse_tag', 'Reverse Tag'),
    ('accumulation', 'Accumulate'), ('juggernaut', 'Juggernaut'),
    ('stalker', 'Stalker'), ('king', 'King'), ('king_pro', 'King Pro'),
    ('crazy_king', 'Crazy King'), ('race', 'Race'), ('rally', 'Rally'),
    ('ctf', 'CTF'), ('invasion', 'Invasion'), ('iron_ctf', 'Iron CTF'),
    ('ctf_pro', 'CTF Pro'), ('team_race', 'Team Race'),
    ('team_rally', 'Team Rally'), ('team_oddball', 'Team Ball'),
    ('team_king', 'Team King'), ('team_slayer', 'Team Slayer'))


def render():
    source = (ROOT / 'source/game/game_engine.c').read_text()
    lines = ['/* Generated from source/game/game_engine.c; do not edit by hand. */']
    for index, (key, name) in enumerate(PRESETS):
        body = re.search(r'struct game_variant \*build_game_variant_' + key +
                         r'\([^)]*\)\s*\{(.*?)\n\}', source, re.S).group(1)
        fields = dict(re.findall(r'result\.([\w.]+)\s*=\s*([^;]+);', body))
        flags = dict(re.findall(r'SET_FLAG\(result.universal_variant.flags, '
                                r'_game_variant_(\w+)_bit, (TRUE|FALSE)\)', body))

        def value(field, default='0'):
            v = fields.get(field, default)
            return {'TRUE': '1', 'FALSE': '0'}.get(v, v)

        def universal(field):
            return value('universal_variant.' + field)

        engine = fields['game_engine_index'].removeprefix('game_engine_')
        engine_id = ('slayer', 'ctf', 'oddball', 'king', 'race').index(engine)
        options = []
        for flag, symbol in [('always_invisible', 'INVISIBLE'),
                             ('generic_starting_equipment', 'GENERIC'),
                             ('draw_object_in_motion_sensor', 'SENSOR')]:
            if flags[flag] == 'TRUE': options.append('BG_MODE_' + symbol)
        for field, symbol in [('odd_man_out', 'ODD_MAN')]:
            if universal(field) == '1': options.append('BG_MODE_' + symbol)
        for field, symbol in [('slayer.no_death_bonus', 'NO_DEATH_BONUS'),
                              ('slayer.no_kill_penalty', 'NO_KILL_PENALTY'),
                              ('slayer.kill_in_order', 'TARGETS'),
                              ('king.moving_hill', 'MOVING_HILL'),
                              ('ctf.assault', 'ASSAULT'),
                              ('ctf.flag_at_home_to_score', 'FLAG_HOME'),
                              ('ctf.flag_must_reset', 'FLAG_RESET')]:
            if value('game_engine_variant.' + field) == '1':
                options.append('BG_MODE_' + symbol)
        radar = {'_radar_motion_tracker': 0, '_radar_nav_point': 1, '_radar_none': 2}[universal('goal_radar')]
        vehicle = {'_game_engine_vehicles_none': 0, '_game_engine_vehicles_warthog': 1,
                   '_game_engine_vehicles_tank': 2}[universal('vehicle_set')]
        weapon = {'_game_engine_weapons_normal': -1, '_game_engine_weapons_sniping': 6,
                  '_game_engine_weapons_rocket_launchers': 7}[universal('weapon_set')]
        row = [str(index), key.upper(), '"' + name + '"', str(engine_id), universal('teams'),
               str(radar), str(vehicle), str(weapon), universal('health'),
               universal('score_to_win'), universal('lives'), universal('respawn_time'),
               universal('suicide_penalty'), universal('respawn_time_growth'),
               '|'.join(options) or '0']
        row += [value('game_engine_variant.oddball.' + f) for f in
                ('oddball_ball_type', 'ball_spawn_count', 'ball_spawn_delay',
                 'trait_with_ball', 'trait_without_ball', 'speed_with_ball')]
        row += [value('game_engine_variant.race.race_type')]
        lines.append('BG_MODE(' + ', '.join(row) + ')')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = Path(__file__).with_name('game_modes.def')
    if args.check:
        assert path.read_text() == render(), 'N64 presets differ from source builders'
        print('PASS: all 26 preset builders match the N64 rule table')
    else:
        path.write_text(render())
