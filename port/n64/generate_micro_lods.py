#!/usr/bin/env python3
"""Derive optional tiny far models from locally extracted/reduced game assets.

This recipe writes a separate JSON and provenance report. It does not pack C,
modify existing banks, or select a runtime profile. All generated game content
must remain under ignored build/. Blender runs in a separate factory session.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import platform
from pathlib import Path
import numpy as np
from micro_lod_geometry import restore_materials, support_hull
from model_colors import load_images, bake_triangle, bake_team_mask
from pack_assets import position
from pack_mesh import indexed_mesh, model_color_tolerance

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VEHICLES = ('warthog', 'ghost', 'scorpion', 'banshee')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed_far_inputs(reduced, recipe, generated=None):
    """Recreate actual far RGB/material corners before geometric reduction."""
    selected = set(recipe['models']) | set(recipe['aliases'])
    models, textures = {}, set()
    preview = json.loads((generated/'model-preview.json').read_text()) if generated else None
    for name, source in list(reduced['pickup_lods'].items()) + list(reduced['vehicle_lods'].items()):
        if name not in selected:
            continue
        bank = name + ('_lod' if name in VEHICLES else '_pickup_lod')
        positions, colors, team, materials = [], [], [], []
        images = load_images(source['textures'])
        masks = load_images(source.get('team_masks', []))
        channels = source.get('team_mask_channels', [])
        textures.update(Path(p) for p in source['textures'] + source.get('team_masks', []) if p)
        for triangle in source['triangles']:
            positions.extend([[round(x*1024) for x in position(p, (0, 0, 0))] for p in triangle['p']])
            colors.extend(bake_triangle(triangle, images, source))
            team.extend(bake_team_mask(triangle, masks, channels))
            materials.extend([triangle['material']]*3)
        if name == 'overshield':
            colors = [[238, 92, 52]]*len(colors)
        if name == 'camouflage':
            colors = [[57, 151, 234]]*len(colors)
        if any(team):
            raise ValueError('Static micro recipe must not discard team masks: '+name)
        mesh = indexed_mesh(positions, colors, team, None, None, reorder_static=True,
                            color_tolerance=model_color_tolerance('world', bank), material_keys=materials)
        order = mesh['triangle_order']
        corners = [3*t+c for t in order for c in range(3)]
        model = {'positions': [[v/1024 for v in positions[i]] for i in corners],
                 'colors': [mesh['colors'][i] for i in corners],
                 'materials': [materials[3*t] for t in order],
                 'triangle_count': len(order), 'source_bank': bank,
                 'source_vertices': len(mesh['vertices'])}
        if preview:
            for field in ('positions', 'colors'):
                if model[field] != preview[bank][field]:
                    raise ValueError(f'Far input differs from generated bank: {bank} {field}')
        models[name] = model
    if set(models) != selected:
        raise ValueError('Missing source far models: '+str(selected-set(models)))
    return models, textures


def generate(args):
    output = args.output.resolve()
    if ROOT/'build' not in output.parents:
        raise ValueError('Derived game geometry must be written under ignored build/')
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent/(output.stem+'-work')
    work.mkdir(exist_ok=True)
    recipe_path = args.recipe.resolve()
    recipe = json.loads(recipe_path.read_text())
    if recipe['version'] != 1 or recipe['position_scale'] != 1024:
        raise ValueError('Unsupported micro recipe')
    reduced_path = args.assets.resolve()/'extended-reduced.json'
    reduced = json.loads(reduced_path.read_text())
    generated = args.verify_generated.resolve() if args.verify_generated else None
    models, textures = packed_far_inputs(reduced, recipe, generated)
    files = {reduced_path, recipe_path, Path(__file__).resolve(), HERE/'reduce_micro_lods.py',
             HERE/'micro_lod_geometry.py', HERE/'pack_mesh.py', HERE/'model_colors.py',
             HERE/'pack_assets.py', *textures}
    if generated:
        files.update(generated/name for name in ('model-preview.json', 'models_data.c', 'extended-report.json'))
    hashes = {str(p): sha(p) for p in sorted(files)}
    job = work/'input.json'
    job.write_text(json.dumps({'recipe': recipe, 'models': models}, separators=(',', ':'))+'\n')
    worker_output = work/'collapsed.json'
    blender = args.blender or shutil.which('blender') or '/Applications/Blender.app/Contents/MacOS/Blender'
    subprocess.run([blender, '--background', '--factory-startup', '--python',
                    str(HERE/'reduce_micro_lods.py'), '--', str(job), str(worker_output)], check=True)
    collapsed = json.loads(worker_output.read_text())
    result, details = {}, {}
    for name, settings in recipe['models'].items():
        source = models[name]
        if settings['method'] == 'collapse':
            model = collapsed['models'][name]
        elif settings['method'] == 'support_hull':
            model = support_hull(source, settings['triangles'])
        else:
            raise ValueError('Unknown micro method: '+settings['method'])
        if settings.get('restore_materials'):
            model = restore_materials(model, source, settings['restore_materials'])
        model['source_bank'] = source['source_bank']
        model['maximum_projected_gate_pixels'] = recipe['maximum_projected_pixels']
        points = [[round(v*1024)/1024 for v in p] for p in model['positions']]
        bounds = [[min(p[a] for p in source['positions']) for a in range(3)],
                  [max(p[a] for p in source['positions']) for a in range(3)]]
        excursion = max(0., *(bounds[0][a]-p[a] for p in points for a in range(3)),
                        *(p[a]-bounds[1][a] for p in points for a in range(3)))
        if excursion:
            raise ValueError(f'Micro candidate leaves original far AABB: {name} {excursion}')
        if model['triangle_count'] > source['triangle_count']:
            raise ValueError('Micro candidate exceeds existing far triangles: '+name)
        if not all(math.isfinite(v) for p in points for v in p):
            raise ValueError('Non-finite geometry: '+name)
        model['source_far_bounds'] = bounds
        result[name] = model
        details[name] = {'method': settings['method'], 'triangles': model['triangle_count'],
                         'source_triangles': source['triangle_count'],
                         'source_vertices': source['source_vertices'],
                         'restored_materials': settings.get('restore_materials', []),
                         'outside_source_aabb_max_halo': excursion}
    for path, digest in hashes.items():
        if sha(Path(path)) != digest:
            raise RuntimeError('Input changed during generation: '+path)
    output.write_text(json.dumps({'schema': 'Expanded static corners, engine Y-up Halo units, RGB bytes, per-triangle materials; quantize1024 and protected-weld once.',
                                 'models': result, 'aliases': recipe['aliases'],
                                 'quality_notes': recipe['quality_notes'],
                                 'recipe_version': recipe['version']}, separators=(',', ':'))+'\n')
    proof = {'output_sha256': sha(output), 'blender_version': collapsed['blender_version'],
             'python_version': platform.python_version(), 'numpy_version': np.__version__,
             'inputs_sha256': hashes, 'models': details,
             'status': 'Generated recipe, not a target visual/performance acceptance result'}
    output.with_suffix('.provenance.json').write_text(json.dumps(proof, indent=2)+'\n')
    print('Generated', len(result), 'micro models:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=ROOT/'build/n64/assets')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-generated', type=Path, help='Assert far inputs equal this existing generated bank')
    parser.add_argument('--recipe', type=Path, default=HERE/'micro_lod_recipe.json')
    parser.add_argument('--blender', help='Background Blender executable; factory startup avoids altering open scenes')
    generate(parser.parse_args())
