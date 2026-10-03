#!/usr/bin/env python3
"""Pack the original Blood Gulch collision BSP without decimation or axis changes.

Reclaimer exposes these cache blocks as little-endian raw bytes. Each scalar is
decoded explicitly; C initializers then use the compiler's native target endian.
No source bytes, generated arrays, or game data are checked into the repository.
"""
import argparse, contextlib, hashlib, json, math, struct
from pathlib import Path

ARRAYS = (
    ('bsp3d_nodes', 'blam_bsp3d_node', '3i'),
    ('planes', 'blam_plane3', '4f'),
    ('leaves', 'blam_collision_leaf', 'Hhi'),
    ('bsp2d_references', 'blam_bsp2d_reference', '2i'),
    ('bsp2d_nodes', 'blam_bsp2d_node', '3f2i'),
    ('surfaces', 'blam_collision_surface', '2iBBh'),
    ('edges', 'blam_collision_edge', '6i'),
    ('vertices', 'blam_collision_vertex', '3fi'),
)


def decode(map_path):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    halo = Halo1Map(); halo.load_map(map_path)
    index = next(i for i, e in enumerate(halo.tag_index.tag_index)
                 if e.class_1.enum_name == 'scenario_structure_bsp' and 'bloodgulch' in e.path)
    blocks = halo.get_meta(index, disable_tag_cleaning=True).collision_bsp.STEPTREE
    if len(blocks) != 1: raise ValueError('Expected exactly one Blood Gulch collision BSP')
    data = {}
    for name, _, fmt in ARRAYS:
        block = getattr(blocks[0], name); raw = bytes(block.STEPTREE)
        if len(raw) != block.size * struct.calcsize('<'+fmt):
            raise ValueError('Invalid collision array size: '+name)
        data[name] = list(struct.iter_unpack('<'+fmt, raw))
    spawns = [list(s.position) for s in halo.scnr_meta.player_starting_locations.STEPTREE]
    return data, spawns


def check(data):
    def index(value, key):
        if not 0 <= value < len(data[key]): raise ValueError(f'{key} index out of bounds: {value}')
    def designator(value, key): index(value & 0x7fffffff, key)
    for plane, back, front in data['bsp3d_nodes']:
        designator(plane, 'planes')
        for child in (back, front):
            if child == -1: continue
            (designator if child < 0 else index)(child, 'leaves' if child < 0 else 'bsp3d_nodes')
    for flags, count, first in data['leaves']:
        if count < 0 or (count and not 0 <= first <= len(data['bsp2d_references'])-count):
            raise ValueError('Invalid collision leaf reference range')
    for plane, root in data['bsp2d_references']:
        designator(plane, 'planes')
        (designator if root < 0 else index)(root, 'surfaces' if root < 0 else 'bsp2d_nodes')
    for *plane, left, right in data['bsp2d_nodes']:
        for child in (left, right):
            (designator if child < 0 else index)(child, 'surfaces' if child < 0 else 'bsp2d_nodes')
    for plane, edge, *_ in data['surfaces']:
        designator(plane, 'planes'); index(edge, 'edges')
    for v0, v1, e0, e1, s0, s1 in data['edges']:
        for v in (v0, v1): index(v, 'vertices')
        for e in (e0, e1): index(e, 'edges')
        for s in (s0, s1):
            if s != -1: index(s, 'surfaces')
    for *point, edge in data['vertices']: index(edge, 'edges')
    for rows in data.values():
        if any(isinstance(v, float) and not math.isfinite(v) for row in rows for v in row):
            raise ValueError('Nonfinite collision scalar')
    def depth(key, children):
        state = [0]*len(data[key]); depths = [0]*len(state)
        def visit(i):
            if i < 0: return 0
            if state[i] == 1: raise ValueError('Cycle in '+key)
            if state[i] == 2: return depths[i]
            state[i] = 1
            depths[i] = 1+max(visit(j) for j in children(data[key][i]))
            state[i] = 2
            return depths[i]
        return max((visit(i) for i in range(len(state))), default=0)
    depths = {'bsp3d': depth('bsp3d_nodes', lambda r:r[1:]),
              'bsp2d': depth('bsp2d_nodes', lambda r:r[3:])}
    # Each surface must have a closed, consistently oriented edge ring.
    polygon_sizes = [len(p) for p in polygons(data)]
    return {**depths, 'max_polygon_edges': max(polygon_sizes)}


def polygons(data):
    result = []
    for surface, record in enumerate(data['surfaces']):
        first = record[1]; edge = first; seen = set(); vertices = []
        while edge not in seen:
            seen.add(edge); e = data['edges'][edge]
            if surface not in e[4:]: raise ValueError('Surface edge ring changes ownership')
            reverse = e[5] == surface
            vertices.append(e[reverse]); next_edge = e[2+reverse]
            n = data['edges'][next_edge]
            if n[n[5] == surface] != e[not reverse]: raise ValueError('Surface edge ring is disconnected')
            edge = next_edge
        if edge != first or len(vertices) < 3: raise ValueError('Surface edge ring does not close')
        result.append(vertices)
    return result


def number(v):
    # Hex floats preserve the exact source float32, including negative zero.
    return v.hex()+'f' if isinstance(v, float) else str(v)


def row(name, values):
    v = [number(x) for x in values]
    if name == 'bsp3d_nodes': return '{'+v[0]+',{'+','.join(v[1:])+'}}'
    if name == 'planes': return '{{.n={'+','.join(v[:3])+'}},'+v[3]+'}'
    if name == 'bsp2d_nodes': return '{{{.n={'+','.join(v[:2])+'}},'+v[2]+'},{'+','.join(v[3:])+'}}'
    if name == 'edges': return '{'+','.join('{'+','.join(v[i:i+2])+'}' for i in (0,2,4))+'}'
    if name == 'vertices': return '{{.n={'+','.join(v[:3])+'}},'+v[3]+'}'
    return '{'+','.join(v)+'}'


def export(map_path, output):
    output.mkdir(parents=True, exist_ok=True)
    with (output/'collision-export.log').open('w') as log, contextlib.redirect_stdout(log):
        data, spawns = decode(map_path)
    topology = check(data)
    lines = ['/* Generated from the user\'s local Xbox cache. Do not commit. */',
             '#include "blam/collision.h"']
    report = {'source_sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
              'coordinate_basis': 'original Halo XYZ; no rescaling', 'arrays': {},
              'topology': topology, 'spawn_positions': spawns}
    for name, ctype, fmt in ARRAYS:
        lines += [f'static const {ctype} bg_blam_{name}[]={{']
        lines += [row(name, r)+',' for r in data[name]]
        lines += ['};']
        report['arrays'][name] = {'count': len(data[name]), 'stride': struct.calcsize('<'+fmt),
                                 'bytes': len(data[name])*struct.calcsize('<'+fmt)}
    lines += ['#define BLOCK(name) {sizeof(bg_blam_##name)/sizeof(bg_blam_##name[0]),bg_blam_##name,0}',
              'const blam_collision_bsp bg_blam_collision_bsp={',
              '{BLOCK(bsp3d_nodes),BLOCK(planes)},BLOCK(leaves),BLOCK(bsp2d_references),',
              '{BLOCK(bsp2d_nodes)},BLOCK(surfaces),BLOCK(edges),BLOCK(vertices)', '};', '#undef BLOCK']
    report['array_bytes'] = sum(a['bytes'] for a in report['arrays'].values())
    report['n64_root_bytes'] = 96
    (output/'blam_collision_data.c').write_text('\n'.join(lines)+'\n')
    (output/'blam-collision-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('arrays','array_bytes','n64_root_bytes')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map', type=Path, default=Path('build/n64/assets/bloodgulch-decompressed.map'))
    p.add_argument('--output', type=Path, default=Path('build/n64/generated'))
    args = p.parse_args(); export(args.map, args.output)
