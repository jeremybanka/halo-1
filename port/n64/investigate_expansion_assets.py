"""Size exact animation representations and inspect owned-map source PVS.

PVS rows are unweighted source clusters, not camera-replay visibility or FPS.
All source triangles lacking cluster membership are kept visible. Mapping the
current packed chunks and proving the retained occluders are separate steps.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import re
import statistics
import struct
import subprocess
from asset_ids import map_ids

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(out):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    maps, inputs = {}, {}
    for name in map_ids():
        path = ROOT / 'build/n64-map-survey' / (name + '-decompressed.map')
        inputs[str(path.relative_to(ROOT))] = sha(path)
        with (out / (name + '-extract.log')).open('w') as log, contextlib.redirect_stdout(log):
            halo = Halo1Map()
            halo.load_map(path)
            entries = halo.tag_index.tag_index
            bsp = halo.get_meta(next(i for i, entry in enumerate(entries)
                                    if entry.class_1.enum_name == 'scenario_structure_bsp'))
        count = len(bsp.clusters.STEPTREE)
        raw = bytes(bsp.cluster_data.STEPTREE)
        stride = ((count + 31) // 32) * 4
        assert len(raw) == count * stride
        rows = [int.from_bytes(raw[i*stride:(i+1)*stride], 'little') & ((1 << count)-1)
                for i in range(count)]
        assert all(row & (1 << i) for i, row in enumerate(rows))
        leaves = list(struct.iter_unpack('<6BHhhi', bytes(bsp.leaves.STEPTREE)))
        references = list(struct.iter_unpack('<ii', bytes(bsp.leaf_surfaces.STEPTREE)))
        triangles = len(bytes(bsp.surface.STEPTREE)) // 6
        members = [set() for _ in range(count)]
        for leaf in leaves:
            cluster, length, first = leaf[-3:]
            if cluster < 0:
                continue
            assert cluster < count and 0 <= first <= len(references)-length
            for surface, _ in references[first:first+length]:
                assert 0 <= surface < triangles
                members[cluster].add(surface)
        assigned = set().union(*members)
        missing = set(range(triangles)) - assigned
        retained = [len(set().union(*(members[j] for j in range(count) if row >> j & 1)) | missing)
                    for row in rows]
        maps[name] = dict(clusters=count, portals=len(bsp.cluster_portals.STEPTREE),
            pvs_bytes=len(raw), triangles=triangles, unassigned_triangles=len(missing),
            visible_clusters_min_median_max=[min(x.bit_count() for x in rows),
                statistics.median(x.bit_count() for x in rows), max(x.bit_count() for x in rows)],
            retained_source_triangles_min_median_max=[min(retained), statistics.median(retained), max(retained)],
            cluster_triangle_bitsets_bytes=count*((triangles+31)//32)*4,
            current_512_chunk_row_bitsets_bytes=count*64,
            current_512_chunk_membership_bytes=512*stride)
    animations, poses = {}, {}
    generated = ROOT / 'halo64-assets/generated'
    for filename in ('models_data.c', 'firstperson_data.c'):
        path = generated / filename
        inputs[str(path.relative_to(ROOT))] = sha(path)
        clips = re.findall(r'\{(\w+),(\w+),(\d+),(\d+),(\d+),[0-9.]+f,\{[^}]+\}\}', path.read_text())
        assert clips
        animations[filename] = dict(clips=len(clips),
            current_resident_compressed_positions_bytes=sum(int(f)*int(t)*3 for a,b,f,v,t in clips),
            expanded_aligned_track_endpoint_bytes=sum(int(f)*int(t)*8 for a,b,f,v,t in clips),
            all_257_fractions_track_bytes=sum((int(f)-1)*int(t)*8*257 for a,b,f,v,t in clips))
    path = generated / 'interaction_assets.c'
    inputs[str(path.relative_to(ROOT))] = sha(path)
    unique = set()
    for name, body in re.findall(r'const bg_rom_pose\s+(\w+)[^=]*=(.*?);', path.read_text()):
        records = {tuple(map(int, match)) for match in re.findall(r'\{(\d+),(\d+),(\d+),(\d+),', body)}
        unique |= records
        poses[name] = dict(clips=len(records), endpoint_payload_bytes=sum(stride*frames for off,stride,vertices,frames in records))
    bank = ROOT / 'halo64-assets/frontend-files/interactions.bin'
    inputs[str(bank.relative_to(ROOT))] = sha(bank)
    for off, stride, vertices, frames in unique:
        assert off % 16 == 0 and stride % 16 == 0 and stride >= vertices*6
        assert off + stride*frames <= bank.stat().st_size
    result = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Owned-source payload sizing and unweighted cluster-PVS census; not target timing or safe runtime culling proof.',
        inputs=inputs, maps=maps, compressed_animations=animations,
        interaction_bank_bytes=bank.stat().st_size, interaction_groups=poses,
        current_pose_cache_bytes=8*(8736+128),
        notes=['Compressed motion arrays already reside in RDRAM; expansion targets decode work, not ROM DMA.',
               'Full resident interaction bank exceeds the spare RAM. Clip budgets must be selected by measured traffic.',
               'PVS must be mapped conservatively to every current packed triangle/chunk, with unassigned data failing open.',
               'Dynamic actors need conservative multi-cluster bounds; scoped/portal-boundary pixels require target checks.'])
    (out / 'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'maps':len(maps),'interaction_bank_bytes':result['interaction_bank_bytes'],
                      'compressed_animations':animations},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/n64-expansion-research/assets')
    run(parser.parse_args().output_dir)
