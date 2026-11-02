"""Matched rear material/part visibility against the intact Reach assembly."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from audit_models import Mesh, engine, matching_bounds
from demake_raster import Raster
from extract_gungnir import bone_globals
from pack_gungnir import prepare_broad_colors, corner_colors, palette
from gungnir_assets import texture_path


def run(source, motion, candidate, output):
    output.mkdir(parents=True, exist_ok=True)
    original = json.loads(source.read_text())
    data = json.loads((candidate/'solid.json').read_text())
    raster = Raster(output)
    textures = {i: Image.open(texture_path(p, source)).convert('RGB')
                for i, p in enumerate(data['textures']) if p}
    prepare_broad_colors(data, textures)
    native = np.load(motion/'native-poses.npz')
    inverse = np.linalg.inv(np.array(bone_globals(original['nodes'])))
    points = np.c_[original['vertices'], np.ones(len(original['vertices']))]
    faces = np.array(original['faces'])
    source_armor = np.array([r == 'body' and m == 6 for r, m in
                             zip(original['regions'], original['materials'])])
    source_colors = np.array([[[180, 186, 181] if a else [44, 49, 51]]*3
                              for a in source_armor])
    records = []
    for clip, fraction in [('bind', 0), ('idle', .45), ('run', .4), ('reload', .45), ('passenger', .5)]:
        ci = next((i for i, c in enumerate(data['lods'][0]['animations']) if c['name'] == clip), 0)
        fi = round(fraction*(len(native['matrices_'+str(ci)])-1))
        skin = native['matrices_'+str(ci)][fi]@inverse
        posed = np.zeros((len(points), 3))
        for vi, ws in enumerate(original['weights']):
            for b, w in ws:
                posed[vi] += (skin[b]@points[vi])[:3]*w
        src = Mesh(np.rint(engine(original['vertices'] if clip == 'bind' else posed)[faces]*512)/512, rgb=source_colors)
        models = []
        for lod, model in enumerate(data['lods']):
            poses = np.load(candidate/f'poses-{lod}.npz')
            colors = np.array([palette(*corner_colors(t, data['materials'], textures), 0)
                               for t in model['triangles']])
            geometry = engine([p for t in model['triangles'] for p in t['p']]) if clip == 'bind' else poses['frames_'+str(ci)][fi]
            models.append(Mesh(np.rint(geometry*512).reshape(-1, 3, 3)/512,
                               rgb=colors))
        for angle, direction in [('rear', (-1, .02, 0)), ('rear-left', (-1, .02, -1)),
                                 ('rear-right', (-1, .02, 1))]:
            bounds = matching_bounds([src, *models], direction)
            sheet = Image.new('RGB', (640, 280), '#202428')
            draw = ImageDraw.Draw(sheet)
            for col, (mesh, label) in enumerate(zip([src, *models],
                    ['Source plate IDs', 'Near packed RGB', 'Far packed RGB'])):
                im, ids, _ = raster.render(mesh, bounds, direction, width=160, height=256)
                sheet.paste(im, (col*160, 24)); draw.text((col*160+2, 4), label, fill='white')
                if col:
                    ts = data['lods'][col-1]['triangles']
                    part_colors = np.array([[[180, 186, 181] if t['component'].startswith('torso')
                                            else [44, 49, 51]]*3 for t in ts])
                    part_mesh = Mesh(mesh.p, rgb=part_colors)
                    part_im, part_ids, _ = raster.render(part_mesh, bounds, direction, width=160, height=256)
                    if col == 2:
                        sheet.paste(part_im, (480, 24)); draw.text((482, 4), 'Far torso IDs', fill='white')
                    visible = ids[ids >= 0]
                    from collections import Counter
                    counts = Counter(ts[int(i)]['component'] for i in visible)
                    records.append(dict(clip=clip, angle=angle, lod=col-1,
                                        visible_pixels=dict(counts)))
            sheet.save(output/f'{clip}-{angle}.png')
    report = dict(candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), views=records)
    (output/'rear-visibility.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('source', 'motion', 'candidate', 'output'): p.add_argument(name, type=Path)
    a = p.parse_args(); run(a.source, a.motion, a.candidate, a.output)
