"""Component-aware GUNGNIR near/far candidates from the intact Reach source.

The source shoulder pilot and native-rig proof precede this stage. Original
visible armor is collapsed locally; only boots/gloves use source-fitted closed
contours. Every omission, merge, correspondence and soft-budget change is saved.
Coverage and plate-depth audits must accept the quantized result before publish.
"""
import sys,json,hashlib,argparse
from pathlib import Path
from collections import defaultdict
import bpy,bmesh,numpy as np
from mathutils import Vector,interpolate,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import components,source_part
from pack_assets import position


def close_returns(points,faces):
    """Cap actual local rim loops with their existing contour points."""
    from mathutils.geometry import tessellate_polygon
    edges=defaultdict(list)
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))].append((a,b))
    boundary={values[0] for values in edges.values() if len(values)==1};result=list(faces)
    while boundary:
        first=min(boundary);boundary.remove(first);loop=[first[0],first[1]]
        while loop[-1]!=loop[0] and len(loop)<=len(points):
            options=sorted(e for e in boundary if e[0]==loop[-1])
            if len(options)!=1:break
            edge=options[0];boundary.remove(edge);loop.append(edge[1])
        if loop[-1]!=loop[0] or len(loop)<4:continue
        loop=loop[:-1][::-1];lookup={tuple(Vector(points[i])):i for i in loop}
        for tri in tessellate_polygon([[Vector(points[i]) for i in loop]]):
            f=[loop[p] if isinstance(p,int) else lookup[tuple(p)] for p in tri]
            if len(set(f))==3 and (Vector(points[f[1]])-Vector(points[f[0]])).cross(Vector(points[f[2]])-Vector(points[f[0]])).length>1e-10:result.append(f)
    return result


def envelope(points,faces=None):
    bm=bmesh.new()
    ids=sorted({i for f in faces for i in f}) if faces else list(range(len(points)))
    for i in ids:bm.verts.new(points[i])
    result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    discard=[g for g in result['geom_interior']+result['geom_unused'] if g.is_valid]
    if discard:bmesh.ops.delete(bm,geom=list(set(discard)),context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.verts.ensure_lookup_table();bm.verts.index_update()
    xyz=[v.co.copy() for v in bm.verts];fs=[[v.index for v in f.verts] for f in bm.faces];bm.free();return xyz,fs


def positive_half(points,faces):
    result=[];triangles=[];lookup={}
    for face in faces:
        polygon=[]
        for ia,ib in zip(face,face[1:]+face[:1]):
            a,b=Vector(points[ia]),Vector(points[ib]);inside=a.y>=0
            if inside:polygon.append(a)
            if inside!=(b.y>=0):polygon.append(a+(b-a)*(-a.y/(b.y-a.y)))
        ids=[]
        for p in polygon:
            if abs(p.y)<1e-6:p.y=0
            key=tuple(round(v,8) for v in p)
            if key not in lookup:lookup[key]=len(result);result.append(list(p))
            ids.append(lookup[key])
        for i in range(1,len(ids)-1):
            f=[ids[0],ids[i],ids[i+1]]
            if len(set(f))==3:triangles.append(f)
    return result,triangles


def reflect(points,faces):
    result=[Vector(p) for p in points];mirror={}
    for i,p in enumerate(points):
        if abs(p[1])<1e-6:result[i].y=0;mirror[i]=i
        else:mirror[i]=len(result);result.append(Vector((p[0],-p[1],p[2])))
    return result,[*faces,*[[mirror[f[2]],mirror[f[1]],mirror[f[0]]] for f in faces]]


def groups(model,original_garment=True):
    parts=components(model);by_id={p['id']:p for p in parts};result=[];used=set()
    def add(name,ids,budget,method='original surface collapse',kind='surface'):
        ids=[p for p in ids if p in by_id];assert not used.intersection(ids);used.update(ids)
        if ids:result.append(dict(id=name,source_components=ids,faces=[f for i in ids for f in by_id[i]['faces']],material=by_id[ids[0]]['material'],region=name,targets=budget,method=method,kind=kind))
    add('helmet-shell',['head-55:001'],(100,68),'reduce a closed contour from the original helmet shell points; remove dense inward returns/recess construction; fit retained points to the original shell and mirror independent half LODs',kind='hull')
    add('helmet-lens',['head-82:000'],(12,12),'retain original single-eye lens; no substitute visor')
    add('torso',['body-06:005'],(68,40),'retain original authored torso exterior and panel taper; simplify inward shell construction',kind='outer')
    torso=next(g for g in result if g['id']=='torso');back=[]
    for fi in torso['faces']:
        p=np.array([model['vertices'][i] for i in model['faces'][fi]])
        if p[:,0].mean()<-.062 and p[:,2].mean()>.505:back.append(fi)
    torso['faces']=[fi for fi in torso['faces'] if fi not in set(back)]
    result.append(dict(id='torso-back',source_components=['body-06:005 / upper-back panel'],faces=back,material=6,region='torso-back',targets=(20,12),method='original upper-back exterior and collar return reduced independently; preserve its authored open topology',kind='open'))
    add('chest-lower',['body-06:001'],(12,8),'source-fitted separate lower breast-pack contour',kind='hull')
    add('belt',['body-06:025'],(24,16),'retain original belt/codpiece exterior; remove inward shell construction',kind='outer')
    # Secondary side buckles and rear belt fittings are explicit omissions;
    # keep the original main belt/codpiece and breast-pack assembly.
    for side,thigh,calf,boots in [('right',23,15,(14,16,17)),('left',24,20,(18,19,21))]:
        add(side+'-thigh',[f'body-06:{thigh:03d}'],(24,14),'retain original curved thigh exterior and its contact extrema; remove inward returns',kind='outer')
        add(side+'-calf',[f'body-06:{calf:03d}'],(32,20))
        add(side+'-boot',[f'body-06:{i:03d}' for i in boots],(24,14),'local closed contour from retained original boot points; no primitive reconstruction')
    for side,i in [('left',0),('right',1)]:
        add(side+'-forearm',[f'arms-04:{i:03d}'],(28,16))
        add(side+'-upperarm',[f'arms-06:{i:03d}'],(12,8))
    for side,i in [('right',0),('left',1)]:add(side+'-glove',[f'arms-05:{i:03d}'],(20,12),'local source glove contour; retain wrist and hand contact extrema')
    add('chest-parafoil',['flair_chest_a-16:000'],(20,14),'source-fitted main breast-pack contour; remove inset fastening construction',kind='hull')
    for i in (1,2):add('chest-pouch-'+str(i),[f'flair_chest_a-16:{i:03d}'],(10,8),'source-fitted local pouch contour',kind='hull')
    # Small separate chest straps are explicitly omitted at both LODs.
    for side in ('left','right'):add('shoulder-'+side,[f'flair_{side}_shoulder-96:000'],(28,16),'retain original curved shoulder plate, taper and mount contour',kind='surface')
    for side,i in [('left',0),('right',2)]:add('knee-'+side,[f'flair_knees-118:{i:03d}'],(12,8),'original external knee contour; omit interior mounting layer',kind='hull')
    add('wrist-buckler',['flair_forearm-22:000'],(24,14))
    if original_garment:
        for name,ids,budget in [
            ('armpit',['arms-87:000'],(24,16)),('elbow-left',['arms-87:001'],(10,8)),('elbow-right',['arms-87:002'],(10,8)),
            ('neck',['body-87:002','body-87:003'],(32,20)),('pelvis',['body-87:004'],(48,32)),('torso',['body-87:005'],(48,32)),
            ('knee-right',['body-87:000'],(32,24)),('knee-left',['body-87:007'],(32,24)),
            ('foot-right',['body-87:006'],(12,8)),('foot-left',['body-87:008'],(12,8)),
            ('ankle-right',['body-87:001','body-87:009'],(12,8)),('ankle-left',['body-87:010','body-87:011'],(12,8))]:
            kind='hull' if name.startswith(('elbow','knee','neck','foot')) else 'cloth'
            add('garment-'+name,ids,budget,'retain original garment contours and native joint skinning; simplify cloth curvature and close local joint returns',kind=kind)
    omitted=[dict(id=p['id'],source_triangles=len(p['faces']),decision='replaced by measured local continuous undersuit span' if p['material']==87 and p['region'] in ('arms','body') else 'omit original interior head behind the closed GUNGNIR shell' if p['material'] in (44,45) else 'omit unsupported shield/decal overlay' if p['material'] in (130,131,139) else 'omit inspected small fastener, mount or secondary layer; original main plate retained') for p in parts if p['id'] not in used]
    return result,omitted


def collapse(model,group,lod,budget_trial=False):
    group={**group,'faces':list(group['faces'])};removed=[]
    hull=group['id'].endswith(('-boot','-glove','-calf','-forearm','-upperarm')) or group.get('kind')=='hull'
    if group.get('kind')=='outer' or (hull and not group['id'].startswith(('garment-','helmet-'))):
        ids={v for fi in group['faces'] for v in model['faces'][fi]};center=np.mean([model['vertices'][i] for i in ids],axis=0);keep=[]
        for fi in group['faces']:
            p=np.array([model['vertices'][i] for i in model['faces'][fi]]);n=np.cross(p[1]-p[0],p[2]-p[0])
            if np.dot(n,p.mean(0)-center)>=-1e-10:keep.append(fi)
            else:removed.append(fi)
        group['faces']=keep
    points,faces,source_vertices=source_part(model,group);target=group['targets'][lod]
    if not target:return [],dict(actual=0,requested=0)
    tree=BVHTree.FromPolygons([Vector(p) for p in points],faces,all_triangles=True)
    symmetric=group['id']=='helmet-shell'
    requested=target;source_count=len(faces)
    while True:
        print('COLLAPSE',lod,group['id'],target,flush=True)
        work_points=points;work_faces=faces
        if symmetric:
            # Clip source triangles explicitly. Reach's overlapping shell
            # returns can make BMesh bisect's normal update loop indefinitely.
            # This preserves each original side rather than merging its fan.
            work_points,work_faces=positive_half(points,faces);work_faces=close_returns(work_points,work_faces)
        mesh=bpy.data.meshes.new(group['id'])
        if hull:
            work_points,work_faces=envelope(work_points)
        elif not symmetric and group.get('kind') not in ('outer','cloth','open') and group['id']!='helmet-lens':work_faces=close_returns(work_points,work_faces)
        mesh.from_pydata(work_points,[],work_faces)
        # source_part already welds compatible bind positions AND weights.
        # A positional remove_doubles here would merge distinct joint skin.
        mesh.validate(clean_customdata=False);mesh.update();mesh.calc_loop_triangles()
        edge_counts=defaultdict(int)
        for face in mesh.loop_triangles:
            for a,b in zip(face.vertices,(*face.vertices[1:],face.vertices[0])):edge_counts[tuple(sorted((a,b)))]+=1
        rim={v for e,n in edge_counts.items() if n==1 for v in e}
        ob=bpy.data.objects.new(group['id'],mesh);bpy.context.scene.collection.objects.link(ob)
        # Preserve source deformation channels through collapse. Coincident
        # bind points can legitimately have different fixup weights. They
        # must not be assigned whichever face a geometric BVH returns first.
        for bi,node in enumerate(model['nodes']):ob.vertex_groups.new(name='Native source / '+node['name'])
        original_points=np.array(points)
        for v in mesh.vertices:
            si=v.index if not hull and not symmetric else int(np.argmin(np.linalg.norm(original_points-np.array(v.co),axis=1)))
            for bi,w in model['weights'][source_vertices[si]]:ob.vertex_groups[bi].add([v.index],w,'REPLACE')
        mod=ob.modifiers.new('Original surfaces / component budget','DECIMATE');mod.ratio=min(1,(target/2 if symmetric else target)/max(1,len(mesh.loop_triangles)));mod.use_collapse_triangulate=True
        protected=[]
        # Mirror the independently reduced positive half after fitting.
        if group['id'].startswith('garment-') or group['id'] in ('torso','torso-back','belt') or group['id'].endswith(('-thigh','-upperarm','-calf','-forearm')) or group['id'].startswith('shoulder-'):
            extrema={fn(range(len(mesh.vertices)),key=lambda i:mesh.vertices[i].co[a]) for a in range(3) for fn in (min,max)}
            if symmetric:
                for axis,bound,less in [(2,.665,False),(2,.582,True),(0,.072,False)]:
                    subset=[v.index for v in mesh.vertices if (v.co[axis]<bound if less else v.co[axis]>bound)]
                    for a in range(3):
                        if subset:extrema.update((min(subset,key=lambda i:mesh.vertices[i].co[a]),max(subset,key=lambda i:mesh.vertices[i].co[a])))
            if group['id'].startswith('garment-') and not hull and lod==0:
                # Preserve the original garment's limb/joint ends, without
                # freezing every disconnected seam hidden below a plate.
                source_points=np.array(points)
                for bone in ('b_l_upperarm_fixup','b_r_upperarm_fixup','b_l_forearm','b_r_forearm','b_l_calf','b_r_calf','b_l_thigh','b_r_thigh','b_neck0'):
                    bi=next(i for i,n in enumerate(model['nodes']) if n['name']==bone)
                    subset=[i for i,vi in enumerate(source_vertices) if any(b==bi and w>.25 for b,w in model['weights'][vi])]
                    for axis in range(3):
                        if subset:extrema.update((min(subset,key=lambda i:source_points[i,axis]),max(subset,key=lambda i:source_points[i,axis])))
            weights=ob.vertex_groups.new(name='Source joint contact extrema');weights.add(list(range(len(mesh.vertices))),1,'REPLACE');weights.add(sorted(extrema),.02 if lod==0 else .1,'REPLACE');mod.vertex_group=weights.name;mod.vertex_group_factor=1000
            protected=[mesh.vertices[i].co.copy() for i in sorted(extrema)]
        ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles();xyz=[v.co.copy() for v in me.vertices];fs=[list(t.vertices) for t in me.loop_triangles]
        native_skin=[{g.group:g.weight for g in v.groups if g.group<len(model['nodes']) and g.weight>1e-7} for v in me.vertices]
        native_skin_points=[p.copy() for p in xyz]
        if symmetric:
            xyz=[Vector((p.x,max(0,p.y),p.z)) for p in xyz];fs=[f for f in fs if any(abs(xyz[i].y)>1e-6 for i in f)]
        if hull:xyz,fs=envelope(xyz,fs)
        elif not symmetric and group.get('kind') not in ('outer','cloth','open') and group['id']!='helmet-lens':fs=close_returns(xyz,fs)
        fitted_skin=[native_skin[int(np.argmin([(p-q).length_squared for q in native_skin_points]))] for p in xyz]
        fit_maximum=0.
        for p in xyz:
            on_plane=symmetric and abs(p.y)<1e-6
            hit,_,_,distance=tree.find_nearest(p)
            # As in the accepted Jorge/ODST fit, spend at most 16 mm restoring
            # original exterior curvature after a compatible-edge collapse.
            if distance>1e-10:
                amount=min(distance, .016/3.048);p+=(hit-p)*(amount/distance);fit_maximum=max(fit_maximum,amount)
            if symmetric:p.y=0 if on_plane else max(0,p.y)
        # Convex-contour rebuilding retains a subset of evaluated points.
        # Associate their source channels before the final hull/reindex.
        point_skin={tuple(round(v,7) for v in p):ws for p,ws in zip(xyz,fitted_skin)}
        if symmetric:
            # Clip-plane vertices stay shared. Other vertices are reflected,
            # with reversed winding and source-derived correspondence.
            mirror={}
            for i,p in enumerate(list(xyz)):
                if abs(p.y)<1e-6:p.y=0;mirror[i]=i
                else:
                    mirror[i]=len(xyz);q=Vector((p.x,-p.y,p.z));xyz.append(q);point_skin[tuple(round(v,7) for v in q)]=point_skin[tuple(round(v,7) for v in p)]
            fs += [[mirror[f[2]],mirror[f[1]],mirror[f[0]]] for f in list(fs)]
        if hull or symmetric:
            # The final source-fitted point contour must be a closed outer
            # shell. Remove the temporary mirrored cut-plane construction.
            xyz,fs=envelope(xyz,fs)
            # Source-fit projection can turn tiny former return triangles
            # inward. Check actual final winding, rather than trusting the
            # decimator/hull normals from before fitting.
            center=sum(xyz,Vector())/max(1,len(xyz))
            for face in fs:
                a,b,c=[xyz[i] for i in face]
                if (b-a).cross(c-a).dot((a+b+c)/3-center)<0:face.reverse()
        distances=[tree.find_nearest(p)[3] for p in xyz]
        candidate=BVHTree.FromPolygons(xyz,fs,all_triangles=True)
        source_samples=[Vector(points[f[0]])/3+Vector(points[f[1]])/3+Vector(points[f[2]])/3 for f in faces]
        reverse=[candidate.find_nearest(p)[3] for p in source_samples]
        p95=float(np.percentile(reverse,95));maximum=float(max(distances,default=0))
        contact_error=max((min((a-b).length for b in xyz) for a in protected),default=0)
        ev.to_mesh_clear();bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
        # These are sampled source-surface gates, not a universal volume rule.
        # Large shape deviations earn back geometry before coverage review.
        surface_limit=(.013 if group['id'].endswith('-glove') else .009 if group['id'].endswith('-boot') else .0065 if lod==0 else .0082)
        safe_points=maximum<(.0066 if lod==0 else .010) and contact_error<(.003 if lod==0 else .006)
        plate=not group['id'].startswith('garment-')
        safe_shape=not plate or p95<(.0072 if lod==0 else .0098)
        if (safe_points and safe_shape and (budget_trial or p95<surface_limit)) or target>=source_count:break
        target=min(source_count,max(target+2,round(target*1.25)))
    result=[]
    for face in fs:
        if len(set(tuple(round(v,7) for v in xyz[i]) for i in face))<3:continue
        tri=dict(p=[list(xyz[i]) for i in face],uv=[],weights=[],material=group['material'],component=group['id'],source_components=group['source_components'],source_faces=[],construction=group['method'])
        for vi in face:
            nearest=tree.find_nearest(xyz[vi]);expected=point_skin[tuple(round(v,7) for v in xyz[vi])];options=tree.find_nearest_range(xyz[vi],nearest[3]+.000003);best=None
            for hit,normal,fi,distance in options:
                ids=model['faces'][group['faces'][fi]];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(model['vertices'][i]) for i in ids],hit));bary/=max(1e-30,bary.sum());weights=defaultdict(float)
                for i,w in zip(ids,bary):
                    for b,value in model['weights'][i]:weights[b]+=w*value
                score=sum(abs(weights.get(b,0)-expected.get(b,0)) for b in set(weights)|set(expected))
                if best is None or score<best[0]:best=score,fi,bary,weights,distance
            score,fi,bary,weights,distance=best
            values=sorted(((b,w) for b,w in weights.items() if w>1e-7),key=lambda x:-x[1])[:4];total=sum(w for b,w in values);assert total
            ids=model['faces'][group['faces'][fi]];tri['weights'].append([(b,w/total) for b,w in values]);tri['uv'].append((bary@np.array([model['uv'][i] for i in ids])).tolist());tri['source_faces'].append(dict(face=group['faces'][fi],barycentric=bary.tolist(),surface_distance=distance,native_weight_tie_error=score))
        result.append(tri)
    return result,dict(source_triangles=source_count,requested=requested,actual=len(result),surface_p95_halo_units=p95,maximum_retained_point_error_halo_units=maximum,maximum_contact_error_halo_units=contact_error,maximum_fit_displacement_m=fit_maximum*3.048,final_soft_target=target,boundary_vertices=len(rim),omitted_inner_source_faces=removed)


def bake(model,triangles,motion_folder):
    from extract_gungnir import bone_globals
    report=json.loads((Path(motion_folder)/'motion-report.json').read_text());poses=np.load(Path(motion_folder)/'native-poses.npz');inverse=np.linalg.inv(np.array(bone_globals(model['nodes'])))
    points=np.array([p+[1] for t in triangles for p in t['p']]);weights=np.zeros((len(points),len(model['nodes'])))
    for i,values in enumerate(w for t in triangles for w in t['weights']):
        for b,w in values:weights[i,b]=w
    data={};clips=[];basis=np.array(((1,0,0),(0,0,1),(0,-1,0)),dtype=float);hand=next(i for i,n in enumerate(model['nodes']) if n['name']=='b_r_grip')
    for ci,clip in enumerate(report['clips']):
        frames=[];grips=[]
        for pose in poses['matrices_'+str(ci)]:
            skin=pose@inverse;frame=np.zeros((len(points),3))
            for b in np.flatnonzero(weights.sum(0)):frame+=(points@skin[b].T)[:,:3]*weights[:,b,None]
            frames.append(frame@basis.T);rotation=basis@pose[hand,:3,:3]@basis.T;q=Matrix(rotation).to_quaternion().normalized();grips.append([*(basis@pose[hand,:3,3]),q.x,q.y,q.z,q.w])
        data['frames_'+str(ci)]=np.array(frames,dtype=np.float32);data['grips_'+str(ci)]=np.array(grips,dtype=np.float32);clips.append(dict(name=clip['name'],duration=clip['duration'],frames=len(frames)))
    return data,clips


def run(source,motion_folder,output,budget_trial=False,repair_report=None,original_garment=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);model=json.loads(Path(source).read_text());model['skin_weights']=model['weights'];plan,omitted=groups(model,original_garment);lods=[];ledger=[]
    for lod in range(2):
        triangles=[]
        for group in plan:
            tris,report=collapse(model,group,lod,budget_trial);triangles.extend(tris);ledger.append(dict(lod=lod,id=group['id'],source_components=group['source_components'],decision=group['method'],**report));print('PART',lod,group['id'],report,flush=True)
        # Keep the original off-center single-eye lens readable after the
        # low-resolution shell closes its dense authored recess. Measure the
        # shell at that lens and restore at most 16 mm of shallow clearance.
        shell=[t for t in triangles if t['component']=='helmet-shell'];lens=[t for t in triangles if t['component']=='helmet-lens']
        if shell and lens:
            lens_points=np.array([p for t in lens for p in t['p']]);center=lens_points.mean(0);display_scale=1.5 if lod==0 else 1.8
            for t in lens:
                for p,record in zip(t['p'],t['source_faces']):
                    old=list(p);p[1]=center[1]+(p[1]-center[1])*display_scale;p[2]=center[2]+(p[2]-center[2])*display_scale;record['display_contour_offset']=[p[k]-old[k] for k in range(3)]
            tree=BVHTree.FromPolygons([Vector(p) for t in shell for p in t['p']],[[i*3+j for j in range(3)] for i in range(len(shell))],all_triangles=True)
            hit,_,_,_=tree.ray_cast(Vector((.2,center[1],center[2])),Vector((-1,0,0)))
            delta=max(0,float(hit.x)-float(lens_points[:,0].min())+.0005) if hit is not None else 0;assert delta*3.048<=.016,(lod,'lens clearance',delta)
            for t in lens:
                for p,record in zip(t['p'],t['source_faces']):p[0]+=delta;record['identity_clearance_offset']=[delta,0,0]
            ledger.append(dict(lod=lod,id='original-single-eye-clearance',actual=len(lens),forward_offset_m=delta*3.048,lens_display_scale=display_scale,decision='original asymmetric lens geometry retained; shallow clearance measured against reduced shell'))
        continuity=[]
        if not original_garment:
            from gungnir_continuity import connected_backing
            backing,continuity=connected_backing(model,lod);triangles.extend(backing);continuity=[continuity]
        else:
            from gungnir_continuity import torso_backing
            backing,record=torso_backing(model,lod)
            triangles.extend(backing);continuity=[record]
        if repair_report:
            from gungnir_seams import source_seams
            repairs=json.loads(Path(repair_report).read_text())['repair_source_faces'][lod]
            patches,patch_ledger=source_seams(model,repairs,lod,triangles)
            triangles.extend(patches);ledger.extend(patch_ledger)

        (output/f'continuity-{lod}.json').write_text(json.dumps(continuity,indent=2)+'\n')
        poses,clips=bake(model,triangles,motion_folder);np.savez_compressed(output/f'poses-{lod}.npz',**poses);lods.append(dict(triangles=triangles,animations=clips))
    result=dict(quality_state='candidate: independent coverage, clearance and export acceptance required',publication_approved=False,budget_trial=budget_trial,source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),motion_report_sha256=hashlib.sha256((Path(motion_folder)/'motion-report.json').read_bytes()).hexdigest(),nodes=model['nodes'],materials=model['material_metadata'],textures=[m.get('diffuse') for m in model['material_metadata']],lods=lods,ledger=ledger,omitted_components=omitted,color_tolerance=40,opaque_motion_reorder=True,policy='CHARACTER_DEMAKE.md and JORGE_LODS.md; component-local source surfaces; independent native rig; coverage and plate-depth gates required')
    (output/'solid.json').write_text(json.dumps(result,separators=(',',':'))+'\n');(output/'component-decisions.json').write_text(json.dumps(dict(retained=ledger,omitted=omitted),indent=2)+'\n');print('CANDIDATE',[len(l['triangles']) for l in lods],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('output');p.add_argument('--repair-report');p.add_argument('--original-garment',action='store_true',default=True,help='Retain the original local garment surfaces (default)');p.add_argument('--budget-trial',action='store_true',help='Diagnostic only: retain requested budgets and report errors for matched coverage/plate review; not publication approval');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.output,a.budget_trial,a.repair_report,a.original_garment)
