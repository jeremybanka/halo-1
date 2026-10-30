#!/usr/bin/env python3
"""CE skeletal layers over the approved N64 meshes; no geometry reduction.

The node frames stay in ROM. Runtime combines locomotion, replacement/overlay
weapon actions, then the authored aiming screen before skinning either LOD.
"""
import contextlib
import hashlib
import json
import math
from pathlib import Path
import struct
import numpy as np
from pack_interactions import matrices
from extract_extended import MODEL_PATHS

ROOT = Path(__file__).resolve().parents[2]
A, G, F = [ROOT / 'build/n64' / n for n in ('assets', 'generated', 'frontend-files')]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def cvalue(value):
    if isinstance(value, (list, tuple, np.ndarray)):
        return '{' + ','.join(cvalue(x) for x in value) + '}'
    if isinstance(value, (float, np.floating)):
        return f'{value:.9e}f'
    return str(int(value))


def run():
    with (A / 'player-animation-extraction.log').open('w') as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        from reclaimer.meta.wrappers.halo1_map import Halo1Map
        from reclaimer.animation.animation_decompilation import extract_animation
        h = Halo1Map()
        h.load_map(A / 'bloodgulch-decompressed.map')
    entries = h.tag_index.tag_index

    def meta(kind, path):
        index = next(i for i, t in enumerate(entries) if t.class_1.enum_name == kind and t.path == path)
        value = h.get_meta(index)
        if kind == 'model_animations':
            h.meta_to_tag_data(value, 'antr', entries[index])
        return value

    graph = meta('model_animations', r'characters\cyborg\cyborg')
    raw = json.loads((A / 'extended-raw.json').read_text())
    world = json.loads((A / 'extended-reduced.json').read_text())
    mapping = json.loads((G / 'world-mesh-sources.json').read_text())
    nodes = raw['models']['spartan']['nodes']
    assert len(nodes) == 19 and all(n['parent'] < i for i, n in enumerate(nodes))
    inverse = np.linalg.inv(matrices(nodes, nodes))
    bank, clips, decoded, lookup = bytearray(), [], [], {}

    def add(index, loop=False):
        if index < 0:
            return -1
        key = index, loop
        if key in lookup:
            return lookup[key]
        source = graph.animations.STEPTREE[index]
        clip = extract_animation(index, graph, write_jma=False)
        clip.apply_root_node_info_to_states(undo=True)
        count = source.frame_count
        # Reclaimer prepends a default frame to UNCOMPRESSED overlays and
        # appends a closing frame to base/replacement exports. Neither belongs
        # in CE's aiming grid (the neutral cell is the center, never frame 0).
        frames = (clip.frames[1:count + 1] if clip.anim_type == 'overlay' and
                  not source.flags.compressed_data else clip.frames[:count])
        states = [[dict(q=[n.rot_i, n.rot_j, n.rot_k, n.rot_w],
                        p=[n.pos_x / 100, n.pos_y / 100, n.pos_z / 100]) for n in f] for f in frames]
        assert len(states) == count
        assert all(abs(n.scale - 1) < 1e-5 for f in frames for n in f), source.name
        # Preserve main's approved locomotion/action samples and clocks. Only
        # the aim screens are new; firing/reload already compose correctly.
        legacy = next((c for c in raw['animations'].values() if c['tag_name'] == source.name), None)
        duration = count / 30
        if legacy is not None:
            reduced = world['animations'][next(k for k, c in raw['animations'].items() if c is legacy)]
            samples = len(reduced['frames'])
            states = [legacy['frames'][round(i * (len(legacy['frames']) - 1) / max(1, samples - 1))]
                      for i in range(samples)]
            duration = legacy['duration']
        stride = (19 * 14 + 15) & ~15
        offset = len(bank)
        for frame in states:
            values = []
            for n in frame:
                q = np.array(n['q']); q /= np.linalg.norm(q)
                values.extend(round(x * 32767) for x in q)
                values.extend(round(x * 4096) for x in n['p'])
            assert all(-32768 <= v <= 32767 for v in values)
            bank.extend(struct.pack('>' + 'h' * len(values), *values))
            bank.extend(bytes(stride - len(values) * 2))
        kind = ('base', 'overlay', 'replacement').index(clip.anim_type)
        item = dict(name=source.name, source_index=index, offset=offset,
                    rotations=clip.rot_flags_int, translations=clip.trans_flags_int,
                    frames=len(states), stride=stride, duration=duration, type=kind,
                    loop=loop, compressed=bool(source.flags.compressed_data))
        lookup[key] = len(clips); clips.append(item); decoded.append(states)
        return lookup[key]

    def screen(w):
        return [[w.right_yaw_per_frame, w.left_yaw_per_frame],
                [w.down_pitch_per_frame, w.up_pitch_per_frame],
                [w.right_frame_count, w.left_frame_count], [w.down_frame_count, w.up_frame_count]]

    # CE unit weapon-class slots, followed by weapon-type fire/reload/melee.
    slots = [0, 8, 9, 10, 11, 16, 17, 18, 20, 23, 25, 26]
    units = [next(u for u in graph.units.STEPTREE if u.label == name) for name in ('stand', 'crouch')]
    # The existing Spartan bank uses the rifle rig for every held weapon.
    # Retain that contract; this change adds aiming, not new weapon stances.
    labels = ['ar'] * 9
    sets, names = [], []
    for stance, unit in enumerate(units):
        row, row_names = [], []
        for label in labels:
            choices = [(w, t) for w in unit.weapons.STEPTREE for t in w.weapon_types.STEPTREE if t.label == label]
            # Some graphs contain an empty placeholder in a different class.
            w, weapon = max(choices, key=lambda pair: sum(a.animation >= 0 for a in pair[1].animations.STEPTREE))
            standing = next(x for x in units[0].weapons.STEPTREE if x.name == w.name)
            fallback = units[0].weapons.STEPTREE[0]
            indices = []
            for slot in slots:
                value = w.animations.STEPTREE[slot].animation
                if value < 0:
                    value = standing.animations.STEPTREE[slot].animation
                if value < 0 and slot == 26:
                    value = w.animations.STEPTREE[25].animation
                if value < 0 and slot == 23:
                    value = fallback.animations.STEPTREE[slot].animation
                indices.append(add(value, slot in (0, 8, 9, 10, 11, 16)))
            for slot in (4, 0, 8):
                value = weapon.animations.STEPTREE[slot].animation
                if value < 0:
                    st = next((t for t in standing.weapon_types.STEPTREE if t.label == label), None)
                    if st is not None:
                        value = st.animations.STEPTREE[slot].animation
                indices.append(add(value))
            row.append([indices, screen(w)]); row_names.append([unit.label, w.name, label])
        sets.append(row); names.append(row_names)
    look_index = next(i for i, a in enumerate(graph.animations.STEPTREE) if a.name == 'stand look')
    look = add(look_index)
    marker = raw['models']['spartan']['markers']['right hand'][0]
    marker_matrix = matrices([marker], [{'parent': -1}])[0][:3]
    lines = ['/* Generated from owned CE tags by extract_player_aim.py. */', '#include "player_aim.h"']
    lines += ['const int8_t bg_player_parents[BG_PLAYER_NODES]=' + cvalue([n['parent'] for n in nodes]) + ';',
              'const bg_node_matrix bg_player_inverse_bind[BG_PLAYER_NODES]={' + ','.join('{' + cvalue(m[:3]) + '}' for m in inverse) + '};',
              'const bg_node_matrix bg_player_hand_marker={' + cvalue(marker_matrix) + '};',
              f'const unsigned bg_player_hand_node={marker["node"]};',
              'const bg_node_clip bg_player_node_clips[]={' + ','.join(cvalue([c[k] for k in
                  ('offset', 'rotations', 'translations', 'frames', 'stride', 'duration', 'type')]) for c in clips) + '};',
              'const bg_player_anim_set bg_player_anim_sets[2][9]=' + cvalue(sets) + ';',
              f'const int bg_player_look_clip={look};',
              'const bg_aim_screen bg_player_look_screen=' + cvalue(screen(units[0])) + ';']
    bind_radius = np.zeros(19)
    skin_sizes, skin_tracks = [], []
    for name, model in [('spartan', world['models']['spartan']), ('spartan_lod', world['spartan_lod'])]:
        corners = [(p, weights) for t in model['triangles'] for p, weights in zip(t['p'], t['weights'])]
        vertices, weights, seen = [], [], {}
        for index in mapping[name]:
            p, ws = corners[index]
            assert abs(sum(w for _, w in ws) - 1) < 1e-5 and len(ws) < 256
            key = (*p, tuple(tuple(w) for w in ws))
            if key in seen:
                vertices.append([seen[key], 0])
                continue
            seen[key] = len(vertices)
            vertices.append([len(weights), len(ws)])
            for bone, weight in ws:
                local = (inverse[bone] @ [*p, 1])[:3]
                weights.append([local, weight, bone])
                bind_radius[bone] = max(bind_radius[bone], np.linalg.norm(local))
        lines += [f'static const bg_skin_vertex {name}_vertices[]=' + cvalue(vertices) + ';',
                  f'static const bg_skin_weight {name}_weights[]=' + cvalue(weights) + ';']
        skin_sizes.append(len(vertices))
        skin_tracks.append(len(seen))
    lines += ['const bg_player_skin bg_player_skins[2]={{spartan_vertices,spartan_weights,' + str(skin_sizes[0]) +
              '},{spartan_lod_vertices,spartan_lod_weights,' + str(skin_sizes[1]) + '}};']
    collision = meta('model_collision_geometry', r'characters\cyborg\cyborg')
    hit_vertices = []
    for node in collision.nodes.STEPTREE:
        ni = next(i for i, n in enumerate(nodes) if n['name'] == node.name)
        for bsp in node.bsps.STEPTREE:
            hit_vertices.extend([[x, y, z], ni] for x, y, z, _ in struct.iter_unpack('<fffi', bsp.vertices.STEPTREE))
    lines += ['const bg_hit_bind_vertex bg_player_hit_bind[]=' + cvalue(hit_vertices) + ';']
    # Analytic rotation-independent bound: chain translation lengths plus
    # bone-local vertex reach. Linear translation blends and normalized
    # quaternion interpolation stay inside it, including between aim cells.
    base = np.zeros(19); additive = np.zeros(19)
    for c, frames in zip(clips, decoded):
        reach = np.max([[np.linalg.norm(n['p']) for n in f] for f in frames], axis=0) + .0003
        if c['type'] == 1:
            reach = np.array([r if c['translations'] & (1 << i) else 0 for i, r in enumerate(reach)])
            additive = np.maximum(additive, reach)
        else:
            base = np.maximum(base, reach)
    total = base + 3 * additive  # fire + aiming + looking (all translations)
    for i, n in enumerate(nodes):
        if n['parent'] >= 0:
            total[i] += total[n['parent']]
    radius = float(max(total + bind_radius)) + .02
    lines += ['const bg_bounds bg_player_aim_bounds=' + cvalue([[-radius] * 3, [radius] * 3]) + ';']
    (G / 'player_animation_data.c').write_text('\n'.join(lines) + '\n')
    (F / 'player-animation.bin').write_bytes(bank)
    inputs = [A / 'bloodgulch-decompressed.map', A / 'extended-raw.json', A / 'extended-reduced.json',
              G / 'world-mesh-sources.json', Path(__file__), ROOT / 'port/n64/pack_interactions.py',
              ROOT / 'port/n64/pack_fp_ammo.py']
    report = dict(inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                  files={str(p.relative_to(ROOT)): sha(p) for p in [G / 'player_animation_data.c', F / 'player-animation.bin']},
                  clips=clips, sets=names, rom_bytes=len(bank), vertices=skin_sizes, skin_tracks=skin_tracks,
                  collision_vertices=len(hit_vertices), cull_radius=radius)
    (G / 'player-animation-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('rom_bytes', 'vertices', 'collision_vertices', 'cull_radius')}))


if __name__ == '__main__':
    run()
