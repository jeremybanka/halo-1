"""Conservatively transfer visibility only for exactly preserved geometry.

Changed triangles have no certified source-cluster provenance and fail open.
Opaque terrain batches composed entirely of original geometric triangles can
use the union of their original batch masks. All unchanged nonterrain batches
retain the previously pixel-guarded masks through a verified byte bijection.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
ACCEPTED=ROOT/'halo64-assets/generated/maps/sidewinder.map64'

def sha(data):return hashlib.sha256(data).hexdigest()

def sections(blob):
    return [blob[o:o+n*s] for o,n,s in (struct.unpack_from('>3I',blob,16+12*i) for i in range(23))]

def batches(blob):
    ss=sections(blob)
    for c in struct.iter_unpack('>IHH6hHH',ss[1]):
        first,count,material,*rest=c;at,n=rest[-2:]
        vertex=ss[0][first//2*32:(first+((count+1)&~1))//2*32]
        indices=ss[2][at*2:(at+n)*2]
        identity=(count,material,*rest[:6],vertex,indices)
        points=[]
        for i in range(count):points.append(struct.unpack_from('>3h',vertex,i//2*32+i%2*8))
        ids=[x[0] for x in struct.iter_unpack('>H',indices)]
        triangles=[tuple(sorted(points[i] for i in ids[t:t+3])) for t in range(0,len(ids),3)]
        yield material,identity,triangles

def remap(source,original,candidate,extra_guards=()):
    assert source['map_name']=='sidewinder' and source['map_id']==1
    assert sha(original)==source['map_sha256']
    assert sections(original)[3:]==sections(candidate)[3:],'Non-render sections changed'
    old=list(batches(original));new=list(batches(candidate));all_mask=(1<<source['clusters'])-1
    assert len(old)==len(source['chunk_masks'])
    exact=collections.defaultdict(list);terrain=collections.defaultdict(int)
    for i,(material,identity,tris) in enumerate(old):
        if material in (7,8):
            for tri in tris:terrain[material,tri]|=source['chunk_masks'][i]
        else:exact[identity].append(i)
    masks=[];origins=[];unknown=[];transferred=[];known_terrain=[]
    for j,(material,identity,tris) in enumerate(new):
        if material in (7,8):
            matched=[terrain[material,tri] for tri in tris]
            if all(matched):
                mask=0
                for m in matched:mask|=m
                known_terrain.append(j);origin='exact original terrain triangles'
            else:mask=all_mask;unknown.append(j);origin='modified/unassigned terrain: fail open'
        else:
            assert exact[identity],'Protected batch lost exact identity'
            i=exact[identity].pop(0);mask=source['chunk_masks'][i]
            transferred.append([i,j]);origin='unchanged original batch '+str(i)
        masks.append(mask);origins.append(origin)
    assert not any(exact.values()),'Protected batch missing'
    assert len(transferred)==383
    guards=[new_i for old_i,new_i in transferred if old_i in source['pixel_fail_open_chunks']]
    assert len(guards)==len(source['pixel_fail_open_chunks'])
    for chunk in extra_guards:
        assert isinstance(chunk,int) and 0<=chunk<len(new)
        masks[chunk]=all_mask;origins[chunk]='additional native pixel guard'
    guards=sorted(set(guards)|set(extra_guards))
    assert all(masks[i]==all_mask for i in unknown+guards)
    flags=sections(candidate)[6]
    nonopaque=[i for i,(m,_,_) in enumerate(new) if flags[m]]
    assert all(masks[i]==all_mask for i in nonopaque)
    return dict(nonopaque_fail_open_chunks=nonopaque,chunk_masks=masks,chunk_origins=origins,modified_fail_open_chunks=unknown,
                exact_terrain_chunks=known_terrain,transferred_batches=transferred,
                pixel_fail_open_chunks=guards,fail_open_chunks=[i for i,m in enumerate(masks) if m==all_mask])

def validate(data,payload):
    assert data['schema']==3 and sha(payload)==data['map_sha256']
    source_bytes=Path(data['baseline_sidecar_path']).read_bytes()
    assert sha(source_bytes)==data['baseline_sidecar_sha256'],'Stale baseline sidecar'
    original=ACCEPTED.read_bytes();assert sha(original)==data['baseline_map_sha256']
    source=json.loads(source_bytes)
    for k in ['nodes','planes','leaf_clusters','rows','clusters','map_name','map_id','normal_limit','cluster_probes']:
        assert data[k]==source[k],('Source visibility changed',k)
    expected=remap(source,original,payload,data.get('additional_pixel_fail_open_chunks',[]))
    for k,v in expected.items():assert data[k]==v,('Visibility transfer proof mismatch',k)

def export(sidecar,bank,out):
    out.mkdir(parents=True,exist_ok=True);source_bytes=sidecar.read_bytes();source=json.loads(source_bytes)
    original=ACCEPTED.read_bytes();candidate=bank.read_bytes();mapped=remap(source,original,candidate)
    data={**source,**mapped,'schema':3,'map_sha256':sha(candidate),'baseline_map_sha256':sha(original),
          'baseline_sidecar_path':str(sidecar.resolve()),'baseline_sidecar_sha256':sha(source_bytes),
          'candidate_bank_path':str(bank.resolve()),'remapper_sha256':sha(Path(__file__).read_bytes()),
          'scope':'Exact geometry transfer; modified/unassigned terrain remains visible. Existing nonopaque and pixel exceptions preserved.'}
    data.pop('chunk_source_ids',None)
    data['static_bytes']=len(data['nodes'])*12+len(data['planes'])*16+len(data['leaf_clusters'])*2+len(data['chunk_masks'])*8+data['clusters']*8
    validate(data,candidate)
    (out/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({k:data[k] for k in ['map_sha256','static_bytes','modified_fail_open_chunks','exact_terrain_chunks','pixel_fail_open_chunks']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sidecar',type=Path,required=True)
    p.add_argument('--bank',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();export(a.sidecar,a.bank,a.output)
