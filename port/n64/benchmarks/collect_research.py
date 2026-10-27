#!/usr/bin/env python3
"""Archive selected benchmark evidence without copying private game payloads.

The input is the original research checkout. No emulation or asset generation
runs here. Paths and camera transforms are removed; numeric observations and
counter lines are retained with SHA256 provenance for their private originals.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
# Deliberately explicit: never recursively publish build/ or an asset sidecar.
SOURCES = {
    'n64-all-map-audit': 'timing verification compiler-input-verification',
    'n64-expansion-research': 'quiet-timing native-costs native-validation',
    'n64-chiron-visibility': 'quiet-timing validation-final pixel-comparisons native-census',
    'n64-visibility-rollout': 'results',
    'n64-sidewinder-photography': 'timing validation',
    'n64-sidewinder-aggressive': 'timing validation',
    'n64-sidewinder-combined': 'timing timing-summary validation',
    'n64-sidewinder-cluster-terrain': 'timing timing-summary validation',
    'n64-sidewinder-cost-breakdown': 'results',
    'n64-sidewinder-structures': 'measurements validation',
    'n64-sidewinder-structures-aggressive': 'measurements appraisal rejection',
    'n64-sidewinder-structures-extreme': 'measurements rejection',
    'n64-sidewinder-base-remodel': 'rejection',
    'n64-sidewinder-west-base': 'measurements preservation',
    'n64-sidewinder-trees': 'timing timing-summary validation',
    'n64-sidewinder-world-lod': 'timing timing-records measurements validation',
    'n64-sidewinder-canyon-rebuild': 'timing timing-records measurements validation',
    'n64-sidewinder-budget': 'timing timing-records measurements validation',
    'n64-sidewinder-budget-cells': 'timing timing-records measurements profiling camera-budgets validation',
    'n64-sidewinder-throughput': 'timing experiment-ledger profiling camera-budgets validation native-controls',
    'n64-sidewinder-visibility-audit': 'timing profiling camera-budgets validation',
    'n64-sidewinder-sections': 'timing profiling camera-budgets validation native-rejection-controls',
    'n64-sidewinder-submission-profile': 'summary instrumentation',
    'n64-sidewinder-hierarchy': 'timing profiling camera-budgets validation host-validation hierarchy-data native-census',
    'n64-summercart64-20261024': 'deployment release-boot-result native-qa-result',
}
RUN_DIRS = {
    'n64-sidewinder-throughput', 'n64-sidewinder-visibility-audit',
    'n64-sidewinder-sections', 'n64-sidewinder-submission-profile',
    'n64-sidewinder-hierarchy',
}
# Only observational counters; omit camera matrices, source geometry and chats.
OMIT = {'eye_x', 'eye_y', 'eye_z', 'eye', 'pose', 'matrix_columns', 'levels',
        'before_levels', 'pvs_mask', 'user_feedback', 'original_settings_sha256',
        'global_settings_sha256', 'global_settings_mtime'}
COUNTERS = ('BENCH ', 'SUBMIT ', 'SUBDETAIL ', 'HIERARCHY ', 'CENSUS ',
            'FRONTEND_QA ', 'HALO N64 ', 'PASS:', 'PASS map',
            '200000 inherited-plane certificates')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clean(value, root):
    if isinstance(value, dict):
        return {clean(k, root): clean(v, root) for k, v in value.items() if k not in OMIT}
    if isinstance(value, list):
        return [clean(v, root) for v in value]
    if isinstance(value, str):
        value = value.replace(str(root) + '/', '')
        value = value.replace('/Users/jem/dojo/halo-1/', '')
        value = re.sub(r'/Users/[^/\s]+/', '<home>/', value)
        return value.replace('/Volumes/DISK_IMG/', 'DISK_IMG/')
    return value


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def collect(root, destination):
    root = root.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    index = {'schema': 1, 'documented_on': '2026-10-27', 'records': [],
             'scope': 'Historical Ares measurements and host/pixel validations; cartridge play feedback is qualitative. No new timing run performed for this archive.',
             'excluded': ['ROMs', 'map banks', 'visibility sidecars', 'textures',
                          'images', 'Blender files', 'camera transforms', 'chat transcripts']}
    for directory, names in SOURCES.items():
        base = root / 'build' / directory
        record = {'artifact_directory': 'build/' + directory, 'results': {},
                  'provenance': [], 'native_counter_logs': {}}
        def remember(path):
            raw = path.read_bytes()
            record['provenance'].append({'artifact': str(path.relative_to(root)),
                                         'bytes': len(raw), 'sha256': sha(raw)})
            return raw
        for name in names.split():
            path = base / (name + '.json')
            record['results'][name] = clean(json.loads(remember(path)), root)
        if directory in RUN_DIRS:
            record['runs'] = []
            for path in sorted(base.glob('*-run.json')):
                run = json.loads(remember(path))
                record['runs'].append(clean(run, root))
                rom = Path(run['rom'])
                if not rom.is_absolute():
                    rom = root / rom
                assert sha(rom.read_bytes()) == run['sha256'], 'ROM identity changed: ' + str(rom)
                path = Path(run['log'])
                if not path.is_absolute():
                    path = root / path
                raw = remember(path)
                lines = [s for s in raw.decode().splitlines() if s.startswith(COUNTERS)]
                assert lines, 'No counters: ' + str(path)
                record['native_counter_logs'][path.name] = clean(lines, root)
        if directory == 'n64-summercart64-20261024':
            for name in ('native-qa.log', 'release-boot.log', 'candidate-host-tests.log', 'hierarchy-tests.log'):
                raw = remember(base / name)
                record['native_counter_logs'][name] = [s for s in raw.decode().splitlines() if s.startswith(COUNTERS)]
            manifest = next((base / 'source/build/cartridge-release').glob('*.build.json'))
            build = json.loads(remember(manifest))
            record['build'] = clean({k: build[k] for k in ('runtime_commit', 'asset_commit', 'toolchain', 'options', 'rom')}, root)
            assert sha(Path(build['rom']['path']).read_bytes()) == build['rom']['sha256']
        payload = encode(record)
        assert b'/Users/' not in payload
        (destination / (directory + '.json')).write_bytes(payload)
        index['records'].append({'file': directory + '.json', 'sha256': sha(payload), 'source_artifacts': len(record['provenance'])})
    (destination / 'index.json').write_bytes(encode(index))
    print('Archived', len(index['records']), 'studies with', sum(r['source_artifacts'] for r in index['records']), 'source artifacts')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'results/2026-10')
    args = parser.parse_args()
    collect(args.source_root, args.output_dir)
