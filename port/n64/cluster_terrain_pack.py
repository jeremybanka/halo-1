"""Pack cluster-local terrain, propagating each face membership through UV splits."""
import collections
import hashlib
import json
import math
from pathlib import Path
import struct
from pack_maps import bank,packed,uv_safe_triangles
from pack_terrain import indexed_terrain
from pack_sidewinder_candidate import assemble,sections

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-cluster-terrain'

def sha(blob):return hashlib.sha256(blob).hexdigest()

def replacement(groups,material):
    vertices=[];indices=[];chunks=[];members=[]
    for key,records in sorted(groups.items()):
        if key[0]!=material:continue
        tris=[];masks=[]
        for mask,tri in sorted(records,key=lambda r:r[0]):
            expanded=uv_safe_triangles([tri]);tris.extend(expanded);masks.extend([mask]*len(expanded))
        # The batcher preserves face order. UV subdivisions inherit their
        # parent membership; a mixed batch gets the union, never one owner.
        at=0
        for batch in indexed_terrain(tris,uv_period=2048 if material==8 else 1024):
            unique=batch['vertices'];first=len(vertices);vertices.extend(unique)
            start=len(indices);ix=batch['indices'];count=len(ix);indices.extend(ix)
            while len(indices)%4:indices.append(0)
            bounds=[math.floor(min(v[a] for v in unique)/8) for a in range(3)]+[math.ceil(max(v[a] for v in unique)/8) for a in range(3)]
            chunks.append((first,len(unique),material,*bounds,start,count))
            partition_masks=sorted(set(masks[at:at+count//3]));mask=0
            for m in partition_masks:mask|=m
            members.append({'mask':mask,'partition_masks':partition_masks,'material':material,'triangles':count//3})
            at+=count//3
            if len(vertices)%2:vertices.append(vertices[-1])
        assert at==len(tris)
    pairs=[]
    for a,b in zip(vertices[::2],vertices[1::2]):
        rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        pairs.append((*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]))
    return packed('3hH3hHII4h',pairs),chunks,packed('H',[(i,) for i in indices]),members

def pack():
    original=(ROOT/'halo64-assets/generated/maps/sidewinder.map64').read_bytes()
    source_path=OUT/'data/cluster-source.json';source=json.loads(source_path.read_text())
    candidate_path=OUT/'terrain-candidate.json';candidate=json.loads(candidate_path.read_text())
    assert sha(source_path.read_bytes())==candidate['cluster_source_sha256']
    assert candidate['source_sha256']==source['source_sha256']
    valid={(r['material'],r['mask']) for r in source['triangles']}
    groups=collections.defaultdict(list)
    for key,tri in candidate['groups']:
        assert (key[0],key[4]) in valid
        groups[tuple(key[:4])].append((key[4],tri))
    preview=json.loads(Path(source['preview_path']).read_text());control_groups=collections.defaultdict(list)
    for key,tris in preview['groups']:control_groups[tuple(key)].extend(tris)
    assemble(original,control_groups,OUT/'no-change.map64');assert (OUT/'no-change.map64').read_bytes()==original
    ss=sections(original);vertex=bytearray();indices=bytearray();chunks=[];proof=[];done=set()
    for old_chunk,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c
        if material in (7,8):
            if material in done:continue
            done.add(material);v,cs,ix,ms=replacement(groups,material)
        else:
            at,n=rest[-2:];v=ss[0][first//2*32:(first+((count+1)&~1))//2*32]
            ix=ss[2][at*2:(at+((n+3)&~3))*2];cs=[(0,count,material,*rest[:6],0,n)];ms=[{'old_chunk':old_chunk}]
        bv=len(vertex)//16;bi=len(indices)//2;vertex.extend(v);indices.extend(ix)
        for c,m in zip(cs,ms):chunks.append((c[0]+bv,*c[1:9],c[9]+bi,c[10]));proof.append(m)
    assert len(chunks)<=512 and len(indices)//2<65536
    destination=OUT/'candidate-maps';destination.mkdir(exist_ok=True)
    for p in (ROOT/'halo64-assets/generated/maps').iterdir():
        if p.suffix in ('.map64','.bin') and p.name!='sidewinder.map64' and not (destination/p.name).exists():(destination/p.name).symlink_to(p.resolve())
    ss[0]=bytes(vertex);ss[1]=packed('IHH6hHH',chunks);ss[2]=bytes(indices)
    report=bank(destination/'sidewinder.map64',1,ss);blob=(destination/'sidewinder.map64').read_bytes()
    assert sections(blob)[3:]==sections(original)[3:]
    from remap_sidewinder_visibility import batches
    before=list(batches(original));after=list(batches(blob))
    for i,m in enumerate(proof):
        if 'old_chunk' in m:assert before[m['old_chunk']][1]==after[i][1]
    assert sum('old_chunk' in m for m in proof)==383
    record={'schema':1,'candidate_map_sha256':sha(blob),'baseline_map_sha256':sha(original),
            'candidate_json_path':str(candidate_path),'candidate_json_sha256':sha(candidate_path.read_bytes()),
            'cluster_source_path':str(source_path),'cluster_source_sha256':sha(source_path.read_bytes()),'batches':proof}
    (OUT/'data/batch-memberships.json').write_text(json.dumps(record,separators=(',',':'))+'\n')
    report.update(vertices=len(vertex)//16,chunks=len(chunks),triangles=sum(c[-1]//3 for c in chunks),protected_batches=383,
                  all_nonrender_sections_identical=True,no_change_control_identical=True,baseline_sha256=sha(original),blender_report=candidate['report'],
                  terrain_membership_batches=sum('mask' in m for m in proof),mixed_membership_batches=sum(len(m.get('partition_masks',[]))>1 for m in proof))
    (OUT/'packing-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['vertices','chunks','triangles','terrain_membership_batches','mixed_membership_batches']}))

if __name__=='__main__':pack()
