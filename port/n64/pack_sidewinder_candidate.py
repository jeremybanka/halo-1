"""Replace only selected terrain render batches in an isolated private map bank."""
import collections
import hashlib
import json
import math
from pathlib import Path
import struct
from pack_maps import bank,uv_safe_triangles,packed
from pack_terrain import indexed_terrain

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-photography'

def sections(blob):
    result=[]
    for index in range(23):
        offset,count,stride=struct.unpack_from('>3I',blob,16+index*12)
        result.append(blob[offset:offset+count*stride])
    return result

def replacement(groups,mi):
    vertices=[];chunks=[];indices=[]
    for key,tris in sorted(groups.items()):
        if key[0]!=mi:continue
        for batch in indexed_terrain(uv_safe_triangles(tris),uv_period=2048 if mi==8 else 1024):
            unique=batch['vertices'];first=len(vertices);vertices.extend(unique)
            bounds=[math.floor(min(v[a] for v in unique)/8) for a in range(3)]+[math.ceil(max(v[a] for v in unique)/8) for a in range(3)]
            start=len(indices);indices.extend(batch['indices']);count=len(batch['indices'])
            while len(indices)%4:indices.append(0)
            chunks.append((first,len(unique),mi,*bounds,start,count))
            if len(vertices)%2:vertices.append(vertices[-1])
    vp=[]
    for a,b in zip(vertices[::2],vertices[1::2]):
        rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        vp.append((*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]))
    return packed('3hH3hHII4h',vp),chunks,packed('H',[(i,) for i in indices])

def assemble(original,groups,path):
    data=sections(original);vertices=bytearray();indices=bytearray();chunks=[];done=set()
    for chunk in struct.iter_unpack('>IHH6hHH',data[1]):
        first,count,mi,*rest=chunk
        if mi in (7,8):
            if mi in done:continue
            done.add(mi);v,cs,ix=replacement(groups,mi)
        else:
            start,index_count=rest[-2:];v=data[0][first//2*32:(first+((count+1)&~1))//2*32]
            ix=data[2][start*2:(start+((index_count+3)&~3))*2]
            cs=[(0,count,mi,*rest[:6],0,index_count)]
        base_vertex=len(vertices)//16;base_index=len(indices)//2
        vertices.extend(v);indices.extend(ix)
        for c in cs:chunks.append((c[0]+base_vertex,*c[1:9],c[9]+base_index,c[10]))
    assert len(chunks)<=512 and len(indices)//2<65536
    data[0]=bytes(vertices);data[1]=packed('IHH6hHH',chunks);data[2]=bytes(indices)
    info=bank(path,1,data)
    original_sections=sections(original);candidate_sections=sections(path.read_bytes())
    assert all(a==b for a,b in zip(original_sections[3:],candidate_sections[3:]))
    # Every nonterrain batch retains its complete vertex bytes, local indices,
    # count, bounds, material and relative draw order; offsets alone may change.
    def unaffected(ss):
        result=[]
        for c in struct.iter_unpack('>IHH6hHH',ss[1]):
            first,count,mi,*rest=c
            if mi in (7,8):continue
            at,n=rest[-2:]
            result.append((count,mi,*rest[:6],ss[0][first//2*32:(first+((count+1)&~1))//2*32],ss[2][at*2:(at+n)*2]))
        return result
    assert unaffected(original_sections)==unaffected(candidate_sections),'Protected render batch changed'
    info.update(vertices=len(vertices)//16,chunks=len(chunks),triangles=sum(c[-1]//3 for c in chunks),
                protected_batches=len(unaffected(original_sections)),all_nonrender_sections_identical=True)
    return info

def main():
    original=(ROOT/'halo64-assets/generated/maps/sidewinder.map64').read_bytes()
    source=json.loads((ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/bsp-source.json').read_text())
    baseline=collections.defaultdict(list)
    for key,tris in source['groups']:baseline[tuple(key)].extend(tris)
    control=OUT/'no-change.map64';assemble(original,baseline,control)
    assert control.read_bytes()==original,'No-change terrain packing must reproduce every byte'
    candidate=json.loads((OUT/'terrain-candidate.json').read_text());groups=collections.defaultdict(list)
    assert candidate['source_sha256']==source['source_sha256']
    for key,tri in candidate['groups']:groups[tuple(key)].append(tri)
    destination=OUT/'candidate-maps';destination.mkdir(exist_ok=True)
    for p in (ROOT/'halo64-assets/generated/maps').iterdir():
        if p.suffix in ('.map64','.bin') and p.name!='sidewinder.map64':
            target=destination/p.name
            if not target.exists():target.symlink_to(p.resolve())
    report=assemble(original,groups,destination/'sidewinder.map64')
    report['baseline_sha256']=hashlib.sha256(original).hexdigest();report['blender_report']=candidate['report']
    report['no_change_control_identical']=True
    (OUT/'packing-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
