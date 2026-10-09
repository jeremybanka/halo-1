"""Small Blender-authored closures for open low-poly attachment surfaces.

Never blanket-fill model boundaries: cockpits, muzzles and decorative sheets
are intentionally open. These selectors name reviewed anatomy/hull regions.
Caps reuse boundary vertices, UVs and weights, including every baked pose.
"""
from collections import Counter, defaultdict
from copy import deepcopy


def closure_region(name, points):
    lo=[min(p[a] for p in points) for a in range(3)]
    hi=[max(p[a] for p in points) for a in range(3)]
    if name=='spartan':
        # Authored segmented armor has open neck, waist, wrists and ankles.
        # Close the cut faces without bridging independently moving segments.
        if .59 < lo[2] <= hi[2] < .60:return 'neck'
        if .42 < lo[2] <= hi[2] < .45:return 'waist'
        if .05 < lo[2] <= hi[2] < .071:return 'ankle'
        if .34 < lo[2] <= hi[2] < .37 and (lo[1]>.12 or hi[1]<-.12):return 'wrist'
    if name=='scorpion':
        if hi[1]-lo[1]<1e-5 and .43<abs(lo[1])<1.19 and hi[2]<.36:return 'track side'
        if hi[2]-lo[2]<1e-5 and .73<lo[2]<.74 and hi[0]<-.3:return 'rear deck'
    if name=='plasma_pistol':
        if .035<lo[2] <= hi[2]<.036 and .03<lo[0]<hi[0]<.065:return 'upper attachment'
        if .048<lo[0]<hi[0]<.074 and -.017<lo[2]<hi[2]<-.009:return 'lower attachment'
    if name=='pistol':
        if -.037<lo[2]<hi[2]<-.034:return 'grip base'
    return None


def close_model(model, name, clips=None):
    """Use BMesh to cap only reviewed simple loops; return report and mesh."""
    import bpy, bmesh
    triangles=model['triangles']; original_count=len(triangles)
    mesh=bpy.data.meshes.new(name+' occlusion repair')
    mesh.from_pydata([p for t in triangles for p in t['p']],[],
                     [[3*i+j for j in range(3)] for i in range(len(triangles))])
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bm.faces.ensure_lookup_table()
    # Original corners are retained separately: BMesh welding must not erase
    # UV seams or assign animation weights from a neighboring moving piece.
    corners=defaultdict(list)
    for i,t in enumerate(triangles):
        for j,p in enumerate(t['p']):corners[tuple(round(x,6) for x in p)].append((i,j))
    edges={e for e in bm.edges if e.is_boundary}; report=[]; new_faces=[]
    while edges:
        seed=min(edges,key=lambda e:tuple(sorted(tuple(v.co) for v in e.verts)))
        edges.remove(seed);pending=[seed];loop=[]
        while pending:
            edge=pending.pop();loop.append(edge)
            for v in edge.verts:
                for other in v.link_edges:
                    if other in edges:edges.remove(other);pending.append(other)
        vertices={v for e in loop for v in e.verts}
        if not all(sum(e in loop for e in v.link_edges)==2 for v in vertices):continue
        region=closure_region(name,[v.co for v in vertices])
        if region is None:continue
        adjacent=[e.link_faces[0] for e in loop]
        material=Counter(triangles[f.index]['material'] for f in adjacent).most_common(1)[0][0]
        # holes_fill follows the existing directed rim; triangulate adds no
        # positions, so silhouettes and exact baked vertex trajectories stay.
        faces=bmesh.ops.holes_fill(bm,edges=loop,sides=0)['faces']
        faces=bmesh.ops.triangulate(bm,faces=faces)['faces']
        for f in faces:new_faces.append((f,material))
        if faces:report.append({'region':region,'rim_vertices':len(vertices),'triangles':len(faces)})
    append_corners=[]
    for face,material in new_faces:
        ids=[]
        for vertex in face.verts:
            key=tuple(round(x,6) for x in vertex.co)
            choices=corners[key]
            i,j=min(choices,key=lambda ij:(triangles[ij[0]]['material']!=material,ij))
            ids.append((i,j))
        t=deepcopy(triangles[ids[0][0]])
        for field in ('p','uv','weights'):t[field]=[deepcopy(triangles[i][field][j]) for i,j in ids]
        t['material']=material;t['occlusion_closure']=True
        triangles.append(t);append_corners.extend(3*i+j for i,j in ids)
    if clips:
        for clip in clips.values():
            for frame in clip['frames']:frame.extend(deepcopy(frame[i]) for i in append_corners)
    bm.free();bpy.data.meshes.remove(mesh)
    mesh=bpy.data.meshes.new(name+' closed review')
    # Match the exported triangle order for a inspectable Blender object.
    mesh.from_pydata([p for t in triangles for p in t['p']],[],
                                         [[3*i+j for j in range(3)] for i in range(len(triangles))])
    mesh.update()
    return {'before':original_count,'after':len(triangles),'closures':report},mesh


def apply_closures(data, scene):
    """Run after skinning so appended corners copy all original animation frames."""
    import bpy
    report={}
    for name in ('spartan','scorpion','pistol','plasma_pistol'):
        model=data['models'][name]
        info,mesh=close_model(model,name,data['animations'] if name=='spartan' else None)
        report[name]=info
        obj=bpy.data.objects.new(name+' closed surfaces',mesh);scene.collection.objects.link(obj)
        obj.location=(list(report).index(name)*4,-7,0)
    # Far Spartan uses its own topology and all matching animation frames.
    info,mesh=close_model(data['spartan_lod'],'spartan',data['animations_lod'])
    report['spartan_lod']=info
    obj=bpy.data.objects.new('spartan far closed surfaces',mesh);scene.collection.objects.link(obj);obj.location=(0,-9,0)
    data['occlusion_closures']=report
    return report
