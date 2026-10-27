"""Private, complete-view Sidewinder budget prototype; collision is immutable."""

import collections,csv,json,math,struct,sys

from pathlib import Path

import numpy as np

from sidewinder_world_lod import ROOT,decode,signature,sections,sha,region

from sidewinder_canyon_rebuild import visible_chunks

BASE=ROOT/'build/n64-sidewinder-canyon-rebuild/candidate'

OUT=ROOT/'build/n64-sidewinder-budget'

ALL=(1<<35)-1

PROMPT='Let’s do it. Build that worst-case Sidewinder view to the 1,500-load budget. Preserve movement and recognizable shapes, use the same photos, diff filters, and native perf checks, then stop for appraisal.'

def prepare():
    from photo_sidewinder_structures import load_bank,render
    from report_canyon_rebuild import selected
    from PIL import Image
    OUT.mkdir(exist_ok=True)
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes();vis=json.loads((BASE/'visibility.json').read_text());rows=decode(payload);chunks=list(struct.iter_unpack('>IHH6hHH',sections(payload)[1]))
    old=json.loads((ROOT/'build/n64-sidewinder-world-lod/source.json').read_text());labels={}
    for g in old['groups']:
        for r in g['rows']:labels[signature(r)]=g['key']
    for g in json.loads((ROOT/'build/n64-sidewinder-world-lod/authored.json').read_text())['groups']:
        for r in g['triangles']:labels[signature(r)]=g['key']
    def label(r):
        m=r['material'];s=labels.get(signature(r))
        if m in (7,8,9):return ['terrain',str(m)]
        if m in (18,19,29,30):return ['trees',str(m)]
        if s:return s
        return ['scenery',str(m)]
    bybatch=collections.defaultdict(list)
    for r in rows:bybatch[r['batch']].append(r)
    census={}
    for ds in ('replay','photos'):
        views=visible_chunks(payload,vis,ds,BASE/ds);out=[]
        for v in views:
            costs=collections.Counter();groups=collections.Counter()
            for b in v['chunks']:
                labs=collections.Counter(tuple(label(r)) for r in bybatch[b]);loads=(chunks[b][1]+1)&~1
                # Batches are overwhelmingly homogeneous; mixed labels use face
                # fractions only for diagnosis. Exact total remains verified.
                for lab,n in labs.items():costs[lab[0]]+=loads*n/sum(labs.values());groups[' / '.join(map(str,lab))]+=loads*n/sum(labs.values())
            out.append({**v,'categories':dict(costs),'groups':dict(groups)})
        census[ds]=out
    (OUT/'baseline-census.json').write_text(json.dumps(census,indent=2)+'\n')
    target=max(census['replay'],key=lambda v:v['vertices']);print(json.dumps(target,indent=2))
    traces=list(csv.reader((BASE/'replay/lod-trace.csv').open()));trace=next(r for r in traces if list(map(int,r[:2]))==[target['tick'],target['camera']]);matrix=np.array(list(map(float,trace[2:18]))).reshape(4,4);levels=np.array(list(map(int,trace[18:])));cam=next(r for r in csv.DictReader((BASE/'replay/cameras.csv').open()) if r['candidate']=='1' and int(r['tick'])==target['tick'] and int(r['camera'])==target['camera']);target.update(pose=cam,matrix_columns=matrix.tolist(),levels=levels.tolist());(OUT/'target.json').write_text(json.dumps(target,indent=2)+'\n')
    bank=selected(load_bank(BASE/'candidate-maps/sidewinder.map64'),vis,levels)
    for scale in (1,4):Image.fromarray(render(bank,matrix,vis['chunk_masks'],int(cam['pvs_mask']),width=160*scale,height=120*scale)).save(OUT/f'target-before-{scale}.png')
    near=[{**r,'label':label(r),'mask':vis['chunk_masks'][r['batch']]} for r in rows if not vis['lod_chunks'][r['batch']] or (vis['lod_chunks'][r['batch']]-1)%2==0]
    (OUT/'source.json').write_text(json.dumps(dict(bank_sha256=sha(payload),rows=near),separators=(',',':'))+'\n')
    print('near',len(near),collections.Counter(r['label'][0] for r in near))

def pack_trial(input_name='beam-trial.json'):
    from sidewinder_canyon_rebuild import culler,unwrap
    from pack_terrain import indexed_terrain
    from pack_maps import uv_safe_triangles
    import ctypes
    data=json.loads((OUT/input_name).read_text());rows=data['rows'];t=json.loads((OUT/'target.json').read_text());dll=culler();matrix=(ctypes.c_float*16)(*np.array(t['matrix_columns']).reshape(-1));sizes=list(sections((BASE/'candidate-maps/sidewinder.map64').read_bytes())[4]);results=[]
    for cell in (2,4,8,16,1000):
        groups=collections.defaultdict(list)
        # Align integer diffuse repeats across original batching seams first.
        aligned=[r for mi in sorted({r['material'] for r in rows}) for r in unwrap([r for r in rows if r['material']==mi],sizes[mi]*32)]
        for r in aligned:
            p=np.mean([v[:3] for v in r['triangle']],axis=0)/256;groups[r['material'],*(math.floor(v/cell) for v in p)].append(r['triangle'])
        loads=total=chunks=tris=0;work=[]
        first={}
        for b,c in enumerate(struct.iter_unpack('>IHH6hHH',sections((BASE/'candidate-maps/sidewinder.map64').read_bytes())[1])):first.setdefault(c[2],b)
        for (mi,*key),rs in sorted(groups.items(),key=lambda item:(first[item[0][0]],item[0][1:])):
            for b in indexed_terrain(uv_safe_triangles(rs),color_delta=8,uv_period=sizes[mi]*32):
                vs=b['vertices'];bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)];n=(len(vs)+1)&~1;total+=n;work.append(dict(material=mi,**b,bounds=bounds))
                if dll.box(matrix,(ctypes.c_int16*6)(*bounds),160,120):loads+=n;chunks+=1;tris+=len(b['indices'])//3
        print('cell',cell,'actual target loads',loads,'triangles',tris,'chunks',chunks,'total',total,len(work),flush=True);results.append(dict(cell=cell,loads=loads,triangles=tris,chunks=chunks,total=total,work=work))
    (OUT/'packing-trials.json').write_text(json.dumps(results,separators=(',',':'))+'\n')

def representation_plan():
    source=json.loads((OUT/'source.json').read_text());lo=np.array([47.8,.30,-28.2]);hi=np.array([53.6,1.40,-21.8]);rows=source['rows'];groups=collections.defaultdict(list);near=[]
    for r in rows:
        ps=np.array([v[:3] for v in r['triangle']],dtype=float)/256;distance=np.linalg.norm(np.maximum(np.maximum(lo-ps,ps-hi),0),axis=1).min()
        if distance<5 or r['material'] in (18,19):near.append(r);continue
        category=r['label'][0]
        key=('structures',region(r['triangle'])) if category=='structures' else (category,)
        groups[key].append(r)
    # Distant pine impostors already authored in the preceding LOD study.
    world=json.loads((ROOT/'build/n64-sidewinder-world-lod/source.json').read_text());tree_ids={}
    for g in world['groups']:
        if g['category']!='trees':continue
        ps=np.array([v[:3] for r in g['rows'] for v in r['triangle']],dtype=float)/256;d=np.linalg.norm(np.maximum(np.maximum(lo-ps,ps-hi),0),axis=1).min()
        if d>=5:
            for r in g['rows']:tree_ids[signature(r)]=g['id']
    near=[r for r in near if signature(r) not in tree_ids]
    trees=[g for g in world['groups'] if g['id'] in set(tree_ids.values())]
    pins={tuple(v[:3]) for r in near for v in r['triangle']}
    records=[]
    for key,rs in groups.items():
        records.append(dict(key=key,rows=rs,pins=sorted({tuple(v[:3]) for r in rs for v in r['triangle']} & pins)))
    data=dict(source_sha256=sha((OUT/'source.json').read_bytes()),lo=lo.tolist(),hi=hi.tolist(),near_radius=5,near=near,groups=records,trees=trees)
    (OUT/'representation-plan.json').write_text(json.dumps(data,separators=(',',':'))+'\n');print('near',len(near),collections.Counter(r['label'][0] for r in near),'groups',[(g['key'],len(g['rows']),len(g['pins'])) for g in records],'far trees',len(trees),flush=True)

def author_representation(ratio=.035):
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    data=json.loads((OUT/'representation-plan.json').read_text());scene=bpy.data.scenes.new('Sidewinder — budgeted east outpost scene');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard';collections_=[]
    for name in ('Unmodified near room and walking surface','Distant scene proxies','Original distant scene'):
        c=bpy.data.collections.new(name);scene.collection.children.link(c);collections_.append(c)
    source_data=json.loads((OUT/'source.json').read_text());allmats=[]
    for mi in range(31):
        m=bpy.data.materials.new('Budget source '+str(mi));m.use_nodes=True;ns=m.node_tree.nodes;ns.clear();tex=ns.new('ShaderNodeTexImage');path=ROOT/f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{mi}.png'
        if mi>=29:path=ROOT/f'build/n64-sidewinder-world-lod/tree-impostor-{mi-29}.png'
        tex.image=bpy.data.images.load(str(path),check_existing=True);tex.interpolation='Closest';color=ns.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=ns.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;em=ns.new('ShaderNodeEmission');out=ns.new('ShaderNodeOutputMaterial');lk=m.node_tree.links;lk.new(tex.outputs['Color'],mix.inputs[1]);lk.new(color.outputs['Color'],mix.inputs[2]);lk.new(mix.outputs[0],em.inputs['Color']);lk.new(em.outputs[0],out.inputs['Surface']);allmats.append(m)
    def mesh_object(name,rows,collection):
        points=[];lookup={};faces=[]
        for r in rows:
            face=[]
            for v in r['triangle']:
                p=tuple(v[:3])
                if p not in lookup:lookup[p]=len(points);points.append((p[0]/256,-p[2]/256,p[1]/256))
                face.append(lookup[p])
            faces.append(face)
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces)
        for m in allmats:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for f,r in zip(mesh.polygons,rows):
            mi=r['material'];period=2048 if mi==8 else 1024;f.material_index=mi
            for li,v in zip(f.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/period,1-v[7]/period);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);return obj,lookup,points,faces
    mesh_object('Exact nearby geometry',data['near'],collections_[0]);output=[];reports=[]
    for group in data['groups']:
        rows=group['rows'];key=group['key'];kind=key[0];obj,lookup,ps,fs=mesh_object(' / '.join(key),rows,collections_[2]);clone=obj.copy();clone.data=obj.data.copy();collections_[1].objects.link(clone)
        pins={lookup[tuple(p)] for p in group['pins']}
        if kind=='structures':
            points=np.array(ps)
            for elevation in (-.4,0,.4):
                for azimuth in np.linspace(0,math.tau,8,endpoint=False):
                    direction=np.array([math.cos(elevation)*math.cos(azimuth),math.cos(elevation)*math.sin(azimuth),math.sin(elevation)])
                    pins.add(int(np.argmax(points@direction)))
        # Keep the genuinely shared seam to the exact near representation.
        # The far representations may sacrifice tiny openings and recesses;
        # they are never used when the camera approaches those distant assets.
        free=[i for i in range(len(ps)) if i not in pins];vg=clone.vertex_groups.new(name='Distant detail')
        if free:vg.add(free,1,'REPLACE')
        mod=clone.modifiers.new('Budgeted distant representation','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=ratio if kind!='terrain' else ratio*1.8;mod.vertex_group=vg.name;mod.vertex_group_factor=1000;mod.use_collapse_triangulate=True
        bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();dg.update();ev=clone.evaluated_get(dg);em=ev.to_mesh();mesh=em.copy();ev.to_mesh_clear();clone.modifiers.remove(mod);clone.data=mesh;mesh.calc_loop_triangles();uv=mesh.uv_layers.active;color=mesh.color_attributes['Source lightmap'];new=[]
        for t in mesh.loop_triangles:
            mi=t.material_index;period=2048 if mi==8 else 1024;tri=[]
            for vi,li in zip(t.vertices,t.loops):
                x,y,z=mesh.vertices[vi].co;u,v=uv.data[li].uv;rgb=color.data[li].color
                tri.append([round(x*256),round(z*256),round(-y*256),*[max(0,min(255,round(c*255))) for c in rgb[:3]],round(u*period),round((1-v)*period)])
            if len({tuple(v[:3]) for v in tri})==3:new.append(dict(material=mi,triangle=tri,label=key,mask=ALL))
        reference=BVHTree.FromPolygons([Vector(p) for p in ps],fs,all_triangles=True);errors=[reference.find_nearest(Vector((v[0]/256,-v[2]/256,v[1]/256)))[3] for r in new for v in r['triangle']];report=dict(key=key,source_triangles=len(rows),proxy_triangles=len(new),pinned_seam_vertices=len(pins),max_vertex_distance=max(errors,default=0));reports.append(report);output.extend(new);print(report,flush=True)
    # Reuse the already appraised two-card pine representations at distance.
    from sidewinder_world_lod import impostor_triangles
    for g in data['trees']:output.extend({**r,'mask':ALL,'label':['trees','distant']} for r in impostor_triangles(g))
    output=data['near']+output
    (OUT/'authored-representation.json').write_text(json.dumps(dict(plan_sha256=sha((OUT/'representation-plan.json').read_bytes()),ratio=ratio,rows=output,report=reports),separators=(',',':'))+'\n')
    collections_[2].hide_render=True;collections_[2].hide_viewport=True
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'budget-scene-appraisal.blend'));print('complete representation',len(output),'triangles',flush=True)

def trim_backfaces():
    data=json.loads((OUT/'authored-representation.json').read_text());plan=json.loads((OUT/'representation-plan.json').read_text());lo=np.array(plan['lo']);hi=np.array(plan['hi']);ss=sections((BASE/'candidate-maps/sidewinder.map64').read_bytes());flags=list(ss[6]);kept=[];removed=[]
    for r in data['rows']:
        p=np.array([v[:3] for v in r['triangle']],float)/256;n=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(n)
        if length<1e-10:removed.append(r);continue
        n/=length;minimum=n@np.where(n>=0,lo,hi)-n@p[0]
        if not flags[r['material']]&4 and minimum>.03:removed.append(r)
        else:kept.append(r)
    data.update(rows=kept,backface_removed=len(removed),untrimmed_triangles=len(data['rows']),trim_bounds=[*lo,*hi]);(OUT/'trimmed-representation.json').write_text(json.dumps(data,separators=(',',':'))+'\n');print('trimmed',len(data['rows']),'removed',len(removed),collections.Counter(r['label'][0] for r in removed))

def pack_candidate():
    from pack_maps import bank,packed
    trial=next(t for t in json.loads((OUT/'packing-trials.json').read_text()) if t['cell']==16);original=(BASE/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(original);vis=json.loads((BASE/'visibility.json').read_text());plan=json.loads((OUT/'representation-plan.json').read_text());vertices=bytearray(ss[0]);indices=bytearray(ss[2]);chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));original_count=len(chunks);proof=[]
    for w in trial['work']:
        vs=w['vertices'];ix=w['indices'];mi=w['material'];pad=vs+([vs[-1]] if len(vs)%2 else []);first=len(vertices)//16;at=len(indices)//2;rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        vertices.extend(packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])]))
        indices.extend(packed('H',[(i,) for i in ix]))
        while len(indices)%8:indices.extend(b'\0\0')
        chunks.append((first,len(vs),mi,*w['bounds'],at,len(ix)));proof.append(dict(material=mi,loads=len(pad),triangles=len(ix)//3))
    assert len(chunks)<=1024 and len(indices)//2<65536
    ss[0],ss[1],ss[2]=bytes(vertices),packed('IHH6hHH',chunks),bytes(indices);dest=OUT/'candidate-maps';dest.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (dest/p.name).exists():(dest/p.name).symlink_to(p.resolve())
    result=bank(dest/'sidewinder.map64',1,ss);payload=(dest/'sidewinder.map64').read_bytes();result.update(source_sha256=sha(original),original_chunks=original_count,extra_chunks=len(proof),extra_bank_bytes=len(payload)-len(original),batches=proof,plan_sha256=sha((OUT/'representation-plan.json').read_bytes()),authored_sha256=sha((OUT/'authored-representation.json').read_bytes()),trimmed_sha256=sha((OUT/'trimmed-representation.json').read_bytes()))
    report=OUT/'packing-report.json';report.write_text(json.dumps(result,indent=2)+'\n')
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    floor=[r for r in plan['near'] if r['material']==4];footprint=unary_union([Polygon([(v[0]/256,v[2]/256) for v in r['triangle']]) for r in floor]).convex_hull.buffer(-.03,join_style=2);poly=np.array(list(footprint.exterior.coords)[:-1]);center=poly.mean(0);planes=[]
    for a,b in zip(poly,np.roll(poly,-1,axis=0)):
        n=np.array([-(b-a)[1],(b-a)[0]]);n/=np.linalg.norm(n)
        if n@(center-a)<0:n=-n
        planes.append([*n,float(n@a)])
    data={**vis,'schema':8,'map_sha256':sha(payload),'chunk_masks':vis['chunk_masks']+[ALL]*len(proof),'lod_chunks':vis['lod_chunks']+[0]*len(proof),'representation':dict(bounds=[*plan['lo'],*plan['hi']],original_chunks=original_count,total_chunks=len(chunks),footprint_planes=planes,footprint_polygon=poly.tolist()),'budget_baseline_sidecar':str(BASE/'visibility.json'),'budget_baseline_sidecar_sha256':sha((BASE/'visibility.json').read_bytes()),'budget_baseline_bank':str(BASE/'candidate-maps/sidewinder.map64'),'budget_packing_report':str(report),'budget_packing_report_sha256':sha(report.read_bytes()),'candidate_bank_path':str(dest/'sidewinder.map64')}
    validate(data,payload);(OUT/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    from export_chiron_visibility import emit_c
    emit_c(data,OUT/'visibility-data.c',dest/'sidewinder.map64');print('packed',result['extra_bank_bytes'],'extra bytes,',len(chunks),'chunks')

def validate(data,payload):
    from sidewinder_canyon_rebuild import validate as base_validate
    raw=Path(data['budget_baseline_sidecar']).read_bytes();assert sha(raw)==data['budget_baseline_sidecar_sha256'];base=json.loads(raw);original=Path(data['budget_baseline_bank']).read_bytes();base_validate(base,original)
    old,new=sections(original),sections(payload);assert old[3:]==new[3:]
    assert all(new[i].startswith(old[i]) for i in range(3)),'Original rendering changed'
    assert sha(payload)==data['map_sha256'];n=len(old[1])//24;total=len(new[1])//24;rep=data['representation'];assert rep['original_chunks']==n and rep['total_chunks']==total
    assert data['chunk_masks']==base['chunk_masks']+[ALL]*(total-n)
    assert data['lod_chunks']==base['lod_chunks']+[0]*(total-n) and data['lod_groups']==base['lod_groups']
    for k in ('nodes','planes','leaf_clusters','rows','clusters','map_name','map_id','normal_limit','cluster_probes'):assert data[k]==base[k]
    raw=Path(data['budget_packing_report']).read_bytes();assert sha(raw)==data['budget_packing_report_sha256'];proof=json.loads(raw);assert proof['sha256']==sha(payload) and proof['source_sha256']==sha(original)
    assert len(rep['bounds'])==6 and all(math.isfinite(x) for x in rep['bounds']);assert all(rep['bounds'][a]<rep['bounds'][a+3] for a in range(3))

def emit_rep(data):
    rep=data['representation'];bounds=','.join(float(x*32).hex()+'f' for x in rep['bounds']);planes=','.join('{'+','.join(float(x*(32 if i==2 else 1)).hex()+'f' for i,x in enumerate(p))+'}' for p in rep['footprint_planes'])
    return '#include "render_world_rep.h"\nstatic const float room_footprint[][3]={'+planes+'};\nconst bg_world_rep_data bg_world_rep={{'+bounds+'},'+','.join(map(str,[rep['original_chunks'],rep['total_chunks'],data['map_id']]))+',room_footprint,'+str(len(rep['footprint_planes']))+'};\n'


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','plan','trim','trial','pack'))
    args=parser.parse_args()
    {'prepare':prepare,'plan':representation_plan,'trim':trim_backfaces,'trial':lambda:pack_trial('trimmed-representation.json'),'pack':pack_candidate}[args.action]()
