"""Private regional far meshes with exact near geometry and independent collision."""
import collections,json,math,struct
from pathlib import Path
import numpy as np
from sidewinder_world_lod import ROOT,decode,signature,sections,sha

BASE=ROOT/'build/n64-sidewinder-budget-cells'
OUT=ROOT/'build/n64-sidewinder-throughput/regions'

def plan():
    OUT.mkdir(parents=True,exist_ok=True)
    meta=json.loads((BASE/'visibility.json').read_text());rows=decode((BASE/'candidate-maps/sidewinder.map64').read_bytes())
    near=[r for r in rows if r['batch']<meta['representation']['original_chunks'] and (not meta['lod_chunks'][r['batch']] or (meta['lod_chunks'][r['batch']]-1)%2==0)]
    groups=collections.defaultdict(list);metadata={};terrain_keys={}
    for r in near:
        code=meta['lod_chunks'][r['batch']]
        if r['material'] in (7,8):
            center=np.mean([v[:3] for v in r['triangle']],axis=0)/256
            key=tuple(np.floor(center[[0,2]]/32).astype(int))
            gi=terrain_keys.setdefault(key,len(meta['lod_groups'])+len(terrain_keys))
            metadata[gi]=dict(key=['terrain region',*map(int,key)],category='terrain',new_region=True)
        elif code and meta['lod_groups'][(code-1)//2]['category']=='structures':
            gi=(code-1)//2;metadata[gi]=dict(meta['lod_groups'][gi],new_region=False)
        else:continue
        groups[gi].append(r)
    owners=collections.defaultdict(set)
    for gi,rs in groups.items():
        for r in rs:
            for v in r['triangle']:owners[tuple(v[:3])].add(gi)
    for r in near:
        if r['material'] not in (7,8) and not (meta['lod_chunks'][r['batch']] and meta['lod_groups'][(meta['lod_chunks'][r['batch']]-1)//2]['category']=='structures'):
            for v in r['triangle']:owners[tuple(v[:3])].add(-1)
    output=[]
    for gi,rs in groups.items():
        points=np.array([v[:3] for r in rs for v in r['triangle']],float)/256
        lo,hi=points.min(0),points.max(0);center=(lo+hi)/2
        md=metadata[gi]
        if md['new_region']:md.update(center=center.tolist(),bounds=[*lo,*hi],radius=float(np.linalg.norm(points-center,axis=1).max()),error=0.,pixels=0.,diameter_pixels=128.,near_distance=8.)
        pins={tuple(v[:3]) for r in rs for v in r['triangle'] if len(owners[tuple(v[:3])])>1}
        output.append(dict(id=gi,**md,rows=rs,seams=sorted(pins)))
    (OUT/'plan.json').write_text(json.dumps(output,separators=(',',':'))+'\n')
    print('regional proxies',len(output),'faces',sum(len(g['rows']) for g in output))

def author():
    import bpy,bmesh
    data=json.loads((OUT/'plan.json').read_text());scene=bpy.data.scenes.new('Sidewinder regional far meshes');bpy.context.window.scene=scene
    scene.view_settings.view_transform='Standard';result=[]
    for group in data:
        rows=group['rows'];points=[];lookup={};faces=[]
        for r in rows:
            f=[]
            for v in r['triangle']:
                key=tuple(v[:3])
                if key not in lookup:lookup[key]=len(points);points.append((v[0]/256,-v[2]/256,v[1]/256))
                f.append(lookup[key])
            faces.append(f)
        mesh=bpy.data.meshes.new(str(group['key']));mesh.from_pydata(points,[],faces)
        for mi in range(31):mesh.materials.append(bpy.data.materials.get('Regional source '+str(mi)) or bpy.data.materials.new('Regional source '+str(mi)))
        uv=mesh.uv_layers.new(name='Source diffuse');col=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for face,r in zip(mesh.polygons,rows):
            face.material_index=r['material'];period=2048 if r['material']==8 else 1024
            for li,v in zip(face.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/period,1-v[7]/period);col.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        ob=bpy.data.objects.new(mesh.name,mesh);scene.collection.objects.link(ob)
        original=ob.copy();original.data=mesh.copy();original.name+=' SOURCE';scene.collection.objects.link(original);original.hide_set(True)
        bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        # True openings and inter-region seams retain their exact vertices.
        pins={v.index for edge in bm.edges if len(edge.link_faces)!=2 for v in edge.verts}
        pins|={lookup[tuple(p)] for p in group['seams']}
        ps=np.array(points)
        # Retain directional outline extrema in addition to opening seams.
        for a in (-1,0,1):
          for b in (-1,0,1):
           for c in (-1,0,1):
            if a or b or c:pins.add(int(np.argmax(ps@np.array([a,b,c]))))
        pin_positions={tuple(round(x*256) for x in bm.verts[i].co) for i in pins};bm.free()
        free=[i for i in range(len(points)) if i not in pins];vg=ob.vertex_groups.new(name='Far detail')
        if free:vg.add(free,1,'REPLACE')
        mod=ob.modifiers.new('Regional low detail','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=.045 if group['category']=='structures' else .08;mod.use_collapse_triangulate=True;mod.vertex_group=vg.name;mod.vertex_group_factor=1000
        if not free:mod.ratio=1
        bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());tmp=ev.to_mesh();reduced=tmp.copy();ev.to_mesh_clear();ob.modifiers.remove(mod);ob.data=reduced;reduced.calc_loop_triangles()
        remaining={tuple(round(x*256) for x in v.co) for v in reduced.vertices};assert not pin_positions-remaining,(group['key'],'lost outline/opening pins')
        uv=reduced.uv_layers.active;col=reduced.color_attributes['Source lightmap'];far=[]
        for t in reduced.loop_triangles:
            mi=t.material_index;period=2048 if mi==8 else 1024;tri=[]
            for vi,li in zip(t.vertices,t.loops):
                x,y,z=reduced.vertices[vi].co;u,v=uv.data[li].uv;rgb=col.data[li].color
                tri.append([round(x*256),round(z*256),round(-y*256),*[max(0,min(255,round(c*255))) for c in rgb[:3]],round(u*period),round((1-v)*period)])
            far.append(dict(material=mi,triangle=tri))
        result.append(dict(id=group['id'],key=group['key'],source_faces=len(rows),new_region=group['new_region'],far=far,pinned_vertices=len(pins),missing_pins=0))
        print(group['key'],len(rows),'->',len(far),'pins',len(pins),flush=True)
    (OUT/'authored.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'regional-appraisal.blend'))

def pack():
    from sidewinder_canyon_rebuild import unwrap
    from pack_terrain import indexed_terrain
    from pack_maps import bank,packed,uv_safe_triangles
    original=(BASE/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(original)
    old=json.loads((BASE/'visibility.json').read_text());rows=decode(original)
    counts=collections.Counter(old['lod_chunks'][r['batch']] for r in rows)
    authored=json.loads((OUT/'authored.json').read_text())
    adopted={g['id']:g for g in authored if g['new_region'] or len(g['far'])<counts[2+2*g['id']]*.85}
    plans={g['id']:g for g in json.loads((OUT/'plan.json').read_text())}
    lod=[dict(g) for g in old['lod_groups']]
    for gi,g in adopted.items():
        if g['new_region']:
            assert gi==len(lod)
            lod.append({k:v for k,v in plans[gi].items() if k not in ('rows','seams','id')})
        # Explicit screen-size treatment; do not reuse the old mesh's error bound.
        lod[gi].update(error=0.,pixels=0.,box_diameter=True,diameter_pixels=(224. if gi==0 else 128.) if lod[gi]['category']=='structures' else 160.)
        points=np.array([v[:3] for r in g['far'] for v in r['triangle']],float)/256
        lod[gi]['radius']=max(lod[gi]['radius'],float(np.linalg.norm(points-np.array(lod[gi]['center']),axis=1).max()))
        lod[gi]['bounds']=[*np.minimum(lod[gi]['bounds'][:3],points.min(0)).tolist(),*np.maximum(lod[gi]['bounds'][3:],points.max(0)).tolist()]
    new_codes={signature(r):1+2*gi for gi,g in adopted.items() if g['new_region'] for r in plans[gi]['rows']}
    retired={i for i,g in enumerate(old['lod_groups']) if g['category']=='terrain'}
    work_rows=[]
    for r in rows:
        b=r['batch'];code=old['lod_chunks'][b];room=b>=old['representation']['original_chunks']
        if not room and code and (code-1)%2 and (code-1)//2 in (set(adopted)|retired):continue
        if not room:code=new_codes.get(signature(r),code)
        work_rows.append(dict(**r,code=code,mask=old['chunk_masks'][b],room=room))
    for gi,g in adopted.items():
        for r in g['far']:work_rows.append(dict(**r,batch=0,code=2+2*gi,mask=(1<<35)-1,room=False))
    first={}
    for r in rows:first.setdefault(r['material'],r['batch'])
    groups=collections.defaultdict(list)
    for r in work_rows:
        mi,code,room=r['material'],r['code'],r['room'];p=np.array([v[:3] for v in r['triangle']],float)/256
        if room or ss[6][mi]&1:key=(room,mi,code,'ordered',r['batch'])
        else:
            # Coarser packing trades some conservative rejection for fewer
            # batches. Far meshes remain whole regional/material packets.
            far=bool(code and (code-1)%2)
            n=np.cross(p[1]-p[0],p[2]-p[0]);axis=int(np.argmax(abs(n)));direction=axis*2+int(n[axis]<0)
            key=(room,mi,code,'far' if far else 'near',0 if far else direction,*([0,0,0] if far else np.floor(p.mean(0)/48).astype(int)))
        groups[key].append(r)
    work=[]
    for key,rs in sorted(groups.items(),key=lambda x:(x[0][0],first[x[0][1]],min(r['batch'] for r in x[1]),str(x[0]))):
        room,mi,code,*_=key;mask=0
        for r in rs:mask|=r['mask']
        aligned=unwrap(rs,ss[4][mi]*32)
        for chunk in indexed_terrain(uv_safe_triangles([r["triangle"] for r in aligned]),color_delta=0,uv_period=ss[4][mi]*32):
            work.append(dict(room=room,material=mi,code=code,mask=mask,**chunk))
    vertices=bytearray();indices=bytearray();chunks=[]
    for w in work:
        vs=w['vertices'];ix=w['indices'];pad=vs+([vs[-1]] if len(vs)%2 else [])
        bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
        chunks.append((len(vertices)//16,len(vs),w['material'],*bounds,len(indices)//2,len(ix)))
        rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        vertices.extend(packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])]))
        indices.extend(packed('H',[(i,) for i in ix]))
        while len(indices)%8:indices.extend(b'\0\0')
    assert len(chunks)<4096 and len(indices)//2<65536
    ss[:3]=[bytes(vertices),packed('IHH6hHH',chunks),bytes(indices)]
    directory=OUT/'candidate-maps';directory.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (directory/p.name).exists():(directory/p.name).symlink_to(p.resolve())
    result=bank(directory/'sidewinder.map64',1,ss)
    meta={**old,'schema':10,'map_sha256':result['sha256'],'candidate_bank_path':str(directory/'sidewinder.map64'),
        'lod_groups':lod,'lod_chunks':[w['code'] for w in work],'chunk_masks':[w['mask'] for w in work],
        'representation':{**old['representation'],'original_chunks':sum(not w['room'] for w in work),'total_chunks':len(chunks)},
        'regional_base_bank':str(BASE/'candidate-maps/sidewinder.map64'),'regional_base_sha256':sha(original),
        'regional_base_sidecar':str(BASE/'visibility.json'),'regional_adopted':list(adopted),
        'regional_retired':sorted(retired),'regional_plan':str(OUT/'plan.json'),'regional_plan_sha256':sha((OUT/'plan.json').read_bytes()),
        'regional_authored':str(OUT/'authored.json'),'regional_authored_sha256':sha((OUT/'authored.json').read_bytes())}
    # All-eye/all-direction backface certificates only. No source occluder
    # assumptions survive a proxy replacement without being certified anew.
    payload=(directory/'sidewinder.map64').read_bytes();rs=decode(payload)
    ps=np.array([[v[:3] for v in r['triangle']] for r in rs],float)/256
    ns=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);length=np.linalg.norm(ns,axis=1);ns/=np.maximum(length[:,None],1e-30)
    owner=np.array([r['batch'] for r in rs]);two=np.array([bool(ss[6][r['material']]&4) for r in rs]);dots=(ns*ps[:,0]).sum(1)
    origin=np.array([-64,-6,-64]);step=np.array([8,2,8]);dims=[16,4,16];words=(len(chunks)+31)//32;bits=[]
    for y in range(4):
      for z in range(16):
       for x in range(16):
        lo=origin+step*np.array([x,y,z]);hi=lo+step
        facing=(np.where(ns>=0,lo,hi)*ns).sum(1)<=dots+.015;facing|=two
        keep=np.zeros(len(chunks),bool);np.logical_or.at(keep,owner,facing)
        bits.extend(sum(int(v)<<bit for bit,v in enumerate(keep[i:i+32])) for i in range(0,len(chunks),32))
    meta['cells']=dict(origin=origin.tolist(),step=step.tolist(),dimensions=dims,words=words,visible=bits,scope='All-eye backface certificates; no occluder rejection; outside fails open')
    (OUT/'visibility.json').write_text(json.dumps(meta,separators=(',',':'))+'\n')
    result.update(adopted_regions=list(adopted),chunks=len(chunks),source_chunks=len(old['lod_chunks']))
    (OUT/'packing-report.json').write_text(json.dumps(result,indent=2)+'\n')
    validate(meta,payload)
    from export_chiron_visibility import emit_c
    emit_c(meta,OUT/'visibility-data.c',directory/'sidewinder.map64')
    print(json.dumps(result),flush=True)

def validate(data,payload):
    original=Path(data['regional_base_bank']).read_bytes();old=json.loads(Path(data['regional_base_sidecar']).read_text())
    assert sha(original)==data['regional_base_sha256'] and sha(payload)==data['map_sha256']
    assert sections(original)[3:]==sections(payload)[3:],'Texture/gameplay bytes changed'
    raw=Path(data['regional_authored']).read_bytes();assert sha(raw)==data['regional_authored_sha256']
    adopted=set(data['regional_adopted'])|set(data['regional_retired'])
    plans=json.loads(Path(data['regional_plan']).read_text());assert sha(Path(data['regional_plan']).read_bytes())==data['regional_plan_sha256']
    remap={signature(r):1+2*g['id'] for g in plans if g['new_region'] for r in g['rows']}
    def retained(rows,meta):
        out=collections.Counter()
        for r in rows:
            b=r['batch'];code=meta['lod_chunks'][b];room=b>=meta['representation']['original_chunks']
            if not room and code and (code-1)%2 and (code-1)//2 in adopted:continue
            if not room:code=remap.get(signature(r),code)
            out[signature(r),code,room]+=1
        return out
    assert retained(decode(original),old)==retained(decode(payload),data),'Near/unchanged geometry differs'
    # Repacking may widen membership but must never make a retained face
    # unavailable to a source cluster. Duplicate faces share the union mask.
    def memberships(rows,meta):
        masks=collections.defaultdict(int)
        for r in rows:
            b=r['batch'];code=meta['lod_chunks'][b];room=b>=meta['representation']['original_chunks']
            if not room and code and (code-1)%2 and (code-1)//2 in adopted:continue
            if not room:code=remap.get(signature(r),code)
            masks[signature(r),code,room]|=meta['chunk_masks'][b]
        return masks
    previous=memberships(decode(original),old);current=memberships(decode(payload),data)
    assert all(current[k]&mask==mask for k,mask in previous.items()),'Retained PVS membership narrowed'
    # Bind every new far face to the authored mesh, including legal UV edge
    # splits and whole-repeat offsets introduced by the packer.
    from pack_maps import uv_safe_triangles
    from sidewinder_canyon_rebuild import unwrap
    expected=collections.Counter();actual=collections.Counter()
    for group in json.loads(raw):
        if group['id'] not in data['regional_adopted']:continue
        by_material=collections.defaultdict(list)
        for r in group['far']:by_material[r['material']].append(r)
        for mi,rows in by_material.items():
            for tri in uv_safe_triangles([r['triangle'] for r in unwrap(rows,sections(payload)[4][mi]*32)]):
                expected[signature(dict(material=mi,triangle=tri)),2+2*group['id']]+=1
    for r in decode(payload):
        code=data['lod_chunks'][r['batch']]
        if r['batch']<data['representation']['original_chunks'] and code and (code-1)%2 and (code-1)//2 in data['regional_adopted']:
            actual[signature(r),code]+=1
            assert data['chunk_masks'][r['batch']]==(1<<data['clusters'])-1
    assert actual==expected,'Packed far mesh differs from authored geometry'
    plan_by_id={g['id']:g for g in plans}
    def edges(rows):
        counts=collections.Counter()
        for r in rows:
            t=[tuple(v[:3]) for v in r['triangle']]
            for a,b in ((0,1),(1,2),(2,0)):counts[tuple(sorted((t[a],t[b])))]+=1
        return counts
    for group in json.loads(raw):
        old_edges=edges(plan_by_id[group['id']]['rows']);new_edges=edges(group['far'])
        assert all(edge in new_edges for edge,count in old_edges.items() if count!=2),'Open boundary edge lost'
    for r in decode(payload):
        code=data['lod_chunks'][r['batch']]
        if not code:continue
        g=data['lod_groups'][(code-1)//2]
        if g.get('box_diameter'):
            assert all(g['bounds'][a]<=v[a]/256<=g['bounds'][a+3] for v in r['triangle'] for a in range(3)),'Projected box does not enclose its meshes'
    assert len(data['lod_chunks'])==len(data['chunk_masks'])==len(sections(payload)[1])//24
    assert len(data['cells']['visible'])==math.prod(data['cells']['dimensions'])*data['cells']['words']
    for key in ('nodes','planes','leaf_clusters','rows','clusters','map_name','map_id'):assert data[key]==old[key]

if __name__=='__main__':
    import sys
    {'plan':plan,'pack':pack}.get(sys.argv[1] if len(sys.argv)>1 else 'plan',plan)()
