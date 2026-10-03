"""Blender background worker; invoked by generate_micro_lods.py, not the UI."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def collapse(name, model, target):
    vertices, lookup, faces = [], {}, []
    for triangle in range(model['triangle_count']):
        face = []
        for point in model['positions'][3*triangle:3*triangle+3]:
            key = tuple(point)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(point)
            face.append(lookup[key])
        if len(set(face)) == 3:
            faces.append((face, triangle))
    bounds = [[min(p[a] for p in vertices), max(p[a] for p in vertices)] for a in range(3)]
    surface = BVHTree.FromPolygons([Vector(p) for p in vertices], [f for f, _ in faces], all_triangles=True)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], [f for f, _ in faces])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for i in range(max(model['materials'])+1):
        mesh.materials.append(bpy.data.materials.new('source'+str(i)))
    attr = mesh.color_attributes.new(name='Source RGB', type='FLOAT_COLOR', domain='CORNER')
    for polygon, (_, triangle) in zip(mesh.polygons, faces):
        polygon.material_index = model['materials'][triangle]
        for j, loop in enumerate(polygon.loop_indices):
            attr.data[loop].color = tuple(c/255 for c in model['colors'][triangle*3+j]) + (1.,)
    modifier = obj.modifiers.new('Micro collapse', 'DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = min(1., target/len(faces))
    modifier.use_collapse_triangulate = True
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    reduced = evaluated.to_mesh()
    reduced.calc_loop_triangles()
    color = reduced.color_attributes['Source RGB']
    result = {'positions': [], 'colors': [], 'materials': []}
    for triangle in reduced.loop_triangles:
        for vertex, loop in zip(triangle.vertices, triangle.loops):
            point = reduced.vertices[vertex].co.copy()
            if any(point[a] < bounds[a][0]-1e-8 or point[a] > bounds[a][1]+1e-8 for a in range(3)):
                hit = surface.find_nearest(point)
                if hit:
                    point = hit[0]
            result['positions'].append([float(x) for x in point])
            result['colors'].append([round(min(1, max(0, c))*255) for c in color.data[loop].color[:3]])
        result['materials'].append(triangle.material_index)
    result['triangle_count'] = len(result['materials'])
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return result


if __name__ == '__main__':
    source, output = map(Path, sys.argv[sys.argv.index('--')+1:])
    job = json.loads(source.read_text())
    models = {}
    for name, settings in job['recipe']['models'].items():
        if settings['method'] == 'collapse':
            models[name] = collapse(name, job['models'][name], settings['triangles'])
            print(name, models[name]['triangle_count'], flush=True)
    output.write_text(json.dumps({'blender_version': bpy.app.version_string, 'models': models}, separators=(',', ':'))+'\n')
