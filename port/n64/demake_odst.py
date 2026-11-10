"""Fresh, component-local ODST demake from the untouched retail extraction.

Run in factory-startup Blender. The discarded ODST reduction is never an input.
Preserve source faces/weights, save the solid checkpoint, and soften budgets
when boundary, volume or surface-error constraints reject a collapse.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector, interpolate
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pack_assets import position


def paint_source(model):
    """Partition the authored pale crown paint before any collapse."""
    model = {**model, 'materials': list(model['materials'])}
    mi = next(i for i, m in enumerate(model['material_metadata']) if m['path'].endswith('odst_helmet'))
    image = bpy.data.images.load(model['textures'][mi], check_existing=True)
    w, h = image.size; pixels = np.array(image.pixels[:]).reshape(h, w, 4)
    selected = []
    for fi, (face, material) in enumerate(zip(model['faces'], model['materials'])):
        if material != mi: continue
        points = np.array([model['vertices'][i] for i in face])
        uv = np.mean([model['uv'][i] for i in face], axis=0)
        rgb = pixels[h-1-int(uv[1]%1*h), int(uv[0]%1*w), :3]
        if rgb.mean() > 90/255 and abs(points[:,1].mean()) < .02:
            selected.append(fi)
    assert selected, 'Missing original crown paint'
    paint = len(model['material_metadata'])
    for fi in selected: model['materials'][fi] = paint
    model['material_metadata'] = [*model['material_metadata'], {**model['material_metadata'][mi], 'path':'odst_crown_stripe', 'role':'profile/team color'}]
    model['textures'] = [*model['textures'], model['textures'][mi]]
    model['stripe_source_faces'] = selected
    return model

def components(model):
    groups = defaultdict(list)
    for fi, key in enumerate(zip(model['regions'], model['materials'])):
        groups[key].append(fi)
    result = []
    keys = [tuple(round(x, 6) for x in p) for p in model['vertices']]
    for (region, material), faces in groups.items():
        adjacency = defaultdict(list)
        for fi in faces:
            for vi in model['faces'][fi]:
                adjacency[keys[vi]].append(fi)
        remaining = set(faces)
        index = 0
        while remaining:
            pending = [min(remaining)]
            remaining.remove(pending[0])
            part = []
            while pending:
                fi = pending.pop()
                part.append(fi)
                for vi in model['faces'][fi]:
                    for other in adjacency[keys[vi]]:
                        if other in remaining:
                            remaining.remove(other)
                            pending.append(other)
            result.append(dict(id=f'{region}-{material:02d}:{index:03d}',
                               region=region, material=material, faces=sorted(part)))
            index += 1
    return result


def globals_for(nodes, states=None):
    result = []
    for i, n in enumerate(states or nodes):
        x, y, z, w = n['q']
        matrix = Quaternion((w, -x, -y, -z)).to_matrix().to_4x4()
        matrix.translation = Vector(n['p'])
        parent = nodes[i]['parent']
        result.append(result[parent] @ matrix if parent >= 0 else matrix)
    return result


def source_part(model, part):
    lookup = {}
    points, faces, source_vertices = [], [], []
    for fi in part['faces']:
        face = []
        for vi in model['faces'][fi]:
            # Weld only identical bind positions AND influences.
            key = (tuple(round(x, 6) for x in model['vertices'][vi]),
                   tuple((b, round(w, 6)) for b, w in model['skin_weights'][vi]))
            if key not in lookup:
                lookup[key] = len(points)
                points.append(model['vertices'][vi])
                source_vertices.append(vi)
            face.append(lookup[key])
        faces.append(face)
    return points, faces, source_vertices


def budget(part, count, lod):
    name, region = part['id'], part['region']
    if name in {'gear-02:000', 'gear-18:000', 'gear-20:000'}:
        return 0, 'omit tiny fastening/decal overlay; retain parent surface'
    if lod and name in {*(f'gear-02:{i:03d}' for i in (6,7,8,9,14,15,20,21,22,23,24,25,26,27,28,29,30,31))}:
        return 0, 'far: omit small belt equipment and layered pack straps; retain original main pack and pouches'
    if region == 'helmet':
        return max(16, round(count * (.40 if lod == 0 else .16))), 'protect helmet and visor identity'
    if name == 'body-23:002':
        return (600 if lod == 0 else 200), 'continuous garment, joints and boots; coverage outranks budget'
    if region == 'hands':
        return max(8, round(count * (.25 if lod == 0 else .08))), 'retain articulation and original skinning'
    return max(8 if lod == 0 else 4, round(count * (.30 if lod == 0 else .10))), 'retain original plate/equipment surface'


def reduce_part(scene, model, part, target, lod=0):
    points, faces, source_vertices = source_part(model, part)
    tree = BVHTree.FromPolygons([Vector(p) for p in points], faces, all_triangles=True)
    edges = defaultdict(int)
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            edges[tuple(sorted((a, b)))] += 1
    rim = {v for e, count in edges.items() if count == 1 for v in e}
    original_volume = abs(sum(Vector(points[f[0]]).dot(Vector(points[f[1]]).cross(Vector(points[f[2]]))) for f in faces) / 6)
    requested = target
    while True:
        mesh = bpy.data.meshes.new(part['id'])
        mesh.from_pydata(points, [], faces)
        ob = bpy.data.objects.new(part['id'], mesh)
        scene.collection.objects.link(ob)
        if target < len(faces):
            group = ob.vertex_groups.new(name='Interiors only; preserve original open rim')
            group.add(list(range(len(points))), 1, 'REPLACE')
            if rim:
                group.add(sorted(rim), .02 if lod==0 else .1, 'REPLACE')
            mod = ob.modifiers.new('Component-local constrained collapse', 'DECIMATE')
            mod.ratio = target / len(faces)
            mod.use_collapse_triangulate = True
            mod.vertex_group = group.name
            mod.vertex_group_factor = 1000
        deps = bpy.context.evaluated_depsgraph_get()
        deps.update()
        ev = ob.evaluated_get(deps)
        reduced = ev.to_mesh()
        reduced.calc_loop_triangles()
        xyz = [v.co.copy() for v in reduced.vertices]
        fs = [list(t.vertices) for t in reduced.loop_triangles]
        rim_error = max((min((v - Vector(points[i])).length for v in xyz) for i in rim), default=0)
        distances = [tree.find_nearest(p)[3] for p in xyz]
        volume = abs(sum(xyz[f[0]].dot(xyz[f[1]].cross(xyz[f[2]])) for f in fs) / 6)
        volume_ok = bool(rim) or original_volume < 1e-10 or (.90 if lod==0 else .80) <= volume / original_volume <= 1.10
        okay = rim_error < (.002 if lod==0 else .004) and max(distances, default=0) < (.006 if lod==0 else .008) and volume_ok
        ev.to_mesh_clear()
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        if okay or target >= len(faces):
            break
        target = min(len(faces), max(target + 2, round(target * 1.3)))
    triangles = []
    for face in fs:
        tri = dict(p=[list(xyz[i]) for i in face], uv=[], weights=[],
                   material=part['material'], component=part['id'], source_faces=[])
        for vi in face:
            hit, _, fi, _ = tree.find_nearest(xyz[vi])
            ids = model['faces'][part['faces'][fi]]
            bary = np.maximum(0, interpolate.poly_3d_calc([Vector(model['vertices'][i]) for i in ids], hit))
            bary /= bary.sum()
            weights = defaultdict(float)
            for i, value in zip(ids, bary):
                for bone, weight in model['skin_weights'][i]:
                    weights[bone] += value * weight
            values = sorted(((b, w) for b, w in weights.items() if w > 1e-8), key=lambda x: -x[1])[:4]
            total = sum(w for b, w in values)
            tri['weights'].append([(b, w / total) for b, w in values])
            tri['uv'].append((bary @ np.array([model['uv'][i] for i in ids])).tolist())
            tri['source_faces'].append(dict(face=part['faces'][fi], barycentric=bary.tolist()))
        triangles.append(tri)
    return triangles, dict(source_triangles=len(faces), requested=requested, actual=len(fs),
                           boundary_vertices=len(rim), maximum_rim_error=float(rim_error),
                           maximum_sampled_surface_error=float(max(distances, default=0)),
                           closed_volume_ratio=float(volume / original_volume) if original_volume > 1e-10 and not rim else None)


def bake(model, triangles, clips):
    nodes = model['nodes']
    inv = [m.inverted() for m in globals_for(nodes)]
    weights = [w for t in triangles for w in t['weights']]
    points = [Vector(p) for t in triangles for p in t['p']]
    idle = clips['idle']['frames'][0]
    marker = model['markers']['right hand'][0]
    marker_matrix = globals_for([dict(parent=-1, **marker)])[0]
    basis = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
    result = []
    for name, clip in clips.items():
        count = min(12, len(clip['frames']))
        frames, grips = [], []
        for fi in range(count):
            states = clip['frames'][round(fi * (len(clip['frames']) - 1) / max(1, count - 1))]
            if clip['type'] == 'overlay':
                combined = []
                for ni, (a, b) in enumerate(zip(idle, states)):
                    ax, ay, az, aw = a['q']; bx, by, bz, bw = b['q']
                    q = Quaternion((bw, bx, by, bz)) @ Quaternion((aw, ax, ay, az)) if clip['rot_flags'] & (1 << ni) else Quaternion((aw, ax, ay, az))
                    combined.append(dict(p=[a['p'][i] + (b['p'][i] if clip['trans_flags'] & (1 << ni) else 0) for i in range(3)], q=[q.x, q.y, q.z, q.w]))
                states = combined
            pose = globals_for(nodes, states)
            skin = [p @ b for p, b in zip(pose, inv)]
            frame = []
            for p, values in zip(points, weights):
                v = sum(((skin[b] @ p) * w for b, w in values), Vector((0, 0, 0)))
                frame.append(position(v, (0, 0, 0)))
            hand = basis @ pose[marker['node']] @ marker_matrix @ basis.inverted()
            q = hand.to_quaternion().normalized()
            grips.append([*hand.translation, q.x, q.y, q.z, q.w])
            frames.append(frame)
        result.append(dict(name=name, duration=clip['duration'], frames=frames, grips=grips))
        print('BAKED', name, count, flush=True)
    return result


def run(source, extra_motion, output, pilot=False):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = json.loads(source.read_text()); model = paint_source(raw['models']['spartan'])
    parts = components(model)
    (output / 'source-components.json').write_text(json.dumps(parts, indent=2))
    clips = dict(raw['animations']); clips.update(json.loads(Path(extra_motion).read_text()))
    scene = bpy.context.scene
    lods, ledger = [], []
    for lod in range(1 if pilot else 2):
        triangles = []
        for part in parts:
            if pilot and part['region'] != 'l_shoulder':
                continue
            target, decision = budget(part, len(part['faces']), lod)
            if target:
                tris, report = reduce_part(scene, model, part, target, lod)
                triangles.extend(tris)
            else:
                report = dict(source_triangles=len(part['faces']), actual=0, requested=0)
            ledger.append(dict(lod=lod, id=part['id'], decision=decision, **report))
            print('PART', lod, part['id'], report['source_triangles'], report['actual'], flush=True)
        animations = [] if pilot else bake(model, triangles, clips)
        arrays = {}
        for i, clip in enumerate(animations):
            arrays['frames_'+str(i)] = np.array(clip.pop('frames'), dtype=np.float32)
            arrays['grips_'+str(i)] = np.array(clip.pop('grips'), dtype=np.float32)
            clip['frames'] = len(arrays['frames_'+str(i)])
        if arrays: np.savez_compressed(output / f'poses-{lod}.npz', **arrays)
        lods.append(dict(triangles=triangles, animations=animations))
    result = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  policy='CHARACTER_DEMAKE.md: fresh source, component ledger, protected rims and soft budgets',
                  nodes=model['nodes'], materials=model['material_metadata'], textures=model['textures'], stripe_source_faces=model['stripe_source_faces'], lods=lods, ledger=ledger)
    (output / ('pilot.json' if pilot else 'solid.json')).write_text(json.dumps(result))
    (output / 'component-decisions.json').write_text(json.dumps(ledger, indent=2))
    print('DEMAKE', [len(l['triangles']) for l in lods], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('extra_motion'); parser.add_argument('output')
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    run(args.source, args.extra_motion, args.output, args.pilot)
