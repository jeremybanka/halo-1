"""Restore the authored rear torso exterior without a convex replacement.

The rear frame has long lateral rails. Collapsing the complete frame into a
convex upper-back contour consumed its width at the far LOD. Reduce the intact
rear surface separately, retaining original correspondence and native skin.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from demake_gungnir import collapse, bake


def run(source, motion, candidate, inventory, output):
    output.mkdir(parents=True, exist_ok=True)
    original = json.loads(source.read_text())
    original['skin_weights'] = original['weights']
    data = json.loads((candidate/'solid.json').read_text())
    parts = json.loads(inventory.read_text())
    source_faces = next(p['faces'] for p in parts if p['id'] == 'body-06:005')
    rear = []
    for fi in source_faces:
        p = np.array([original['vertices'][i] for i in original['faces'][fi]])
        n = np.cross(p[1]-p[0], p[2]-p[0])
        if p[:, 0].mean() < -.045 and n[0] < -.1*np.linalg.norm(n):
            rear.append(fi)
    group = dict(id='torso-back', source_components=['body-06:005'], faces=rear,
                 material=6, region='torso-back', targets=(40, 28), kind='open',
                 method='independently reduced original rear torso frame; preserve authored rails and open surface, no convex envelope')
    report = []
    for lod, model in enumerate(data['lods']):
        replacement, proof = collapse(original, group, lod)
        retained = []
        removed = 0
        for t in model['triangles']:
            p = np.array(t['p']); n = np.cross(p[1]-p[0], p[2]-p[0])
            if t['component'] == 'torso-back' or (t['component'] == 'torso' and
                    p[:, 0].mean() < -.045 and n[0] < -.1*np.linalg.norm(n)):
                removed += 1
            else:
                retained.append(t)
        model['triangles'] = retained + replacement
        frames, clips = bake(original, model['triangles'], motion)
        np.savez_compressed(output/f'poses-{lod}.npz', **frames)
        model['animations'] = clips
        report.append(dict(lod=lod, removed_triangles=removed, replacement=proof))
    data['rear_repair_parent_sha256'] = hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest()
    data['rear_repair'] = report
    data['publication_approved'] = False
    (output/'solid.json').write_text(json.dumps(data, separators=(',', ':'))+'\n')
    (output/'rear-repair.json').write_text(json.dumps(report, indent=2)+'\n')
    print('REAR REPAIR', report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('source', 'motion', 'candidate', 'inventory', 'output'):
        p.add_argument(name, type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(a.source, a.motion, a.candidate, a.inventory, a.output)
