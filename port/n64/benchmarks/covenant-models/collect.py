#!/usr/bin/env python3
"""Summarize matched native model experiments and verify input provenance."""
import argparse, hashlib, importlib.util, json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('navigation_collect', HERE.parent/'firefight-navigation/collect.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inputs(manifest):
    result = prior.inputs(manifest)
    # The candidate replaces this one compiled visual bank, never simulation.
    for key in list(result):
        if key.endswith('/bank/pve_data.c'):
            result['halo64-assets/generated/pve/pve_data.c'] = result.pop(key)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--logs-only', action='store_true')
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    archived = json.loads((a.capture/'provenance.json').read_text()) if a.logs_only else None
    cases, provenance, matched = {}, {}, {}
    for kind in ['opening', 'perf']:
        for players in range(1, 5):
            manifests = {}
            for version in ['baseline', 'candidate']:
                name = f'{version}-{kind}-{players}'
                log = a.capture/(name+'-native.log')
                result = prior.summarize(log)
                assert result['observations'] == (75 if kind == 'opening' else 45), name
                rows = result.pop('samples')[5:]
                alive = [r for r in rows if r['FF_STATE']['living'] == players and
                         r['FF_STATE']['enemies'] > 0 and r['FF_STATE']['arriving'] == 0]
                result['all_humans_and_landed_enemies'] = {
                    'observations': len(alive),
                    'fps_mean': round(statistics.mean(r['PERF']['fps'] for r in alive), 2),
                    'fps_min': min(r['PERF']['fps'] for r in alive),
                    'fps_max': max(r['PERF']['fps'] for r in alive),
                } if alive else None
                result['max_reported_frame_ms'] = round(max(r['PHASE']['frame_max'] for r in rows)/1000, 3)
                result['npc_animation_ms'] = result['npc_prepare_ms']
                cases[name] = result
                if a.logs_only:
                    assert sha(log) == archived['cases'][name]['log_sha256'], name
                    continue
                manifest = next((a.capture/name).glob('*.build.json'))
                rom = next((a.capture/name).glob('*.z64'))
                m = manifests[version] = json.loads(manifest.read_text())
                assert m['options']['profile'] and not m['options']['validate']
                assert not m['options'].get('pve_model_qa')
                assert m['options']['pve_players'] == players
                assert m['options']['pve_qa'] == (3 if kind == 'opening' else 4)
                assert bool(m['options'].get('pve_model_bank')) == (version == 'candidate')
                bank = Path(m['options'].get('pve_model_bank') or
                            next(k for k in m['sources'] if k.endswith('/pve/pve_data.c'))).resolve()
                if bank.suffix == '.c': bank = bank.parent
                provenance[name] = {
                    'source_commit': m['runtime_commit'], 'asset_commit': m['asset_commit'],
                    'log_sha256': sha(log), 'rom_sha256': sha(rom),
                    'manifest_sha256': sha(manifest), 'local_manifest': str(manifest.resolve()),
                    'local_rom': str(rom.resolve()), 'toolchain': m['toolchain'],
                    'render_bank_sha256': m['render_bank_experiment']['sha256'],
                    'motion_bank_sha256': sha(bank/'pve-motion.bin'),
                }
            if not a.logs_only:
                b, c = manifests['baseline'], manifests['candidate']
                bo, co = dict(b['options']), dict(c['options'])
                for opts in (bo, co):
                    for key in ('output_dir', 'pve_model_bank', 'pve_model_qa'): opts.pop(key, None)
                assert bo == co, (kind, players, bo, co)
                assert b['asset_commit'] == c['asset_commit']
                assert b['render_bank_experiment']['sha256'] == c['render_bank_experiment']['sha256']
                bi, ci = inputs(b), inputs(c)
                changes = {k: {'baseline': bi.get(k), 'candidate': ci.get(k)}
                           for k in sorted(bi.keys() | ci.keys()) if bi.get(k) != ci.get(k)}
                allowed = {'port/n64/main.c', 'port/n64/scene.c', 'port/n64/runtime_qa.c',
                           'port/n64/pve_draw.inc', 'port/n64/pve_model_candidate.inc',
                           'port/n64/pve_model_qa.h', 'port/n64/asset_pve.h',
                           'halo64-assets/generated/pve/pve_data.c'}
                assert set(changes) <= allowed, (kind, players, changes)
                assert 'halo64-assets/generated/pve/pve_data.c' in changes
                matched[f'{kind}-{players}'] = {
                    'options_identical_except_output_and_model_override': True,
                    'canonical_assets_and_render_bank_identical': True,
                    'simulation_collision_navigation_unchanged': True,
                    'runtime_input_differences': changes,
                }
            before = cases[f'baseline-{kind}-{players}']['living_players_and_landed_enemies']
            after = cases[f'candidate-{kind}-{players}']['living_players_and_landed_enemies']
            print(kind, players, before['fps_mean'], after['fps_mean'],
                  round(100*(after['fps_mean']/before['fps_mean']-1), 1))
    (a.output/'results.json').write_text(json.dumps({'schema': 1, 'cases': cases}, indent=2)+'\n')
    if not a.logs_only:
        (a.output/'provenance.json').write_text(json.dumps({
            'schema': 1, 'emulator': 'Ares v148, NTSC 320x240, 8 MiB, audio enabled, uncapped',
            'settings_sha256': sha(a.capture/'ares.bml'), 'cases': provenance, 'matched_inputs': matched,
        }, indent=2)+'\n')

if __name__ == '__main__': main()
