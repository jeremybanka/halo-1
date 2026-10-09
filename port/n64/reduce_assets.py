"""Run in Blender: reduce the extracted map, preserving material/UV boundaries.

Creates a separate scene and writes only build artifacts. The current scene's
objects and any existing .blend file are untouched.
"""
import json
import math
from pathlib import Path


def reduce_assets(source, output):
    import bpy
    import bmesh
    from mathutils import Quaternion

    data = json.loads(Path(source).read_text())
    output = Path(output)
    scene = bpy.data.scenes.new('Halo N64 - Blood Gulch')
    if bpy.context.window:
        bpy.context.window.scene = scene
    materials = []
    for entry in data['materials']:
        mat = bpy.data.materials.new('N64 ' + entry['name'].split('\\')[-1])
        mat.use_nodes = True
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        color = (0.45, 0.5, 0.38, 1)
        if 'blue' in entry['name']: color = (0.12, 0.35, 0.95, 1)
        if 'red' in entry['name']: color = (0.85, 0.12, 0.1, 1)
        shader.inputs['Base Color'].default_value = color
        mat.diffuse_color = color
        if entry['texture']:
            node = mat.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = bpy.data.images.load(entry['texture'], check_existing=True)
            mat.node_tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
        materials.append(mat)

    vertices, faces, uv, face_materials = [], [], [], []
    architecture = {i for i, m in enumerate(data['materials'])
                    if m['name'].split('\\')[-1] not in
                    ('cap_cliff01b', 'beavercreek boulder', 'blood ground')}
    for group in data['groups']:
        if group['material'] in architecture:continue
        start = len(vertices)
        vertices.extend(group['vertices'])
        uv.extend(group['uv'])
        faces.extend([[start+i for i in f] for f in group['faces']])
        face_materials.extend([group['material']]*len(group['faces']))
    mesh = bpy.data.meshes.new('Blood Gulch source BSP')
    mesh.from_pydata(vertices, [], faces)
    for mat in materials: mesh.materials.append(mat)
    layer = mesh.uv_layers.new(name='Halo diffuse UV')
    for polygon, material in zip(mesh.polygons, face_materials):
        polygon.material_index = material
        for loop in polygon.loop_indices:
            u, v = uv[mesh.loops[loop].vertex_index]
            layer.data[loop].uv = (u, 1-v)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    terrain = bpy.data.objects.new('Blood Gulch - N64 environment', mesh)
    scene.collection.objects.link(terrain)
    # Pin the open BSP/architecture joins. Reducing across a base/ground seam
    # moves the ground away from the original ramp, exposing the sky below it.
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
    boundary={v.index for e in bm.edges if e.is_boundary for v in e.verts};bm.free()
    group=terrain.vertex_groups.new(name='Landscape interior')
    group.add([v.index for v in mesh.vertices if v.index not in boundary],1,'REPLACE')
    modifier = terrain.modifiers.new('N64 environment triangle budget', 'DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = 0.35
    modifier.vertex_group=group.name
    modifier.vertex_group_factor=1000
    modifier.use_collapse_triangulate = True

    def evaluated(obj):
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        evaluated_obj = obj.evaluated_get(depsgraph)
        result = evaluated_obj.to_mesh()
        result.calc_loop_triangles()
        layer = result.uv_layers.active
        triangles = []
        for triangle in result.loop_triangles:
            verts = [list(result.vertices[i].co) for i in triangle.vertices]
            uvs = [list(layer.data[i].uv) for i in triangle.loops] if layer else [[0,0]]*3
            triangles.append({'p': verts, 'uv': [[u, 1-v] for u,v in uvs],
                              'material': triangle.material_index})
        evaluated_obj.to_mesh_clear()
        return triangles

    # Preserve the shipped BSP architecture verbatim. Its doors, ramp lips,
    # roof openings and interior floors are collision surfaces, not distant
    # landscape. Reduce the landscape separately, with its joins pinned.
    reduced = evaluated(terrain)
    key=lambda p:tuple(round(v,4) for v in p)
    pinned={key(mesh.vertices[i].co) for i in boundary}
    if pinned-{key(p) for t in reduced for p in t['p']}:
        raise ValueError('Landscape reduction displaced an original BSP boundary')
    preserved = [{'p':[group['vertices'][i] for i in face],
                  'uv':[group['uv'][i] for i in face], 'material':group['material']}
                 for group in data['groups'] if group['material'] in architecture
                 for face in group['faces']]
    result = {'source_sha256': data['source_sha256'], 'original_triangles': data['bsp_triangles'],
              'architecture_triangles':len(preserved),
              'architecture_materials':sorted(architecture),
              'landscape_boundary_vertices':len(pinned),
              'materials': data['materials'],
              'triangles': [t for t in reduced if t['material'] not in architecture] + preserved,
              'spawns': data['spawns'], 'flags': data['flags'], 'models': {}}
    for name, model in data['models'].items():
        mesh = bpy.data.meshes.new('Halo ' + name)
        mesh.from_pydata(model['vertices'], [], model['faces'])
        for polygon, material in zip(mesh.polygons, model['materials']): polygon.material_index = material
        obj = bpy.data.objects.new('N64 ' + name, mesh)
        scene.collection.objects.link(obj)
        if name == 'spartan':
            mod = obj.modifiers.new('N64 player triangle budget', 'DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = 0.55
            mod.use_collapse_triangulate = True
        result['models'][name] = evaluated(obj)
        obj.hide_set(True)
    output.write_text(json.dumps(result))
    # The review scene must show exactly the exported hybrid, not the modifier.
    terrain.hide_set(True)
    preview = bpy.data.meshes.new('Preserved architecture and reduced landscape')
    preview.from_pydata([p for t in result['triangles'] for p in t['p']], [],
                        [(i*3,i*3+1,i*3+2) for i in range(len(result['triangles']))])
    for mat in materials: preview.materials.append(mat)
    layer = preview.uv_layers.new(name='Halo diffuse UV')
    for polygon, tri in zip(preview.polygons, result['triangles']):
        polygon.material_index = tri['material']
        for loop, (u,v) in zip(polygon.loop_indices, tri['uv']):layer.data[loop].uv=(u,1-v)
    terrain = bpy.data.objects.new('Blood Gulch - exact architecture', preview)
    scene.collection.objects.link(terrain)
    scene.view_layers[0].objects.active = terrain
    terrain.select_set(True, view_layer=scene.view_layers[0])
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            region = area.spaces.active.region_3d
            region.view_location = (68, -118, 0)
            region.view_distance = 190
            region.view_rotation = Quaternion((0.88,0.28,0.12,0.36)).normalized()
    # Write a library containing this scene, without changing the user's file.
    bpy.data.libraries.write(str(output.with_suffix('.blend')), {scene})
    print(json.dumps({'scene':scene.name, 'environment_triangles':len(result['triangles']),
                     'model_triangles':{k:len(v) for k,v in result['models'].items()}}))


if __name__ == '__main__':
    import sys
    args = sys.argv[sys.argv.index('--')+1:]
    reduce_assets(args[0], args[1])
