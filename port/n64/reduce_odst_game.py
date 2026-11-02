"""Source-surface ODST reduction toward the production CE vertex budgets.

Semantic omissions are explicit. No earlier failed candidate is an input.
Keep the previously accepted source and its separate component decisions.
"""
import sys,json,hashlib
from pathlib import Path
from collections import defaultdict
import bpy,bmesh,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import components,paint_source,source_part,bake,globals_for

def budget(part,lod):
    name=part['id'];region=part['region'];n=int(name.split(':')[1])
    if name=='body-23:002':return (280,144)[lod],'continuous original torso, upper sleeves, legs and boots; recessed garment front; lower forearm fabric replaced by local fitted sleeves'
    if name.startswith('body-17:'):return ((8,0,4,0,8),(6,0,2,0,6))[lod][n],'retain broad leg plates; omit covered fasteners'
    if name.startswith('body-23:'):
        return ((8 if n in (1,3,4,9) else 0) if not lod else (4 if n in (1,3) else 0)),'retain near hip/codpiece plates; omit layered collar and small panel backing'
    if name.startswith('body-24:'):return ((14 if n in (0,2) else 4) if not lod else (14 if n in (0,2) else 0)),'retain original forearm guards'
    if region=='chest':return (20,8)[lod],'retain main curved chest plate'
    if region=='gear':
        return ({3:12,4:4,5:4}.get(n,0),{3:12,4:4,5:4}.get(n,0))[lod],'retain main pack and broad side bags; omit small belt fittings, straps and buckles'
    if region=='knife':return 0,'omit knife and sheath at game scale'
    if region=='hands':return (16,8)[lod],'source-derived closed mitten cage, including thumb and original hand contact'
    if region=='helmet':return (80,40)[lod],'jointly reduce original helmet surfaces; paint remains on shared geometry'
    if region in ('l_shoulder','r_shoulder'):return ((12,24,0),(6,14,0))[lod][n],'retain rounded outer shoulder; omit covered interior mount and small returns'
    raise ValueError(name)

def reduce(model,part,target,lod):
    points,faces,_=source_part(model,part);tree=BVHTree.FromPolygons([Vector(p) for p in points],faces,all_triangles=True)
    mesh=bpy.data.meshes.new(part['id']);mesh.from_pydata(points,[],faces)
    local_backing=part['region']=='hands' or part['id']=='body-23:002' or part['id'].startswith('body-24:')
    bm=bmesh.new();bm.from_mesh(mesh)
    if part['region']=='hands':
        # At this scale articulated fingers share the CE hand bone. Preserve
        # the source hand's extremal cage, closing the local glove around it.
        bmesh.ops.delete(bm,geom=list(bm.faces),context='FACES_ONLY')
        bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
        # Hull operator leaves interior original faces: keep boundary hull only.
        for e in list(bm.edges):
            if not e.link_faces:bmesh.ops.delete(bm,geom=[e],context='EDGES')
    elif local_backing:
        bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
    if local_backing:bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    if part['id']=='body-23:002':
        anchors=set()
        for bone in ('bip01 l foot','bip01 r foot','bip01 l calf','bip01 r calf','bip01 l thigh','bip01 r thigh'):
            bi=next(i for i,n in enumerate(model['nodes']) if n['name']==bone)
            subset=[i for i,vi in enumerate(source_part(model,part)[2]) if max(model['skin_weights'][vi],key=lambda x:x[1])[0]==bi]
            for axis in ((0,1,2) if bone.endswith('foot') else (2,)):
                if subset:anchors.update((min(subset,key=lambda i:points[i][axis]),max(subset,key=lambda i:points[i][axis])))

    ob=bpy.data.objects.new(part['id'],mesh);bpy.context.scene.collection.objects.link(ob)
    mod=ob.modifiers.new('Source surface collapse / explicit game budget','DECIMATE');mesh.calc_loop_triangles();mod.ratio=min(1,target/len(mesh.loop_triangles));mod.use_collapse_triangulate=True
    if part['id']=='body-23:002':
        group=ob.vertex_groups.new(name='Preserve source boot and limb extrema');group.add(list(range(len(mesh.vertices))),1,'REPLACE');group.add(sorted(anchors),.02,'REPLACE');mod.vertex_group=group.name;mod.vertex_group_factor=30
    if part['region']=='hands':
        anchors={f(range(len(mesh.vertices)),key=lambda i:mesh.vertices[i].co[a]) for a in range(3) for f in (min,max)}
        group=ob.vertex_groups.new(name='Source hand contact extrema');group.add(list(range(len(mesh.vertices))),1,'REPLACE');group.add(sorted(anchors),0,'REPLACE');mod.vertex_group=group.name;mod.vertex_group_factor=1000
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    # Repair local open returns after collapse, using existing rim vertices.
    # This spends indices rather than replacing the source exterior with boxes.
    returns=bmesh.new();returns.from_mesh(me)
    if part['id'].startswith('body-24:'):
        # As in Jorge's near/far pass, rebuild a local guard volume from its
        # retained original contour points; collapse must not leave flat fins.
        bmesh.ops.delete(returns,geom=list(returns.faces),context='FACES_ONLY')
        bmesh.ops.convex_hull(returns,input=list(returns.verts),use_existing_faces=False)
    else:
        bmesh.ops.holes_fill(returns,edges=[e for e in returns.edges if e.is_boundary],sides=0)
    bmesh.ops.recalc_face_normals(returns,faces=list(returns.faces))
    returns.to_mesh(me);returns.free();me.calc_loop_triangles()
    xyz=[v.co.copy() for v in me.vertices];fs=[list(t.vertices) for t in me.loop_triangles];result=[];error=0
    for face in fs:
        t=dict(p=[list(xyz[i]) for i in face],uv=[],weights=[],material=part['material'],component=part['id'],source_faces=[],local_continuity=local_backing)
        if part['region']=='helmet':t['material']=model['materials'][part['faces'][tree.find_nearest(sum((xyz[i] for i in face),Vector())/3)[2]]]
        for vi in face:
            hit,_,fi,dist=tree.find_nearest(xyz[vi]);error=max(error,dist);ids=model['faces'][part['faces'][fi]]
            bary=np.maximum(0,interpolate.poly_3d_calc([Vector(model['vertices'][i]) for i in ids],hit));bary/=bary.sum();weights=defaultdict(float)
            for i,v in zip(ids,bary):
                for b,w in model['skin_weights'][i]:weights[b]+=v*w
            values=sorted(((b,w) for b,w in weights.items() if w>1e-8),key=lambda x:-x[1])[:4];total=sum(w for b,w in values)
            t['weights'].append([(b,w/total) for b,w in values]);t['uv'].append((bary@np.array([model['uv'][i] for i in ids])).tolist());t['source_faces'].append(dict(face=part['faces'][fi],barycentric=bary.tolist()))
        result.append(t)
    ev.to_mesh_clear();bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
    return result,dict(source_triangles=len(faces),requested=target,actual=len(fs),maximum_sampled_surface_error=error,local_continuity=local_backing)

def sleeve_backing(model,lod):
    bind=globals_for(model['nodes']);points=np.array(model['vertices']);out=[]
    for side in ('l','r'):
        names=[f'bip01 {side} '+s for s in ('upperarm','forearm','hand')];bones=[next(i for i,n in enumerate(model['nodes']) if n['name']==s) for s in names]
        centers=[np.array(bind[b].translation) for b in bones]
        rings=[]
        for j,center in enumerate(centers):
            axis=centers[min(j+1,2)]-centers[max(j-1,0)];axis/=np.linalg.norm(axis)
            u=np.cross(axis,[1,0,0]);u/=np.linalg.norm(u);v=np.cross(u,axis)
            delta=points-center;along=delta@axis;radial=np.linalg.norm(delta-along[:,None]*axis,axis=1)
            candidates=np.where((abs(along)<.012)&(radial>.008)&(radial<.045)&(abs(points[:,1]-center[1])<.05))[0]
            radius=(float(np.quantile(radial[candidates],.55)) if len(candidates) else .022)+.002
            radius=min(.032,max(.016,radius))*.60
            ring=[]
            for k in range(4):
                angle=k*np.pi/2+np.pi/4;p=center+radius*(np.cos(angle)*u+np.sin(angle)*v)
                ring.append(dict(p=p.tolist(),weights=[(bones[min(j,1)],1)],uv=[0,0]))
            rings.append(ring)
        for j in range(1,2):
            for k in range(4):
                corners=[rings[j][k],rings[j+1][k],rings[j+1][(k+1)%4],rings[j][(k+1)%4]]
                for ids in ((0,1,2),(0,2,3)):
                    vs=[corners[i] for i in ids];out.append(dict(p=[x['p'] for x in vs],weights=[x['weights'] for x in vs],uv=[x['uv'] for x in vs],material=23,component='local-sleeve-'+side,local_continuity=True,source_faces=[],color_override=[38,42,44]))
    return out

def pack_backing(triangles):
    # A recessed continuity layer fitted to the retained original pack panels.
    # The original panel surfaces and their colors remain separate and intact.
    source=[t for t in triangles if t['component'] in ('gear-02:003','gear-02:004','gear-02:005')]
    lookup={}
    for t in source:
        for p,ws,uv in zip(t['p'],t['weights'],t['uv']):lookup.setdefault(tuple(p),dict(p=p,weights=ws,uv=uv))
    values=list(lookup.values());pts=np.array([v['p'] for v in values]);center=(pts.min(0)+pts.max(0))/2
    mesh=bpy.data.meshes.new('Local pack continuity');bm=bmesh.new()
    for p in pts:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False);bm.to_mesh(mesh);bm.free();mesh.calc_loop_triangles();out=[]
    for f in mesh.loop_triangles:
        vs=[min(values,key=lambda v:np.linalg.norm(np.array(v['p'])-mesh.vertices[i].co)) for i in f.vertices]
        out.append(dict(p=[(center+(np.array(v['p'])-center)*.96).tolist() for v in vs],weights=[v['weights'] for v in vs],uv=[v['uv'] for v in vs],material=2,component='local-pack-lining',local_continuity=True,source_faces=[],color_override=[52,54,50]))
    bpy.data.meshes.remove(mesh);return out

def cache_order(triangles):
    # Opaque faces are independent within a physical component. Keep the
    # assembly/component order, and improve its bounded 60-vertex cache reuse.
    groups={}
    for t in triangles:groups.setdefault(t['component'],[]).append(t)
    ordered=[]
    for tris in groups.values():
        keys=[{(tuple(p),tuple((b,w) for b,w in ws)) for p,ws in zip(t['p'],t['weights'])} for t in tris]
        remaining=set(range(len(tris)));cache=set();count=0
        while remaining:
            if not cache:i=min(remaining)
            else:i=max(remaining,key=lambda i:(len(keys[i]&cache),-i))
            if len(cache|keys[i])>56 or count==38:cache=set();count=0;continue
            ordered.append(tris[i]);remaining.remove(i);cache|=keys[i];count+=1
    return ordered

def fit_overlap(triangles):
    # Adapt fit_jorge_coverage.py: 5% component overlap, capped at 16 mm.
    # Each fitted point retains its inherited source skin/UV correspondence;
    # record the geometric offset rather than claiming unchanged source points.
    groups={};report=[]
    for t in triangles:groups.setdefault(t['component'],[]).append(t)
    for name,tris in groups.items():
        if name.startswith('local-') or name=='body-23:002':continue # Recessed backing must stay recessed.
        center=np.mean([p for t in tris for p in t['p']],0);maximum=0
        for t in tris:
            offsets=[]
            for i,p in enumerate(t['p']):
                p=np.array(p);delta=(p-center)*.05;n=np.linalg.norm(delta)
                if n>1e-10:delta*=min(.016/3.048,max(1/512,n))/n
                t['p'][i]=(p+delta).tolist();offsets.append(delta.tolist());maximum=max(maximum,float(np.linalg.norm(delta)))
            t['fit_offsets']=offsets
        report.append(dict(component=name,maximum_offset_halo=maximum,maximum_offset_m=maximum*3.048))
    return report

def run(folder,output):
    folder=Path(folder);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=folder/'source/odst-ce-raw.json';raw=json.loads(source.read_text());model=paint_source(raw['models']['spartan']);parts=components(model)
    clips=dict(raw['animations']);clips.update(json.loads((folder.parent/'jorge/playable-half/ce-motion-source.json').read_text()));lods=[];ledger=[];fits=[]
    # Collapse the two complete source hand assemblies as closed local cages,
    # rather than retaining disconnected palm/finger overlays.
    grouped=[dict(p) for p in parts if p['region'] not in ('hands','helmet')]
    forearm_bones={i for i,n in enumerate(model['nodes']) if n['name'].endswith('forearm')}
    garment=next(p for p in grouped if p['id']=='body-23:002')
    keep=[]
    for fi in garment['faces']:
        influences=defaultdict(float)
        for vi in model['faces'][fi]:
            for b,w in model['skin_weights'][vi]:influences[b]+=w
        if max(influences,key=influences.get) not in forearm_bones:keep.append(fi)
    omitted_forearm_faces=sorted(set(garment['faces'])-set(keep));garment['faces']=keep
    grouped.append(dict(id='helmet-03:000',region='helmet',material=3,faces=[fi for p in parts if p['region']=='helmet' for fi in p['faces']]))
    for side in ('l','r'):
        bi=next(i for i,n in enumerate(model['nodes']) if n['name']==f'bip01 {side} hand')
        fs=[fi for p in parts if p['region']=='hands' for fi in p['faces'] if max(((b,w) for vi in model['faces'][fi] for b,w in model['skin_weights'][vi]),key=lambda x:x[1])[0]==bi]
        grouped.append(dict(id='hands-'+side+':000',region='hands',material=24,faces=fs))
    for lod in range(2):
        triangles=[]
        for part in grouped:
            target,decision=budget(part,lod)
            if target:
                tris,report=reduce(model,part,target,lod)
                if part['id']=='body-23:002':
                    for t in tris:
                        before=np.array(t['p'])
                        for p in t['p']:
                            if p[2]>.46:p[0]=min(p[0],.006)
                        t['garment_recess_offsets']=(np.array(t['p'])-before).tolist()
                triangles.extend(tris)
            else:report=dict(source_triangles=len(part['faces']),requested=0,actual=0)
            ledger.append(dict(lod=lod,id=part['id'],decision=decision,**report))
        triangles.extend(sleeve_backing(model,lod));triangles.extend(pack_backing(triangles));fits.append(fit_overlap(triangles));triangles=cache_order(triangles)
        arrays={};animations=bake(model,triangles,clips)
        for i,c in enumerate(animations):
            arrays['frames_'+str(i)]=np.array(c.pop('frames'),np.float32);arrays['grips_'+str(i)]=np.array(c.pop('grips'),np.float32);c['frames']=len(arrays['frames_'+str(i)])
        np.savez_compressed(output/f'poses-{lod}.npz',**arrays);lods.append(dict(triangles=triangles,animations=animations))
    result=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256((folder/'covered/solid.json').read_bytes()).hexdigest(),policy='CHARACTER_DEMAKE.md / source surfaces, explicit omissions, game-scale coverage gate',color_tolerance=48,nodes=model['nodes'],materials=model['material_metadata'],textures=model['textures'],stripe_source_faces=model['stripe_source_faces'],lods=lods,ledger=ledger,omitted_forearm_garment_faces=omitted_forearm_faces,garment_fit='front recessed to x=0.006 Halo above z=0.46; per-corner displacements retained; source forearm fabric replaced by recessed source-fitted sleeves',overlap_measurements=fits,coverage_fit='original armor: 5% overlap with one packed-unit minimum capped at 16 mm; hidden garment/backing excluded; per-corner offsets retained')
    (output/'solid.json').write_text(json.dumps(result));(output/'component-decisions.json').write_text(json.dumps(ledger,indent=2)+'\n');print('GAME REDUCTION',[len(l['triangles']) for l in lods],flush=True)
if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
