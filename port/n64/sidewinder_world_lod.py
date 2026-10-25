"""Private screen-size world LOD experiment; close geometry and gameplay stay exact."""
import collections
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import numpy as np
from remap_sidewinder_visibility import sections, batches, sha
from pack_terrain import indexed_terrain

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-world-lod'
BASE=ROOT/'build/n64-sidewinder-trees/lean'
ALL=(1<<35)-1

def region(t):
    x,y,z=np.mean([v[:3] for v in t],axis=0)/256
    if z>15 and x<-24:return 'West base'
    if z>15 and x>23:return 'East base'
    if z>10:return 'Central tunnels'
    if abs(x)<15:return 'Central bridge'
    if z<-35:return 'West far outpost' if x<0 else 'East far outpost'
    if x<-44:return 'West near outpost'
    if x>44:return 'East near outpost'
    return 'West recessed structure'

def decode(payload):
    ss=sections(payload);rows=[]
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,mi,*rest=c;at,n=rest[-2:];vs=[]
        for i in range(count):
            o=(first+i)//2*32;h=(first+i)%2
            vs.append([*struct.unpack_from('>3h',ss[0],o+h*8),*ss[0][o+16+h*4:o+19+h*4],*struct.unpack_from('>2h',ss[0],o+24+h*4)])
        ix=struct.unpack_from('>'+str(n)+'H',ss[2],at*2)
        for f in range(n//3):rows.append(dict(batch=b,face=f,material=mi,triangle=[vs[i] for i in ix[f*3:f*3+3]]))
    return rows

def prepare():
    OUT.mkdir(exist_ok=True)
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes()
    proof=json.loads((BASE/'packing-report.json').read_text())
    old=json.loads((ROOT/'build/n64-sidewinder-structures/source.json').read_text())
    categories={(r['batch'],r['face']):r['category'] for r in old['triangles']}
    rows=decode(payload);groups=collections.defaultdict(list);unchanged=[]
    masks=json.loads((BASE/'visibility.json').read_text())['chunk_masks']
    for r in rows:
        meta=proof['batches'][r['batch']];mi=r['material'];t=r['triangle']
        if mi in (18,19):key=('trees',meta['tree'],meta['instance'])
        elif mi in (7,8):
            center=np.mean([v[:3] for v in t],axis=0)/256
            key=('terrain',mi,math.floor(center[0]/16),math.floor(center[2]/16))
        elif categories[meta['old_batch'],r['face']]=='structures' and mi<7:key=('structures',region(t))
        else:unchanged.append(r);continue
        groups[key].append({**r,'mask':masks[r['batch']]})
    records=[]
    for gi,(key,rs) in enumerate(groups.items()):
        ps=np.array([v[:3] for r in rs for v in r['triangle']])/256
        lo,hi=ps.min(0),ps.max(0);center=(lo+hi)/2
        records.append(dict(id=gi,key=key,category=key[0],rows=rs,center=center.tolist(),bounds=[*lo,*hi],radius=float(np.max(np.linalg.norm(ps-center,axis=1)))))
    source=dict(bank_sha256=sha(payload),groups=records,unchanged=unchanged)
    (OUT/'source.json').write_text(json.dumps(source,separators=(',',':'))+'\n')
    print(collections.Counter(r['category'] for r in records),sum(len(r['rows']) for r in records),'LOD source triangles')

def author():
    """Blender collapse proxies. Boundary pins keep holes and patch seams fixed."""
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    source=json.loads((OUT/'source.json').read_text())
    scene=bpy.data.scenes.new('Sidewinder — screen-size world LOD');bpy.context.window.scene=scene
    scene.view_settings.view_transform='Standard'
    collection=bpy.data.collections.new('Distance proxies');scene.collection.children.link(collection)
    mats=[]
    for mi in range(20):
        mat=bpy.data.materials.new('World LOD source '+str(mi));mat.use_nodes=True
        ns=mat.node_tree.nodes;ns.clear();out=ns.new('ShaderNodeOutputMaterial');em=ns.new('ShaderNodeEmission');tex=ns.new('ShaderNodeTexImage');color=ns.new('ShaderNodeVertexColor');color.layer_name='Source lightmap'
        tex.image=bpy.data.images.load(str(ROOT/f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{mi}.png'),check_existing=True);tex.interpolation='Closest'
        mix=ns.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        links=mat.node_tree.links;links.new(tex.outputs['Color'],mix.inputs[1]);links.new(color.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],em.inputs['Color'])
        if mi in (18,19):
            transparent=ns.new('ShaderNodeBsdfTransparent');alpha=ns.new('ShaderNodeMixShader');links.new(tex.outputs['Alpha'],alpha.inputs[0]);links.new(transparent.outputs[0],alpha.inputs[1]);links.new(em.outputs[0],alpha.inputs[2]);links.new(alpha.outputs[0],out.inputs['Surface'])
        else:links.new(em.outputs[0],out.inputs['Surface'])
        mats.append(mat)
    result=[]
    for record in source['groups']:
        rows=record['rows'];kind=record['category'];lookup={};ps=[];fs=[]
        for r in rows:
            face=[]
            for v in r['triangle']:
                xyz=(v[0]/256,-v[2]/256,v[1]/256)
                if xyz not in lookup:lookup[xyz]=len(ps);ps.append(xyz)
                face.append(lookup[xyz])
            fs.append(face)
        mesh=bpy.data.meshes.new(str(record['key']));mesh.from_pydata(ps,[],fs)
        for m in mats:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,r in zip(mesh.polygons,rows):
            poly.material_index=r['material'];period=2048 if r['material']==8 else 1024
            for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/period,1-v[7]/period);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(str(record['key']),mesh);collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        pins={v.index for e in bm.edges if len(e.link_faces)!=2 for v in e.verts}
        # Material boundaries are patch boundaries too; pinning prevents mixed
        # materials from moving openings or snow/cliff seams independently.
        if kind!='trees':pins|={v.index for e in bm.edges if len({f.material_index for f in e.link_faces})>1 for v in e.verts}
        if kind=='trees':
            # Keep a sparse set of the actual broad branch cards, distributed
            # across height, and a six-sided tapered trunk. No floating blobs.
            cards=collections.defaultdict(list)
            parent=list(range(len(rows)))
            def root(i):
                while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
                return i
            edges={}
            for i,r in enumerate(rows):
                if r['material']!=19:continue
                for a,b in ((0,1),(1,2),(2,0)):
                    edge=tuple(sorted((tuple(r['triangle'][a][:3]),tuple(r['triangle'][b][:3]))))
                    if edge in edges:parent[root(i)]=root(edges[edge])
                    else:edges[edge]=i
            for i,r in enumerate(rows):
                if r['material']==19:cards[root(i)].append(r)
            byheight=collections.defaultdict(list);lo=record['bounds'][1];height=record['bounds'][4]-lo
            for rs in cards.values():
                p=np.array([v[:3] for r in rs for v in r['triangle']])/256
                area=sum(np.linalg.norm(np.cross(np.subtract(r['triangle'][1][:3],r['triangle'][0][:3]),np.subtract(r['triangle'][2][:3],r['triangle'][0][:3]))) for r in rs)
                byheight[min(5,int((p[:,1].mean()-lo)/height*6))].append((area,rs))
            far=[r for candidates in byheight.values() for _,rs in sorted(candidates,key=lambda p:p[0],reverse=True)[:2] for r in rs]
            # Source trunk is already modest; keep it exact for this first LOD.
            far += [r for r in rows if r['material']==18]
            error=0.;missing=0;sampled=0.
            # Make the inspected object match the exported card selection.
            selected={(r['batch'],r['face']) for r in far};drop=[f for f,r in zip(bm.faces,rows) if (r['batch'],r['face']) not in selected]
            bmesh.ops.delete(bm,geom=drop,context='FACES');bm.to_mesh(mesh);bm.free()
        else:
            free=[v.index for v in bm.verts if v.index not in pins];pin_positions={tuple(round(x*256) for x in bm.verts[i].co) for i in pins};bm.free()
            vg=obj.vertex_groups.new(name='Interior detail');
            if free:vg.add(free,1,'REPLACE')
            mod=obj.modifiers.new('Distant surface proxy','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=.16 if kind=='structures' else .22;mod.vertex_group=vg.name;mod.vertex_group_factor=1000;mod.use_collapse_triangulate=True
            if not free:mod.ratio=1.
            bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();dg.update();ev=obj.evaluated_get(dg);emesh=ev.to_mesh()
            # Copy evaluated data before releasing its temporary mesh.
            reduced=emesh.copy();ev.to_mesh_clear();obj.modifiers.remove(mod);obj.data=reduced;mesh=reduced
            mesh.calc_loop_triangles();newps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in mesh.vertices];newfs=[list(t.vertices) for t in mesh.loop_triangles]
            oldps=[Vector(p) for p in ps];a=BVHTree.FromPolygons(oldps,fs,all_triangles=True);b=BVHTree.FromPolygons(newps,newfs,all_triangles=True)
            missing=len(pin_positions-{tuple(round(x*256) for x in p) for p in newps})
            assert missing==0,(record['key'],missing)
            # Symmetric continuous surface-distance bound. Distance to a mesh
            # is 1-Lipschitz; sample distance + subtriangle radius bounds the
            # whole subtriangle. Subdivide until bound is within .035 world
            # units of the sampled maximum (or .04-unit triangles).
            sampled=0.;error=0.
            for points,faces,target in ((oldps,fs,b),(newps,newfs,a)):
                for face in faces:
                    stack=[tuple(points[i] for i in face)]
                    while stack:
                        aa,bb,cc=stack.pop();q=(aa+bb+cc)/3;d=target.find_nearest(q)[3];sampled=max(sampled,d);radius=max((p-q).length for p in (aa,bb,cc))
                        upper=d+radius
                        if upper<=sampled+.035 or radius<=.04:error=max(error,upper);continue
                        lengths=[(aa-bb).length_squared,(bb-cc).length_squared,(cc-aa).length_squared];edge=lengths.index(max(lengths))
                        if edge==0:m=(aa+bb)/2;stack.extend(((aa,m,cc),(m,bb,cc)))
                        elif edge==1:m=(bb+cc)/2;stack.extend(((aa,bb,m),(aa,m,cc)))
                        else:m=(cc+aa)/2;stack.extend(((aa,bb,m),(m,bb,cc)))
            far=[];uv=mesh.uv_layers.active;color=mesh.color_attributes['Source lightmap']
            for t in mesh.loop_triangles:
                mi=t.material_index;period=2048 if mi==8 else 1024;triangle=[]
                for vi,li in zip(t.vertices,t.loops):
                    x,y,z=mesh.vertices[vi].co;rgb=color.data[li].color;u,v=uv.data[li].uv
                    triangle.append([round(x*256),round(z*256),round(-y*256),*[max(0,min(255,round(c*255))) for c in rgb[:3]],round(u*period),round((1-v)*period)])
                far.append(dict(material=mi,triangle=triangle))
        # Collapse can be a no-op for a heavily pinned patch. Keep its original
        # chunks only: no selection overhead or duplicated geometry needed.
        accepted=len(far)<len(rows)*.9
        result.append(dict(id=record['id'],key=record['key'],category=kind,triangles=far if accepted else [],source_triangles=len(rows),far_triangles=len(far),accepted=accepted,error_bound=error,sampled_error=sampled,missing_pins=missing))
        obj.hide_set(not accepted)
        print(record['id'],kind,len(rows),'->',len(far),'bound',round(error,4),flush=True)
    (OUT/'authored.json').write_text(json.dumps(dict(source_sha256=sha((OUT/'source.json').read_bytes()),groups=result),separators=(',',':'))+'\n')
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'world-lod-appraisal.blend'))


def signature(r):
    # Whole texture repeat offsets preserve perspective interpolation exactly.
    p=2048 if r['material']==8 else 1024;t=r['triangle'];base=[t[0][6]//p*p,t[0][7]//p*p]
    return (r['material'],tuple(tuple(v[:6]+[v[6]-base[0],v[7]-base[1]]) for v in t))

def emit_lod(data):
    def f(x):return float(x).hex()+'f'
    groups=[]
    for g in data['lod_groups']:
        groups.append('{ {'+','.join(f(x*32) for x in g['center'])+'},'+','.join(f(g[k]*(32 if k in ('radius','error','near_distance') else 1)) for k in ('radius','error','pixels','diameter_pixels','near_distance'))+', {'+','.join(f(x*32) for x in g['bounds'])+'},'+str(int(g.get('box_diameter',False)))+' }')
    return '#include "render_world_lod.h"\nstatic const bg_world_lod_group world_lod_groups[]={'+','.join(groups)+'};\nstatic const uint16_t world_lod_chunks[]={'+','.join(map(str,data['lod_chunks']))+'};\nconst bg_world_lod_data bg_world_lod={world_lod_groups,world_lod_chunks,'+str(len(groups))+','+str(len(data['lod_chunks']))+','+str(data['map_id'])+'};\n'

def validate(data,payload):
    from sidewinder_tree_visibility import validate as base_validate
    raw=Path(data['lod_baseline_sidecar']).read_bytes();assert sha(raw)==data['lod_baseline_sidecar_sha256'];base=json.loads(raw)
    original=Path(data['lod_baseline_bank']).read_bytes();base_validate(base,original)
    assert sha(payload)==data['map_sha256'] and sections(original)[7:]==sections(payload)[7:]
    for section in range(3,7):assert sections(payload)[section].startswith(sections(original)[section])
    for k in ('nodes','planes','leaf_clusters','rows','clusters','map_name','map_id','normal_limit','cluster_probes'):assert data[k]==base[k]
    raw=Path(data['lod_packing_report']).read_bytes();assert sha(raw)==data['lod_packing_report_sha256'];proof=json.loads(raw)
    assert proof['candidate_sha256']==sha(payload) and proof['source_bank_sha256']==sha(original)
    assert data['chunk_masks']==proof['chunk_masks'] and data['lod_chunks']==proof['lod_chunks'] and data['lod_groups']==proof['lod_groups']
    assert len(data['lod_groups'])<=128 and len(data['lod_chunks'])==len(sections(payload)[1])//24
    for g in data['lod_groups']:
        assert len(g['center'])==3 and len(g['bounds'])==6
        assert all(math.isfinite(float(x)) for x in [*g['center'],*g['bounds'],g['radius'],g['error'],g['pixels'],g['diameter_pixels'],g['near_distance']])
        assert g['radius']>0 and g['error']>0 and g['pixels']>0 and g['diameter_pixels']>=0 and g['near_distance']>=0
        assert all(g['bounds'][a]<=g['center'][a]<=g['bounds'][a+3] for a in range(3))
    assert all(isinstance(code,int) and 0<=code<=2*len(data['lod_groups']) for code in data['lod_chunks'])
    old=decode(original);new=decode(payload);near=[r for r in new if not data['lod_chunks'][r['batch']] or (data['lod_chunks'][r['batch']]-1)%2==0]
    assert collections.Counter(map(signature,old))==collections.Counter(map(signature,near)),'Close triangles changed'
    for r in new:
        code=data['lod_chunks'][r['batch']]
        if code and (code-1)%2:assert data['chunk_masks'][r['batch']]==ALL
    # Near masks are a source union, never a stricter visibility assertion.
    oldm={signature(r):base['chunk_masks'][r['batch']] for r in old}
    for r in near:assert data['chunk_masks'][r['batch']]&oldm[signature(r)]==oldm[signature(r)]
    order=[r['material'] for r in new];first={}
    for r in old:first.setdefault(r['material'],r['batch'])
    first[29]=first[30]=first[19]
    assert [first[mi] for mi in order]==sorted(first[mi] for mi in order),'Material/pass order changed'

def pack():
    from pack_maps import bank, packed, uv_safe_triangles
    source=json.loads((OUT/'source.json').read_text());auth=json.loads((OUT/'authored.json').read_text());assert sha((OUT/'source.json').read_bytes())==auth['source_sha256']
    original=(BASE/'candidate-maps/sidewinder.map64').read_bytes();assert sha(original)==source['bank_sha256'];ss=sections(original)
    oldvis=json.loads((BASE/'visibility.json').read_text());auth={g['id']:g for g in auth['groups']}
    groups=[];work=[];fixed=collections.defaultdict(list)
    for r in source['unchanged']:fixed[r['batch']].append(r)
    for g in source['groups']:
        a=auth[g['id']]
        if g['category']=='trees':a={**a,'triangles':impostor_triangles(g),'accepted':True,'error_bound':0}
        if not a['accepted']:
            for r in g['rows']:fixed[r['batch']].append(r)
            continue
        gi=len(groups);groups.append({k:g[k] for k in ('key','category','center','bounds','radius')})
        groups[-1].update(error=max(a['error_bound'],.005),pixels=3.0 if g['category']=='structures' else 1.5,diameter_pixels=48.0 if g['category']=='trees' else 0.,near_distance=8. if g['category']!='trees' else 3.)
        # The projection Jacobian must cover BOTH representations, including
        # quantized collapse vertices and transparent impostor-card corners.
        far_points=np.array([v[:3] for r in a['triangles'] for v in r['triangle']],dtype=float)/256
        groups[-1]['radius']=max(g['radius'],float(np.max(np.linalg.norm(far_points-np.array(g['center']),axis=1))))+.005
        groups[-1]['bounds']=[*np.minimum(g['bounds'][:3],far_points.min(0)),*np.maximum(g['bounds'][3:],far_points.max(0))]
        for level,rows in enumerate((g['rows'],a['triangles'])):
            bymat=collections.defaultdict(list)
            for r in rows:bymat[r['material']].append(r)
            for mi,rs in bymat.items():work.append((mi,gi,level,rs))
    for b,rs in fixed.items():work.append((rs[0]['material'],None,0,rs))
    first={}
    for r in decode(original):first.setdefault(r['material'],r['batch'])
    first[29]=first[30]=first[19]
    work.sort(key=lambda w:(first[w[0]],w[1] if w[1] is not None else 999,w[2]))
    vertices=bytearray();indices=bytearray();chunks=[];masks=[];codes=[];inventory=[]
    for mi,gi,level,rs in work:
        mask=ALL if gi is not None and level else 0
        if not mask:
            for r in rs:mask|=oldvis['chunk_masks'][r['batch']]
        start=len(chunks);loads=0
        for batch in indexed_terrain(uv_safe_triangles([r['triangle'] for r in rs]),color_delta=0,uv_period=(ss[4][mi]*32 if mi<len(ss[4]) else 1024)):
            vs,ix=batch['vertices'],batch['indices'];at=len(indices)//2;vfirst=len(vertices)//16;pad=vs+([vs[-1]] if len(vs)%2 else [])
            rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
            vertices.extend(packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])]))
            indices.extend(packed('H',[(i,) for i in ix]))
            while len(indices)%8:indices.extend(b'\0\0')
            bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
            chunks.append((vfirst,len(vs),mi,*bounds,at,len(ix)));masks.append(mask);codes.append(0 if gi is None else 1+2*gi+level);loads+=len(pad)
        inventory.append(dict(group=gi,level=level,material=mi,chunks=len(chunks)-start,loads=loads))
    assert len(chunks)<=1024 and len(indices)//2<65536
    ss[0],ss[1],ss[2]=bytes(vertices),packed('IHH6hHH',chunks),bytes(indices)
    ss[3]+= (OUT/'tree-impostors.rgba16').read_bytes()
    ss[4]+=bytes([32,32]);ss[5]+=bytes([0,0]);ss[6]+=bytes([6,6])
    dest=OUT/'candidate-maps';dest.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (dest/p.name).exists():(dest/p.name).symlink_to(p.resolve())
    result=bank(dest/'sidewinder.map64',1,ss);payload=(dest/'sidewinder.map64').read_bytes()
    result.update(source_bank_sha256=sha(original),candidate_sha256=sha(payload),lod_groups=groups,lod_chunks=codes,chunk_masks=masks,inventory=inventory,chunk_count=len(chunks),paired_vertex_entries=len(vertices)//16,index_entries=len(indices)//2,extra_bank_bytes=len(payload)-len(original))
    report=OUT/'packing-report.json';report.write_text(json.dumps(result,indent=2)+'\n')
    data={**oldvis,'schema':6,'map_sha256':sha(payload),'chunk_masks':masks,'lod_groups':groups,'lod_chunks':codes,'lod_baseline_sidecar':str(BASE/'visibility.json'),'lod_baseline_sidecar_sha256':sha((BASE/'visibility.json').read_bytes()),'lod_baseline_bank':str(BASE/'candidate-maps/sidewinder.map64'),'lod_packing_report':str(report),'lod_packing_report_sha256':sha(report.read_bytes())}
    validate(data,payload);(OUT/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    from export_chiron_visibility import emit_c
    emit_c(data,OUT/'visibility-data.c',dest/'sidewinder.map64')
    print({k:result[k] for k in ('chunk_count','paired_vertex_entries','index_entries','extra_bank_bytes')})

def bake_trees():
    """Two orthogonal 16x32 images per size, baked from the accepted lean tree."""
    from photo_sidewinder_structures import load_bank,render
    from PIL import Image
    data=json.loads((OUT/'source.json').read_text());source=load_bank(BASE/'candidate-maps/sidewinder.map64');encoded=bytearray();meta=[]
    for species in range(2):
        g=next(g for g in data['groups'] if g['category']=='trees' and ('snowsmall' in str(g['key']))==bool(species))
        ids={r['batch'] for r in g['rows']};keep=np.isin(source[2],list(ids));tree=(source[0][keep],source[1][keep],source[2][keep],source[3],source[4]);lo=np.array(g['bounds'][:3])*32;hi=np.array(g['bounds'][3:])*32;center=(lo+hi)/2
        atlas=np.zeros((32,32,4),np.uint8)
        # Cards extend to the exact orthographic framing, including one source
        # texel of transparent padding on all sides to keep bilinear edges clean.
        horizontal=max(hi[0]-lo[0],hi[2]-lo[2])*16/14;vertical=(hi[1]-lo[1])*32/30
        for side,direction in enumerate((np.array([0.,0.,1.]),np.array([1.,0.,0.]))):
            forward=-direction;right=np.cross(forward,[0,1,0]);up=np.cross(right,forward);view=np.eye(4);view[:3,:3]=np.stack((right,up,-forward));view[:3,3]=-view[:3,:3]@(center+direction*300*32)
            proj=np.eye(4);proj[0,0]=2/horizontal;proj[1,1]=2/vertical;proj[2,2]=-2/(700*32);proj[2,3]=-1
            rgb,mask=render(tree,(proj@view).T,width=16,height=32,return_mask=True);atlas[:,side*16:(side+1)*16,:3]=rgb;atlas[:,side*16:(side+1)*16,3]=mask*255
        # Replicate nearby opaque RGB into transparent texels: filtered cutout
        # edges must not pick up the renderer's dark background color.
        opaque=atlas[:,:,3]>0
        for y,x in np.argwhere(~opaque):
            choices=np.argwhere(opaque & (np.indices(opaque.shape)[1]//16==x//16))
            if len(choices):yy,xx=choices[np.argmin(np.sum((choices-[y,x])**2,axis=1))];atlas[y,x,:3]=atlas[yy,xx,:3]
        Image.fromarray(atlas).save(OUT/f'tree-impostor-{species}.png')
        rgba=atlas.astype(np.uint16);pixels=((rgba[:,:,0]*31//255)<<11)|((rgba[:,:,1]*31//255)<<6)|((rgba[:,:,2]*31//255)<<1)|(rgba[:,:,3]>=128)
        encoded.extend(pixels.astype('>u2').tobytes());meta.append(dict(species=species,horizontal=horizontal/32,vertical=vertical/32,source_group=g['id']))
    (OUT/'tree-impostors.rgba16').write_bytes(encoded);(OUT/'tree-impostors.json').write_text(json.dumps(meta,indent=2)+'\n')

def impostor_triangles(g):
    species=int('snowsmall' in str(g['key']));meta=json.loads((OUT/'tree-impostors.json').read_text())[species];cx,cy,cz=g['center'];w=meta['horizontal']/2;h=meta['vertical']/2;out=[]
    for side,points in enumerate(([(cx-w,cy-h,cz),(cx+w,cy-h,cz),(cx+w,cy+h,cz),(cx-w,cy+h,cz)],[(cx,cy-h,cz+w),(cx,cy-h,cz-w),(cx,cy+h,cz-w),(cx,cy+h,cz+w)])):
        # Card source RGB is already baked. UVs match the top-down RGBA atlas.
        uv=[(side*.5,1),((side+1)*.5,1),((side+1)*.5,0),(side*.5,0)];vs=[[*[round(x*256) for x in p],255,255,255,round(u*1024),round(v*1024)] for p,(u,v) in zip(points,uv)]
        out.extend(dict(material=29+species,triangle=[vs[i] for i in ix]) for ix in ((0,1,2),(0,2,3)))
    return out

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','bake','pack'))
    args=parser.parse_args()
    {'prepare':prepare,'bake':bake_trees,'pack':pack}[args.action]()
