"""Exact-bank, all-eye visibility experiment for central tunnels and west base.

No triangles, attributes, batches, LOD policy or gameplay bytes are changed.
Opaque polygons are reconstructed from this bank, never from an older mesh.
"""
import collections, csv, hashlib, json, math, os, shutil, struct, sys
from pathlib import Path
import numpy as np
from sidewinder_world_lod import ROOT, decode, sections

BASE = ROOT / 'build/n64-sidewinder-throughput/regions'
OUT = ROOT / 'build/n64-sidewinder-visibility-audit'
TARGETS = (0, 1)

def save(name, value):
    (OUT/name).write_text(json.dumps(value, separators=(',', ':'), default=lambda v:v.item())+'\n')

def setup():
    OUT.mkdir(exist_ok=True)
    (OUT/'candidate-maps').mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        dest=OUT/'candidate-maps'/p.name
        if not dest.exists():dest.symlink_to(p.resolve())
    return json.loads((BASE/'visibility.json').read_text()), (BASE/'candidate-maps/sidewinder.map64').read_bytes()

def occluders():
    from shapely.geometry import Polygon
    from shapely.ops import unary_union, triangulate
    meta,payload=setup();rows=decode(payload);flags=sections(payload)[6]
    groups=collections.defaultdict(list)
    for ri,r in enumerate(rows):
        code=meta['lod_chunks'][r['batch']]
        if code not in (1,3) or flags[r['material']]:continue
        p=np.array([v[:3] for v in r['triangle']],dtype=np.int64)
        n=np.cross(p[1]-p[0],p[2]-p[0]);g=math.gcd(*map(int,n))
        if not g:continue
        n//=g;key=(code,*map(int,n),int(n@p[0]))
        groups[key].append((ri,r))
    result=[]
    for key,rs in groups.items():
        code,*plane=key;n=np.array(plane[:3]);drop=int(np.argmax(abs(n)));axes=[a for a in range(3) if a!=drop]
        union=unary_union([Polygon([[v[a]/256 for a in axes] for v in r['triangle']]) for _,r in rs])
        if union.area<.25:continue
        pieces=[t for t in triangulate(union) if union.covers(t)]
        changed=True
        while changed:
            changed=False
            for i in range(len(pieces)):
                for j in range(i+1,len(pieces)):
                    if not pieces[i].intersects(pieces[j]):continue
                    u=pieces[i].union(pieces[j]);h=u.convex_hull
                    if h.area-u.area<1e-10 and len(h.exterior.coords)<=9:
                        pieces[i]=h;pieces.pop(j);changed=True;break
                if changed:break
        masks=sorted(set(meta['chunk_masks'][r['batch']] for _,r in rs))
        for polygon in pieces:
            # Inset beyond packing precision; never bridge a door or hole.
            p=polygon.buffer(-.05,join_style=2)
            if p.is_empty or p.geom_type!='Polygon' or p.area<.2:continue
            assert union.covers(p) and p.equals(p.convex_hull)
            points=[]
            for q in list(p.exterior.coords)[:-1]:
                xyz=np.zeros(3);xyz[axes]=q;xyz[drop]=(plane[3]/256-n[axes]@q)/n[drop];points.append(xyz)
            result.append(dict(points=np.array(points).tolist(),normal=(n/np.linalg.norm(n)).tolist(),
                plane=plane,group=(code-1)//2,area=p.area,support_faces=[i for i,_ in rs],support_masks=masks))
    result.sort(key=lambda o:o['area'],reverse=True)
    save('occluders.json',result)
    print('Certified inset convex polygons',len(result),collections.Counter(o['group'] for o in result),flush=True)

def bake(fine=False):
    from report_budget_cells import cell_row
    meta,payload=setup();ss=sections(payload);chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));rows=decode(payload)
    target=np.array([bool(meta['lod_chunks'][r['batch']] and (meta['lod_chunks'][r['batch']]-1)//2 in TARGETS) for r in rows])
    ids=np.flatnonzero(target);rs=[rows[i] for i in ids];owner=np.array([r['batch'] for r in rs])
    ps=np.array([[v[:3] for v in r['triangle']] for r in rs],float)/256
    ns=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);ns/=np.maximum(np.linalg.norm(ns,axis=1)[:,None],1e-30)
    dots=(ns*ps[:,0]).sum(1);two=np.array([bool(ss[6][r['material']]&4) for r in rs])
    occ=json.loads((OUT/'occluders.json').read_text());all_mask=(1<<meta['clusters'])-1
    # Runtime camera masks are unions of these rows, or the all-visible fallback.
    # If a target is eligible in any row, EVERY supporting wall face must be too.
    camera_rows=list(set(meta['rows']+[all_mask]));tm=np.array([meta['chunk_masks'][r['batch']] or all_mask for r in rs],dtype=np.uint64)
    for o in occ:
        allowed=np.ones(len(rs),bool)
        for mask in camera_rows:
            if any(m and not(m&mask) for m in o['support_masks']):allowed&=(tm&mask)==0
        o['allowed']=allowed;o['p']=np.array(o['points']);o['n']=np.array(o['normal'])
    origin=np.array([-44,-6,6] if fine else [-64,-6,-64]);step=np.array([2,1,2] if fine else [4,2,4]);dims=[36,12,24] if fine else [32,4,32];words=meta['cells']['words']
    output=[];proof=[];summary=[];target_chunks=sorted(set(owner));near_clearance=.35 if fine else 1.6
    on=np.array([o['n'] for o in occ]);od=np.array([o['n']@o['p'][0] for o in occ]);og=np.array([o['group'] for o in occ])
    face_lists={b:np.flatnonzero(owner==b) for b in target_chunks}
    behind=(ps@on.T).min(1)>od+.04
    layer=os.environ.get('SIDEWINDER_AUDIT_LAYER') if fine else None
    layers=[] if layer=='merge' else [int(layer)] if layer is not None else range(dims[1])
    for y in layers:
      for z in range(dims[2]):
       for x in range(dims[0]):
        lo=origin+step*np.array([x,y,z]);hi=lo+step
        eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)])
        old=cell_row(meta,(lo+hi)/2);bits=old.copy() if old is not None else [0xffffffff]*words
        front=(np.where(ns>=0,lo,hi)*ns).sum(1)<=dots+.02;front|=two
        witnesses=np.full(len(rs),-2,dtype=np.int32);witnesses[~front]=-1
        near=[]
        for gi in TARGETS:
            g=meta['lod_groups'][gi];bounds=np.array(g['bounds']);delta=np.maximum(np.maximum(bounds[:3]-lo,hi-bounds[3:]),0)
            near.append(delta@delta < (g['near_distance']-.02)**2)
        eligible=((lo+hi)/2@on.T + (hi-lo)/2@abs(on).T-od < -near_clearance)&np.array(near)[og]
        for oi in np.flatnonzero(eligible):
            o=occ[oi]
            p,n=o['p'],o['n'];d=n@p[0]
            if (eyes@n-d).max()>-near_clearance:continue
            g=meta['lod_groups'][o['group']];bounds=np.array(g['bounds']);delta=np.maximum(np.maximum(bounds[:3]-eyes,eyes-bounds[3:]),0)
            # All cameras in this cell are forced to use the original wall.
            if (delta*delta).sum(1).max()>=(g['near_distance']-.02)**2:continue
            selected=np.flatnonzero((witnesses==-2)&o['allowed']&behind[:,oi])
            if not len(selected):continue
            center=p.mean(0)
            for eye in eyes:
                for a,b in zip(p,np.roll(p,-1,axis=0)):
                    v=np.cross(b-eye,a-eye);length=np.linalg.norm(v)
                    if length<1e-12:selected=selected[:0];break
                    v/=length
                    if v@(center-eye)<0:v=-v
                    selected=selected[(ps[selected]@v).min(1)>v@eye+.025]
                    if not len(selected):break
                if not len(selected):break
            witnesses[selected]=oi
        changed=[]
        for b in target_chunks:
            if not (bits[b//32]>>(b%32)&1):continue
            faces=face_lists[b]
            if np.all(witnesses[faces]!=-2):
                bits[b//32]&=~(1<<(b%32));changed.append(b)
        cell=(y*dims[2]+z)*dims[0]+x
        if changed:
            proof.append(dict(cell=cell,chunks=changed,witnesses=[[int(ids[i]),int(witnesses[i])] for i in np.flatnonzero(np.isin(owner,changed))]))
        output.extend(bits);summary.append([len(changed),sum((chunks[b][1]+1)&~1 for b in changed),int(np.count_nonzero(witnesses>=0))])
      print('layer',y,'new batch rejections',sum(s[0] for s in summary),'max loads',max(s[1] for s in summary),flush=True)
    if layer is not None and layer!='merge':
        save('layer-'+layer+'.json',dict(visible=output,certificates=proof,statistics=summary));return
    if layer=='merge':
        for y in range(dims[1]):
            part=json.loads((OUT/f'layer-{y}.json').read_text());output+=part['visible'];proof+=part['certificates'];summary+=part['statistics']
    meta['candidate_bank_path']=str(OUT/'candidate-maps/sidewinder.map64')
    fallback=meta['cells']
    meta['cells']=dict(origin=origin.tolist(),step=step.tolist(),dimensions=dims,words=words,visible=output,
        scope='Unchanged baseline masks plus target-only all-eye backface / opaque shadow certificates. Original near wall guaranteed throughout cell; all PVS-row unions covered.',near_clearance=near_clearance)
    if fine:
        meta['schema']=11;meta['cells']['fallback']=fallback;meta['cells']['unscoped_only']=True
    meta['audit_baseline']=str(BASE/'visibility.json')
    save('visibility.json',meta);save('certificates.json',proof);save('bake-statistics.json',summary)
    from export_chiron_visibility import emit_c
    emit_c(meta,OUT/'visibility-data.c',OUT/'candidate-maps/sidewinder.map64')
    print('table bytes',len(output)*4,'certified cells',len(proof),'bank unchanged',hashlib.sha256(payload).hexdigest(),flush=True)

def parallel_bake():
    import concurrent.futures,subprocess
    def run(layer):
        env={**os.environ,'SIDEWINDER_AUDIT_LAYER':str(layer),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
        with (OUT/f'layer-{layer}.log').open('w') as f:
            subprocess.run([sys.executable,__file__,'fine'],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        print('finished layer',layer,flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,range(12)))
    os.environ['SIDEWINDER_AUDIT_LAYER']='merge';bake(True)

def validate_bank(data,payload):
    old=json.loads((BASE/'visibility.json').read_text())
    assert payload==(BASE/'candidate-maps/sidewinder.map64').read_bytes()
    for key in old:
        if key not in ('cells','candidate_bank_path','schema'):assert data[key]==old[key],key
    c=data['cells'];assert len(c['visible'])==math.prod(c['dimensions'])*c['words']
    assert c['fallback']==old['cells'] and c['unscoped_only'] and c['near_clearance']==.35

def emit_cells(data):
    from sidewinder_budget_cells import emit_cells as legacy
    c=data['cells'];fallback=legacy({**data,'cells':c['fallback']}).replace('world_cells_visible','audit_fallback_visible').replace('bg_world_cells=','audit_fallback=')
    unique=[];lookup={};indices=[];words=c['words']
    for at in range(0,len(c['visible']),words):
        row=tuple(c['visible'][at:at+words])
        if row not in lookup:lookup[row]=len(unique);unique.append(row)
        indices.append(lookup[row])
    assert len(unique)<65536
    f=lambda v:float(v).hex()+'f'
    text=fallback+'static const uint16_t audit_indices[]={'+','.join(map(str,indices))+'};\n'
    text+='static const uint32_t audit_visible[]={'+','.join('0x%xU'%v for row in unique for v in row)+'};\n'
    text+='const bg_world_cells_data bg_world_cells={{'+','.join(f(v*32) for v in c['origin'])+'},{'+','.join(f(v*32) for v in c['step'])+'},{'+','.join(map(str,c['dimensions']))+'},'+','.join(map(str,[words,len(data['chunk_masks']),data['map_id']]))+',audit_visible,audit_indices,&audit_fallback};\n'
    save('table-packing.json',dict(cells=len(indices),unique_rows=len(unique),index_bytes=len(indices)*2,row_bytes=len(unique)*words*4,fallback_bytes=len(c['fallback']['visible'])*4))
    return text

def audit():
    """Attribute actual submissions and final visible pixels; no sampled culling."""
    import ctypes, inspect
    from PIL import Image, ImageDraw
    from photo_sidewinder_structures import load_bank, render
    from report_budget_cells import selected, native_faces
    from report_world_lod import subset
    meta,payload=setup();chunks=list(struct.iter_unpack('>IHH6hHH',sections(payload)[1]));bank=load_bank(BASE/'candidate-maps/sidewinder.map64')
    dll=ctypes.CDLL(str(ROOT/'build/n64-sidewinder-canyon-rebuild/culler.dylib'))
    dll.box.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.POINTER(ctypes.c_int16),ctypes.c_int,ctypes.c_int]
    source=inspect.getsource(render).replace('def render(', 'def render_ids(')
    source=source.replace('clip=np.concatenate', 'ids=np.full((h,w),-1,dtype=np.int32)\n    clip=np.concatenate')
    source=source.replace('image[y0+yy0,x0+xx0]=', 'ids[y0+yy0,x0+xx0]=owners[ti]\n            image[y0+yy0,x0+xx0]=')
    source=source.replace('return (image,np.isfinite(depth)) if return_mask else image', 'return image,ids')
    ns=dict(np=np);exec(source,ns);render_ids=ns['render_ids']
    coverage=source.replace('def render_ids(', 'def render_coverage(').replace('ids=np.full','covered=set()\n    ids=np.full').replace('&(z<old)','')
    coverage=coverage.replace('ids[y0+yy0,x0+xx0]=owners[ti]','if len(yy0):covered.add(int(owners[ti]))\n            ids[y0+yy0,x0+xx0]=owners[ti]').replace('return image,ids','return covered')
    exec(coverage,ns);render_coverage=ns['render_coverage']
    (OUT/'audit-images').mkdir(exist_ok=True);records=[]
    cameras={(int(r['tick']),int(r['camera'])):r for r in csv.DictReader((BASE/'replay/cameras.csv').open()) if r['candidate']=='1'}
    for row in csv.reader((BASE/'replay/lod-trace.csv').open()):
        tick,cam=map(int,row[:2]);pose=cameras[tick,cam];eye=[float(pose['eye_'+a]) for a in 'xyz'];levels=np.array(list(map(int,row[18:])));matrix=np.array(list(map(float,row[2:18]))).reshape(4,4)
        view=selected(bank,meta,levels,eye);mask=int(pose['pvs_mask']);mat=(ctypes.c_float*16)(*map(float,row[2:18]));submitted=[]
        for b in sorted(set(map(int,view[2]))):
            if meta['chunk_masks'][b] and not meta['chunk_masks'][b]&mask:continue
            if dll.box(mat,(ctypes.c_int16*6)(*chunks[b][3:9]),160,120):submitted.append(b)
        assert sum((chunks[b][1]+1)&~1 for b in submitted)==int(pose['vertices'])
        view=subset(view,np.isin(view[2],submitted));front=native_faces(view,eye);image,ids=render_ids(front,matrix,width=160,height=120)
        covered=render_coverage(front,matrix,width=160,height=120);front_owners=set(map(int,front[2]))
        costs={};labels=np.full((120,160,3),(18,24,34),dtype=np.uint8)
        for gi,color in [(0,(242,171,71)),(1,(102,206,230))]:
            bs=[b for b in submitted if meta['lod_chunks'][b] and (meta['lod_chunks'][b]-1)//2==gi]
            live=set(map(int,ids[np.isin(ids,bs)].ravel()));invisible=[b for b in bs if b not in live]
            costs[str(gi)]=dict(loads=sum((chunks[b][1]+1)&~1 for b in bs),batches=len(bs),visible_pixels=int(np.isin(ids,bs).sum()),
                zero_pixel_batch_loads=sum((chunks[b][1]+1)&~1 for b in invisible),zero_pixel_batches=invisible)
            costs[str(gi)]['zero_pixel_reasons']={label:sum((chunks[b][1]+1)&~1 for b in invisible if predicate(b)) for label,predicate in [
                ('all_backfacing',lambda b:b not in front_owners),
                ('clipped_or_subpixel',lambda b:b in front_owners and b not in covered),
                ('depth_hidden',lambda b:b in covered)]}
            labels[np.isin(ids,bs)]=color
        if (tick,cam) in [(180,3),(600,2),(1500,2),(1950,0)]:
            prefix=f'audit-images/{tick}-{cam}'
            Image.fromarray(image).save(OUT/(prefix+'-normal.png'));Image.fromarray(labels).save(OUT/(prefix+'-visible.png'))
            # Wireframe of every submitted target face, without depth hiding.
            wire=Image.fromarray((image*.25).astype(np.uint8));draw=ImageDraw.Draw(wire)
            for tri,b in zip(view[0],view[2]):
                code=meta['lod_chunks'][int(b)]
                if not code or (code-1)//2 not in TARGETS:continue
                clip=np.c_[tri[:,:3],np.ones(3)]@matrix
                if np.any(clip[:,3]<=0):continue
                ndc=clip[:,:2]/clip[:,3,None];points=[((p[0]+1)*80,(1-p[1])*60) for p in ndc]
                if any(abs(x)>10000 or abs(y)>10000 for x,y in points):continue
                draw.line(points+[points[0]],fill=(242,171,71) if (code-1)//2==0 else (102,206,230))
            wire.save(OUT/(prefix+'-submitted.png'))
        records.append(dict(tick=tick,camera=cam,pose=pose,groups=costs))
    save('audit.json',dict(scope='Final static-world visible pixels at 160x120; zero pixels in sampled views is diagnostic, never permission to cull. Occlusion, backface, clipping and subpixel effects all contribute.',cameras=records))
    for gi in TARGETS:
        print('Group',gi,{k:round(np.mean([r['groups'][str(gi)][k] for r in records]),2) for k in ('loads','visible_pixels','zero_pixel_batch_loads')},flush=True)

def validate():
    """Recheck certificates through segment/polygon intersections, independently
    of the bake's shadow halfspaces, plus exact bank and metadata preservation."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from report_budget_cells import cell_row
    old,payload=setup();new=json.loads((OUT/'visibility.json').read_text());rows=decode(payload)
    assert (OUT/'candidate-maps/sidewinder.map64').read_bytes()==payload
    for key in old:
        if key not in ('cells','candidate_bank_path','schema'):assert new[key]==old[key],key
    occ=json.loads((OUT/'occluders.json').read_text());proof=json.loads((OUT/'certificates.json').read_text());ss=sections(payload)
    for o in occ:
        n=np.array(o['normal']);drop=int(np.argmax(abs(n)));axes=[a for a in range(3) if a!=drop]
        source=unary_union([Polygon([[v[a]/256 for a in axes] for v in rows[i]['triangle']]) for i in o['support_faces']])
        poly=Polygon(np.array(o['points'])[:,axes]);assert source.covers(poly) and poly.equals(poly.convex_hull)
        assert all(not ss[6][rows[i]['material']] and new['lod_chunks'][rows[i]['batch']]==1+2*o['group'] for i in o['support_faces'])
    bycell={r['cell']:r for r in proof};c=new['cells'];words=c['words'];dims=c['dimensions'];all_mask=(1<<new['clusters'])-1
    checks=0;occluded_faces=0;back_faces=0;rng=np.random.default_rng(71523)
    batch_faces=collections.defaultdict(list)
    for i,r in enumerate(rows):batch_faces[r['batch']].append(i)
    for cell in range(math.prod(dims)):
        x=cell%dims[0];z=(cell//dims[0])%dims[2];y=cell//(dims[0]*dims[2]);lo=np.array(c['origin'])+np.array(c['step'])*[x,y,z];hi=lo+c['step']
        before=cell_row(old,(lo+hi)/2) or [0xffffffff]*words;after=c['visible'][cell*words:(cell+1)*words]
        removed=[b for b in range(len(new['chunk_masks'])) if before[b//32]>>(b%32)&1 and not after[b//32]>>(b%32)&1]
        assert all(a&~b==0 for a,b in zip(after,before))
        if not removed:assert cell not in bycell;continue
        cert=bycell[cell];assert removed==cert['chunks'];witness=dict(cert['witnesses'])
        eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)]+[rng.uniform(lo,hi).tolist() for _ in range(4)])
        expected={i for b in removed for i in batch_faces[b]};assert set(witness)==expected
        for i in expected:
            r=rows[i]
            assert i in witness and new['lod_chunks'][r['batch']] in (1,2,3,4)
            points=np.array([v[:3] for v in r['triangle']],float)/256
            if witness[i]==-1:
                assert not(ss[6][r['material']]&4)
                n=np.cross(points[1]-points[0],points[2]-points[0]);assert np.all((eyes-points[0])@n>0)
                back_faces+=1;continue
            o=occ[witness[i]];p=np.array(o['points']);n=np.array(o['normal']);g=new['lod_groups'][o['group']];bounds=np.array(g['bounds'])
            delta=np.maximum(np.maximum(bounds[:3]-eyes,eyes-bounds[3:]),0)
            assert np.all((delta*delta).sum(1)<g['near_distance']**2)
            assert np.all((eyes-p[0])@n < -c['near_clearance']+1e-8)
            targetmask=new['chunk_masks'][r['batch']] or all_mask
            for mask in set(new['rows']+[all_mask]):
                if mask&targetmask:assert all(not m or mask&m for m in o['support_masks'])
            # All triangle corners and its centroid, from all cell corners and
            # independent random interior eyes: ray hits inside the real wall.
            q=np.concatenate((points,points.mean(0)[None,:]));direction=q[None,:,:]-eyes[:,None,:]
            t=((p[0]-eyes)@n)[:,None]/(direction@n)
            assert np.all((t>0)&(t<1));hits=eyes[:,None,:]+t[:,:,None]*direction
            center=p.mean(0)
            for a,b in zip(p,np.roll(p,-1,axis=0)):
                edge=np.cross(b-a,n)
                if edge@(center-a)<0:edge=-edge
                assert np.all((hits-a)@edge>0)
            checks+=hits.shape[0]*hits.shape[1];occluded_faces+=1
    result=dict(bank_byte_identical=True,map_sha256=hashlib.sha256(payload).hexdigest(),lod_and_cluster_metadata_identical=True,
        source_polygons=len(occ),certified_cells=len(proof),occluded_face_certificates=occluded_faces,backface_certificates=back_faces,
        independent_segment_checks=checks,non_target_visibility_unchanged=True,cell_table_bytes=len(c['visible'])*4,
        guarantee=f'All cell eye positions, original near LOD guaranteed, opaque source polygons inset 0.05 world units, PVS-row implication, {c["near_clearance"]}-unit wall clearance; scoped/outside fine grid retains baseline visibility.',
        limits='Finite image tests supplement conservative geometric certificates; native precision and device validation remain necessary.')
    save('certificate-validation.json',result);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    {'occluders':occluders,'bake':bake,'fine':lambda:bake(True),'parallel':parallel_bake,'audit':audit,'validate':validate}[sys.argv[1]]()
