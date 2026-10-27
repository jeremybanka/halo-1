"""Private exact-geometry directional batches and conservative camera-cell visibility.

Source triangles, UV interpolation, colors, texture and gameplay bytes are exact.
Cells bound all eye positions and directions, not just saved replay cameras.
"""
import collections, json, math, struct
from pathlib import Path
import numpy as np
from sidewinder_world_lod import ROOT, decode, signature, sections, sha
from sidewinder_canyon_rebuild import unwrap
from pack_terrain import indexed_terrain

BASE=ROOT/'build/n64-sidewinder-budget'
OUT=ROOT/'build/n64-sidewinder-budget-cells'

def scenery_plan():
    rows=[r for r in json.loads((BASE/'source.json').read_text())['rows'] if r['label'][0]=='scenery']
    parent=list(range(len(rows)));lookup={}
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,r in enumerate(rows):
        for v in r['triangle']:
            j=lookup.setdefault(tuple(v[:3]),i);parent[root(i)]=root(j)
    groups=collections.defaultdict(list)
    for i,r in enumerate(rows):groups[root(i)].append(r)
    records=[]
    for rs in groups.values():
        if len(rs)<24:continue
        p=np.array([v[:3] for r in rs for v in r['triangle']],float)/256;lo=p.min(0);hi=p.max(0);center=(lo+hi)/2
        records.append(dict(id=len(records),rows=rs,center=center.tolist(),bounds=[*lo,*hi],radius=float(np.linalg.norm(p-center,axis=1).max())))
    OUT.mkdir(exist_ok=True);(OUT/'scenery-plan.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
    print('scenery components',len(records),'triangles',sum(len(g['rows']) for g in records))

def author_scenery():
    import bpy
    records=json.loads((OUT/'scenery-plan.json').read_text());scene=bpy.data.scenes.new('Sidewinder — distant scenery detail');bpy.context.window.scene=scene
    result=[]
    for g in records:
        points=[];lookup={};faces=[]
        for r in g['rows']:
            face=[]
            for v in r['triangle']:
                key=tuple(v[:3])
                if key not in lookup:lookup[key]=len(points);points.append([x/256 for x in key])
                face.append(lookup[key])
            faces.append(face)
        mesh=bpy.data.meshes.new('Scenery '+str(g['id']));mesh.from_pydata(points,[],faces)
        for mi in range(31):mesh.materials.append(bpy.data.materials.get('Cell source '+str(mi)) or bpy.data.materials.new('Cell source '+str(mi)))
        uv=mesh.uv_layers.new(name='Source diffuse');col=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for face,r in zip(mesh.polygons,g['rows']):
            face.material_index=r['material']
            for li,v in zip(face.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,v[7]/1024);col.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        ob=bpy.data.objects.new(mesh.name,mesh);scene.collection.objects.link(ob)
        # Preserve the component's directional supports; fine curved detail
        # is replaced only when the whole object is small on screen.
        ps=np.array(points);pins=set()
        for a in (-1,0,1):
          for b in (-1,0,1):
           for c in (-1,0,1):
            if a or b or c:pins.add(int(np.argmax(ps@np.array([a,b,c]))))
        free=[i for i in range(len(ps)) if i not in pins];vg=ob.vertex_groups.new(name='Fine distant detail')
        if free:vg.add(free,1,'REPLACE')
        mod=ob.modifiers.new('Small-screen scenery','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=.12;mod.use_collapse_triangulate=True;mod.vertex_group=vg.name;mod.vertex_group_factor=1000
        bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());tmp=ev.to_mesh();reduced=tmp.copy();ev.to_mesh_clear();ob.modifiers.remove(mod);ob.data=reduced;reduced.calc_loop_triangles();uv=reduced.uv_layers.active;col=reduced.color_attributes['Source lightmap'];new=[]
        for t in reduced.loop_triangles:
            tri=[]
            for vi,li in zip(t.vertices,t.loops):
                p=reduced.vertices[vi].co;u,v=uv.data[li].uv;rgb=col.data[li].color
                tri.append([*[round(x*256) for x in p],*[max(0,min(255,round(c*255))) for c in rgb[:3]],round(u*1024),round(v*1024)])
            new.append(dict(material=t.material_index,triangle=tri))
        # Truly subpixel details are omitted; larger components retain a
        # support-pinned mesh at a maximum projected diameter of 12 pixels.
        omit=g['radius']<.12
        result.append(dict(**g,far=[] if omit else new,diameter_pixels=.75 if omit else 12,omitted_subpixel=omit,pinned_supports=len(pins)))
        print(g['id'],len(g['rows']),'->',0 if omit else len(new),flush=True)
    (OUT/'scenery-authored.json').write_text(json.dumps(result,separators=(',',':'))+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scenery-appraisal.blend'))

def preview_scenery():
    """Paired, normalized source/proxy assets; export data is left untouched."""
    import bpy
    data=json.loads((OUT/'scenery-authored.json').read_text());scene=bpy.data.scenes.new('Sidewinder — source and distant scenery pairs');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    mats=[]
    for mi in range(29):
        mat=bpy.data.materials.new('Appraisal source '+str(mi));mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{mi}.png'),check_existing=True);tex.interpolation='Closest';col=nodes.new('ShaderNodeVertexColor');col.layer_name='Source lightmap';mul=nodes.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1;em=nodes.new('ShaderNodeEmission');output=nodes.new('ShaderNodeOutputMaterial');links=mat.node_tree.links;links.new(tex.outputs['Color'],mul.inputs[1]);links.new(col.outputs['Color'],mul.inputs[2]);links.new(mul.outputs[0],em.inputs['Color']);links.new(em.outputs[0],output.inputs['Surface']);mats.append(mat)
    for i,g in enumerate(data):
        scale=2.5/max(g['bounds'][a+3]-g['bounds'][a] for a in range(3));cx=(i%5)*7;cy=(i//5)*5
        for label,rows,dx in [('SOURCE',g['rows'],-1.6),('DISTANT',g['far'],1.6)]:
            if not rows:continue
            points=[];faces=[]
            for r in rows:
                face=[]
                for v in r['triangle']:
                    x,y,z=np.array(v[:3])/256-np.array(g['center']);face.append(len(points));points.append((cx+dx+x*scale,cy-z*scale,y*scale))
                faces.append(face)
            mesh=bpy.data.meshes.new(f'{g["id"]:02} {label}');mesh.from_pydata(points,[],faces)
            for mat in mats:mesh.materials.append(mat)
            uv=mesh.uv_layers.new(name='Source diffuse');colors=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
            for poly,r in zip(mesh.polygons,rows):
                poly.material_index=r['material']
                for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);colors.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
            ob=bpy.data.objects.new(mesh.name,mesh);scene.collection.objects.link(ob);ob['source_component']=g['id'];ob['triangles']=len(rows);ob['normalized_for_inspection']=True;ob['source_bounds']=g['bounds'];ob['diameter_threshold_pixels']=g['diameter_pixels'];ob['adopted_proxy']=len(g['far'])<len(g['rows'])*.85
        text=bpy.data.curves.new('Component '+str(g['id']),'FONT');text.body=f'{g["id"]:02}: {len(g["rows"])} -> {len(g["far"])} triangles / {g["diameter_pixels"]} px';text.size=.24;ob=bpy.data.objects.new(text.body,text);scene.collection.objects.link(ob);ob.location=(cx-3,cy-1.8,0);ob.rotation_euler=(math.pi/2,0,0)
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scenery-appraisal.blend'))

def pack(merge_masks=False,spatial=24):
    from pack_maps import bank, packed
    OUT.mkdir(exist_ok=True)
    source=(BASE/'candidate-maps/sidewinder.map64').read_bytes()
    meta=json.loads((BASE/'visibility.json').read_text())
    ss=sections(source); rows=decode(source); groups=collections.defaultdict(list)
    lod_groups=[{**g,'pixels':g['pixels']*2 if g['category'] in ('structures','terrain') else g['pixels']} for g in meta['lod_groups']];scenery_codes={};extra=[]
    if (OUT/'scenery-authored.json').exists():
        for g in json.loads((OUT/'scenery-authored.json').read_text()):
            if len(g['far'])>=len(g['rows'])*.85:continue
            gi=len(lod_groups);assert gi<128
            lod_groups.append(dict(key=['scenery',g['id']],category='scenery',center=g['center'],bounds=g['bounds'],radius=g['radius'],error=0.,pixels=0.,diameter_pixels=g['diameter_pixels'],near_distance=2.))
            for r in g['rows']:scenery_codes[signature(r)]=1+2*gi
            for r in g['far']:extra.append({**r,'code':2+2*gi,'mask':(1<<35)-1,'room':False,'batch':0})
    first={}
    for r in rows:first.setdefault(r['material'],r['batch'])
    for r in rows+extra:
        b=r['batch']; mi=r['material']; p=np.array([v[:3] for v in r['triangle']],float)
        normal=np.cross(p[1]-p[0],p[2]-p[0]); axis=int(np.argmax(abs(normal)))
        direction=axis*2+int(normal[axis]<0)
        room=r.get('room',b>=meta['representation']['original_chunks']);code=r.get('code',meta['lod_chunks'][b]);mask=r.get('mask',meta['chunk_masks'][b])
        if not room and 'code' not in r:code=scenery_codes.get(signature(r),code)
        # Preserve non-depth-writing source passes and their triangle order.
        if room or ss[6][mi]&1:key=(room,mi,code,mask,'ordered',b)
        else:key=(room,mi,code,0 if merge_masks else mask,direction,*np.floor(p.mean(0)/256/spatial).astype(int))
        groups[key].append({**r,'original_pvs':mask})
    work=[]
    for key,rs in sorted(groups.items(),key=lambda x:(x[0][0],first[x[0][1]],min(r['batch'] for r in x[1]),str(x[0]))):
        room,mi,code,mask,*_=key
        if not mask:
            for r in rs:mask|=r['original_pvs']
        for w in indexed_terrain([r['triangle'] for r in unwrap(rs,ss[4][mi]*32)],color_delta=0,uv_period=ss[4][mi]*32):
            work.append(dict(room=room,material=mi,code=code,mask=mask,**w))
    vertices=bytearray();indices=bytearray();chunks=[];cut=sum(not w['room'] for w in work)
    for w in work:
        vs=w['vertices'];ix=w['indices'];pad=vs+([vs[-1]] if len(vs)%2 else []);at=len(indices)//2
        bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
        rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        chunks.append((len(vertices)//16,len(vs),w['material'],*bounds,at,len(ix)))
        vertices.extend(packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])]))
        indices.extend(packed('H',[(i,) for i in ix]))
        while len(indices)%8:indices.extend(b'\0\0')
    assert len(chunks)<4096 and len(indices)//2<65536,(len(chunks),len(indices)//2)
    ss[0:3]=[bytes(vertices),packed('IHH6hHH',chunks),bytes(indices)]
    directory=OUT/'candidate-maps';directory.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (directory/p.name).exists():(directory/p.name).symlink_to(p.resolve())
    result=bank(directory/'sidewinder.map64',1,ss)
    data={**meta,'schema':9,'map_sha256':result['sha256'],'candidate_bank_path':str(directory/'sidewinder.map64'),
          'chunk_masks':[w['mask'] for w in work],'lod_chunks':[w['code'] for w in work],'lod_groups':lod_groups,
          'representation':{**meta['representation'],'original_chunks':cut,'total_chunks':len(chunks)},
          'cells_baseline_bank':str(BASE/'candidate-maps/sidewinder.map64'),'cells_baseline_sidecar':str(BASE/'visibility.json'),
          'cells_baseline_sha256':sha(source)}
    (OUT/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    result.update(original_chunks=meta['representation']['original_chunks'],repacked_chunks=cut,total_chunks=len(chunks),index_count=len(indices)//2,exact_expanded_attributes=True,merge_masks=merge_masks,spatial=spatial)
    (OUT/'packing-report.json').write_text(json.dumps(result,indent=2)+'\n')
    validate(data,(directory/'sidewinder.map64').read_bytes(),require_cells=False)
    print('packed',len(chunks),'chunks',len(indices)//2,'indices',flush=True)

def bake():
    data=json.loads((OUT/'visibility.json').read_text());payload=(OUT/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(payload)
    chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));rows=decode(payload)
    ps=np.array([[v[:3] for v in r['triangle']] for r in rows],float)/256
    normals=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);length=np.linalg.norm(normals,axis=1);normals/=np.maximum(length[:,None],1e-30)
    owners=np.array([r['batch'] for r in rows]);two=np.array([bool(ss[6][r['material']]&4) for r in rows]);dots=(normals*ps[:,0]).sum(1)
    boxlo=np.array([c[3:6] for c in chunks],float)/32;boxhi=np.array([c[6:9] for c in chunks],float)/32
    origin=np.array([-64,-6,-64]);step=np.array([8,2,8]);dims=[16,4,16]
    # Large certified convex opaque source polygons only. Small faces cannot
    # hide an appreciable whole batch across an eight-unit camera cell.
    occ=[o for o in json.loads((BASE/'occluders.json').read_text()) if o['area']>=4]
    original=json.loads((BASE/'visibility.json').read_text())
    plane_groups=collections.defaultdict(set)
    plane_pvs=collections.defaultdict(lambda:(1<<35)-1)
    for r in json.loads((BASE/'source.json').read_text())['rows']:
        p=np.array([v[:3] for v in r['triangle']],dtype=np.int64)
        n=np.cross(p[1]-p[0],p[2]-p[0]);g=math.gcd(*map(int,n))
        if not g:continue
        n//=g;key=(*map(int,n),int(n@p[0]))
        plane_pvs[key]&=original['chunk_masks'][r['batch']]
        code=original['lod_chunks'][r['batch']]
        if code:plane_groups[key].add((code-1)//2)
    records=[];stats=[]
    for iy in range(dims[1]):
      for iz in range(dims[2]):
       for ix in range(dims[0]):
        lo=origin+step*np.array([ix,iy,iz]);hi=lo+step
        facing=(np.where(normals>=0,lo,hi)*normals).sum(1)<=dots+.015
        facing|=two
        visible=np.zeros(len(chunks),bool);np.logical_or.at(visible,owners,facing)
        back=int((~visible).sum());hidden=np.zeros(len(chunks),bool)
        eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)])
        for o in occ:
            if plane_pvs[tuple(o['plane'])]!=(1<<35)-1:continue
            p=np.array(o['points']);n=np.array(o['normal']);d=n@p[0]
            # Source winding, scoped near plane (one world unit), and a
            # positive margin at every camera corner. No back-side occluders.
            if (eyes@n-d).max()>-1.05:continue
            center=p.mean(0)
            if np.linalg.norm(center-eyes.mean(0))>45:continue
            # A source wall can only be an occluder if its original surface
            # is guaranteed selected throughout this cell. Never hide faces
            # behind a detailed wall that LOD may replace with a proxy.
            certified=True
            for gi in plane_groups[tuple(o['plane'])]:
                group=data['lod_groups'][gi];bounds=group['bounds']
                delta=np.maximum(np.maximum(np.array(bounds[:3])-eyes,eyes-np.array(bounds[3:])),0)
                if (delta*delta).sum(1).max()>=group['near_distance']**2:
                    certified=False;break
            if not certified:continue
            candidates=visible&~hidden&((np.where(n>=0,boxlo,boxhi)@n)>d+.03)
            if not candidates.any():continue
            ids=np.flatnonzero(candidates);keep=np.ones(len(ids),bool)
            for eye in eyes:
                for a,b in zip(p,np.roll(p,-1,axis=0)):
                    v=np.cross(b-eye,a-eye);ln=np.linalg.norm(v)
                    if ln<1e-12:keep[:]=False;break
                    v/=ln
                    if v@(center-eye)<0:v=-v
                    keep&=np.where(v>=0,boxlo[ids],boxhi[ids])@v>v@eye+.02
                if not keep.any():break
            hidden[ids[keep]]=True
        visible&=~hidden
        words=[sum(int(v)<<bit for bit,v in enumerate(visible[i:i+32])) for i in range(0,len(visible),32)]
        records.extend(words);stats.append([back,int(hidden.sum()),int(visible.sum())])
      print('baked vertical layer',iy,'/',dims[1],flush=True)
    data['cells']=dict(origin=origin.tolist(),step=step.tolist(),dimensions=dims,words=(len(chunks)+31)//32,visible=records,
                       scope='All eye positions and all view directions in each fixed 8x2x8 world-unit cell. Whole-batch opaque shadows and all-face back-facing rejection. Outside grid fails open.',
                       near_clearance=1.05,occluders=len(occ),statistics=stats)
    (OUT/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    validate(data,payload)
    from export_chiron_visibility import emit_c
    emit_c(data,OUT/'visibility-data.c',OUT/'candidate-maps/sidewinder.map64')
    print('visibility bytes',len(records)*4,'mean rejection',np.mean(np.array(stats)[:,:2],axis=0),flush=True)

def validate(data,payload,require_cells=True):
    from sidewinder_budget import validate as old_validate
    base=Path(data['cells_baseline_bank']).read_bytes();old=json.loads(Path(data['cells_baseline_sidecar']).read_text());old_validate(old,base)
    assert sha(base)==data['cells_baseline_sha256'] and sha(payload)==data['map_sha256']
    assert sections(base)[3:]==sections(payload)[3:],'Texture/gameplay data changed'
    a=decode(base);b=decode(payload)
    # Whole texture repeat is the only permitted expanded-attribute change.
    original_groups=len(old['lod_groups'])
    kept_b=[r for r in b if data['lod_chunks'][r['batch']]<=2*original_groups or (data['lod_chunks'][r['batch']]-1)%2==0]
    assert collections.Counter(map(signature,a))==collections.Counter(map(signature,kept_b)),'Expanded original triangle attributes changed'
    assert len(data['lod_chunks'])==len(data['chunk_masks'])==len(sections(payload)[1])//24
    for a_group,b_group in zip(old['lod_groups'],data['lod_groups'][:original_groups]):
        expected={**a_group,'pixels':a_group['pixels']*2 if a_group['category'] in ('structures','terrain') else a_group['pixels']}
        assert b_group==expected,'Unexpected LOD policy change'
    for k in ('nodes','planes','leaf_clusters','rows','clusters','map_name','map_id'):assert data[k]==old[k]
    def labeled(rows,meta):
        return collections.Counter((signature(r),meta['lod_chunks'][r['batch']],r['batch']>=meta['representation']['original_chunks']) for r in rows)
    # New scenery groups replace formerly fixed scenery with exact near
    # triangles. Other original LOD and PVS memberships are immutable.
    adjusted=dict(data);adjusted['lod_chunks']=[c if c<=2*original_groups else 0 for c in data['lod_chunks']]
    assert labeled(a,old)==labeled(kept_b,adjusted),'LOD, PVS or regional ownership changed'
    memberships=collections.defaultdict(int)
    for r in a:memberships[signature(r),old['lod_chunks'][r['batch']],r['batch']>=old['representation']['original_chunks']]|=old['chunk_masks'][r['batch']]
    for r in kept_b:
        mask=memberships[signature(r),adjusted['lod_chunks'][r['batch']],r['batch']>=adjusted['representation']['original_chunks']]
        assert mask&data['chunk_masks'][r['batch']]==mask,'Source PVS membership narrowed'
    if require_cells:
        c=data['cells'];assert len(c['visible'])==math.prod(c['dimensions'])*c['words']

def emit_cells(data):
    c=data['cells'];f=lambda v:float(v).hex()+'f'
    return '#include "render_world_cells.h"\nstatic const uint32_t world_cells_visible[]={'+','.join('0x%xU'%v for v in c['visible'])+'};\nconst bg_world_cells_data bg_world_cells={{'+','.join(f(v*32) for v in c['origin'])+'},{'+','.join(f(v*32) for v in c['step'])+'},{'+','.join(map(str,c['dimensions']))+'},'+','.join(map(str,[c['words'],len(data['chunk_masks']),data['map_id']]))+',world_cells_visible,0,0};\n'

if __name__=='__main__':
    import sys
    {'plan':scenery_plan,'pack':pack,'bake':bake}[sys.argv[1]]()
