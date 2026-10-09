#!/usr/bin/env python3
"""Optional tiny-LOD supplement to the ordinary model audit.

Keeps the original 59 entries and their quality aggregate unchanged. Tiny
models have a separate projected-size gate, eight directions including bottom,
and four subpixel phases at each of 4, 6 and 8 pixels. No target timing claim.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from audit_models import Mesh, source_mesh, render, matching_bounds, camera_basis, label, compare, texture_paths
from pack_mesh import indexed_mesh, model_color_tolerance

VIEWS = (('front', (1, .02, 0)), ('right', (0, .02, 1)),
         ('rear', (-1, .02, 0)), ('left', (0, .02, -1)),
         ('front 3/4', (1, .4, 1)), ('rear 3/4', (-1, .4, -1)),
         ('top', (.001, 1, .001)), ('bottom', (.001, -1, .001)))
PHASES = ((0, 0), (.25, .25), (.5, .5), (.75, .75))
VEHICLES = ('warthog', 'ghost', 'scorpion', 'banshee')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_c(source, previews, text):
    """Decode emitted vertex/index arrays; check geometry and shader seams."""
    pair = re.compile(r'\{\{(-?\d+),(-?\d+),(-?\d+)\},0,\{(-?\d+),(-?\d+),(-?\d+)\},0,0x([0-9a-fA-F]+),0x([0-9a-fA-F]+),')
    proof = {}
    for name, model in source.items():
        prefix = 'micro_'+name
        body = re.search(r'static T3DVertPacked '+prefix+r'\[\].*?=\{(.*?)\n\};', text, re.S)
        assert body, name
        positions, colors = [], []
        for item in pair.findall(body[1]):
            positions.extend((tuple(map(int, item[:3])), tuple(map(int, item[3:6]))))
            for rgba in item[6:]:
                value = int(rgba, 16)
                assert value & 255 == 255
                colors.append([(value >> shift) & 255 for shift in (24, 16, 8)])
        match = re.search(r'static int16_t '+prefix+r'_indices\[\][^=]*=\{(.*?)\};', text, re.S)
        assert match, name
        indices = list(map(int, re.findall(r'-?\d+', match[1])))
        match = re.search(r'static const bg_mesh_batch '+prefix+r'_batches\[\]=\{(.*?)\};', text, re.S)
        assert match, name
        batches = [tuple(map(int, b)) for b in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}', match[1])]
        corners, end = [], 0
        for first, count, start, size in batches:
            assert first == end and first % 2 == 0 and 0 < count <= 60 and count % 2 == 0
            assert start % 4 == 0 and 0 < size <= 120 and size % 3 == 0
            local = indices[start:start+size]
            assert len(local) == size and all(0 <= i < count for i in local)
            corners.extend(first+i for i in local)
            end = first+count
        assert end == len(positions) and len(corners) == model['triangle_count']*3
        preview = previews[name]
        assert preview['positions'] == [[v/1024 for v in positions[i]] for i in corners], name
        assert preview['colors'] == [colors[i] for i in corners], name
        original_positions = [tuple(round(v*1024) for v in p) for p in model['positions']]
        materials = [m for m in model['materials'] for _ in range(3)]
        tolerance = model_color_tolerance('world', model.get('source_bank', name))
        expected = indexed_mesh(original_positions, model['colors'], [0]*len(materials), None, None,
                                reorder_static=True, color_tolerance=tolerance, material_keys=materials)
        order = [3*t+c for t in expected['triangle_order'] for c in range(3)]
        assert [positions[i] for i in corners] == [original_positions[i] for i in order], name
        sharing, maximum = {}, 0
        for source_corner, vertex in zip(order, corners):
            material = materials[source_corner]
            if vertex in sharing:
                assert sharing[vertex] == material, (name, 'material seam')
            sharing[vertex] = material
            delta = max(abs(a-b) for a, b in zip(model['colors'][source_corner], colors[vertex]))
            assert delta <= tolerance, (name, 'source color drift')
            maximum = max(maximum, delta)
        proof[name] = {'vertices': len(positions), 'triangles': len(corners)//3,
                       'batches': len(batches), 'maximum_source_rgb_delta': maximum,
                       'color_tolerance': tolerance, 'material_boundaries_preserved': True}
    return proof


def native_metric(before, after, old_mask, new_mask):
    intersection, union = old_mask & new_mask, old_mask | new_mask
    a, b = np.array(before, float), np.array(after, float)
    return {'silhouette_iou': float(intersection.sum()/union.sum()) if union.any() else 1.,
            'changed_mask_pixels': int(np.sum(old_mask != new_mask)),
            'before_pixels': int(old_mask.sum()), 'after_pixels': int(new_mask.sum()),
            'lost_whole_visible_model': bool(old_mask.any() and not new_mask.any()),
            'overlap_rgb_mae': float(abs(a-b)[intersection].mean()) if intersection.any() else None}


def audit_micro(bank, baseline, reference, output, external_proof=None):
    bank, baseline, reference, output = map(lambda p: Path(p).resolve(), (bank, baseline, reference, output))
    output.mkdir(parents=True, exist_ok=True)
    (output/'images').mkdir(exist_ok=True)
    report = load(bank/'micro-report.json')
    source_path = Path(report['source'])
    source = load(source_path)
    quality_notes = source.get('quality_notes', load(Path(__file__).with_name('micro_lod_recipe.json'))['quality_notes'])
    previews = load(bank/'micro-preview.json')
    old = load(baseline/'model-preview.json')
    original = load(reference)
    files = [source_path, bank/'micro-report.json', bank/'micro-preview.json', bank/'micro_data.c',
             baseline/'model-preview.json', baseline/'models_data.c', reference]
    if external_proof:
        files.append(Path(external_proof).resolve())
    textures = set()
    for name in source['models']:
        model = original['models'][name]
        textures.update(Path(p) for p in texture_paths(model) if p)
    files.extend(sorted(textures))
    hashes = {str(p): sha(p) for p in files}
    if report['source_sha256'] != sha(source_path) or report['generated_c_sha256'] != sha(bank/'micro_data.c'):
        raise ValueError('Stale micro provenance')
    if report['baseline_c_sha256'] != sha(baseline/'models_data.c'):
        raise ValueError('Micro bank was generated against a different far bank')
    c_proof = validate_c(source['models'], previews, (bank/'micro_data.c').read_text())
    results = {}
    for name, model in source['models'].items():
        old_name = name+('_lod' if name in VEHICLES else '_pickup_lod')
        to_mesh = lambda m: Mesh(np.array(m['positions']).reshape(-1, 3, 3), np.array(m['colors'], float).reshape(-1, 3, 3))
        meshes = [source_mesh(original['models'][name]), to_mesh(old[old_name]), to_mesh(previews[name])]
        hero = Image.new('RGB', (3*224, 32+len(VIEWS)*184), 'white')
        sheets = {span: Image.new('RGB', (3*192, 32+len(VIEWS)*208), 'white') for span in (4, 6, 8)}
        for i, title in enumerate(('Original highest LOD', 'Current far', 'Tiny candidate')):
            label(hero, title, (i*224+4, 4), 13)
            for sheet in sheets.values():
                label(sheet, title, (i*192+4, 4), 12)
        native, hero_metrics = [], []
        for row, (angle, direction) in enumerate(VIEWS):
            bounds = matching_bounds(meshes[:2], direction)
            _, right, up = camera_basis(direction)
            frames = [render(m, bounds, direction) for m in meshes]
            for i, (image, _) in enumerate(frames):
                hero.paste(image, (i*224, 32+row*184))
            hero_metrics.append({'angle': angle,
                                 'far_vs_original': compare(frames[0][0], frames[1][0], frames[0][1], frames[1][1]),
                                 'micro_vs_original': compare(frames[0][0], frames[2][0], frames[0][1], frames[2][1])})
            for span, sheet in sheets.items():
                for phase, (dx, dy) in enumerate(PHASES):
                    scale = span/max(bounds[1])
                    shifted = bounds[0]-right*dx/scale+up*dy/scale, bounds[1]
                    frames = [render(m, shifted, direction, 160, 120, pixel_span=span) for m in meshes]
                    for i, (image, _) in enumerate(frames):
                        crop = image.crop((64, 44, 96, 76)).resize((96, 96), Image.Resampling.NEAREST)
                        sheet.paste(crop, (i*192+(phase % 2)*96, 32+row*208+(phase//2)*96))
                    native.append({'angle': angle, 'extent_pixels': span, 'phase': [dx, dy],
                                   'vs_current': native_metric(frames[1][0], frames[2][0], frames[1][1], frames[2][1]),
                                   'vs_original': native_metric(frames[0][0], frames[2][0], frames[0][1], frames[2][1])})
                for i in range(3):
                    label(sheet, angle, (i*192+4, 32+row*208+192), 11)
        hero.save(output/'images'/(name+'-hero.png'))
        for span, sheet in sheets.items():
            sheet.save(output/'images'/f'{name}-{span}px.png')
        results[name] = {**c_proof[name], 'old_far_triangles': old[old_name]['triangle_count'],
                         'angles': hero_metrics, 'native': native,
                         'quality_note': quality_notes.get(name, '')}
        print('Micro audit:', name, flush=True)
    for path, digest in hashes.items():
        if sha(Path(path)) != digest:
            raise RuntimeError('Micro audit input changed: '+path)
    manifest = {'status': 'Offline tiny-model quality supplement; target acceptance and timing are separate evidence',
                'renderer': 'CPU barycentric z-buffer, two-sided, no N64 coverage AA; exact decoded C geometry/RGB',
                'angles': [name for name, _ in VIEWS], 'extent_pixels': [4, 6, 8], 'phases': PHASES,
                'comparison_scope': 'Separate from the existing59 entries and near-model0.03 IoU budget',
                'results': results, 'aliases': source.get('aliases', {}), 'inputs_sha256': hashes,
                'external_proof': str(Path(external_proof).resolve()) if external_proof else None}
    (output/'metrics.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if external_proof:
        shutil.copyfile(external_proof, output/'external-c-proof.json')
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Tiny far models</title><style>body{font:15px system-ui;max-width:1200px;margin:auto}img{max-width:100%}td,th{padding:8px;text-align:left}</style>'+micro_html(manifest, '')+'\n')
    return manifest


def micro_html(manifest, prefix='micro/'):
    esc = html.escape
    parts = ['<section id="tiny-models"><h2>Optional tiny far models</h2>',
             '<p>These additional models use a separate conservative projected-size gate. The existing near/mid models and 59-entry quality aggregate remain unchanged. Each native sheet shows eight directions, including the bottom, at four quarter-pixel positions. Enlarged pixels use nearest-neighbor display. This CPU audit is not an N64 screenshot, antialiasing emulation or frame-rate result.</p>',
             f'<p><a href="{prefix}metrics.json">Micro metrics, decoded-C checks and input hashes</a></p>',
             '<table><tr><th>Model</th><th>Far → micro triangles</th><th>Micro loaded vertices</th><th>Quality decision</th></tr>']
    for name, row in manifest['results'].items():
        parts.append(f'<tr><td>{esc(name.replace("_", " "))}</td><td>{row["old_far_triangles"]} → {row["triangles"]}</td><td>{row["vertices"]}</td><td>{esc(row["quality_note"])}</td></tr>')
    parts.append('</table><p>The following models deliberately retain the existing far bank:</p><ul>')
    for name, reason in manifest['aliases'].items():
        parts.append(f'<li><strong>{esc(name.replace("_", " "))}</strong>: {esc(reason)}</li>')
    parts.append('</ul>')
    if manifest.get('external_proof'):
        parts.append(f'<p><a href="{prefix}external-c-proof.json">Separate independent emitted-C proof</a></p>')
    for name in manifest['results']:
        parts.append(f'<details><summary>{esc(name.replace("_", " "))}: eight angles and native 4/6/8px phases</summary>')
        for suffix in ('hero', '8px', '6px', '4px'):
            url = prefix+'images/'+name+'-'+suffix+'.png'
            parts.append(f'<a href="{url}"><img loading="lazy" src="{url}" alt="{esc(name)} {suffix}"></a>')
        parts.append('</details>')
    parts.append('</section>')
    return '\n'.join(parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', type=Path)
    args = parser.parse_args()
    audit_micro(args.bank, args.baseline, args.reference, args.output, args.proof)
