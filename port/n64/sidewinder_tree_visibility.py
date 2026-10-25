"""Transfer validated cluster-terrain PVS through an isolated tree replacement.

Every non-tree batch must have an exact identity bijection. Replacement tree
batches are restricted to the existing two tree materials and always fail open.
The source classifier, PVS rows, and native pixel exceptions are inherited.
"""
import json
from pathlib import Path
from remap_sidewinder_visibility import batches, sections, sha
from sidewinder_trees import OUT, PREVIOUS


def validate(data, payload):
    from cluster_terrain_visibility import validate as validate_baseline
    assert data['schema'] == 5 and sha(payload) == data['map_sha256']
    baseline_path = Path(data['tree_baseline_sidecar_path'])
    raw = baseline_path.read_bytes()
    assert sha(raw) == data['tree_baseline_sidecar_sha256']
    baseline = json.loads(raw)
    original = Path(data['tree_baseline_bank_path']).read_bytes()
    validate_baseline(baseline, original)
    assert sections(original)[3:] == sections(payload)[3:]
    for key in ['nodes', 'planes', 'leaf_clusters', 'rows', 'clusters', 'map_name', 'map_id', 'normal_limit', 'cluster_probes']:
        assert data[key] == baseline[key], ('Source classifier changed', key)
    raw = Path(data['tree_packing_report_path']).read_bytes()
    assert sha(raw) == data['tree_packing_report_sha256']
    proof = json.loads(raw)
    assert proof['source_bank_sha256'] == sha(original) and proof['candidate_sha256'] == sha(payload)
    old, new = list(batches(original)), list(batches(payload))
    assert len(new) == len(proof['batches']) == len(data['chunk_masks'])
    transferred = set()
    first_tree = {material: next(i for i, row in enumerate(old) if row[0] == material) for material in (18, 19)}
    order = []
    for i, ((material, identity, _), entry) in enumerate(zip(new, proof['batches'])):
        if entry['unchanged']:
            j = entry['old_batch']
            assert j not in transferred and old[j][0] not in (18, 19) and old[j][1] == identity
            assert data['chunk_masks'][i] == baseline['chunk_masks'][j]
            transferred.add(j)
            order.append(j)
        else:
            assert material in (18, 19) and entry['old_batch'] is None
            assert data['chunk_masks'][i] == (1 << data['clusters'])-1
            order.append(first_tree[material])
    assert transferred == {i for i, row in enumerate(old) if row[0] not in (18, 19)}
    assert order == sorted(order), 'Tree replacement changed original material/pass order'
    assert data['chunk_masks'] == proof['chunk_masks']


def export(variant='lean'):
    output = OUT / variant
    sidecar = PREVIOUS / 'data/visibility.json'
    baseline = json.loads(sidecar.read_text())
    report = output / 'packing-report.json'
    bank = output / 'candidate-maps/sidewinder.map64'
    proof = json.loads(report.read_text())
    data = {**baseline, 'schema': 5, 'map_sha256': sha(bank.read_bytes()),
            'tree_baseline_sidecar_path': str(sidecar), 'tree_baseline_sidecar_sha256': sha(sidecar.read_bytes()),
            'tree_baseline_bank_path': str(PREVIOUS / 'candidate-maps/sidewinder.map64'),
            'tree_packing_report_path': str(report), 'tree_packing_report_sha256': sha(report.read_bytes()),
            'chunk_masks': proof['chunk_masks'], 'candidate_bank_path': str(bank),
            'scope': 'Exact non-tree batch transfer from validated cluster-terrain bank. Only snow pine materials 18/19 replaced; new tree batches fail open.'}
    # These indices describe the previous bank and must not masquerade as new ones.
    for key in ['chunk_origins', 'transferred_batches', 'cluster_terrain_chunks', 'pixel_fail_open_chunks', 'nonopaque_fail_open_chunks', 'fail_open_chunks', 'additional_pixel_fail_open_chunks']:
        data.pop(key, None)
    data['static_bytes'] = len(data['nodes'])*12+len(data['planes'])*16+len(data['leaf_clusters'])*2+len(data['chunk_masks'])*8+data['clusters']*8
    validate(data, bank.read_bytes())
    (output / 'visibility.json').write_text(json.dumps(data, separators=(',', ':'))+'\n')
    print('Validated tree visibility:', variant, len(data['chunk_masks']), 'batches')


if __name__ == '__main__':
    import sys
    export(sys.argv[1] if len(sys.argv) > 1 else 'lean')
