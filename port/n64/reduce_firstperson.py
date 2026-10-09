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

# Measured against the approved quality meshes in eight matching views. The
# profile is opt-in so isolated experiments never replace the quality baseline.
PERFORMANCE_GUNS = {
    'ar':{'budget':210,'refine':True,'cosmetic_min':2},
    'pistol':{'budget':238},'plasma_pistol':{'budget':221},
    'plasma_rifle':{'budget':255},
    'needler':{'budget':360,'omit_opaque_cores':True},
    'shotgun':{'budget':196,'refine':True,'cosmetic_min':2},
    'sniper':{'budget':306},'rocket':{'budget':224,'cosmetic_min':2},
    'flamethrower':{'budget':238}}


def reduce_firstperson(source, output, hand_budget=220, boundary_strength=0,
                       gun_budgets=None, hand_topology='anatomy', needle_min=8,
                       cosmetic_min=None, feature_minima=None, refine_approved=False,
                       performance_profile=False):
    import bpy
    from mathutils import Quaternion, Vector

    data = json.loads(Path(source).read_text())
    if performance_profile:hand_budget=200;hand_topology='connected'
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
            if hand_topology=='connected':
                labels[i]='left hand' if 'frame l ' in name else 'right hand'
                continue
            # Keep each whole finger connected while retaining its interpolated
            # weights at all three source joints.
            labels[i] = re.sub(r'\s*(low|mid|tip)$', '', name)
            if hand_topology=='continuous' and any(p in name for p in ('upperarm','forearm','wriste')):
                # Preserve the independently weighted fingers, but allow each
                # material's arm/wrist shell to collapse without artificial cuts.
                labels[i] = 'frame l arm' if 'frame l ' in name else 'frame r arm'
        return labels

    def importance_for(model, hands=False, weapon_name=None, approved_baseline=False, settings=None):
        settings=settings if settings is not None else {'needle_min':needle_min,'cosmetic_min':cosmetic_min}
        def importance(material, bone, component):
            name = model.get('material_names', [''] * len(model['textures']))[material]
            if hands:
                return 1.65 if any(x in bone for x in ('index','thumb','middle','ring','pinky')) else 1.2
            for rule in ({} if approved_baseline or performance_profile else (feature_minima or {})).get(weapon_name,[]):
                if (rule.get('bone',bone)==bone and rule.get('material',material)==material
                        and component['face_count']>=rule.get('source_min',0)):
                    return {'weight':rule.get('weight',1),'min':min(rule['minimum'],component['face_count'])}
            if 'needle' in bone:
                return {'weight':2.4, 'min':min(8 if approved_baseline else settings.get('needle_min',8), component['face_count'])}
            if any(x in name for x in ('display','screen','luminous','decal')):
                return 1.4
            if any(x in bone for x in ('magazine','tubes','pump','cover','wing','rod')):
                return 1.25
            if not approved_baseline and settings.get('cosmetic_min') is not None and component['face_count']<=24:
                return {'weight':.65,'min':min(settings['cosmetic_min'],component['face_count'])}
            return 1.0
        return importance

    def refinement_source(model, triangles):
        # Refine the already approved piecewise-planar gun shape in bind pose.
        # Its rigid gun parts retain exact bone identity through the second
        # collapse; no animation or pose inversion is required.
        refined={**model,'vertices':[],'faces':[],'uv':[],'materials':[],'weights':[]}
        for tri in triangles:
            first=len(refined['vertices'])
            refined['vertices'].extend(tri['p']);refined['uv'].extend(tri['uv'])
            refined['faces'].append([first,first+1,first+2]);refined['materials'].append(tri['material'])
            for skin in tri['weights']:
                if len(skin)>2:raise ValueError('Gun refinement requires at most two influences per vertex')
                total=sum(weight for _,weight in skin)
                refined['weights'].append([skin[0][0],skin[1][0] if len(skin)>1 else -1,
                                           skin[1][1]/total if len(skin)>1 else 0])
        return refined

    budgets={**GUN_BUDGETS,**(gun_budgets or {})}
    hands = data['hands']
    hand_obj, hand_tris, hand_weights, hand_report = reduce_geometry(
        scene, hands, 'Xbox hands', hand_budget,
        part_importance=importance_for(hands, True), bone_labels=anatomy_labels(hands),
        partition_colors=False, protect_boundaries=boundary_strength,
        project_surface=hand_topology!='connected', partition_materials=hand_topology!='connected')
    hand_obj.hide_set(True)
    hand_inverse = [m.inverted() for m in globals_for(
        hands['nodes'], [n['parent'] for n in hands['nodes']])]
    result = {'weapons':{}, 'hand_triangle_count':len(hand_tris),
              'reduction_report':{'hands':hand_report}, 'hand_topology':hand_topology,
              'reference_note':data.get('reference_note', ''),
              'reduction_profile':'performance' if performance_profile else 'quality-or-custom'}
    limits = {'idle':4, 'fire':4, 'reload':8, 'melee':6}
    for index, (name, weapon) in enumerate(data['weapons'].items()):
        gun = weapon['gun']
        settings=PERFORMANCE_GUNS[name] if performance_profile else {
            'budget':budgets[name],'refine':refine_approved,'needle_min':needle_min,'cosmetic_min':cosmetic_min}
        refine=settings.get('refine',False)
        obj, gun_tris, gun_weights, report = reduce_geometry(
            scene, gun, 'FP ' + name, GUN_BUDGETS[name] if refine else settings['budget'],
            part_importance=importance_for(gun,weapon_name=name,approved_baseline=refine,settings=settings), partition_colors=False, protect_boundaries=boundary_strength, project_surface='outside')
        if refine:
            obj.hide_set(True)
            refined=refinement_source(gun,gun_tris);baseline_report=report
            obj,gun_tris,gun_weights,report=reduce_geometry(
                scene,refined,'FP refined '+name,settings['budget'],
                part_importance=importance_for(refined,weapon_name=name,settings=settings),partition_colors=False,
                protect_boundaries=boundary_strength,project_surface='outside')
            report['approved_baseline_triangles']=baseline_report['triangles']
        if settings.get('omit_opaque_cores'):
            # The N64 glass proxy is opaque. Retain all sixteen complete outer
            # crystals and omit only their original additive interior planes.
            omitted={i for i,part in enumerate(report['parts'])
                     if part['material']==3 and 'needle' in part['bone']}
            outer=[part for part in report['parts'] if part['material']==2 and 'needle' in part['bone']]
            if len(omitted)!=16 or len(outer)!=16 or any(part['triangles']<=0 for part in outer):
                raise ValueError('Needler performance profile expects all sixteen original crystal shells and core planes')
            keep=[i for i,tri in enumerate(gun_tris) if tri['part'] not in omitted]
            report['opaque_shell_core_triangles_removed']=len(gun_tris)-len(keep)
            # Keep the reviewable .blend mesh consistent with the packed JSON.
            import bmesh
            mesh=bmesh.new();mesh.from_mesh(obj.data);mesh.faces.ensure_lookup_table()
            retained=set(keep)
            bmesh.ops.delete(mesh,geom=[face for i,face in enumerate(mesh.faces) if i not in retained],context='FACES')
            mesh.to_mesh(obj.data);mesh.free()
            gun_weights=[point for i in keep for point in gun_weights[i*3:i*3+3]]
            gun_tris=[gun_tris[i] for i in keep];report['triangles']=len(gun_tris)
            for i in omitted:
                report['parts'][i]['triangles']=0
                report['parts'][i]['omitted_reason']='interior additive plane under opaque N64 crystal proxy'
        if name=='sniper':
            # The source screen sits on the housing's rear plane. At the N64
            # animation bank's 1/256-unit precision, rounding can put either
            # surface in front. Lift the two display surfaces 1.5 coordinate
            # steps toward the player in bind space, before skinning every pose.
            screen_materials={i for i,n in enumerate(gun['material_names']) if n.endswith((' screen',' subscreen'))}
            shift=1.5/256
            moved=set()
            for i,tri in enumerate(gun_tris):
                if tri['material'] not in screen_materials:continue
                for p in tri['p']:p[0]-=shift
                for p,weights in gun_weights[i*3:i*3+3]:
                    # Weighted points may be shared by adjacent corners.
                    if id(p) not in moved:p.x-=shift;moved.add(id(p))
            vertices={v for face in obj.data.polygons if face.material_index in screen_materials for v in face.vertices}
            for v in vertices:obj.data.vertices[v].co.x-=shift
            report['display_separation']=shift
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
    from plasma_meters import repair_meters, blender_review
    repair_meters(result, data)
    blender_review(result, scene)
    Path(output).write_text(json.dumps(result))
    for layer in scene.view_layers:layer.update()
    bpy.data.libraries.write(str(Path(output).with_suffix('.blend')), {scene})
    print(json.dumps({name:{'hands':w['hand_triangle_count'], 'gun':w['gun_triangle_count']}
                      for name, w in result['weapons'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--hand-budget', type=int, default=220)
    parser.add_argument('--boundary-strength', type=float, default=0)
    parser.add_argument('--budget-file',type=Path,help='Optional JSON weapon-name to triangle-budget overrides')
    parser.add_argument('--hand-topology',choices=('anatomy','continuous','connected'),default='anatomy')
    parser.add_argument('--needle-min',type=int,default=8,help='Minimum triangles per original needle component; each of the 16 crystals is retained')
    parser.add_argument('--cosmetic-min',type=int,help='Optional minimum for tiny static cosmetic components')
    parser.add_argument('--feature-minima',type=Path,help='Optional JSON per-weapon feature allocation rules')
    parser.add_argument('--refine-approved',action='store_true',help='First reproduce the approved gun geometry, then reduce that piecewise-planar mesh with the requested budgets')
    parser.add_argument('--performance-profile',action='store_true',help='Use the verified per-weapon performance allocations and joined 200-budget hands')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    budgets=json.loads(args.budget_file.read_text()) if args.budget_file else None
    features=json.loads(args.feature_minima.read_text()) if args.feature_minima else None
    reduce_firstperson(args.source, args.output, args.hand_budget, args.boundary_strength,
                       budgets,args.hand_topology,args.needle_min,args.cosmetic_min,features,args.refine_approved,args.performance_profile)
