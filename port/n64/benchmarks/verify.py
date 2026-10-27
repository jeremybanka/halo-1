#!/usr/bin/env python3
"""Check archived benchmark arithmetic and identities without private assets."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def counter(lines, prefix):
    matches = [line for line in lines if line.startswith(prefix)]
    assert len(matches) == 1, (prefix, len(matches))
    return dict(re.findall(r'(\w+)=([^ ]+)', matches[0]))


def verify(directory, source_root=None):
    index = json.loads((directory / 'index.json').read_text())
    records = {}
    for entry in index['records']:
        path = directory / entry['file']; raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256'], path
        assert b'/Users/' not in raw and b'"matrix_columns"' not in raw
        record = json.loads(raw); records[path.stem] = record
        assert len(record['provenance']) == entry['source_artifacts']
        if source_root:
            for evidence in record['provenance']:
                source = source_root / evidence['artifact']; original = source.read_bytes()
                assert len(original) == evidence['bytes']
                assert hashlib.sha256(original).hexdigest() == evidence['sha256'], source
        for run in record.get('runs', []):
            assert re.fullmatch('[0-9a-f]{64}', run['sha256'])
            assert Path(run['log']).name in record['native_counter_logs']
        for lines in record['native_counter_logs'].values():
            for line in lines:
                if line.startswith('BENCH vi_fresh '):
                    fields = dict(re.findall(r'(\w+)=([^ ]+)', line))
                    frames = int(fields['frames']); elapsed = int(fields['elapsed_us'])
                    assert frames > 0 and elapsed > 0
                    assert int(fields['flips']) == frames + int(fields['duplicate_poses'])
        timing = record['results'].get('timing', {})
        if isinstance(timing, dict):
            for run in timing.get('runs', []):
                if all(k in run for k in ('frames', 'elapsed_us', 'fps')):
                    assert math.isclose(run['fps'], run['frames'] * 1e6 / run['elapsed_us'], rel_tol=1e-12)
    h = records['n64-sidewinder-hierarchy']; result = h['results']; timing = result['timing']
    runs = {r['label']: r for r in timing['runs']}
    run_evidence = {r['label']: r for r in h['runs']}
    for label, run in runs.items():
        log = Path(run_evidence[label]['log']).name
        raw = counter(h['native_counter_logs'][log], 'BENCH vi_fresh group=ALL ')
        for key, value in raw.items():
            if key != 'group':
                assert run[key] == int(value), (label, key)
    for side in ('before', 'after'):
        a = dict(runs[side + '-four']); b = dict(runs[side + '-four-repeat'])
        a.pop('label'); b.pop('label'); assert a == b
        assert math.isclose(timing[side + '_four'], a['fps'], rel_tol=1e-12)
        assert math.isclose(timing[side + '_one'], runs[side + '-one']['fps'], rel_tol=1e-12)
    assert math.isclose(timing['four_gain_percent'], (timing['after_four'] / timing['before_four'] - 1) * 100)
    profiles = result['profiling']
    assert profiles['before-cpu']['groups']['0']['phases']['world'] == 17393
    assert profiles['after-cpu']['groups']['0']['phases']['world'] == 15036
    for label, profile in profiles.items():
        log = Path(run_evidence[label]['log']).name
        lines = h['native_counter_logs'][log]
        raw_submit = counter(lines, 'SUBMIT ')
        assert profile['submit'] == {k: int(v) for k, v in raw_submit.items()}
        for group, values in profile['groups'].items():
            raw = counter(lines, f'BENCH attribution group={group} ')
            assert values['frames'] == int(raw['frames'])
            assert values['elapsed_us'] == int(raw['elapsed_us'])
            phases = list(map(int, raw['phases'].split(',')))
            # Stable channels in the archived renderer's attribution format.
            for name, position in (('world', 4), ('geometry_rsp_wait', 10),
                                   ('geometry_rdp_wait', 11)):
                assert values['phases'][name] == phases[position], (label, group, name)
        submit = profile['submit']; frames = submit['views'] / 4
        for key, value in profile['submit_ms_per_four_view_frame'].items():
            assert math.isclose(value, submit[key] / frames / 1000, rel_tol=1e-12)
        assert math.isclose(profile['eligibility_cache_hit_fraction'], 1 - submit['rebuilds'] / submit['views'])
    camera = result['camera-budgets']; rows = camera['rows']
    loads = [int(r['vertices']) for r in rows]; live = [r for r in rows if int(r['alive'])]
    assert len(rows) == camera['samples'] == 68 and len(live) == camera['live_samples'] == 63
    assert math.isclose(sum(loads) / len(loads), camera['mean_loads'])
    assert max(loads) == camera['max_loads'] == 6514
    assert sum(int(r['vertices']) < 1500 for r in live) == camera['live_under_1500'] == 9
    validation = result['validation']
    assert validation['offline_pairs'] == 196 and validation['offline_changed_pixels'] == 0
    assert validation['native_primary_camera_images'] == 14 and validation['native_changed_pixels'] == 0
    assert validation['native_counter_cameras'] == 8
    assert validation['all_17222_triangles_preserved'] and validation['collision_and_movement_unchanged']
    assert validation['rdp_errors'] == validation['rdp_warnings'] == 0
    # Earlier rebatching was not pixel-identical: do not erase its counterexample.
    assert records['n64-sidewinder-sections']['results']['validation']['native_primary_changed_pixels'] == 24
    cart = records['n64-summercart64-20261024']; deploy = cart['results']['deployment']
    boot = cart['results']['release-boot-result']; qa = cart['results']['native-qa-result']
    assert deploy['sha256'] == boot['sha256'] == cart['build']['rom']['sha256']
    assert deploy['readback_verified'] and deploy['file_fsynced'] and boot['passed']
    assert qa['passed'] and qa['matches'] == 14 and qa['maps'] == 13 and qa['steps'] == 224
    assert qa['last_progress'] in cart['native_counter_logs']['native-qa.log']
    assert not qa['global_settings_unchanged'] and qa['wrapper_exit_status'] == 1
    assert cart['build']['options']['playable_candidate'] and not cart['build']['options']['demo']
    print('PASS:', len(records), 'studies;', sum(e['source_artifacts'] for e in index['records']),
          'artifact identities; counter arithmetic, repeats, CPU attribution, camera budgets and cartridge evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'results/2026-10')
    parser.add_argument('--source-root', type=Path)
    args = parser.parse_args()
    verify(args.output_dir, args.source_root)
