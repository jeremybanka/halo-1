#!/usr/bin/env python3
"""Expand emitted terrain C against immutable source geometry, UVs and colors."""
import argparse
import collections
import json
import math
from pathlib import Path
import re


def validate(source, generated):
    data = json.loads(Path(source).read_text())
    text = (Path(generated) / 'render_data.c').read_text()
    body = text.split('T3DVertPacked bg_vertices[]', 1)[1].split('};', 1)[0]
    pairs = re.findall(r'\{\{([^}]+)\},0,\{([^}]+)\},0,(0x[0-9a-f]+),(0x[0-9a-f]+),\{([^}]+)\},\{([^}]+)\}\}', body)
    vertices = []
    for a, b, ca, cb, ua, ub in pairs:
        for p, c, uv in ((a, ca, ua), (b, cb, ub)):
            color = int(c, 16)
            assert color & 255 == 255
            vertices.append((tuple(map(int, p.split(','))), tuple((color >> shift) & 255 for shift in (24, 16, 8)), tuple(map(int, uv.split(',')))))
    body = text.split('const bg_chunk bg_chunks[]={', 1)[1].split('};', 1)[0]
    chunks = [(int(a), int(b), int(c), tuple(map(int, bounds.split(','))), int(d), int(e))
              for a, b, c, bounds, d, e in re.findall(r'\{(\d+),(\d+),(\d+),\{([^}]+)\},(\d+),(\d+)\}', body)]
    indices = list(map(int, text.split('bg_chunk_indices[]', 1)[1].split('={', 1)[1].split('};', 1)[0].split(',')))
    groups = collections.defaultdict(list)
    for triangle in data['triangles']:
        points = [(p[0] - 68., p[2], -p[1] - 118.) for p in triangle['p']]
        center = [sum(p[a] for p in points) / 3 for a in range(3)]
        groups[(triangle['material'], int(center[0] // 12), int(center[2] // 12))].append((triangle, points))
    originals = [(key, tri, points) for key, group in sorted(groups.items()) for tri, points in group]
    corner = end = max_error = 0
    for first, count, material, bounds, ii, ic in chunks:
        assert first == end and first % 2 == 0 and 0 < count <= 60
        assert ii % 4 == 0 and 0 < ic <= 120 and ic % 3 == 0
        assert ((count + 1) & ~1) * 36 + ((ic + 3) & ~3) * 2 <= 70 * 36
        local = indices[ii:ii + ic]
        assert len(local) == ic and all(0 <= i < count for i in local)
        assert bounds == tuple(fn(v[0][a] for v in vertices[first:first + count]) for fn in (min, max) for a in range(3))
        group_key = None
        for ti in range(0, ic, 3):
            key, triangle, points = originals[corner // 3]
            if group_key is None:
                group_key = key
            assert key == group_key and material == key[0]
            u = [points[1][a] - points[0][a] for a in range(3)]
            v = [points[2][a] - points[0][a] for a in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            length = math.sqrt(sum(x * x for x in n))
            n = [x / length for x in n] if length > 1e-9 else [0, 1, 0]
            shade = round(255 * (.60 + .40 * max(0, sum(a * b for a, b in zip(n, [.25, .83, .49])))))
            offset = [math.floor(min(v[a] for v in triangle['uv'])) for a in range(2)]
            shifts = []
            for j in range(3):
                p, rgb, uv = vertices[first + local[ti + j]]
                assert p == tuple(round(x * 32) for x in points[j])
                max_error = max(max_error, max(abs(x - shade) for x in rgb))
                expected = [round((triangle['uv'][j][a] - offset[a]) * 1024) for a in range(2)]
                shift = tuple(expected[a] - uv[a] for a in range(2))
                assert all(x % 1024 == 0 for x in shift)
                shifts.append(shift)
            assert shifts[0] == shifts[1] == shifts[2]
            actual_uv=[vertices[first + local[ti + j]][2] for j in range(3)]
            assert all(max(v[a] for v in actual_uv)-min(v[a] for v in actual_uv)<=32767 for a in range(2))
            corner += 3
        end = first + ((count + 1) & ~1)
    assert corner == len(data['triangles']) * 3 and max_error <= 8
    count = int(re.search(r'bg_vertex_count=(\d+)', text)[1])
    assert count == end
    return {'triangles': corner // 3, 'chunks': len(chunks), 'stored_vertices': end, 'max_original_rgb_delta': max_error}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('build/n64/assets/bloodgulch-reduced.json'))
    parser.add_argument('--generated', type=Path, default=Path('build/n64/generated'))
    args = parser.parse_args()
    print(json.dumps(validate(args.source, args.generated), indent=2))
