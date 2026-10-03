#!/usr/bin/env python3
"""Pack animated, on-weapon AR digits and original Needler ammunition poses.

The approved FP bank is read only. Supplemental indices address its exact
indexed vertices, and provenance rejects reuse after the base bank changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from pack_assets import position
from pack_firstperson import prepare_model

CLIPS = ('idle', 'fire', 'reload', 'melee')
AR_SCALE = 4096
AR_ENLARGEMENT = 2.0


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rotate(r, p):
    return [sum(r[i][j] * p[j] for j in range(3)) for i in range(3)]


def inverse_point(transform, p):
    r, origin = transform
    return [sum(r[j][i] * (p[j] - origin[j]) for j in range(3)) for i in range(3)]


def transform_point(transform, p):
    r, origin = transform
    return [origin[i] + v for i, v in enumerate(rotate(r, p))]


def quaternion_product(a, b):
    x, y, z, w = a; X, Y, Z, W = b
    return [w*X+x*W+y*Z-z*Y, w*Y+y*W+z*X-x*Z,
            w*Z+z*W+x*Y-y*X, w*W-x*X-y*Y-z*Z]


def globals_for(states, skeleton):
    result = [None] * len(states)
    def visit(i):
        if result[i] is not None:
            return result[i]
        x, y, z, w = states[i]['q']; p = states[i]['p']
        # Same conjugated JMS quaternion convention as reduce_firstperson.py.
        r = [[1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w)],
             [2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w)],
             [2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y)]]
        parent = skeleton[i]['parent']
        if parent >= 0 and parent != i:
            pr, pp = visit(parent); rp = rotate(pr, p)
            p = [pp[a] + rp[a] for a in range(3)]; r = mul(pr, r)
        result[i] = r, p
        return result[i]
    for i in range(len(states)):
        visit(i)
    return result


def overlay_states(base, overlay, flags):
    result = []
    for i, (b, o) in enumerate(zip(base, overlay)):
        q = quaternion_product(o['q'], b['q']) if flags['rot'] & (1 << i) else b['q']
        p = [b['p'][a] + o['p'][a] for a in range(3)] if flags['trans'] & (1 << i) else b['p']
        if flags['scale'] & (1 << i) and o['s'] != 1:
            raise ValueError('Unexpected Needler scale channel')
        result.append({'q': q, 'p': p})
    return result


def prepare_ar(reduced, metadata):
    w = reduced['weapons']['ar']; offset = len(w['textures']) - 8
    corners = []; uv = []; permutations = []
    for m in sorted(metadata['ar']['materials'], key=lambda m: -m['permutation']):
        matching = [i for i, t in enumerate(w['triangles']) if t['material'] == m['material'] + offset]
        if len(matching) != 2:
            raise ValueError('AR original numeric quad was not preserved')
        seen = {}
        for i in matching:
            for c in range(3):
                key = tuple(w['triangles'][i]['p'][c]) + tuple(w['triangles'][i]['uv'][c])
                if key not in seen:
                    seen[key] = len(corners); corners.append(i*3+c); uv.append(w['triangles'][i]['uv'][c])
        if len(seen) != 4:
            raise ValueError('AR numeric surface must contain four unique corners')
        permutations.append(m['permutation'])
    poses = []
    for name in CLIPS:
        frames = []
        for frame in w['clips'][name]['frames']:
            points = [frame[c] for c in corners]
            center = [sum(p[a] for p in points)/8 for a in range(3)]
            # Source face and animation, deliberately 2x larger for 160x120.
            # A dark opaque texture supplies the enlarged screen backing.
            frames.append([[round(v * AR_SCALE) for v in position(
                [center[a] + AR_ENLARGEMENT*(p[a]-center[a]) for a in range(3)], (0, 0, 0))] for p in points])
        poses.append(frames)
    atlas = Image.new('RGB', (100, 16), (0, 0, 0))
    textures = metadata['ar']['materials'][0]['textures']
    for digit, path in enumerate(textures):
        image = Image.open(path).convert('RGB')
        # Source numeric quads address the central 32x48 region of each 64x64
        # bitmap. Use those original glyphs, with black padding against bleed.
        glyph = image.crop((16, 7, 49, 55)).resize((8, 12), Image.Resampling.LANCZOS)
        atlas.paste(glyph, (digit*10+1, 2))
    pixels = [((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|1 for r, g, b in atlas.getdata()]
    local_uv = []
    for q in range(2):
        chunk = uv[q*4:q*4+4]; us = [p[0] for p in chunk]; vs = [p[1] for p in chunk]
        local_uv.extend([[round((1+(u-min(us))/(max(us)-min(us))*7)*32),
                          round((2+(v-min(vs))/(max(vs)-min(vs))*11)*32)] for u, v in chunk])
    return {'poses': poses, 'uv': local_uv, 'pixels': pixels, 'atlas': atlas,
            'corners': corners, 'permutations': permutations}


def prepare_needler(raw, reduced, metadata):
    original = raw['weapons']['needler']; w = reduced['weapons']['needler']
    mesh, _, _ = prepare_model(w, 'needler')
    skeleton = original['nodes']; lookup = {n['name']: i for i, n in enumerate(skeleton)}
    gun_nodes = original['gun']['nodes']; idle = globals_for(original['clips']['idle']['frames'][0], skeleton)
    affected = []; local_points = []; bones = []
    for index, corner in enumerate(mesh['sources']):
        tri = w['triangles'][corner//3]
        if corner < w['hand_triangle_count']*3:
            continue
        weights = tri['weights'][corner%3]
        if len(weights) != 1 or weights[0][1] != 1:
            if any('needle' in gun_nodes[b]['name'] for b, _ in weights):
                raise ValueError('Needle rigid bone identity was lost')
            continue
        bone = weights[0][0]; name = gun_nodes[bone]['name']
        if 'needle' not in name:
            continue
        bone = lookup[name]
        affected.append(index); bones.append(bone)
        local_points.append(inverse_point(idle[bone], tri['p'][corner%3]))
    if set(bones) != {i for i, n in enumerate(skeleton) if 'needle' in n['name']}:
        raise ValueError('All sixteen original needle components must survive')
    # Deduplicate COMPLETE clip trajectories across all ammo states, never only
    # a rest pose. All original RGB/UV/indices remain untouched in the base bank.
    transforms = []; clip_offsets = []; clip_frames = []
    for name in CLIPS:
        count = len(w['clips'][name]['frames']); full = original['clips'][name]['frames']
        clip_offsets.append(len(transforms)); clip_frames.append(count)
        for f in range(count):
            state = full[round(f*(len(full)-1)/max(1, count-1))]
            transforms.append([globals_for(overlay_states(state, overlay, metadata['needler']['flags']), skeleton)
                               for overlay in metadata['needler']['frames']])
    tracks = []; track_lookup = {}; ammo_indices = []
    visible_counts = []
    for ammo in range(21):
        overlay = metadata['needler']['frames'][ammo]
        folded = {bone for bone in set(bones) if sum(v*v for v in overlay[bone]['q'][:3]) > .2}
        visible_counts.append(16-len(folded))
        for local, bone in zip(local_points, bones):
            # The original empty-state rotations fold the crystals inside the
            # opaque shell. FP rendering intentionally disables depth testing;
            # collapse those fully folded components instead of letting later
            # pink triangles show through the shell. Partly/fully extended
            # states retain their exact original overlay transformations.
            point = [0, 0, 0] if bone in folded else local
            trajectory = tuple(tuple(round(v*256) for v in position(transform_point(frame[ammo][bone], point), (0, 0, 0)))
                               for frame in transforms)
            if trajectory not in track_lookup:
                track_lookup[trajectory] = len(tracks); tracks.append(trajectory)
            ammo_indices.append(track_lookup[trajectory])
    origin = [min(p[a] for track in tracks for p in track) for a in range(3)]
    values = [track[f][a]-origin[a] for f in range(len(transforms)) for track in tracks for a in range(3)]
    if min(values) < 0 or max(values) > 255:
        raise ValueError('Needler ammo trajectory exceeds lossless byte span')
    if len(tracks)>65535 or len(mesh['sources'])>65535 or any(v>65535 for v in affected):
        raise ValueError('Needler indexed vertex/track count exceeds uint16')
    if any(v>255 for v in clip_offsets+clip_frames):
        raise ValueError('Needler clip offset/frame count exceeds uint8')
    return {'vertices': affected, 'bones': bones, 'tracks': len(tracks), 'indices': ammo_indices,
            'origin': origin, 'values': values, 'clip_offsets': clip_offsets, 'clip_frames': clip_frames,
            'base_vertices': len(mesh['sources']), 'frames': len(transforms), 'visible_crystals': visible_counts}


def pack(assets, output):
    assets = Path(assets); output = Path(output); output.mkdir(parents=True, exist_ok=True)
    raw = json.loads((assets/'firstperson-raw.json').read_text())
    reduced = json.loads((assets/'firstperson-reduced.json').read_text())
    metadata = json.loads((assets/'firstperson-ammo.json').read_text())
    ar = prepare_ar(reduced, metadata); needle = prepare_needler(raw, reduced, metadata)
    lines = ['/* Generated from owned Xbox FP ammo sources. Do not commit. */', '#include "asset_fp_ammo.h"']
    def emit(kind, name, values, static=False, aligned=False):
        lines.append(('static ' if static else '') + 'const '+kind+' '+name+'[]'+
                     (' __attribute__((aligned(16)))' if aligned else '')+'={'+','.join(map(str, values))+'};')
    for i, frames in enumerate(ar['poses']):
        emit('int16_t', 'ar_ammo_pose_'+str(i), [v for frame in frames for p in frame for v in p], True)
    lines.append('const bg_ar_ammo_clip bg_ar_ammo_clips[4]={'+','.join(
        '{ar_ammo_pose_'+str(i)+','+str(len(frames))+'}' for i, frames in enumerate(ar['poses']))+'};')
    emit('int16_t', 'bg_ar_ammo_uv', [v for p in ar['uv'] for v in p])
    emit('uint16_t', 'bg_ar_ammo_texture', ar['pixels'], aligned=True)
    emit('uint16_t', 'needle_vertices', needle['vertices'], True)
    emit('uint16_t', 'needle_indices', needle['indices'], True)
    emit('uint8_t', 'needle_positions', needle['values'], True)
    lines.append('const bg_needler_ammo_asset bg_needler_ammo={needle_positions,needle_indices,needle_vertices,'+
                 ','.join(map(str, [needle['tracks'], len(needle['vertices']), needle['base_vertices']]))+',{'+
                 ','.join(map(str, needle['origin']))+'},{'+','.join(map(str, needle['clip_offsets']))+'},{'+
                 ','.join(map(str, needle['clip_frames']))+'}};')
    (output/'firstperson_ammo_data.c').write_text('\n'.join(lines)+'\n')
    ar['atlas'].save(output/'ar-ammo-atlas.png')
    inputs = [assets/n for n in ('firstperson-raw.json', 'firstperson-reduced.json', 'firstperson-ammo.json')]
    inputs += [output/'firstperson_data.c'] if (output/'firstperson_data.c').exists() else []
    report = {'ar': {'triangles': 4, 'vertices': 8, 'scale': AR_SCALE, 'panel_enlargement': AR_ENLARGEMENT,
                    'permutations': ar['permutations'], 'source_corners': ar['corners'], 'texture_bytes': len(ar['pixels'])*2,
                    'animation_bytes': sum(len(f)*8*3*2 for f in ar['poses'])},
              'needler': {k: v for k, v in needle.items() if k not in ('values', 'indices')},
              'needler_bytes': len(needle['values'])+2*len(needle['indices'])+2*len(needle['vertices']),
              'inputs': {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
              'generated_sha256': hashlib.sha256((output/'firstperson_ammo_data.c').read_bytes()).hexdigest(),
              'note': 'Native 21-state overlay applied to all 16 rigid crystal components; fully folded crystals collapse because FP depth is disabled. Partial/full positions remain original. Reload timing normalizes to the demake duration and predicts loaded+reserve. Original additive numeric shader is an opaque dark-backed texture on an enlarged physical panel.'}
    (output/'firstperson-ammo-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('needler', 'inputs')}, indent=2))
    return ar, needle, report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets', type=Path, default=Path('build/n64/assets'))
    p.add_argument('--output', type=Path, default=Path('build/n64/generated'))
    a = p.parse_args(); pack(a.assets, a.output)
