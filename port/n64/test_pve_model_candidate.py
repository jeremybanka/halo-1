"""Audit the actual candidate art, opaque/energy batches and streamed poses."""
import argparse, gzip, hashlib, json, re
from pathlib import Path
import numpy as np

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(gzip.decompress(path.read_bytes()))

def census(text):
    batches = {}
    for symbol, body in re.findall(r'(?:const|static const) bg_mesh_batch (\w+)\[.*?\]\s*=\s*\{(.*?)\};', text, re.S):
        batches[symbol] = [tuple(map(int, x.split(','))) for x in re.findall(r'\{([\d, ]+)\}', body)]
    models = {}
    for symbol, verts, batch, indices, count, tris in re.findall(r'\{(\w+),(\d+),[\d.]+f,(\w+),(\w+),(\d+),(\d+)\}', text):
        assert len(batches[batch]) == int(count)
        models[symbol] = {'triangles': int(tris), 'packed_vertices': int(verts),
                          'vertex_loads': sum((b[1]+1)&~1 for b in batches[batch]), 'batches': int(count)}
    return models, batches

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('capture', type=Path); a = p.parse_args()
    root = Path(__file__).resolve().parents[2]; out = a.capture
    before = read(out/'before-squad-baked.json.gz'); after = read(out/'source/squad-baked.json.gz')
    raw = json.loads((out/'source/squad-source.json').read_text())
    original = (out/'before-pve_data.c').read_text(); candidate = (out/'bank/pve_data.c').read_text()
    report = {'baseline_models': census(original)[0], 'candidate_models': census(candidate)[0]}
    shield_material = next(i for i, m in enumerate(after['jackal'][0]['material_metadata'])
                           if m['path'].endswith('jackal shield'))
    report['jackal_shield_audit'] = {
        'source_superhigh_triangles': raw['models']['jackal']['source_geometry_lods']['base00 superhigh']['materials'].count(shield_material),
        'baseline_lod_triangles': [sum(t['material'] == shield_material for t in m['triangles']) for m in before['jackal']],
        'candidate_lod_triangles': [sum(t['material'] == shield_material for t in m['triangles']) for m in after['jackal']],
        'status': 'Existing missing visual shield; gameplay collision is unchanged. Not repaired by this reduction.',
    }
    equal = {}
    for name in ('pve_defs.c', 'pve_collision.c', 'pve_source_decisions.inc'):
        assert (out/('before-'+name)).read_bytes() == (out/'bank'/name).read_bytes(), name
        assert (out/('before-'+name)).read_bytes() == (root/'halo64-assets/generated/pve'/name).read_bytes(), name
        equal[name] = digest(out/'bank'/name)
    assert (out/'before-pve_nav.c').read_bytes() == (root/'halo64-assets/generated/pve/pve_nav.c').read_bytes()
    for name in ('grunt', 'elite', 'jackal'):
        assert before[name] == after[name], 'Unrequested actor geometry changed: '+name
    for name in ('hunter', 'spirit'):
        for lod in range(2):
            x, y = before[name][lod], after[name][lod]
            assert x['hit'] == y['hit'] and x['grips'] == y['grips'], (name, lod)
            assert set(t['material'] for t in x['triangles']) == set(t['material'] for t in y['triangles'])
            geom = raw['models'][name]['source_geometry_lods'][y['source_lod']]
            assert all(abs(sum(w for _, w in skin)-1) < 1e-6 and len(skin) <= 4 and
                       all(w > 0 and 0 <= b < len(geom['nodes']) for b, w in skin)
                       for skin in geom['skin_weights'])
            assert all(len(set(f)) == 3 and all(0 <= v < len(geom['vertices']) for v in f) for f in geom['faces'])
            for clip in y['clips']:
                assert x['clips'][clip]['duration'] == y['clips'][clip]['duration']
                points = np.array(y['clips'][clip]['frames'])
                assert points.shape[1:] == (3*len(y['triangles']), 3)
                assert np.isfinite(points).all() and abs(points*128).max() < 32767
    modes = {k: list(map(int, body.split(','))) for k, body in re.findall(r'static const uint8_t (pve_\w+)_modes\[\]=\{([^}]+)\};', candidate)}
    batches = census(candidate)[1]; material_counts = {}
    for symbol, body in re.findall(r'static T3DVertPacked (pve_\w+)\[\].*?=\{(.*?)\};', candidate, re.S):
        alpha = [int(v, 16)&255 for v in re.findall(r'0x([0-9a-f]{8})', body)]
        counts = {'opaque_vertices': 0, 'energy_vertices': 0, 'two_sided_batches': 0}
        assert len(modes[symbol]) == len(batches[symbol+'_batches'])
        for mode, (start, count, _, _) in zip(modes[symbol], batches[symbol+'_batches']):
            assert 0 <= mode <= 3
            assert set(alpha[start:start+count]) == {160 if mode&2 else 255}, (symbol, mode)
            counts['energy_vertices' if mode&2 else 'opaque_vertices'] += count
            counts['two_sided_batches'] += bool(mode&1)
        material_counts[symbol] = counts
    motion = (out/'bank/pve-motion.bin').read_bytes(); total_frames = 0; max_dma = 0
    index_arrays = {k: list(map(int, body.split(','))) for k, body in re.findall(r'static const uint16_t (\w+_indices)\[\]=\{([^}]+)\};', candidate)}
    clips = re.findall(r'\{\(const uint16_t\*\)\(uintptr_t\)(\d+),(\w+_indices),(\d+),(\d+),(\d+),([\d.]+)f,\{([^}]+)\}\}', candidate)
    assert len(clips) == 5*2*12
    for offset, indices, frames, vertices, tracks, duration, origin in clips:
        offset, frames, vertices, tracks = map(int, (offset, frames, vertices, tracks))
        assert offset%16 == 0 and 0 < tracks <= 8192 and float(duration) > 0
        assert len(index_arrays[indices]) == vertices and max(index_arrays[indices]) < tracks
        assert offset+frames*tracks*6+16 <= len(motion)
        positions = np.frombuffer(motion, dtype='>u2', count=frames*tracks*3, offset=offset).astype(int).reshape(-1, 3)
        positions += np.array(list(map(int, origin.split(','))))
        assert positions.min() >= -32768 and positions.max() <= 32767
        max_dma = max(max_dma, ((2*tracks*6+30)//16)*16); total_frames += frames
    assert max_dma <= 2*8192*6+32
    # These samples detect the flattened shield and crushed booms rejected
    # during authoring; IoU is not a proof of quality at every possible angle.
    audit = json.loads((out/'audit/audit.json').read_text()); assert len(audit) == 72
    assert min(x['silhouette_iou'] for x in audit) >= .92
    assert max(x['after_backface_only_pixels']-x['before_backface_only_pixels'] for x in audit) <= 3
    quantization = {}
    for name in ('hunter', 'spirit'):
        for lod in range(2):
            row = {}
            for label, model in [('before', before[name][lod]), ('after', after[name][lod])]:
                counts = []
                for clip, data in model['clips'].items():
                    for frame, points in enumerate(data['frames']):
                        t = np.rint(np.array(points)*128).astype(int).reshape(-1, 3, 3)
                        cross = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0])
                        counts.append({'clip': clip, 'frame': frame,
                                       'degenerate_triangles': int(np.all(cross == 0, axis=1).sum())})
                row[label] = {'min': min(x['degenerate_triangles'] for x in counts),
                              'max': max(x['degenerate_triangles'] for x in counts), 'frames': counts}
            quantization[f'{name}-{lod}'] = row
    (out/'quantization-audit.json').write_text(json.dumps(quantization, indent=2)+'\n')
    report.update(unchanged_simulation=equal, unchanged_other_actor_meshes=['grunt','elite','jackal'],
                  unchanged_hit_meshes_and_grips=True, surface_batches=material_counts,
                  pose_frames=total_frames, max_aligned_pose_pair_bytes=max_dma,
                  minimum_silhouette_iou=min(x['silhouette_iou'] for x in audit),
                  motion_bank_sha256=digest(out/'bank/pve-motion.bin'))
    (out/'asset-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS unchanged gameplay/hit/grip data, finite weighted geometry, material regions, opaque armor/energy separation,', total_frames, 'pose frames and 72 silhouette/winding views')
    print('KNOWN ISSUE:', report['jackal_shield_audit'])

if __name__ == '__main__': main()
