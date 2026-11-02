"""Symmetric original-source ODST helmet with an intact crown paint boundary.

The rigid head is separate from the source neck liner. Reduce one material
partition at a time, lock its real rims, then mirror the retained source half.
Both gameplay LODs use the same head, as in the successful Jorge helmet pass.
"""
from collections import defaultdict
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree

def clipped_half(model,faces,center):
    points=[];polygons=[];lookup={}
    for fi in faces:
        vertices=[np.array(model['vertices'][i],dtype=float) for i in model['faces'][fi]]
        for p in vertices:
            p[1]-=center
            if abs(p[1])<1e-5:p[1]=0
        clipped=[]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            if a[1]>=0:clipped.append(a)
            if (a[1]<0<b[1]) or (b[1]<0<a[1]):
                p=a+(b-a)*(-a[1]/(b[1]-a[1]));p[1]=0;clipped.append(p)
        ids=[]
        for p in clipped:
            key=tuple(round(float(x),9) for x in p)
            if key not in lookup:lookup[key]=len(points);points.append(p)
            if not ids or ids[-1]!=lookup[key]:ids.append(lookup[key])
        if len(ids)>2 and ids[0]==ids[-1]:ids.pop()
        for j in range(1,len(ids)-1):
            f=[ids[0],ids[j],ids[j+1]]
            if np.linalg.norm(np.cross(points[f[1]]-points[f[0]],points[f[2]]-points[f[0]]))>1e-12:polygons.append(f)
    return points,polygons

def reduce_half(points,faces,target,name):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces);mesh.update()
    edges=defaultdict(int)
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))]+=1
    rim={v for edge,n in edges.items() if n==1 for v in edge}
    protected=set(rim)
    # Keep source silhouette extrema in addition to material/center-plane rims.
    for direction in ((1,0,0),(-1,0,0),(0,1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,1,0),(0,1,1),(0,1,-1)):
        protected.add(max(range(len(points)),key=lambda i:float(np.dot(points[i],direction))))
    ob=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(ob)
    group=ob.vertex_groups.new(name='Original stripe, visor, neck and symmetry-plane rims')
    group.add(list(range(len(points))),1,'REPLACE');group.add(sorted(protected),0,'REPLACE')
    requested=target
    while True:
        mod=ob.modifiers.new('Source surface collapse with protected boundaries','DECIMATE')
        mod.ratio=min(1,target/len(faces));mod.use_collapse_triangulate=True
        mod.vertex_group=group.name;mod.vertex_group_factor=1000
        ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles()
        xyz=np.array([v.co[:] for v in me.vertices]);triangles=[list(t.vertices) for t in me.loop_triangles]
        missing=max(min(np.linalg.norm(xyz-p,axis=1)) for p in np.array(points)[sorted(protected)])
        if missing<1e-7 or target>=len(faces):
            normals=np.array([v.normal[:] for v in me.vertices]);ev.to_mesh_clear();ob.modifiers.remove(mod);break
        ev.to_mesh_clear();ob.modifiers.remove(mod);target=min(len(faces),max(target+2,round(target*1.12)))
    bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
    assert missing<1e-7,(name,'protected source contour moved',missing)
    return xyz,triangles,normals,dict(requested_half_triangles=requested,actual_half_triangles=len(triangles),protected_vertices=len(protected),maximum_protected_movement=float(missing))

def build_head(model):
    head=next(i for i,n in enumerate(model['nodes']) if n['name']=='bip01 head')
    faces=[fi for fi,r in enumerate(model['regions']) if r=='helmet' and all(max(model['skin_weights'][v],key=lambda w:w[1])[0]==head for v in model['faces'][fi])]
    p=np.array([model['vertices'][v] for fi in faces for v in model['faces'][fi]])
    center=float((p[:,1].min()+p[:,1].max())/2)
    stripe=next(i for i,m in enumerate(model['material_metadata']) if m['path'].endswith('odst_crown_stripe'))
    visor=next(i for i,m in enumerate(model['material_metadata']) if m['path'].endswith('odst_visor'))
    result=[];reports=[]
    for material in sorted({model['materials'][fi] for fi in faces}):
        selected=[fi for fi in faces if model['materials'][fi]==material]
        points,half_faces=clipped_half(model,selected,center)
        region='stripe' if material==stripe else 'visor' if material==visor else 'shell'
        target=len(half_faces) if region=='stripe' else 16 if region=='visor' else 60
        xyz,triangles,normals,report=reduce_half(points,half_faces,target,'ODST symmetric '+region)
        tree=BVHTree.FromPolygons([Vector(v) for v in model['vertices']],[model['faces'][fi] for fi in selected],all_triangles=True)
        image=bpy.data.images.load(model['textures'][material],check_existing=True);w,h=image.size;pixels=np.array(image.pixels[:]).reshape(h,w,4)
        samples=[];error=0
        for i,point in enumerate(xyz):
            original=point.copy();original[1]+=center
            hit,_,fi,distance=tree.find_nearest(Vector(original));error=max(error,distance);ids=model['faces'][selected[fi]]
            bary=np.maximum(0,interpolate.poly_3d_calc([Vector(model['vertices'][v]) for v in ids],hit));bary/=bary.sum()
            uv=bary@np.array([model['uv'][v] for v in ids])
            # A single source-derived vertex color is cloned with each mirrored
            # point. Cache ordering cannot choose different left/right shades.
            normal=normals[i].copy()
            if abs(point[1])<1e-7:normal[1]=0
            normal/=max(1e-12,np.linalg.norm(normal));engine_normal=np.array([normal[0],normal[2],abs(normal[1])])
            light=.68+.32*max(0,float(np.dot(engine_normal,(.25,.83,.49))))
            rgb=np.rint(pixels[h-1-int(uv[1]%1*h),int(uv[0]%1*w),:3]*255*light).astype(int).tolist()
            samples.append(dict(uv=uv.tolist(),source=dict(face=selected[fi],barycentric=bary.tolist()),rgb=rgb))
        for f in triangles:
            for sign,order in ((1,f),(-1,[f[0],f[2],f[1]])):
                p=[(xyz[i]*[1,sign,1]).tolist() for i in order]
                t=dict(p=p,uv=[samples[i]['uv'] for i in order],weights=[[(head,1)]]*3,material=material,
                    component='helmet-head',helmet_region=region,source_faces=[samples[i]['source'] for i in order],
                    source_transform=[[1,0,0,0],[0,sign,0,-sign*center],[0,0,1,0],[0,0,0,1]])
                if region=='shell':t['corner_color_override']=[samples[i]['rgb'] for i in order]
                result.append(t)
        reports.append(dict(region=region,source_triangles=len(selected),source_half_triangles=len(half_faces),maximum_sampled_surface_error=float(error),**report))
    return result,dict(source_mirror_plane_y=center,output_mirror_plane_y=0,shared_head_between_lods=True,regions=reports)

def is_old_head(tri,head):
    helmet=tri['component'].startswith('helmet') or tri.get('source_component','').startswith('helmet')
    return helmet and all(b==head for ws in tri['weights'] for b,w in ws if w>1e-5)
