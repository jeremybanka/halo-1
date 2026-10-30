"""Blender authoring entry: independent rigid parts, symmetric collapse, UVs retained."""
import json, sys, itertools
from pathlib import Path
import bpy, bmesh

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'port/n64'))
from vehicle_parts import split_vehicle

OUT = ROOT / 'build/vehicle-lods'
OUT.mkdir(parents=True, exist_ok=True)
raw = json.loads((ROOT / 'build/pve-vehicles/source/extended-raw.json').read_text())
scene = bpy.data.scenes.new('Wraith and Shade distance LOD authoring')
bpy.context.window.scene = scene
result = {'models': {}}

def mesh_object(name, triangles, model):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([p for t in triangles for p in t['p']], [],
                     [tuple(range(i*3, i*3+3)) for i in range(len(triangles))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    uv = mesh.uv_layers.new(name='Source UV')
    for i, path in enumerate(model['textures']):
        mat = bpy.data.materials.new(name + ' material ' + str(i))
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(path, check_existing=True)
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = .8
        mesh.materials.append(mat)
    for poly, tri in zip(mesh.polygons, triangles):
        poly.material_index = tri['material']
        for loop, p in zip(poly.loop_indices, tri['uv']): uv.data[loop].uv = p
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
    bm.to_mesh(mesh); bm.free(); mesh.update()
    return obj

for name, model in raw['models'].items():
    triangles = [{'p': [model['vertices'][i] for i in f],
                  'uv': [model['uv'][i] for i in f], 'material': material}
                 for f, material in zip(model['faces'], model['materials'])]
    ordered, rig = split_vehicle(name, {**model, 'triangles': triangles}, model)
    result['models'][name] = {'rig': rig, 'tiers': []}
    for tier, ratio in enumerate((.36, .20) if name == 'wraith' else (.30, .12)):
        parts = []
        for index, part in enumerate(rig['parts']):
            tris = ordered['triangles'][part['first']//3:(part['first']+part['count'])//3]
            tris = [t for t in tris if t['p'][0] != t['p'][1]]
            obj = mesh_object(name + ' ' + str(tier) + ' part ' + str(index), tris, model)
            bpy.context.view_layer.objects.active = obj; obj.select_set(True)
            # Each disconnected shell must retain its height/width/depth. Without
            # this, a cheap global collapse turns Shade feet and barrels into needles.
            bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
            seen=set(); locked=set()
            for vertex in bm.verts:
                if vertex in seen: continue
                todo=[vertex]; seen.add(vertex); component=[]
                while todo:
                    v=todo.pop(); component.append(v)
                    for edge in v.link_edges:
                        other=edge.other_vert(v)
                        if other not in seen:seen.add(other);todo.append(other)
                for axis in range(3):
                    for sign in (-1,1):locked.add(max(component,key=lambda v:sign*v.co[axis]).index)
                if name=='shade' and index==1:
                    for direction in itertools.product((-1,0,1),repeat=3):
                        if any(direction):locked.add(max(component,key=lambda v:sum(v.co[a]*direction[a] for a in range(3))).index)
            # Protect the matching opposite-side points too.
            for i in list(locked):
                p=bm.verts[i].co.copy();p.y=-p.y
                other=min(bm.verts,key=lambda v:(v.co-p).length_squared)
                if (other.co-p).length<.015:locked.add(other.index)
            bm.free()
            allow=obj.vertex_groups.new(name='Interior reduction')
            movable=[v.index for v in obj.data.vertices if v.index not in locked]
            if movable:allow.add(movable,1,'REPLACE')
            modifier = obj.modifiers.new('Symmetric silhouette reduction', 'DECIMATE')
            modifier.ratio = ratio if part['kind'] != 4 else max(ratio, .5)
            if name=='shade' and index==1:modifier.ratio=.45 if tier==0 else .22
            modifier.use_symmetry = True; modifier.symmetry_axis = 'Y'
            modifier.vertex_group=allow.name;modifier.vertex_group_factor=1
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            mesh = obj.data; mesh.calc_loop_triangles(); uv = mesh.uv_layers.active
            exported = []
            for tri in mesh.loop_triangles:
                exported.append({'p': [list(mesh.vertices[i].co) for i in tri.vertices],
                                 'uv': [list(uv.data[i].uv) for i in tri.loops],
                                 'material': mesh.polygons[tri.polygon_index].material_index})
            parts.append({'source_part': index, 'triangles': exported})
            obj.location = ((0 if name == 'wraith' else 7), tier*5, 0)
            obj.select_set(False)
        result['models'][name]['tiers'].append(parts)
        print(name, tier, [len(p['triangles']) for p in parts])
(OUT / 'reduced.json').write_text(json.dumps(result, separators=(',', ':')))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'distance-lods.blend'))
print('Saved', OUT / 'reduced.json')
