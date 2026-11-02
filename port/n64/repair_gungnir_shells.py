"""Restore source rear returns and the complete belt/codpiece plate.

Keep the accepted exterior and unrelated components byte-for-byte. The rear
frame needs its original inward faces as well as its rear-facing rails; a body
union silhouette cannot establish either sidedness or plate/cloth ordering.
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
    parts = {p['id']: p for p in json.loads(inventory.read_text())}
    returns = []
    for fi in parts['body-06:005']['faces']:
        p = np.array([original['vertices'][i] for i in original['faces'][fi]])
        n = np.cross(p[1]-p[0], p[2]-p[0])
        if p[:, 0].mean() < -.04 and n[0] >= -.1*np.linalg.norm(n):
            returns.append(fi)
    groups = [
        dict(id='torso-back-return', source_components=['body-06:005'],
             faces=returns, material=6, region='torso-back-return',
             targets=(24, 16), kind='open',
             method='independently reduced original inward rear frame and edge returns; retain native winding and skin'),
        dict(id='belt', source_components=['body-06:025'],
             faces=parts['body-06:025']['faces'], material=6, region='belt',
             targets=(32, 24), kind='open',
             method='complete original belt/codpiece surface including lower tip and returns; no radial inward-face deletion'),
    ]
    report = []
    for lod, model in enumerate(data['lods']):
        before = model['triangles']
        # Earlier rear reduction kept a handful of inward triangles as well.
        # Replace those, avoiding coincident source-return layers.
        def replaced(t):
            if t['component'] in ('belt', 'torso-back-return'):
                return True
            if t['component'] != 'torso-back':
                return False
            p = np.array(t['p']); n = np.cross(p[1]-p[0], p[2]-p[0])
            return p[:, 0].mean() < -.04 and n[0] >= -.1*np.linalg.norm(n)
        retained = [t for t in before if not replaced(t)]
        replacements = []
        for group in groups:
            triangles, proof = collapse(original, group, lod)
            replacements.extend(triangles)
            report.append(dict(lod=lod, component=group['id'], **proof))
        model['triangles'] = retained + replacements
        assert [t for t in model['triangles'] if t not in replacements] == retained
        frames, clips = bake(original, model['triangles'], motion)
        np.savez_compressed(output/f'poses-{lod}.npz', **frames)
        model['animations'] = clips
    data['shell_repair_parent_sha256'] = hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest()
    data['shell_repair'] = report
    data['publication_approved'] = False
    (output/'solid.json').write_text(json.dumps(data, separators=(',', ':'))+'\n')
    (output/'shell-repair.json').write_text(json.dumps(report, indent=2)+'\n')
    print('SHELL REPAIR', report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'motion', 'candidate', 'inventory', 'output'):
        p.add_argument(name, type=Path)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(a.source, a.motion, a.candidate, a.inventory, a.output)
