"""One-bend terrain retopology around walkable surfaces and view silhouettes."""
import collections,csv,ctypes,json,math,struct,subprocess
from pathlib import Path
import numpy as np
from sidewinder_world_lod import ROOT,decode,signature,sha,sections
BASE=ROOT/'build/n64-sidewinder-world-lod'
OUT=ROOT/'build/n64-sidewinder-canyon-rebuild'
ALL=(1<<35)-1

def culler():
    sdk=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src'
    code='''#include <t3d/t3dmath.h>
#include "render_cull.h"
#include "render_visibility.h"
int box(float matrix[4][4],short bounds[6],int w,int h){
 T3DFrustum f;t3d_mat4_to_frustum(&f,(T3DMat4*)matrix);
 bg_visibility_side_planes((float(*)[4])f.planes,matrix,w,h);
 uint8_t selected[6][3];bg_frustum_prepare(selected,(const float(*)[4])f.planes);
 return bg_frustum_box_cached((const float(*)[4])f.planes,selected,bounds);
}'''
    (OUT/'culler.c').write_text(code)
    subprocess.run(['clang','-shared','-fPIC','-O2','-ffp-contract=off','-fno-fast-math','-I'+str(ROOT/'port/n64'),'-I'+str(ROOT/'build/n64-sidewinder-cluster-terrain/cameras'),'-I'+str(sdk),str(OUT/'culler.c'),str(sdk/'t3d/t3dmath.c'),'-lm','-o',str(OUT/'culler.dylib')],check=True)
    dll=ctypes.CDLL(str(OUT/'culler.dylib'));dll.box.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.POINTER(ctypes.c_int16),ctypes.c_int,ctypes.c_int];dll.box.restype=ctypes.c_int
    return dll

def visible_chunks(bank,vis,dataset,directory=None,verify=True):
    directory=directory or BASE/dataset;ss=sections(bank);chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));dll=culler();result=[]
    poses={(int(r['tick']),int(r['camera'])):r for r in csv.DictReader((directory/'cameras.csv').open()) if r['candidate']=='1'}
    for row in csv.reader((directory/'lod-trace.csv').open()):
        key=tuple(map(int,row[:2]));pose=poses[key];matrix=(ctypes.c_float*16)(*map(float,row[2:18]));levels=list(map(int,row[18:]));mask=int(pose['pvs_mask']);selected=[]
        for b,c in enumerate(chunks):
            code=vis['lod_chunks'][b]
            if code and levels[(code-1)//2]!=(code-1)%2:continue
            if not mask&vis['chunk_masks'][b]:continue
            bounds=(ctypes.c_int16*6)(*c[3:9]);w,h=(320,240) if dataset=='photos' else (160,120)
            if dll.box(matrix,bounds,w,h):selected.append(b)
        total=sum((chunks[b][1]+1)&~1 for b in selected)
        if verify:assert total==int(pose['vertices']),(dataset,key,total,pose['vertices'])
        result.append(dict(tick=key[0],camera=key[1],chunks=selected,vertices=total))
    return result

def prepare():
    from PIL import Image,ImageDraw
    OUT.mkdir(exist_ok=True)
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes();vis=json.loads((BASE/'visibility.json').read_text());rows=decode(payload)
    near=[r for r in rows if not vis['lod_chunks'][r['batch']] or (vis['lod_chunks'][r['batch']]-1)%2==0]
    terrain=[r for r in near if r['material'] in (7,8)]
    def sector(r):
        x,y,z=np.mean([v[:3] for v in r['triangle']],axis=0)/256
        return ('West' if x<0 else 'East')+(' bend' if z<0 else ' base side')
    chunks=list(struct.iter_unpack('>IHH6hHH',sections(payload)[1]));reports={}
    for dataset in ('replay','photos'):
        seen=visible_chunks(payload,vis,dataset);out=[]
        for view in seen:
            costs=collections.Counter()
            for b in view['chunks']:
                c=chunks[b]
                if c[2] not in (7,8):continue
                center=[(c[3+a]+c[6+a])/2/32 for a in range(3)]
                name=('West' if center[0]<0 else 'East')+(' bend' if center[2]<0 else ' base side');costs[name]+=(c[1]+1)&~1
            out.append({**view,'sector_loads':dict(costs)})
        reports[dataset]=out
    (OUT/'baseline-visible-chunks.json').write_text(json.dumps(reports,indent=2)+'\n')
    for ds,rs in reports.items():
        print(ds,[(s,round(sum(r['sector_loads'].get(s,0) for r in rs)/len(rs),1),max(r['sector_loads'].get(s,0) for r in rs)) for s in ('West bend','East bend')])
    # Gameplay cameras at the bend look across the canyon too; choose the
    # geometry sector by measured submissions rather than camera location.
    for name in ('West bend','East bend'):
        rs=[r for r in terrain if sector(r)==name];walk=[]
        for r in rs:
            p=np.array([v[:3] for v in r['triangle']],dtype=float);n=np.cross(p[1]-p[0],p[2]-p[0]);walk.append(r['material']==8 or n[1]*n[1]>=.38*(n@n))
        print(name,'faces',len(rs),'walkable',sum(walk),'cliff',sum(r['material']==7 for r in rs))
    im=Image.new('RGB',(1100,1100),(18,24,34));draw=ImageDraw.Draw(im)
    def xy(p):return (550+p[0]/256*7,550+p[2]/256*7)
    for r in sorted(terrain,key=lambda r:np.mean([v[1] for v in r['triangle']])):
        h=np.mean([v[1] for v in r['triangle']])/256;color=(int(90+h*2),int(110+h*2),int(150+h*2)) if r['material']==7 else (205,215,220)
        draw.polygon([xy(v) for v in r['triangle']],fill=color,outline=(55,65,75))
    for pose in json.loads((BASE/'photos/poses.json').read_text())[::2]:
        x,y,z=pose['position'];point=(550+x*7,550+z*7);draw.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill=(255,100,70));draw.text(point,pose['label'],fill='white')
    im.save(OUT/'terrain-overview.png')
    (OUT/'source.json').write_text(json.dumps(dict(bank_sha256=sha(payload),terrain=terrain),separators=(',',':'))+'\n')


def select_patch():
    source=json.loads((OUT/'source.json').read_text());rows=[r for r in source['terrain'] if np.mean([v[0] for v in r['triangle']])>=0 and np.mean([v[2] for v in r['triangle']])<-16*256]
    allpoints=sorted({tuple(v[:3]) for r in source['terrain'] for v in r['triangle']});p=np.array(allpoints,dtype=float)/256;target={tuple(v[:3]) for r in rows for v in r['triangle']};skyline=set()
    cameras=[]
    for ds in ('replay','photos'):
        cameras.extend([np.array([float(r[k]) for k in ('eye_x','eye_y','eye_z')]) for r in csv.DictReader((BASE/ds/'cameras.csv').open()) if r['candidate']=='1' and r['alive']=='1'])
    # Semantic skyline anchors: upper angular envelope of the full terrain
    # from all saved live cameras, not every old triangulation or PVS seam.
    for eye in cameras:
        delta=p-eye;az=np.arctan2(delta[:,2],delta[:,0]);bins=np.floor((az+math.pi)*180/math.tau).astype(int);elev=np.arctan2(delta[:,1],np.hypot(delta[:,0],delta[:,2]))
        for b in np.unique(bins):
            ids=np.flatnonzero(bins==b);i=ids[np.argmax(elev[ids])]
            if allpoints[i] in target:skyline.add(allpoints[i])
    lo=np.min([v[:3] for r in rows for v in r['triangle']],axis=0)/256;hi=np.max([v[:3] for r in rows for v in r['triangle']],axis=0)/256
    data=dict(source_bank_sha256=source['bank_sha256'],selection='Triangle centroid x >= 0, z < -16 world units: upper eastern canyon arc only.',rows=rows,bounds=[*lo,*hi],skyline_pins=sorted(skyline))
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes();visibility=json.loads((BASE/'visibility.json').read_text())
    near=[r for r in decode(payload) if not visibility['lod_chunks'][r['batch']] or (visibility['lod_chunks'][r['batch']]-1)%2==0]
    refs={(r['batch'],r['face']) for r in rows}
    data['outside_vertices']=sorted({tuple(v[:3]) for r in near if (r['batch'],r['face']) not in refs for v in r['triangle']})
    ridge=set()
    for pose in json.loads((BASE/'photos/poses.json').read_text()):
        eye=np.array(pose['position']);eye[1]+=pose['eye_height'];delta=p-eye;theta=np.arctan2(-delta[:,2],delta[:,0]);relative=(theta-pose['yaw']+math.pi)%(2*math.pi)-math.pi;ids=np.flatnonzero(abs(relative)<.66);bins=np.floor((relative+.66)*48/1.32).astype(int);elev=np.arctan2(delta[:,1],np.hypot(delta[:,0],delta[:,2]))
        for b in np.unique(bins[ids]):
            choices=ids[bins[ids]==b];at=int(choices[np.argmax(elev[choices])])
            if allpoints[at] in target and elev[at]>.04:ridge.add(allpoints[at])
    data['ridge_pins']=sorted(ridge)
    (OUT/'patch-source.json').write_text(json.dumps(data,separators=(',',':'))+'\n');print('Patch',len(rows),collections.Counter(r['material'] for r in rows),'skyline anchors',len(skyline),'bounds',data['bounds'])

def unwrap(rows,period):
    """Remove packing-only whole-texture offsets before joining old batches."""
    adjacency=collections.defaultdict(list);edges=collections.defaultdict(list)
    for i,r in enumerate(rows):
        for a,b in ((0,1),(1,2),(2,0)):
            points={tuple(r['triangle'][k][:3]):np.array(r['triangle'][k][6:]) for k in (a,b)};edge=tuple(sorted(points));edges[edge].append((i,points))
    for edge,entries in edges.items():
        for i,a in entries:
            for j,b in entries:
                if i>=j:continue
                diff=[a[p]-b[p] for p in edge]
                if np.array_equal(diff[0],diff[1]) and all(x%period==0 for x in diff[0]):adjacency[i].append((j,diff[0]));adjacency[j].append((i,-diff[0]))
    offsets={}
    for i in range(len(rows)):
        if i in offsets:continue
        offsets[i]=np.array([0,0]);stack=[i]
        while stack:
            at=stack.pop()
            for j,diff in adjacency[at]:
                value=offsets[at]+diff
                if j not in offsets:offsets[j]=value;stack.append(j)
    result=[]
    for i,r in enumerate(rows):result.append({**r,'triangle':[v[:6]+(np.array(v[6:])+offsets[i]).tolist() for v in r['triangle']]})
    return result

def author():
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    data=json.loads((OUT/'patch-source.json').read_text());data['skyline_pins']=data.get('ridge_pins',data['skyline_pins']);scene=bpy.data.scenes.new('Sidewinder — eastern bend terrain rebuild');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard';sky={tuple(p) for p in data['skyline_pins']};output=[];reports=[]
    collections_=[]
    for name in ('Original east bend','Rebuilt east bend'):
        c=bpy.data.collections.new(name);scene.collection.children.link(c);collections_.append(c)
    for mi in (7,8):
        rows=unwrap([r for r in data['rows'] if r['material']==mi],2048 if mi==8 else 1024);period=2048 if mi==8 else 1024
        mat=bpy.data.materials.new('Canyon source '+str(mi));mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear();tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{mi}.png'),check_existing=True);tex.interpolation='Closest';color=ns.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=ns.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;em=ns.new('ShaderNodeEmission');out=ns.new('ShaderNodeOutputMaterial');links=mat.node_tree.links;links.new(tex.outputs['Color'],mix.inputs[1]);links.new(color.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],em.inputs['Color']);links.new(em.outputs[0],out.inputs['Surface'])
        points=[];lookup={};faces=[]
        for r in rows:
            face=[]
            for v in r['triangle']:
                xyz=(v[0]/256,-v[2]/256,v[1]/256)
                if xyz not in lookup:lookup[xyz]=len(points);points.append(xyz)
                face.append(lookup[xyz])
            faces.append(face)
        mesh=bpy.data.meshes.new('Source bend '+str(mi));mesh.from_pydata(points,[],faces);mesh.materials.append(mat);uv=mesh.uv_layers.new(name='Unwrapped original diffuse');rgb=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for f,r in zip(mesh.polygons,rows):
            for li,v in zip(f.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/period,1-v[7]/period);rgb.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();source=bpy.data.objects.new('Original cliffs' if mi==7 else 'Original snow',mesh);collections_[0].objects.link(source);source.hide_set(True);source.hide_render=True
        oldps=[Vector(p) for p in points];reference=BVHTree.FromPolygons(oldps,faces,all_triangles=True);bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
        key=lambda v:tuple(round(x*256) for x in (v.co.x,v.co.z,-v.co.y))
        boundary_edges={tuple(sorted((key(e.verts[0]),key(e.verts[1])))) for e in bm.edges if len(e.link_faces)!=2}
        outside={tuple(v) for v in data['outside_vertices']}
        other={tuple(v[:3]) for r in data['rows'] if r['material']!=mi for v in r['triangle']}
        pinned={v.index for v in bm.verts if key(v) in outside or key(v) in other or key(v) in sky}
        attachment_edges={edge for edge in boundary_edges if all(p in outside or p in other for p in edge)}
        walkable=[f for f in bm.faces if mi==7 and f.normal.z*f.normal.z>=.38];walk_faces={tuple(sorted(key(v) for v in f.verts)) for f in walkable};pinned|={v.index for f in walkable for v in f.verts}
        pin_positions={key(bm.verts[i]) for i in pinned};bm.free()
        # Rebuild coplanar snow polygons across obsolete internal tile/cluster
        # boundaries. Cliff topology is reduced around the protected route and
        # skyline contours, with no old partition edges pinned internally.
        attempts=[];chosen=None
        settings=([.22]*40+[1.])
        for setting in settings:
            obj=bpy.data.objects.new('Trial',mesh.copy());collections_[1].objects.link(obj)
            if True:
                vg=obj.vertex_groups.new(name='Wall panels between path and skyline');free=[i for i in range(len(points)) if i not in pinned]
                if free:vg.add(free,1,'REPLACE')
                mod=obj.modifiers.new('Rebuild wall panels','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=setting if free else 1.;mod.vertex_group=vg.name;mod.vertex_group_factor=1000;mod.use_collapse_triangulate=True
                bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();graph.update();ev=obj.evaluated_get(graph);emesh=ev.to_mesh();newmesh=emesh.copy();ev.to_mesh_clear();obj.modifiers.clear();obj.data=newmesh
            else:
                b=bmesh.new();b.from_mesh(obj.data)
                # Only remove vertices away from the actual patch boundary and
                # skyline; ORIGINAL UV islands are retained after wrap repair.
                b.verts.ensure_lookup_table();fixed={v for v in b.verts if key(v) in pin_positions};edges=[e for e in b.edges if len(e.link_faces)==2 and not all(v in fixed for v in e.verts)]
                bmesh.ops.dissolve_limit(b,angle_limit=setting,use_dissolve_boundaries=False,verts=[v for v in b.verts if v not in fixed],edges=edges,delimit={'UV','NORMAL'})
                bmesh.ops.triangulate(b,faces=list(b.faces),quad_method='BEAUTY',ngon_method='BEAUTY');b.to_mesh(obj.data);b.free()
            m=obj.data;m.update();m.calc_loop_triangles();ps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in m.vertices];fs=[list(t.vertices) for t in m.loop_triangles];target=BVHTree.FromPolygons(ps,fs,all_triangles=True)
            def samples(pp,ff):
                for face in ff:
                    a,b,c=[pp[i] for i in face]
                    yield a;yield b;yield c;yield (a+b)/2;yield (b+c)/2;yield (c+a)/2;yield (a+b+c)/3
            distances=[(reference.find_nearest(p)[3],p) for p in samples(ps,fs)]+[(target.find_nearest(p)[3],p) for p in samples(oldps,faces)]
            error,problem=max(distances,key=lambda x:x[0])
            retained={tuple(round(x*256) for x in (p.x,p.z,-p.y)) for p in ps};missing=len(pin_positions-retained)
            actual_walk={tuple(sorted(tuple(round(x*256) for x in (ps[i].x,ps[i].z,-ps[i].y)) for i in f)) for f in fs};walk_missing=len(walk_faces-actual_walk)
            b=bmesh.new();b.from_mesh(m);after_edges={tuple(sorted((key(e.verts[0]),key(e.verts[1])))) for e in b.edges if len(e.link_faces)!=2};b.free();seam_equal=attachment_edges<=after_edges
            accepted=not missing and not walk_missing and seam_equal and error<=(.35 if mi==7 else .06)
            attempts.append(dict(setting=setting,triangles=len(fs),sampled_symmetric_error=error,missing_pins=missing,walkable_faces_missing=walk_missing,boundary_edges_exact=seam_equal,accepted=accepted))
            if not accepted:
                available=[i for i in range(len(points)) if i not in pinned]
                if available:
                    protect=min(available,key=lambda i:(oldps[i]-problem).length_squared);pinned.add(protect);pin_positions.add(tuple(round(x*256) for x in (oldps[protect].x,oldps[protect].z,-oldps[protect].y)))
                bpy.data.objects.remove(obj,do_unlink=True);continue
            chosen=obj;chosen.name='Rebuilt wall panels' if mi==7 else 'Retriangulated snow surface';newuv=m.uv_layers.active;colors=m.color_attributes['Source lightmap']
            for t in m.loop_triangles:
                tri=[]
                for vi,li in zip(t.vertices,t.loops):
                    x,y,z=ps[vi];u,v=newuv.data[li].uv;rgb=colors.data[li].color
                    tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in rgb[:3]],round(u*period),round((1-v)*period)])
                output.append(dict(material=mi,triangle=tri))
            reports.append(dict(material=mi,source_triangles=len(rows),candidate_triangles=len(fs),pinned_vertices=len(pinned),skyline_vertices=len(sky&pin_positions),walkable_rock_faces=len(walk_faces),attempts=attempts));break
        if chosen is None:raise RuntimeError('No preserved-surface candidate for material '+str(mi))
    (OUT/'authored.json').write_text(json.dumps(dict(source_sha256=sha((OUT/'patch-source.json').read_bytes()),triangles=output,report=reports),separators=(',',':'))+'\n')
    for ob in scene.objects:ob.select_set(not ob.hide_get())
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'canyon-appraisal.blend'));print(json.dumps(reports))

def author_combined():
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    data=json.loads((OUT/'patch-source.json').read_text());scene=bpy.data.scenes.new('Sidewinder — joined playable surface and skyline');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    rows=[r for mi in (7,8) for r in unwrap([r for r in data['rows'] if r['material']==mi],2048 if mi==8 else 1024)]
    source_scene=bpy.data.scenes.get('Sidewinder — eastern bend terrain rebuild');mats=[]
    for mi in (7,8):
        original=next(o for o in source_scene.objects if o.name.startswith('Original cliffs' if mi==7 else 'Original snow'));mats.append(original.data.materials[0])
    lookup={};points=[];faces=[]
    for r in rows:
        face=[]
        for v in r['triangle']:
            p=(v[0]/256,-v[2]/256,v[1]/256)
            if p not in lookup:lookup[p]=len(points);points.append(p)
            face.append(lookup[p])
        faces.append(face)
    mesh=bpy.data.meshes.new('Joined east bend source');mesh.from_pydata(points,[],faces)
    for m in mats:mesh.materials.append(m)
    uv=mesh.uv_layers.new(name='Aligned original diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
    for f,r in zip(mesh.polygons,rows):
        f.material_index=r['material']-7;period=2048 if r['material']==8 else 1024
        for li,v in zip(f.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/period,1-v[7]/period);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
    mesh.update();source=bpy.data.objects.new('Original joined east bend',mesh);scene.collection.objects.link(source);source.hide_set(True);source.hide_render=True
    oldps=[Vector(p) for p in points];reference=BVHTree.FromPolygons(oldps,faces,all_triangles=True);floor_faces=[f for f,r in zip(faces,rows) if r['material']==8];floor_ref=BVHTree.FromPolygons(oldps,floor_faces,all_triangles=True)
    outside={tuple(v) for v in data['outside_vertices']};key=lambda p:tuple(round(x*256) for x in (p.x,p.z,-p.y));pinned={i for i,p in enumerate(oldps) if key(p) in outside};walkfaces=[]
    for f,r in zip(faces,rows):
        a,b,c=[oldps[i] for i in f];n=(b-a).cross(c-a)
        if r['material']==7 and n.z*n.z>=.38*n.length_squared:pinned.update(f);walkfaces.append(f)
    # A small set of silhouette support points from the four bend/canyon
    # stations, sampled in 12-degree angular sectors. Fine source points along
    # those contours can disappear; the actual image skyline is checked later.
    cameras=json.loads((BASE/'photos/poses.json').read_text());sky=set();p=np.array(points)
    for photo in (8,10,12,14):
        pose=cameras[photo];eye=np.array([pose['position'][0],-pose['position'][2],pose['position'][1]+pose['eye_height']]);d=p-eye;az=np.arctan2(d[:,1],d[:,0]);bins=np.floor((az+math.pi)*30/math.tau).astype(int);elev=np.arctan2(d[:,2],np.hypot(d[:,0],d[:,1]))
        for b in np.unique(bins):
            ids=np.flatnonzero(bins==b);at=int(ids[np.argmax(elev[ids])])
            if elev[at]>.04:sky.add(at)
    pinned|=sky;pin_positions={key(oldps[i]) for i in pinned};walk_keys={tuple(sorted(key(oldps[i]) for i in f)) for f in walkfaces}
    # True external attachment edges are protected. Internal material and old
    # tile boundaries can be rebuilt as a coupled surface.
    bm=bmesh.new();bm.from_mesh(mesh);external={tuple(sorted((key(e.verts[0].co),key(e.verts[1].co)))) for e in bm.edges if len(e.link_faces)!=2 and all(key(v.co) in outside for v in e.verts)};bm.free()
    def samples(ps,fs,dense=False):
        for face in fs:
            a,b,c=[ps[i] for i in face];n=max(2,math.ceil(max((a-b).length,(b-c).length,(c-a).length)/.3)) if dense else 2
            for i in range(n+1):
                for j in range(n+1-i):yield a+(b-a)*(i/n)+(c-a)*(j/n)
            yield (a+b+c)/3
    attempts=[];output=[];chosen=None
    for ratio in (.25,.35,.45,.55,.65,.75,.85,.95,1.):
        obj=bpy.data.objects.new('Joined bend trial',mesh.copy());scene.collection.objects.link(obj);vg=obj.vertex_groups.new(name='External joins, walking rocks and skyline anchors');free=[i for i in range(len(points)) if i not in pinned]
        if free:vg.add(free,1,'REPLACE')
        mod=obj.modifiers.new('Rebuild joined floor and wall topology','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=ratio;mod.vertex_group=vg.name;mod.vertex_group_factor=1000;mod.use_collapse_triangulate=True
        bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();dg.update();ev=obj.evaluated_get(dg);temp=ev.to_mesh();m=temp.copy();ev.to_mesh_clear();obj.modifiers.clear();obj.data=m;m.calc_loop_triangles();ps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in m.vertices];fs=[list(t.vertices) for t in m.loop_triangles];floors=[list(t.vertices) for t in m.loop_triangles if t.material_index==1];target=BVHTree.FromPolygons(ps,fs,all_triangles=True);floor_target=BVHTree.FromPolygons(ps,floors,all_triangles=True)
        err=max([reference.find_nearest(p)[3] for p in samples(ps,fs)]+[target.find_nearest(p)[3] for p in samples(oldps,faces)]);floor_error=max([floor_ref.find_nearest(p)[3] for p in samples(ps,floors,True)]+[floor_target.find_nearest(p)[3] for p in samples(oldps,floor_faces,True)])
        retained={key(p) for p in ps};missing=len(pin_positions-retained);actual_walk={tuple(sorted(key(ps[i]) for i in f)) for f in fs};walk_missing=len(walk_keys-actual_walk)
        b=bmesh.new();b.from_mesh(m);newedges={tuple(sorted((key(e.verts[0].co),key(e.verts[1].co)))) for e in b.edges};b.free();external_missing=len(external-newedges)
        accepted=not missing and not walk_missing and not external_missing and err<=.45 and floor_error<=.025
        record=dict(ratio=ratio,triangles=len(fs),surface_sampled_error=err,dense_snow_surface_error=floor_error,missing_pins=missing,walkable_rock_faces_missing=walk_missing,external_edges_missing=external_missing,accepted=accepted);attempts.append(record);print(record,flush=True)
        if not accepted:bpy.data.objects.remove(obj,do_unlink=True);continue
        chosen=obj;obj.name='Rebuilt east bend — joined floor and wall panels';newuv=m.uv_layers.active;rgb=m.color_attributes['Source lightmap']
        for t in m.loop_triangles:
            mi=t.material_index+7;period=2048 if mi==8 else 1024;tri=[]
            for vi,li in zip(t.vertices,t.loops):
                x,y,z=ps[vi];u,v=newuv.data[li].uv;col=rgb.data[li].color
                tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in col[:3]],round(u*period),round((1-v)*period)])
            output.append(dict(material=mi,triangle=tri))
        break
    if chosen is None:raise RuntimeError('No path-preserving joined rebuild')
    report=dict(source_triangles=len(rows),candidate_triangles=len(output),outside_attachment_vertices=sum(key(p) in outside for p in oldps),pinned_vertices=len(pinned),skyline_support_vertices=len(sky),walkable_rock_faces=len(walk_keys),external_attachment_edges=len(external),attempts=attempts,scope='Coupled snow/wall retopology; original external attachments and walkable rock faces exact. Dense symmetric snow-surface checks at <=0.3-world-unit spacing; sampled whole-surface error. Original collision retained separately.')
    (OUT/'authored.json').write_text(json.dumps(dict(source_sha256=sha((OUT/'patch-source.json').read_bytes()),triangles=output,report=report),separators=(',',':'))+'\n')
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'canyon-appraisal.blend'));print(json.dumps(report))

def pack(cell=16,color_delta=8,control=False):
    from pack_maps import bank,packed,uv_safe_triangles
    from pack_terrain import indexed_terrain
    original=(BASE/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(original);vis=json.loads((BASE/'visibility.json').read_text());source=json.loads((OUT/'patch-source.json').read_text());auth=json.loads((OUT/'authored.json').read_text());assert auth['source_sha256']==sha((OUT/'patch-source.json').read_bytes())
    destination=OUT/('control' if control else 'candidate');destination.mkdir(exist_ok=True)
    targets={(r['batch'],r['face']) for r in source['rows']};removed_groups={i for i,g in enumerate(vis['lod_groups']) if g['category']=='terrain' and g['key'][2]>=0 and g['key'][3]<=-2}
    allrows=decode(original);bybatch=collections.defaultdict(list)
    for r in allrows:bybatch[r['batch']].append(r)
    vertices=bytearray();indices=bytearray();chunks=[];masks=[];codes=[];proof=[];work=[]
    oldchunks=list(struct.iter_unpack('>IHH6hHH',ss[1]));first={}
    for b,c in enumerate(oldchunks):first.setdefault(c[2],b)
    def append_batch(vs,ix,mi,mask,code,meta):
        start=len(indices)//2;at=len(vertices)//16;pad=vs+([vs[-1]] if len(vs)%2 else []);rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        vertices.extend(packed('3hH3hHII4h',[(*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]) for a,b in zip(pad[::2],pad[1::2])]))
        indices.extend(packed('H',[(i,) for i in ix]))
        while len(indices)%8:indices.extend(b'\0\0')
        bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)];chunks.append((at,len(vs),mi,*bounds,start,len(ix)));masks.append(mask);codes.append(code);proof.append(meta)
    removed=[]
    for b,c in enumerate(oldchunks):
        code=vis['lod_chunks'][b]
        if code and (code-1)//2 in removed_groups:removed.append(b);continue
        rs=bybatch[b];left=[r for r in rs if (b,r['face']) not in targets]
        if len(left)==len(rs):
            vfirst,count,mi,*rest=c;at,n=rest[-2:];chunks.append((len(vertices)//16,count,mi,*rest[:6],len(indices)//2,n));vertices.extend(ss[0][vfirst//2*32:(vfirst+((count+1)&~1))//2*32]);indices.extend(ss[2][at*2:(at+((n+3)&~3))*2]);masks.append(vis['chunk_masks'][b]);codes.append(code);proof.append(dict(old_batch=b,unchanged=True));continue
        removed.append(b)
        if left:work.append((c[2],left,vis['chunk_masks'][b],code,dict(old_batch=b,unchanged=False,remaining_original=True)))
    rows=([r for mi in (7,8) for r in unwrap([r for r in source['rows'] if r['material']==mi],2048 if mi==8 else 1024)] if control else auth['triangles'])
    grouped=collections.defaultdict(list)
    for r in rows:
        p=np.mean([v[:3] for v in r['triangle']],axis=0)/256;grouped[r['material'],math.floor(p[0]/cell),math.floor(p[2]/cell)].append(r)
    for (mi,x,z),rs in sorted(grouped.items()):work.append((mi,rs,ALL,0,dict(old_batch=None,unchanged=False,replacement=True,cell=[x,z])))
    for mi,rs,mask,code,meta in work:
        delta=color_delta if meta.get('replacement') else 0
        for batch in indexed_terrain(uv_safe_triangles([r['triangle'] for r in rs]),color_delta=delta,uv_period=ss[4][mi]*32):append_batch(batch['vertices'],batch['indices'],mi,mask,code,meta)
    order=sorted(range(len(chunks)),key=lambda i:(first[chunks[i][2]],proof[i].get('old_batch') if proof[i].get('old_batch') is not None else first[chunks[i][2]],i));chunks,masks,codes,proof=([x[i] for i in order] for x in (chunks,masks,codes,proof))
    assert len(chunks)<=1024 and len(indices)//2<65536
    ss[0],ss[1],ss[2]=bytes(vertices),packed('IHH6hHH',chunks),bytes(indices);maps=destination/'candidate-maps';maps.mkdir(exist_ok=True)
    for p in (BASE/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (maps/p.name).exists():(maps/p.name).symlink_to(p.resolve())
    result=bank(maps/'sidewinder.map64',1,ss);payload=(maps/'sidewinder.map64').read_bytes();result.update(source_bank_sha256=sha(original),candidate_sha256=sha(payload),batches=proof,chunk_masks=masks,lod_chunks=codes,lod_groups=vis['lod_groups'],removed_batches=removed,removed_groups=sorted(removed_groups),cell_size=cell,color_delta=color_delta,source_patch_triangles=len(source['rows']),replacement_triangles=len(rows),stored_entries=len(vertices)//16,chunk_count=len(chunks),control=control)
    report=destination/'packing-report.json';report.write_text(json.dumps(result,indent=2)+'\n')
    data={**vis,'schema':7,'map_sha256':sha(payload),'chunk_masks':masks,'lod_chunks':codes,'canyon_baseline_sidecar':str(BASE/'visibility.json'),'canyon_baseline_sidecar_sha256':sha((BASE/'visibility.json').read_bytes()),'canyon_baseline_bank':str(BASE/'candidate-maps/sidewinder.map64'),'canyon_packing_report':str(report),'canyon_packing_report_sha256':sha(report.read_bytes()),'canyon_source_path':str(OUT/'patch-source.json'),'canyon_source_sha256':sha((OUT/'patch-source.json').read_bytes())}
    validate(data,payload);(destination/'visibility.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    from export_chiron_visibility import emit_c
    emit_c(data,destination/'visibility-data.c',maps/'sidewinder.map64')
    print('Packed',cell,color_delta,'control' if control else 'rebuild',len(chunks),len(vertices)//16)
    return destination

def validate(data,payload):
    from sidewinder_world_lod import validate as base_validate
    raw=Path(data['canyon_baseline_sidecar']).read_bytes();assert sha(raw)==data['canyon_baseline_sidecar_sha256'];base=json.loads(raw);original=Path(data['canyon_baseline_bank']).read_bytes();base_validate(base,original)
    assert sha(payload)==data['map_sha256'] and sections(original)[3:]==sections(payload)[3:]
    raw=Path(data['canyon_packing_report']).read_bytes();assert sha(raw)==data['canyon_packing_report_sha256'];proof=json.loads(raw)
    raw=Path(data['canyon_source_path']).read_bytes();assert sha(raw)==data['canyon_source_sha256'];source=json.loads(raw);targets={(r['batch'],r['face']) for r in source['rows']}
    assert proof['source_bank_sha256']==sha(original) and proof['candidate_sha256']==sha(payload)
    for k in ('nodes','planes','leaf_clusters','rows','clusters','map_name','map_id','normal_limit','cluster_probes','lod_groups'):assert data[k]==base[k]
    assert data['chunk_masks']==proof['chunk_masks'] and data['lod_chunks']==proof['lod_chunks']
    old=decode(original);new=decode(payload);oldby=collections.defaultdict(list);newby=collections.defaultdict(list)
    for r in old:oldby[r['batch']].append(r)
    for r in new:newby[r['batch']].append(r)
    assert source['source_bank_sha256']==sha(original)
    refs={(r['batch'],r['face']):r for r in old}
    for r in source['rows']:
        assert signature(r)==signature(refs[r['batch'],r['face']]) and r['material'] in (7,8)
        assert np.mean([v[0] for v in r['triangle']])>=0 and np.mean([v[2] for v in r['triangle']])<-16*256
    transferred=set();kept_old=[];kept_new=[]
    for b,meta in enumerate(proof['batches']):
        if meta.get('replacement'):
            assert all(r['material'] in (7,8) for r in newby[b]);assert data['chunk_masks'][b]==ALL and data['lod_chunks'][b]==0;continue
        at=meta['old_batch'];kept_new.extend(newby[b]);assert data['chunk_masks'][b]==base['chunk_masks'][at] and data['lod_chunks'][b]==base['lod_chunks'][at];transferred.add(at)
    for b in transferred:kept_old.extend(r for r in oldby[b] if (b,r['face']) not in targets)
    assert collections.Counter(map(signature,kept_old))==collections.Counter(map(signature,kept_new)),'Geometry outside the bend changed'
    removable_groups={i for i,g in enumerate(base['lod_groups']) if g['category']=='terrain' and g['key'][2]>=0 and g['key'][3]<=-2}
    for b,rs in oldby.items():
        code=base['lod_chunks'][b]
        if code and (code-1)//2 in removable_groups:continue
        if any((b,r['face']) not in targets for r in rs):assert b in transferred,'Unrelated batch disappeared'
    replacements=[r for r in new if proof['batches'][r['batch']].get('replacement')]
    poskey=lambda r:tuple(sorted(tuple(v[:3]) for v in r['triangle']))
    positions={poskey(r) for r in replacements};allpoints={tuple(v[:3]) for r in replacements for v in r['triangle']}
    for r in source['rows']:
        if r['material']!=7:continue
        p=np.array([v[:3] for v in r['triangle']],dtype=float);normal=np.cross(p[1]-p[0],p[2]-p[0])
        if normal[1]**2>=.38*(normal@normal):assert poskey(r) in positions,'Walking rock face changed'
    assert {tuple(v) for v in source['ridge_pins']}<=allpoints,'Skyline support point changed'
    assert all(0<=code<=2*len(data['lod_groups']) for code in data['lod_chunks'])

def buried_faces():
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes();vis=json.loads((BASE/'visibility.json').read_text());allrows=decode(payload);ice=[r for r in allrows if r['material']==9];patch=json.loads((OUT/'patch-source.json').read_text());results=[]
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    def clip(poly,triangle):
        a=np.array(triangle);sign=1 if cross(a[1]-a[0],a[2]-a[0])>=0 else -1
        for i in range(3):
            p,q=a[i],a[(i+1)%3];out=[]
            for j,x in enumerate(poly):
                y=poly[(j+1)%len(poly)];dx=sign*cross(q-p,x-p);dy=sign*cross(q-p,y-p)
                if dx>=-1e-9:out.append(x)
                if (dx>=0)!=(dy>=0):out.append(x+(y-x)*dx/(dx-dy))
            poly=out
            if len(poly)<3:return []
        return poly
    def area(p):return abs(sum(cross(p[i],p[(i+1)%len(p)]) for i in range(len(p))))/2
    for r in patch['rows']:
        pts=np.array([v[:3] for v in r['triangle']],dtype=float)/256;xz=pts[:,[0,2]];ar=area(xz)
        if ar<1e-8:continue
        plane=np.linalg.solve(np.column_stack((xz,np.ones(3))),pts[:,1]);covered=0
        for upper in ice:
            p=np.array([v[:3] for v in upper['triangle']],dtype=float)/256;uv=p[:,[0,2]]
            if area(uv)<1e-8:continue
            poly=clip(list(xz),uv)
            if not poly:continue
            top=np.linalg.solve(np.column_stack((uv,np.ones(3))),p[:,1]);q=np.column_stack((poly,np.ones(len(poly))))
            if np.min(q@(top-plane))>.03:covered+=area(poly)
        if covered>=ar*(1-1e-7):results.append(dict(batch=r['batch'],face=r['face'],material=r['material'],area=ar))
    (OUT/'buried-face-candidates.json').write_text(json.dumps(results,indent=2)+'\n');print('Fully covered in XZ by higher opaque ice:',len(results),collections.Counter(r['material'] for r in results))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','select','pack','control','buried'))
    args=parser.parse_args()
    if args.action=='pack':pack(12)
    elif args.action=='control':pack(12,control=True)
    else:{'prepare':prepare,'select':select_patch,'buried':buried_faces}[args.action]()
