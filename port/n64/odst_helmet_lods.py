"""Independent mirrored ODST helmets from retained original source vertices.

Collapse compatible edges on a joined source half. Material boundaries and the
symmetry plane may simplify along themselves, never across one another. This
retains the stripe and visor without freezing every source contour sample.
"""
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
import bpy
from odst_helmet import clipped_half,is_old_head


def source_half(model,faces,center):
    points=[];triangles=[];materials=[];lookup={}
    for material in sorted({model['materials'][fi] for fi in faces}):
        p,f=clipped_half(model,[fi for fi in faces if model['materials'][fi]==material],center)
        mapping=[]
        for v in p:
            key=tuple(np.round(v,6))
            if key not in lookup:lookup[key]=len(points);points.append(v)
            mapping.append(lookup[key])
        for t in f:
            ids=[mapping[i] for i in t]
            if len(set(ids))==3:triangles.append(ids);materials.append(material)
    return np.array(points),np.array(triangles),np.array(materials)


def reduce_half(points,faces,materials,target,stripe,visor,lod):
    """Endpoint quadric collapse: retained points remain on original surfaces."""
    quadrics=np.zeros((len(points),4,4));locked=set()
    def topology():
        edges=defaultdict(list);incident=defaultdict(set);neighbors=defaultdict(set)
        for fi,(t,m) in enumerate(zip(faces,materials)):
            for v in t:incident[v].add(int(m))
            for a,b in zip(t,np.roll(t,-1)):
                edges[tuple(sorted((a,b)))].append(fi);neighbors[a].add(b);neighbors[b].add(a)
        tags={v:set(ms) for v,ms in incident.items()}
        for edge,fs in edges.items():
            if len(fs)==1:
                for v in edge:tags[v].add('center' if abs(points[v,1])<1e-8 else 'rim')
        return edges,neighbors,tags
    edges,_,tags=topology()
    # Preserve the characteristic silhouette extrema, not all contour samples.
    directions=[(1,0,0),(-1,0,0),(0,1,0),(0,0,1),(0,0,-1)]
    directions.append((1,1,0))
    if lod==0:directions.append((-1,1,0))
    for d in directions:
        locked.add(int(np.argmax(points@d)))
    for d in ((0,1,1),(0,1,-1),(1,0,1),(-1,0,1)):
        locked.add(int(np.argmax(points@d)))
    stripe_rim=[v for v,ms in tags.items() if stripe in ms and len({m for m in ms if isinstance(m,int)})>1]
    if stripe_rim:
        for x in (-.03,0,.035):
            locked.add(min(stripe_rim,key=lambda v:abs(points[v,0]-x)+max(0,.68-points[v,2])*2))
    # Broad forehead and lower nape returns must survive in both LODs;
    # otherwise coarse chords uncover neck/temple gaps in assembled motion.
    contour_points=((.022,.026,.681),(-.033,.031,.626)) if lod==0 else ((.0145,.0364,.6298),(-.033,.031,.626))
    for point in contour_points:
        locked.add(int(np.argmin(np.linalg.norm(points-np.array(point),axis=1))))
    for m in sorted(set(materials)):
        ids=np.unique(faces[materials==m])
        for axis in (0,):
            locked.add(int(ids[np.argmin(points[ids,axis])]))
            locked.add(int(ids[np.argmax(points[ids,axis])]))
    for t in faces:
        p=points[t];n=np.cross(p[1]-p[0],p[2]-p[0]);n/=max(1e-20,np.linalg.norm(n));plane=np.r_[n,-n@p[0]]
        for v in t:quadrics[v]+=np.outer(plane,plane)
    for (a,b),fs in edges.items():
        if len(fs)==1 or len({materials[i] for i in fs})>1:
            p=points[faces[fs[0]]];n=np.cross(p[1]-p[0],p[2]-p[0]);edge=points[b]-points[a]
            n=np.cross(edge,n);n/=max(1e-20,np.linalg.norm(n));plane=np.r_[n,-n@points[a]]
            for v in (a,b):quadrics[v]+=20*np.outer(plane,plane)
    while len(faces)>target:
        edges,neighbors,tags=topology();candidates=[]
        for (a,b),fs in edges.items():
            for remove,keep in ((a,b),(b,a)):
                if remove in locked or not tags[remove].issubset(tags[keep]):continue
                if len(neighbors[a]&neighbors[b])!=len(fs):continue
                v=np.r_[points[keep],1];cost=float(v@(quadrics[a]+quadrics[b])@v)
                candidates.append((cost,remove,keep))
        accepted=False
        minimum={visor:(4,3)[lod],stripe:(4,3)[lod]}
        for _,remove,keep in sorted(candidates):
            affected=np.any(faces==remove,axis=1);new=faces[affected].copy();new[new==remove]=keep
            survives=np.array([len(set(t))==3 for t in new])
            if any(np.count_nonzero(materials==m)-np.count_nonzero(materials[affected][~survives]==m)<n for m,n in minimum.items()):continue
            before=points[faces[affected][survives]];after=points[new[survives]]
            a=np.cross(before[:,1]-before[:,0],before[:,2]-before[:,0]);b=np.cross(after[:,1]-after[:,0],after[:,2]-after[:,0])
            if np.any(np.linalg.norm(b,axis=1)<1e-10) or np.any(np.sum(a*b,axis=1)<.15*np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)):continue
            faces[faces==remove]=keep;valid=np.array([len(set(t))==3 for t in faces]);faces=faces[valid];materials=materials[valid]
            quadrics[keep]+=quadrics[remove];accepted=True;break
        if not accepted:break
    used=np.unique(faces);mapping={v:i for i,v in enumerate(used)}
    return points[used],np.array([[mapping[v] for v in f] for f in faces]),materials,dict(requested_half_triangles=target,actual_half_triangles=len(faces),retained_half_vertices=len(used),protected_extrema=len(locked),construction='compatible endpoint quadric collapse of original source half')


def close_visor_rim(points,faces,materials,shell):
    # The retail visor overlaps the shell's brow rather than sharing its rim.
    # Seal their reduced narrow return using existing contour vertices. This
    # adds no geometric points and leaves both visible source surfaces intact.
    edges=defaultdict(list)
    for f in faces:
        for a,b in zip(f,np.roll(f,-1)):edges[tuple(sorted((a,b)))].append((int(a),int(b)))
    reverse={b:a for edge,values in edges.items() if len(values)==1 and not all(abs(points[v,1])<1e-8 for v in edge) for a,b in values}
    if not reverse:return faces,materials,0
    starts=set(reverse)-set(reverse.values());assert len(starts)==1,('Unexpected source rim topology',starts)
    path=[starts.pop()]
    while path[-1] in reverse:path.append(reverse[path[-1]])
    assert len(path)==len(reverse)+1 and abs(points[path[0],1])<1e-8 and abs(points[path[-1],1])<1e-8
    returns=[[path[0],path[i],path[i+1]] for i in range(1,len(path)-1)]
    return np.vstack((faces,returns)),np.r_[materials,[shell]*len(returns)],len(returns)


def build_head(model,lod):
    bone=next(i for i,n in enumerate(model['nodes']) if n['name']=='bip01 head')
    source=[fi for fi,r in enumerate(model['regions']) if r=='helmet' and all(max(model['skin_weights'][v],key=lambda w:w[1])[0]==bone for v in model['faces'][fi])]
    p=np.array([model['vertices'][v] for fi in source for v in model['faces'][fi]]);center=float((p[:,1].min()+p[:,1].max())/2)
    points,faces,materials=source_half(model,source,center)
    stripe=next(i for i,m in enumerate(model['material_metadata']) if m['path'].endswith('odst_crown_stripe'))
    visor=next(i for i,m in enumerate(model['material_metadata']) if m['path'].endswith('odst_visor'))
    points,faces,materials,report=reduce_half(points,faces,materials,(38,24)[lod],stripe,visor,lod)
    shell=next(m for m in set(materials) if m not in (stripe,visor))
    faces,materials,report['visor_return_half_triangles']=close_visor_rim(points,faces,materials,shell)
    # Restore the audited original forehead triangle where its broad source
    # curve is exposed as a gap by the collapsed cap in top/run views.
    patch_start=len(faces)
    for fi in (7620,):
        patch=[]
        for vi in model['faces'][fi]:
            v=np.array(model['vertices'][vi]);v[1]-=center
            distances=np.linalg.norm(points-v,axis=1);i=int(distances.argmin())
            if distances[i]>1e-6:i=len(points);points=np.vstack((points,v))
            patch.append(i)
        faces=np.vstack((faces,patch));materials=np.r_[materials,model['materials'][fi]]
    report['restored_source_forehead_faces']=[7620]
    normals=np.zeros_like(points)
    for f in faces:
        n=np.cross(points[f[1]]-points[f[0]],points[f[2]]-points[f[0]])
        for v in f:normals[v]+=n
    normals/=np.maximum(1e-12,np.linalg.norm(normals,axis=1))[:,None]
    result=[];samples={};errors={}
    for material in sorted(set(materials)):
        selected=[fi for fi in source if model['materials'][fi]==material]
        tree=BVHTree.FromPolygons([Vector(v) for v in model['vertices']],[model['faces'][fi] for fi in selected],all_triangles=True)
        im=bpy.data.images.load(model['textures'][material],check_existing=True);w,h=im.size;pixels=np.array(im.pixels[:]).reshape(h,w,4);error=0
        for i in np.unique(faces[materials==material]):
            p=points[i].copy();p[1]+=center;hit,_,fi,distance=tree.find_nearest(Vector(p));error=max(error,distance);ids=model['faces'][selected[fi]]
            bary=np.maximum(0,interpolate.poly_3d_calc([Vector(model['vertices'][v]) for v in ids],hit));bary/=bary.sum();uv=bary@np.array([model['uv'][v] for v in ids])
            n=normals[i].copy()
            if abs(points[i,1])<1e-8:n[1]=0
            n/=max(1e-12,np.linalg.norm(n));light=.68+.32*max(0,float(np.array([n[0],n[2],abs(n[1])])@(.25,.83,.49)))
            rgb=np.rint((np.array((140,143,146)) if material==stripe else pixels[h-1-int(uv[1]%1*h),int(uv[0]%1*w),:3]*255)*light).astype(int).tolist()
            samples[material,i]=dict(uv=uv.tolist(),source=dict(face=selected[fi],barycentric=bary.tolist()),rgb=rgb)
        errors[str(material)]=float(error)
    for face_index,(f,m) in enumerate(zip(faces,materials)):
        region='stripe' if m==stripe else 'visor' if m==visor else 'shell'
        for sign,order in ((1,f),(-1,f[[0,2,1]])):
            t=dict(p=[(points[i]*[1,sign,1]).tolist() for i in order],uv=[samples[m,i]['uv'] for i in order],weights=[[[bone,1]]]*3,material=int(m),component='helmet-head',helmet_region=region,source_faces=[samples[m,i]['source'] for i in order],source_transform=[[1,0,0,0],[0,sign,0,-sign*center],[0,0,1,0],[0,0,0,1]],corner_color_override=[samples[m,i]['rgb'] for i in order])
            if face_index>=patch_start:t['coverage_repair_source_face']=7620
            result.append(t)
    return result,dict(lod=lod,source_mirror_plane_y=center,output_mirror_plane_y=0,source_triangles=len(source),maximum_retained_point_error_by_material=errors,**report)


def audit_source(folder,output):
    """Measure actual triangle surfaces, separately from retained-point error."""
    import json,hashlib
    from pathlib import Path
    from demake_odst import paint_source
    folder=Path(folder);data=json.loads((folder/'helmet-budget/solid.json').read_text())
    model=paint_source(json.loads((folder/'source/odst-ce-raw.json').read_text())['models']['spartan'])
    bone=next(i for i,n in enumerate(model['nodes']) if n['name']=='bip01 head')
    selected=[fi for fi,r in enumerate(model['regions']) if r=='helmet' and all(max(model['skin_weights'][v],key=lambda w:w[1])[0]==bone for v in model['faces'][fi])]
    p=np.array([model['vertices'][v] for fi in selected for v in model['faces'][fi]]);center=float((p[:,1].min()+p[:,1].max())/2)
    pts,faces,_=source_half(model,selected,center);source=pts[faces]
    def samples(tri):return np.concatenate((tri.reshape(-1,3),tri.mean(1),((tri+np.roll(tri,1,axis=1))/2).reshape(-1,3)))
    def tree(tri):return BVHTree.FromPolygons([Vector(v) for v in tri.reshape(-1,3)],[tuple(range(i*3,i*3+3)) for i in range(len(tri))],all_triangles=True)
    rows=[]
    for lod,l in enumerate(data['lods']):
        helmet=[t for t in l['triangles'][::1] if t['component']=='helmet-head'][::2]
        fitted=np.array([t['p'] for t in helmet]);reduced=fitted-np.array([t['fit_offsets'] for t in helmet])
        row=dict(lod=lod,mesh_sha256=hashlib.sha256((folder/'helmet-budget/solid.json').read_bytes()).hexdigest())
        for name,tri in [('before_overlap',reduced),('fitted',fitted)]:
            a=tree(source);b=tree(tri)
            distances=np.array([b.find_nearest(Vector(v))[3] for v in samples(source)]+[a.find_nearest(Vector(v))[3] for v in samples(tri)])*3.048
            row[name]=dict(sampled_maximum_error_m=float(distances.max()),sampled_p95_error_m=float(np.percentile(distances,95)),samples=len(distances))
        assert row['fitted']['sampled_p95_error_m']<.025
        rows.append(row)
    Path(output).write_text(json.dumps(rows,indent=2)+'\n');print('Source-surface comparison',rows)

if __name__=='__main__':
    import sys
    audit_source(*sys.argv[sys.argv.index('--')+1:])
