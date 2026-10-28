#!/usr/bin/env python3
"""Rebuild the isolated Hunter/Spirit appraisal bank using batch Blender."""
import argparse, gzip, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'port/n64'))
from model_colors import load_images, bake_triangle, bake_team_mask

def source_colors(baked):
    colors = {}
    for name in ('hunter', 'spirit'):
        model = baked[name][0]; metadata = model['material_metadata']
        images = load_images(model['textures'])
        masks = load_images([m.get('multipurpose_fullres') for m in metadata])
        channels = [2 if m.get('color_change_source') == 'A' else None for m in metadata]
        colors[name] = [[list(rgb)+[tint] for rgb, tint in
                         zip(bake_triangle(t, images, model), bake_team_mask(t, masks, channels))]
                        for t in model['triangles']]
    return colors

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source', type=Path, default=ROOT/'halo64-assets/assets/firefight-combat')
    p.add_argument('--blender', type=Path, default=Path('/Applications/Blender.app/Contents/MacOS/Blender'))
    a = p.parse_args(); out = a.output.resolve(); source = a.source.resolve()
    if out.exists() and any(out.iterdir()): p.error('Use an empty output directory; never replace the approved bank')
    raw = json.loads((source/'squad-source.json').read_text())
    caches = [source/(raw.get('campaign', 'a30')+'-decompressed.map'), source/'bloodgulch-decompressed.map']
    for cache in caches:
        if not cache.is_file(): p.error('Owned extraction cache required: '+str(cache))
    out.mkdir(parents=True, exist_ok=True)
    original = source/'squad-baked.json.gz'; before = json.loads(gzip.decompress(original.read_bytes()))
    shutil.copyfile(original, out/'before-squad-baked.json.gz')
    for name in ('pve_data.c', 'pve_defs.c', 'pve_collision.c', 'pve_source_decisions.inc',
                 'pve_nav.c', 'pve-motion.bin', 'pve-report.json'):
        shutil.copyfile(ROOT/'halo64-assets/generated/pve'/name, out/('before-'+name))
    colors = out/'source-corner-colors.json'; colors.write_text(json.dumps(source_colors(before)))
    def run(command, log):
        with (out/log).open('w') as stream:
            subprocess.run(list(map(str, command)), cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    run([a.blender, '--background', '--python', ROOT/'port/n64/reduce_pve_blender.py', '--',
         source/'squad-source.json', out/'reduced-source.json', out/'reduced.blend', '--colors', colors], 'reduce.log')
    expression = ('import sys;sys.path.insert(0,'+repr(str(ROOT/'port/n64'))+');'
                  'from bake_pve_blender import bake;bake('+repr(str(out/'reduced-source.json'))+','+
                  repr(str(out/'reduced-baked.json.gz'))+',("hunter","spirit"))')
    run([a.blender, '--background', '--python-expr', expression], 'bake.log')
    candidate_source = out/'source'; candidate_source.mkdir()
    shutil.copyfile(out/'reduced-source.json', candidate_source/'squad-source.json')
    before.update(json.loads(gzip.decompress((out/'reduced-baked.json.gz').read_bytes())))
    (candidate_source/'squad-baked.json.gz').write_bytes(gzip.compress(json.dumps(before).encode(), mtime=0))
    for cache in caches: (candidate_source/cache.name).symlink_to(cache)
    run([sys.executable, ROOT/'port/n64/pack_pve.py', candidate_source, '--output', out/'bank', '--model-candidate'], 'pack.log')
    run([sys.executable, ROOT/'port/n64/audit_pve_models.py', original, out/'reduced-baked.json.gz',
         out/'reduced-source.json', out/'audit'], 'audit.log')
    run([sys.executable, ROOT/'port/n64/test_pve_model_candidate.py', out], 'asset-checks.log')
    print('Candidate bank:', out/'bank')

if __name__ == '__main__': main()
