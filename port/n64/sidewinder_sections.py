"""Private intact-triangle room/wall batching experiment.

BSP room labels are packing hints, never a new visibility certificate. Each
section keeps the union of its source masks. No sampled camera authorizes a
rejection. Runtime uses the existing conservative AABB and backface tests.
"""
import collections, json, math, struct, sys
from pathlib import Path
import numpy as np
from sidewinder_world_lod import ROOT, decode, sections, sha
from pack_maps import bank, packed

BASE = ROOT/'build/n64-sidewinder-throughput/regions'
OUT = ROOT/'build/n64-sidewinder-sections'

def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda v:v.item())+'\n')

def exact_pack(rows):
    """No corner quantization, UV normalization, triangle splitting or welding."""
    vertices=[]; lookup={}; indices=[]; sources=[]
    for r in rows:
        tri=[tuple(v) for v in r['triangle']]
        missing=set(tri)-lookup.keys()
        if indices and (len(vertices)+len(missing)>60 or len(indices)+3>120):
            yield vertices,indices,sources
            vertices=[];lookup={};indices=[];sources=[]
        for v in tri:
            if v not in lookup:lookup[v]=len(vertices);vertices.append(v)
            indices.append(lookup[v])
        sources.append(r['batch'])
    if indices:yield vertices,indices,sources

def room_at(meta, p, origin):
    q=(p[0]+origin[0],-p[2]+origin[1],p[1]+origin[2]);node=0
    for _ in range(len(meta['nodes'])+1):
        if node<0:return -1 if node==-1 else meta['leaf_clusters'][node&0x7fffffff]
        plane,back,front=meta['nodes'][node];v=meta['planes'][plane]
        node=front if sum(v[a]*q[a] for a in range(3))>=v[3] else back
    raise ValueError('Cyclic BSP')

def bake_cells(meta,payload):
    rs=decode(payload);ss=sections(payload)
    p=np.array([[v[:3] for v in r['triangle']] for r in rs],float)/256
    n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
    owner=np.array([r['batch'] for r in rs]);two=np.array([bool(ss[6][r['material']]&4) for r in rs]);d=(n*p[:,0]).sum(1)
    c=meta['cells'];origin=np.array(c['origin']);step=np.array(c['step']);dims=c['dimensions'];words=(len(meta['chunk_masks'])+31)//32;bits=[]
    for y in range(dims[1]):
      for z in range(dims[2]):
       for x in range(dims[0]):
        lo=origin+step*np.array([x,y,z]);hi=lo+step
        front=(np.where(n>=0,lo,hi)*n).sum(1)<=d+.015;front|=two
        keep=np.zeros(len(meta['chunk_masks']),bool);np.logical_or.at(keep,owner,front)
        bits.extend(sum(int(v)<<bit for bit,v in enumerate(keep[i:i+32])) for i in range(0,len(keep),32))
    return dict(origin=c['origin'],step=c['step'],dimensions=dims,words=words,visible=bits,
                scope='Existing all-eye backface test on intact regrouped sections; no occluder or sampled-camera rejection; outside fails open')

def pack(out=OUT,span=8,plane_step=2):
    out.mkdir(parents=True,exist_ok=True)
    raw=(BASE/'candidate-maps/sidewinder.map64').read_bytes();old=json.loads((BASE/'visibility.json').read_text());ss=sections(raw)
    rows=decode(raw);chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));origin=struct.unpack('>4f',ss[21])[:3]
    groups=collections.defaultdict(list);bybatch=collections.defaultdict(list);room_counts=collections.Counter()
    targets=(1,3) if span<=0 else (1,2,3,4)
    for r in rows:
        b=r['batch'];bybatch[b].append(r);code=old['lod_chunks'][b]
        if code not in targets or ss[6][r['material']]:continue
        p=np.array([v[:3] for v in r['triangle']],float)/256;center=p.mean(0)
        normal=np.cross(p[1]-p[0],p[2]-p[0]);normal/=max(np.linalg.norm(normal),1e-30)
        # Probe toward the rendered side to label the adjacent original room.
        # Classification uncertainty affects batching only; masks stay open.
        room=room_at(old,center-normal*.125,origin);axis=int(np.argmax(abs(normal)))
        direction=2*axis+int(normal[axis]<0)
        cell=tuple(int(math.floor(center[a]/(min(span,4) if a==1 else span))) for a in range(3)) if span>0 else (0,0,0)
        wall=int(math.floor(center[axis]/plane_step)) if plane_step>0 else 0
        if plane_step<0:direction=0
        key=(r['material'],code,room,*cell,direction,wall)
        groups[key].append(r);room_counts[(code,room)]+=1
    first=collections.defaultdict(list)
    for key,rs in groups.items():first[min(r['batch'] for r in rs)].append((key,rs))
    target={r['batch'] for rs in groups.values() for r in rs}
    work=[]
    for b,c in enumerate(chunks):
        for key,rs in sorted(first[b],key=lambda x:x[0]):
            for vs,ix,sources in exact_pack(rs):
                mask=0
                for source in sources:mask|=old['chunk_masks'][source]
                work.append(dict(vertices=vs,indices=ix,material=key[0],code=key[1],mask=mask,
                                 sources=sorted(set(sources)),section=list(key),room=False))
        if b in target:continue
        start,count,mi,*rest=c;at,n=rest[-2:]
        work.append(dict(raw_vertices=ss[0][start*16:(start+((count+1)&~1))*16],
                         raw_indices=ss[2][at*2:(at+n)*2],count=count,bounds=rest[:6],material=mi,
                         code=old['lod_chunks'][b],mask=old['chunk_masks'][b],sources=[b],
                         room=b>=old['representation']['original_chunks']))
    vb=bytearray();ib=bytearray();cb=[]
    for w in work:
        if 'vertices' in w:
            vs=w['vertices'];ix=w['indices'];pad=vs+([vs[-1]] if len(vs)%2 else [])
            rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
            vraw=packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])])
            iraw=packed('H',[(i,) for i in ix]);count=len(vs)
            bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
        else:vraw=w['raw_vertices'];iraw=w['raw_indices'];count=w['count'];bounds=w['bounds']
        cb.append((len(vb)//16,count,w['material'],*bounds,len(ib)//2,len(iraw)//2));vb.extend(vraw);ib.extend(iraw)
        while len(ib)%8:ib.extend(b'\0\0')
    assert len(cb)<4096 and len(ib)//2<65536
    ss[:3]=[bytes(vb),packed('IHH6hHH',cb),bytes(ib)]
    directory=out/'candidate-maps';directory.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (directory/p.name).exists():(directory/p.name).symlink_to(p.resolve())
    result=bank(directory/'sidewinder.map64',1,ss);payload=(directory/'sidewinder.map64').read_bytes()
    data={**old,'schema':12,'map_sha256':sha(payload),'candidate_bank_path':str(directory/'sidewinder.map64'),
          'section_baseline':str(BASE/'visibility.json'),'section_baseline_sha256':sha((BASE/'visibility.json').read_bytes()),
          'section_span':span,'section_plane_step':plane_step,'section_target_codes':list(targets),'section_sources':[w['sources'] for w in work],
          'chunk_masks':[w['mask'] for w in work],'lod_chunks':[w['code'] for w in work],
          'representation':{**old['representation'],'original_chunks':sum(not w['room'] for w in work),'total_chunks':len(work)}}
    data['cells']=bake_cells(data,payload)
    save(out/'visibility.json',data)
    validation=validate(data,payload);save(out/'geometry-validation.json',validation)
    from export_chiron_visibility import emit_c
    emit_c(data,out/'visibility-data.c',directory/'sidewinder.map64')
    report=dict(**result,source_chunks=len(chunks),chunks=len(work),source_target_chunks=len(target),
                target_chunks=sum('section' in w for w in work),visibility_sections=len(groups),
                section_keys=[w.get('section') for w in work],room_faces={str(k):v for k,v in room_counts.items()},
                additional_bank_bytes=len(payload)-len(raw),additional_cell_bytes=(len(data['cells']['visible'])-len(old['cells']['visible']))*4)
    save(out/'packing-report.json',report)
    print(out.name,'chunks',len(chunks),'->',len(work),'target',len(target),'->',report['target_chunks'],validation,flush=True)

def validate(data,payload):
    source=Path(data['section_baseline']);assert sha(source.read_bytes())==data['section_baseline_sha256']
    old=json.loads(source.read_text());raw=Path(old['candidate_bank_path']).read_bytes()
    assert sha(raw)==old['map_sha256'] and sha(payload)==data['map_sha256']
    # This private format spells fail-open as the explicit all-cluster mask.
    # Reject zero-mask ambiguity before validating unions as set inclusion.
    for meta in (old,data):
        assert all(isinstance(m,int) and 0<m<(1<<meta['clusters']) for m in meta['chunk_masks'])
    assert sections(raw)[3:]==sections(payload)[3:],'Non-render sections changed'
    for k in ('nodes','planes','leaf_clusters','rows','clusters','lod_groups','map_id'):assert data[k]==old[k],k
    for k in old['representation']:
        if k not in ('original_chunks','total_chunks'):assert data['representation'][k]==old['representation'][k]
    def identity(r,m):
        b=r['batch'];return (r['material'],m['lod_chunks'][b],b>=m['representation']['original_chunks'],tuple(tuple(v) for v in r['triangle']))
    before=decode(raw);after=decode(payload)
    # The decoder's eight fields omit the unused packed normal and alpha.
    # Verify those assumptions explicitly before claiming full preservation.
    for blob,meta in ((raw,old),(payload,data)):
        ss=sections(blob)
        for c in struct.iter_unpack('>IHH6hHH',ss[1]):
            first,count,mi,*rest=c;at,n=rest[-2:]
            assert 0<count<=60 and n%3==0 and n<=120
            indices=struct.unpack_from('>'+str(n)+'H',ss[2],at*2)
            assert all(i<count for i in indices)
            for i in range(count):
                offset=(first+i)//2*32;half=(first+i)%2
                assert struct.unpack_from('>H',ss[0],offset+half*8+6)[0]==0
                assert ss[0][offset+16+half*4+3]==255
                point=struct.unpack_from('>3h',ss[0],offset+half*8)
                assert all(rest[a]<=point[a]/8<=rest[a+3] for a in range(3))
    assert collections.Counter(identity(r,old) for r in before)==collections.Counter(identity(r,data) for r in after),'Exact triangle/corner multiset changed'
    expected=collections.defaultdict(collections.Counter)
    for r in before:expected[r['batch']][identity(r,old)]+=1
    for r in after:
        b=r['batch'];key=identity(r,data);origins=data['section_sources'][b]
        matches=[o for o in origins if expected[o][key]>0];assert matches,(b,'Unproven triangle')
        o=matches[0];expected[o][key]-=1
        assert data['chunk_masks'][b]&old['chunk_masks'][o]==old['chunk_masks'][o],'Source visibility narrowed'
    assert all(not +counter for counter in expected.values())
    # Every unaffected batch retains exact attributes, index order and bounds.
    from remap_sidewinder_visibility import batches
    a=list(batches(raw));b=list(batches(payload));retained=0
    for i,origins in enumerate(data['section_sources']):
        if old['lod_chunks'][origins[0]] not in data['section_target_codes'] or sections(raw)[6][a[origins[0]][0]]:
            assert len(origins)==1 and a[origins[0]][1]==b[i][1];retained+=1
    expected_cells=bake_cells({**data,'cells':old['cells']},payload)
    if data.get('section_rejection_control'):
        for at in range(0,len(expected_cells['visible']),expected_cells['words']):
            for b,code in enumerate(data['lod_chunks']):
                if code in data['section_target_codes']:expected_cells['visible'][at+b//32]|=1<<(b%32)
    assert data['cells']==expected_cells,'Backface table mismatch'
    return dict(triangles=len(before),exact_corner_attributes=True,exact_winding=True,exact_lod_policy=True,
                non_render_sections_byte_identical=True,source_masks_never_narrowed=True,
                unchanged_batches=retained,all_eye_backface_table_verified=True)

def control():
    """Frozen-image diagnostic: same batching, permissive target rejection."""
    out=OUT/'rejection-control';out.mkdir(exist_ok=True);directory=out/'candidate-maps';directory.mkdir(exist_ok=True)
    data=json.loads((OUT/'visibility.json').read_text());raw=(OUT/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(raw)
    rows=[list(c) for c in struct.iter_unpack('>IHH6hHH',ss[1])]
    for b,c in enumerate(rows):
        if data['lod_chunks'][b] in data['section_target_codes']:c[3:9]=[-32768]*3+[32767]*3
    ss[1]=packed('IHH6hHH',rows);result=bank(directory/'sidewinder.map64',1,ss)
    for p in (OUT/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (directory/p.name).exists():(directory/p.name).symlink_to(p.resolve())
    for at in range(0,len(data['cells']['visible']),data['cells']['words']):
        for b,code in enumerate(data['lod_chunks']):
            if code in data['section_target_codes']:data['cells']['visible'][at+b//32]|=1<<(b%32)
    data.update(map_sha256=result['sha256'],candidate_bank_path=str(directory/'sidewinder.map64'),section_rejection_control=True)
    save(out/'visibility.json',data);validate(data,(directory/'sidewinder.map64').read_bytes())
    print('Prepared conservative rejection-disabled diagnostic',flush=True)

if __name__=='__main__':
    pack(Path(sys.argv[1]).resolve() if len(sys.argv)>1 else OUT,float(sys.argv[2]) if len(sys.argv)>2 else 8,float(sys.argv[3]) if len(sys.argv)>3 else 2)
