"""Reduce Xbox FP models by material/anatomy and bake their original animation.

Run using an independent Blender background process. Source references retain
full geometry/textures; only this output contains the N64 mesh reduction.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_reduce import reduce_geometry

GUN_BUDGETS = {'ar':300, 'pistol':280, 'plasma_pistol':260,
               'plasma_rifle':300, 'needler':360, 'shotgun':280,
               'sniper':360, 'rocket':320, 'flamethrower':280}
MATERIAL_METADATA = ('material_names', 'material_types', 'material_colors',
                     'material_overrides', 'texture_sources', 'material_multipurpose',
                     'material_change_source')


def reduce_firstperson(source, output, hand_budget=220, boundary_strength=0):
    import bpy
    from mathutils import Quaternion, Vector

    data = json.loads(Path(source).read_text())
    scene = bpy.data.scenes.new('Halo N64 - First person')
    if bpy.context.window:
        bpy.context.window.scene = scene

    def globals_for(states, parents):
        result = [None] * len(states)
        def visit(i):
            if result[i] is not None:
                return result[i]
            n = states[i]
            x, y, z, w = n['q']
            matrix = Quaternion((w, -x, -y, -z)).to_matrix().to_4x4()
            matrix.translation = Vector(n['p'])
            parent = parents[i]
            result[i] = visit(parent) @ matrix if parent >= 0 and parent != i else matrix
            return result[i]
        for i in range(len(states)):
            visit(i)
        return result

    def anatomy_labels(model):
        labels = {}
        for i, node in enumerate(model['nodes']):
            name = node['name']
            # Keep each whole finger connected while retaining its interpolated
            # weights at all three source joints.
            labels[i] = re.sub(r'\s*(low|mid|tip)$', '', name)
        return labels

    def importance_for(model, hands=False):
        def importance(material, bone, component):
            name = model.get('material_names', [''] * len(model['textures']))[material]
            if hands:
                return 1.65 if any(x in bone for x in ('index','thumb','middle','ring','pinky')) else 1.2
            if 'needle' in bone:
                return {'weight':2.4, 'min':min(8, component['face_count'])}
            if any(x in name for x in ('display','screen','luminous','decal')):
                return 1.4
            if any(x in bone for x in ('magazine','tubes','pump','cover','wing','rod')):
                return 1.25
            return 1.0
        return importance

    hands = data['hands']
    hand_obj, hand_tris, hand_weights, hand_report = reduce_geometry(
        scene, hands, 'Xbox hands', hand_budget,
        part_importance=importance_for(hands, True), bone_labels=anatomy_labels(hands),
        partition_colors=False, protect_boundaries=boundary_strength, project_surface=True)
    hand_obj.hide_set(True)
    hand_inverse = [m.inverted() for m in globals_for(
        hands['nodes'], [n['parent'] for n in hands['nodes']])]
    result = {'weapons':{}, 'hand_triangle_count':len(hand_tris),
              'reduction_report':{'hands':hand_report},
              'reference_note':data.get('reference_note', '')}
    limits = {'idle':4, 'fire':4, 'reload':8, 'melee':6}
    for index, (name, weapon) in enumerate(data['weapons'].items()):
        gun = weapon['gun']
        obj, gun_tris, gun_weights, report = reduce_geometry(
            scene, gun, 'FP ' + name, GUN_BUDGETS[name],
            part_importance=importance_for(gun), partition_colors=False, protect_boundaries=boundary_strength, project_surface='outside')
        obj.location = (index * .5, 0, 0)
        result['reduction_report'][name] = report
        gun_inverse = [m.inverted() for m in globals_for(
            gun['nodes'], [n['parent'] for n in gun['nodes']])]
        skeleton = weapon['nodes']
        lookup = {n['name']:i for i, n in enumerate(skeleton)}
        clips = {}
        for clip_name, clip in weapon['clips'].items():
            frames = []
            count = min(limits[clip_name], len(clip['frames']))
            for fi in range(count):
                states = clip['frames'][round(fi * (len(clip['frames']) - 1) / max(1, count - 1))]
                pose = globals_for(states, [n['parent'] for n in skeleton])
                points = []
                for model, weighted, inverse in [(hands, hand_weights, hand_inverse),
                                                  (gun, gun_weights, gun_inverse)]:
                    skin = [pose[lookup[n['name']]] @ inverse[i] for i, n in enumerate(model['nodes'])]
                    for p, weights in weighted:
                        v = Vector((0, 0, 0))
                        for bone, weight in weights:
                            v += (skin[bone] @ p) * weight
                        if not all(math.isfinite(x) for x in v):
                            raise ValueError('Nonfinite FP skin')
                        points.append(list(v))
                frames.append(points)
            clips[clip_name] = {'frames':frames, 'duration':clip['duration'], 'tag_name':clip['name']}
        triangles = json.loads(json.dumps(hand_tris + gun_tris))
        for triangle in triangles[len(hand_tris):]:
            triangle['material'] += len(hands['textures'])
        for ti, triangle in enumerate(triangles):
            triangle['p'] = clips['idle']['frames'][0][ti * 3:ti * 3 + 3]
        packed = {'triangles':triangles, 'textures':hands['textures'] + gun['textures'],
                  'clips':clips, 'hand_triangle_count':len(hand_tris),
                  'gun_triangle_count':len(gun_tris), 'source_lod':gun.get('source_lod'),
                  'source_triangle_count':len(gun['faces'])}
        for key in MATERIAL_METADATA:
            packed[key] = (hands.get(key, [None] * len(hands['textures'])) +
                           gun.get(key, [None] * len(gun['textures'])))
        result['weapons'][name] = packed
    Path(output).write_text(json.dumps(result))
    bpy.data.libraries.write(str(Path(output).with_suffix('.blend')), {scene})
    print(json.dumps({name:{'hands':w['hand_triangle_count'], 'gun':w['gun_triangle_count']}
                      for name, w in result['weapons'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--hand-budget', type=int, default=220)
    parser.add_argument('--boundary-strength', type=float, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    reduce_firstperson(args.source, args.output, args.hand_budget, args.boundary_strength)
