"""Hash-bound visibility for cluster-local Blender terrain and ordered batches."""
import collections
import hashlib
import json
from pathlib import Path
from pack_maps import uv_safe_triangles
from remap_sidewinder_visibility import ACCEPTED,batches,sections

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-cluster-terrain'

def sha(blob):return hashlib.sha256(blob).hexdigest()

def load_bound(path,expected):
    raw=Path(path).read_bytes();assert sha(raw)==expected,('Stale provenance',path);return json.loads(raw)

def compute(data,payload):
    proof=load_bound(data['membership_path'],data['membership_sha256'])
    assert proof['candidate_map_sha256']==sha(payload)
    original=ACCEPTED.read_bytes();assert proof['baseline_map_sha256']==sha(original)==data['baseline_map_sha256']
    assert sections(original)[3:]==sections(payload)[3:],'Non-render section changed'
    candidate=load_bound(proof['candidate_json_path'],proof['candidate_json_sha256'])
    source=load_bound(proof['cluster_source_path'],proof['cluster_source_sha256'])
    assert candidate['cluster_source_sha256']==proof['cluster_source_sha256']
    baseline=load_bound(data['baseline_sidecar_path'],data['baseline_sidecar_sha256'])
    assert baseline['map_sha256']==sha(original) and source['source_sha256']==baseline['source_sha256']==candidate['source_sha256']
    for k in ['nodes','planes','leaf_clusters','rows','clusters','map_name','map_id','normal_limit','cluster_probes']:
        assert data[k]==baseline[k],('Source visibility changed',k)
    expected_partitions=collections.defaultdict(set)
    expected_counts=collections.Counter()
    for r in source['triangles']:
        expected_partitions[r['material'],r['mask']].update(r['source_ids']);expected_counts[r['material'],r['mask']]+=1
    assert sum(expected_counts.values())==4218 and len({i for s in expected_partitions.values() for i in s})==4218
    assert {(r['material'],r['cluster_mask']) for r in candidate['partitions']}==set(expected_partitions)
    for r in candidate['partitions']:
        k=r['material'],r['cluster_mask'];assert set(r['source_ids'])==expected_partitions[k]
        assert r['source_triangles']==expected_counts[k]
        assert r['attempts'][-1]['missing_pins']==0
        assert r['attempts'][-1]['sampled_max_surface_error']<=r['surface_error_limit']+1e-5
    geometry_masks=collections.defaultdict(int);output_counts=collections.Counter()
    for key,tri in candidate['groups']:
        material,mask=key[0],key[4];assert (material,mask) in expected_partitions
        output_counts[material,mask]+=1
        for expanded in uv_safe_triangles([tri]):
            geometry_masks[material,tuple(sorted(tuple(v[:3]) for v in expanded))]|=mask
    assert all(output_counts[r['material'],r['cluster_mask']]==r['candidate_triangles'] for r in candidate['partitions'])
    guarded=load_bound(data['guard_reference_path'],data['guard_reference_sha256'])
    assert guarded['baseline_map_sha256']==sha(original)
    old_guarded={old for old,new in guarded['transferred_batches'] if new in guarded['pixel_fail_open_chunks']}
    assert set(baseline['pixel_fail_open_chunks'])<=old_guarded
    old=list(batches(original));new=list(batches(payload));entries=proof['batches'];assert len(entries)==len(new)
    masks=[];origins=[];guards=[];transferred=[];terrain=[];all_mask=(1<<data['clusters'])-1
    for i,((material,identity,tris),entry) in enumerate(zip(new,entries)):
        if material in (7,8):
            assert material==entry['material'] and len(tris)==entry['triangles']
            mask=0
            for tri in tris:
                value=geometry_masks[material,tri];assert value,'Packed face lost Blender membership';mask|=value
            assert mask==entry['mask'],'Batch membership does not cover exactly its expanded faces'
            terrain.append(i);origin='Cluster-local terrain; exact expanded-face membership union'
        else:
            j=entry['old_chunk'];assert old[j][1]==identity
            transferred.append([j,i]);mask=baseline['chunk_masks'][j];origin='Unchanged source batch '+str(j)
            if j in old_guarded:mask=all_mask;guards.append(i)
        masks.append(mask);origins.append(origin)
    assert len(transferred)==383 and len({x[0] for x in transferred})==383
    for i in data.get('additional_pixel_fail_open_chunks',[]):
        assert isinstance(i,int) and 0<=i<len(new)
        masks[i]=all_mask;origins[i]='Additional native pixel guard';guards.append(i)
    flags=sections(payload)[6];nonopaque=[i for i,(m,_,_) in enumerate(new) if flags[m]]
    assert all(masks[i]==all_mask for i in nonopaque)
    return dict(chunk_masks=masks,chunk_origins=origins,pixel_fail_open_chunks=sorted(set(guards)),
                source_pixel_guard_chunks=sorted(old_guarded),transferred_batches=transferred,cluster_terrain_chunks=terrain,
                modified_fail_open_chunks=[],nonopaque_fail_open_chunks=nonopaque,
                fail_open_chunks=[i for i,m in enumerate(masks) if m==all_mask])

def validate(data,payload):
    assert data['schema']==4 and sha(payload)==data['map_sha256']
    expected=compute(data,payload)
    for k,v in expected.items():assert data[k]==v,('Cluster provenance mismatch',k)

def export():
    baseline_path=ROOT/'build/n64-visibility-rollout/sidewinder/data/visibility.json'
    reference_path=ROOT/'build/n64-sidewinder-combined/data/visibility.json'
    proof_path=OUT/'data/batch-memberships.json';bank=OUT/'candidate-maps/sidewinder.map64'
    original=ACCEPTED.read_bytes();payload=bank.read_bytes();baseline=json.loads(baseline_path.read_text())
    data={**baseline,'schema':4,'map_sha256':sha(payload),'baseline_map_sha256':sha(original),
          'baseline_sidecar_path':str(baseline_path),'baseline_sidecar_sha256':sha(baseline_path.read_bytes()),
          'guard_reference_path':str(reference_path),'guard_reference_sha256':sha(reference_path.read_bytes()),
          'membership_path':str(proof_path),'membership_sha256':sha(proof_path.read_bytes()),
          'candidate_bank_path':str(bank),'additional_pixel_fail_open_chunks':[],
          'scope':'Source-cluster-local simplification; UV splits and batches carry conservative face-mask unions; unchanged nonterrain and inherited pixel guards preserved.'}
    data.pop('chunk_source_ids',None);data.update(compute(data,payload))
    data['static_bytes']=len(data['nodes'])*12+len(data['planes'])*16+len(data['leaf_clusters'])*2+len(data['chunk_masks'])*8+data['clusters']*8
    validate(data,payload);(OUT/'data/visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({k:data[k] for k in ['map_sha256','static_bytes','source_pixel_guard_chunks','modified_fail_open_chunks']}))

if __name__=='__main__':export()
