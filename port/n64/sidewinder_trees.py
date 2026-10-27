"""Snow-pine prototype: retain authored branch tiers, simplify each branch card.

The medium mesh retains every foliage component. The lean mesh omits the
small two-triangle twig cards, while retaining all larger branch tiers. Both
replace subdivided branch cards with two triangles using their original four
UV corner positions, source textures, and original trunks. No global collapse.
"""
import collections
import contextlib
import json
import math
from pathlib import Path
import re
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/n64-sidewinder-trees'
PREVIOUS = ROOT / 'build/n64-sidewinder-cluster-terrain'
PROMPT = "Oh, yeah. Make the trees an immediate priority. Definitely start there. Preserve their essential character and appearance while doing it more simply. They are douglas fir, are they not?"


def extract():
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.model.model_decompilation import extract_model
    OUT.mkdir(exist_ok=True)
    with (OUT / 'extraction.log').open('w') as log, contextlib.redirect_stdout(log):
        halo = Halo1Map()
        halo.load_map(ROOT / 'build/n64-map-survey/sidewinder-decompressed.map')
        entries = halo.tag_index.tag_index
        scenery = json.loads((ROOT / 'halo64-assets/generated/maps/maps-report.json').read_text())['maps']['sidewinder']['scenery']
        result = []
        for path in sorted({r['path'] for r in scenery if 'trees' in r['path']}):
            ix = next(i for i, e in enumerate(entries) if e.path == path and e.class_1.enum_name == 'scenery')
            obj = halo.get_meta(ix)
            model_path = obj.obje_attrs.model.filepath
            ix = next(i for i, e in enumerate(entries) if e.path == model_path and e.class_1.enum_name == 'model')
            model = halo.get_meta(ix)
            halo.meta_to_tag_data(model, 'mode', entries[ix])
            models = extract_model(model, write_jms=False)
            lods = [dict(name=m.name, vertices=[[v.pos_x/100, v.pos_y/100, v.pos_z/100, v.tex_u, v.tex_v] for v in m.verts],
                         faces=[[t.v0, t.v1, t.v2] for t in m.tris], materials=[t.shader for t in m.tris]) for m in models]
            result.append(dict(path=path, model_path=model_path, shaders=[s.shader.filepath for s in model.shaders.STEPTREE],
                               placements=[r for r in scenery if r['path'] == path], lods=lods))
        (OUT / 'source-models.json').write_text(json.dumps(result)+'\n')
    print([(r['path'], len(r['placements']), [(m['name'], len(m['faces'])) for m in r['lods']]) for r in result])


def components(model):
    vertices = np.array(model['vertices'])
    faces = [f for f, material in zip(model['faces'], model['materials']) if material == 1]
    parent = list(range(len(faces)))
    edges = {}
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, face in enumerate(faces):
        points = [tuple(np.round(vertices[v, :3], 5)) for v in face]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[a], points[b])))
            if edge in edges:
                parent[root(i)] = root(edges[edge])
            else:
                edges[edge] = i
    groups = collections.defaultdict(list)
    for i, face in enumerate(faces):
        groups[root(i)].append(face)
    return list(groups.values())


def simplify(model, variant):
    vertices = model['vertices']
    rows = [(f, 0) for f, material in zip(model['faces'], model['materials']) if material == 0]
    details = []
    for ci, faces in enumerate(components(model)):
        if len(faces) == 2:
            if variant == 'medium':
                rows.extend((f, 1) for f in faces)
            details.append(dict(component=ci, before=2, after=2 if variant == 'medium' else 0, kind='small twig card'))
            continue
        ids = sorted({vi for face in faces for vi in face})
        points = np.array([vertices[vi] for vi in ids])
        minimum, maximum = points[:, 3:].min(0), points[:, 3:].max(0)
        uv = [(minimum[0], minimum[1]), (maximum[0], minimum[1]), (maximum[0], maximum[1]), (minimum[0], maximum[1])]
        corners = []
        for value in uv:
            distances = np.linalg.norm(points[:, 3:]-value, axis=1)
            at = int(np.argmin(distances))
            assert distances[at] < 1e-5
            corners.append(ids[at])
        # Keep the source orientation; material remains double sided in game.
        old_normal = sum((np.cross(np.array(vertices[f[1]][:3])-vertices[f[0]][:3], np.array(vertices[f[2]][:3])-vertices[f[0]][:3]) for f in faces), np.zeros(3))
        new_normal = np.cross(np.array(vertices[corners[1]][:3])-vertices[corners[0]][:3], np.array(vertices[corners[2]][:3])-vertices[corners[0]][:3])
        if old_normal @ new_normal < 0:
            corners.reverse()
        rows.extend([(corners[:3], 1), ([corners[0], corners[2], corners[3]], 1)])
        details.append(dict(component=ci, before=len(faces), after=2, kind='branch tier; original UV corner positions'))
    return dict(name=model['name']+' '+variant, vertices=vertices, faces=[f for f, m in rows], materials=[m for f, m in rows], details=details)


def author():
    """Run through Blender MCP; keep source objects beside the two proposals."""
    import bpy
    source = json.loads((OUT / 'source-models.json').read_text())
    scene = bpy.data.scenes.new('Sidewinder snow pines — tier-preserving prototypes')
    bpy.context.window.scene = scene
    scene.view_settings.view_transform = 'Standard'
    materials = []
    for mi in (18, 19):
        material = bpy.data.materials.new('Snow pine source material '+str(mi))
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial')
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = bpy.data.images.load(str(ROOT / f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{mi}.png'), check_existing=True)
        texture.interpolation = 'Closest'
        emission = nodes.new('ShaderNodeEmission')
        links = material.node_tree.links
        links.new(texture.outputs['Color'], emission.inputs['Color'])
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(texture.outputs['Alpha'], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])
        materials.append(material)
    result = []
    for species, entry in enumerate(source):
        model = entry['lods'][0]
        variants = {'source': model, **{name: simplify(model, name) for name in ('medium', 'lean')}}
        for column, (name, data) in enumerate(variants.items()):
            mesh = bpy.data.meshes.new(f'{species} {name} snow pine')
            mesh.from_pydata([v[:3] for v in data['vertices']], [], data['faces'])
            for material in materials:
                mesh.materials.append(material)
            uv = mesh.uv_layers.new(name='Original branch UV')
            for polygon, material in zip(mesh.polygons, data['materials']):
                polygon.material_index = material
                for li in polygon.loop_indices:
                    v = data['vertices'][mesh.loops[li].vertex_index]
                    uv.data[li].uv = v[3:]
            mesh.update()
            obj = bpy.data.objects.new(('Large' if species == 0 else 'Small')+' snow pine — '+name, mesh)
            scene.collection.objects.link(obj)
            obj.location = (column*6, species*7, 0)
            obj.select_set(True)
            # Export evaluated Blender data, so packing uses the inspected mesh.
            mesh.calc_loop_triangles()
            exported_vertices = []
            exported_faces = []
            exported_materials = []
            for triangle in mesh.loop_triangles:
                face = []
                for vi, li in zip(triangle.vertices, triangle.loops):
                    face.append(len(exported_vertices))
                    exported_vertices.append([*mesh.vertices[vi].co, *uv.data[li].uv])
                exported_faces.append(face)
                exported_materials.append(triangle.material_index)
            if name != 'source':
                variants[name] = {**data, 'vertices': exported_vertices, 'faces': exported_faces, 'materials': exported_materials}
        result.append(dict(path=entry['path'], variants={k: v for k, v in variants.items() if k != 'source'}))
    (OUT / 'authored-models.json').write_text(json.dumps(result)+'\n')
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with bpy.context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_selected()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'tree-appraisal.blend'))
    print([(r['path'], {k: len(v['faces']) for k, v in r['variants'].items()}) for r in result])


def pack(variant='lean'):
    from pack_maps import bank, packed, uv_safe_triangles
    from pack_terrain import indexed_terrain
    from remap_sidewinder_visibility import sections, batches, sha
    source = json.loads((OUT / 'source-models.json').read_text())
    authored = ({r['path']: r['lods'][0] for r in source} if variant == 'control' else
                {r['path']: r['variants'][variant] for r in json.loads((OUT / 'authored-models.json').read_text())})
    output = OUT / variant
    output.mkdir(exist_ok=True)
    original = (PREVIOUS / 'candidate-maps/sidewinder.map64').read_bytes()
    ss = sections(original)
    masks = json.loads((PREVIOUS / 'data/visibility.json').read_text())['chunk_masks']
    vertices, indices, chunks, proof, new_masks = bytearray(), bytearray(), [], [], []
    original_chunks = list(struct.iter_unpack('>IHH6hHH', ss[1]))
    for bi, c in enumerate(original_chunks):
        first, count, material, *rest = c
        if material in (18, 19):
            continue
        at, n = rest[-2:]
        chunks.append((len(vertices)//16, count, material, *rest[:6], len(indices)//2, n))
        vertices.extend(ss[0][first//2*32:(first+((count+1)&~1))//2*32])
        indices.extend(ss[2][at*2:(at+((n+3)&~3))*2])
        proof.append(dict(old_batch=bi, unchanged=True))
        new_masks.append(masks[bi])
    # Group by material, then individual placement. Each batch belongs to one
    # tree, bounding its frustum extent. No added occlusion claim: fail open.
    tree_inventory = []
    for material in (0, 1):
        for entry in source:
            model = authored[entry['path']]
            for ti, placement in enumerate(entry['placements']):
                assert placement['rotation'] == [0, 0, 0]
                position = placement['position']
                triangles = []
                for face, mi in zip(model['faces'], model['materials']):
                    if mi != material:
                        continue
                    triangle = []
                    for vi in reversed(face):
                        x, y, z, u, v = model['vertices'][vi]
                        x += position[0]; y += position[1]; z += position[2]
                        triangle.append([round(x*256), round(z*256), round(-y*256), 255, 255, 255, round(u*1024), round((1-v)*1024)])
                    triangles.append(triangle)
                start_batch = len(chunks)
                load_count = 0
                for batch in indexed_terrain(uv_safe_triangles(triangles), color_delta=0, uv_period=1024):
                    vs, ix = batch['vertices'], batch['indices']
                    first, at = len(vertices)//16, len(indices)//2
                    padded = vs+([vs[-1]] if len(vs)%2 else [])
                    rgba = lambda v: (v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
                    vertices.extend(packed('3hH3hHII4h', [(*a[:3], 0, *b[:3], 0, rgba(a), rgba(b), *a[6:], *b[6:]) for a, b in zip(padded[::2], padded[1::2])]))
                    indices.extend(packed('H', [(i,) for i in ix]))
                    while len(indices)%8:
                        indices.extend(b'\0\0')
                    bounds = [math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
                    chunks.append((first, len(vs), material+18, *bounds, at, len(ix)))
                    proof.append(dict(old_batch=None, unchanged=False, tree=entry['path'], instance=ti))
                    new_masks.append((1<<35)-1)
                    load_count += len(padded)
                tree_inventory.append(dict(path=entry['path'], instance=ti, material=material+18, loads=load_count, batches=len(chunks)-start_batch))
    # Preserve each material's original draw-order position. Alpha-tested tree
    # geometry writes depth and must precede the later transparent effects.
    first_tree = {material: next(i for i, c in enumerate(original_chunks) if c[2] == material) for material in (18, 19)}
    order = sorted(range(len(chunks)), key=lambda i: (proof[i]['old_batch'] if proof[i]['unchanged'] else first_tree[chunks[i][2]], i))
    chunks, proof, new_masks = ([values[i] for i in order] for values in (chunks, proof, new_masks))
    assert len(chunks) <= 512 and len(indices)//2 < 65536
    ss[0], ss[1], ss[2] = bytes(vertices), packed('IHH6hHH', chunks), bytes(indices)
    directory = output / 'candidate-maps'
    directory.mkdir(exist_ok=True)
    for p in (PREVIOUS / 'candidate-maps').iterdir():
        if p.name != 'sidewinder.map64' and not (directory / p.name).exists():
            (directory / p.name).symlink_to(p.resolve())
    result = bank(directory / 'sidewinder.map64', 1, ss)
    payload = (directory / 'sidewinder.map64').read_bytes()
    assert sections(original)[3:] == sections(payload)[3:]
    before, after = list(batches(original)), list(batches(payload))
    for i, row in enumerate(proof):
        if row['unchanged']:
            assert before[row['old_batch']][1] == after[i][1]
    result.update(variant=variant, chunks=len(chunks), vertices=len(vertices)//16, triangles=sum(c[-1]//3 for c in chunks),
                  batches=proof, chunk_masks=new_masks, unchanged_batches=sum(r['unchanged'] for r in proof),
                  unchanged_nonrender_sections=True, source_bank_sha256=sha(original), candidate_sha256=sha(payload), tree_inventory=tree_inventory,
                  source_models_sha256=sha((OUT / 'source-models.json').read_bytes()), authored_models_sha256=sha((OUT / 'authored-models.json').read_bytes()))
    (output / 'packing-report.json').write_text(json.dumps(result, indent=2)+'\n')
    code = (PREVIOUS / 'cameras/visibility-data.c').read_text()
    code, n = re.subn(r'static const uint64_t chunks\[\]=\{[^}]+\};', 'static const uint64_t chunks[]={'+','.join('UINT64_C('+str(m)+')' for m in new_masks)+'};', code)
    assert n == 1
    code, n = re.subn(r'(bg_world_pvs=\{nodes,planes,leaves,rows,chunks,\d+,\d+,\d+,35,)478,', lambda m: m[1]+str(len(chunks))+',', code)
    assert n == 1
    (output / 'visibility-data.c').write_text(code)
    print({k: result[k] for k in ['variant', 'vertices', 'chunks', 'triangles', 'unchanged_batches']})


if __name__ == '__main__':
    if sys.argv[1:] and sys.argv[1] == 'pack':
        pack(sys.argv[2] if len(sys.argv) > 2 else 'lean')
    else:
        extract()
