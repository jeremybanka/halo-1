"""Blender MCP experiment: reduce only within exact source-cluster memberships."""
import collections
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-cluster-terrain'

def prototype():
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import sidewinder_blender as base
    base.OUT=OUT;base.import_scene()
    scene=bpy.context.scene;scene.name='Sidewinder - cluster-aware terrain appraisal'
    source=json.loads((OUT/'data/cluster-source.json').read_text())
    partitions=collections.defaultdict(list)
    for r in source['triangles']:partitions[r['material'],r['mask']].append(r)
    reference=next(o for o in scene.objects if list(o.get('material_ids',[]))==[7])
    materials=list(reference.data.materials)
    for o in scene.objects:
        if list(o.get('material_ids',[])) in ([7],[8]):o.hide_set(True);o.hide_render=True
    bins=json.loads((ROOT/'halo64-assets/generated/maps/maps-report.json').read_text())['maps']['sidewinder']['bins']
    output=[];reports=[];flat_source=set();flat_result=set();pins_by_material=collections.defaultdict(set)
    for (mi,mask),records in sorted(partitions.items()):
        points=[];lookup={};faces=[]
        for r in records:
            face=[]
            for v in r['triangle']:
                p=(v[0]/256,-v[2]/256,v[1]/256)
                if p not in lookup:lookup[p]=len(points);points.append(p)
                face.append(lookup[p])
            faces.append(face)
        mesh=bpy.data.meshes.new(f'Cluster source {mi}/{mask:x}');mesh.from_pydata(points,[],faces)
        for m in materials:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        period=2048 if mi==8 else 1024
        for poly,r in zip(mesh.polygons,records):
            poly.material_index=mi
            for li,v in zip(poly.loop_indices,r['triangle']):
                uv.data[li].uv=(v[6]/period,1-v[7]/period)
                color.data[li].color=tuple(x/255 for x in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(f'Cluster terrain {mi}/{mask:x}',mesh);scene.collection.objects.link(obj)
        obj['cluster_mask_hex']=hex(mask);obj['source_surface_ids']=sorted({i for r in records for i in r['source_ids']})
        bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        boundary={v.index for e in bm.edges if len(e.link_faces)!=2 for v in e.verts};bm.free()
        def face_key(ps):return tuple(sorted(tuple(round(x*256) for x in p) for p in ps))
        flat=[p for p in mesh.polygons if mi==7 and p.normal.z*p.normal.z>=.38]
        boundary.update(i for p in flat for i in p.vertices)
        flat_source.update(face_key([mesh.vertices[i].co for i in p.vertices]) for p in flat)
        pinned={tuple(round(x*256) for x in mesh.vertices[i].co) for i in boundary};pins_by_material[mi].update(pinned)
        group=obj.vertex_groups.new(name='Pinned paths and cluster seams')
        interior=[v.index for v in mesh.vertices if v.index not in boundary]
        if interior:group.add(interior,1,'REPLACE')
        modifier=obj.modifiers.new('Cluster-local terrain reduction','DECIMATE');modifier.decimate_type='COLLAPSE'
        modifier.vertex_group=group.name;modifier.vertex_group_factor=1000;modifier.use_collapse_triangulate=True
        original=[v.co.copy() for v in mesh.vertices];original_faces=[list(p.vertices) for p in mesh.polygons]
        original_bvh=BVHTree.FromPolygons(original,original_faces,all_triangles=True)
        def samples(ps,fs):
            for face in fs:
                a,b,c=[ps[i] for i in face]
                yield a;yield b;yield c;yield (a+b)*.5;yield (b+c)*.5;yield (c+a)*.5;yield (a+b+c)/3
        attempts=[];limit=.75 if mi==7 else .06
        for ratio in ((.5,.6,.65,.675,.7,.725,.75,.775,.8,.825,.85,.875,.9,.92,.97,1.) if interior else (1.,)):
            modifier.ratio=ratio;bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();graph.update()
            evaluated=obj.evaluated_get(graph);result=evaluated.to_mesh();result.calc_loop_triangles()
            ps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in result.vertices];fs=[list(t.vertices) for t in result.loop_triangles]
            missing=len(pinned-{tuple(round(x*256) for x in p) for p in ps});target=BVHTree.FromPolygons(ps,fs,all_triangles=True)
            error=max([original_bvh.find_nearest(p)[3] for p in samples(ps,fs)]+[target.find_nearest(p)[3] for p in samples(original,original_faces)])
            attempts.append(dict(setting=ratio,triangles=len(fs),missing_pins=missing,sampled_max_surface_error=error))
            if missing or error>limit+1e-5:evaluated.to_mesh_clear();continue
            uv=result.uv_layers.active;color=result.color_attributes['Source lightmap']
            for t in result.loop_triangles:
                tri=[]
                for vi,li in zip(t.vertices,t.loops):
                    x,y,z=ps[vi];u,v=uv.data[li].uv;rgb=color.data[li].color[:3]
                    tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in rgb],round(u*period),round((1-v)*period)])
                center=[sum(ps[i][a] for i in t.vertices)/3 for a in range(3)]
                output.append(([mi,*[math.floor(center[a]/bins[a]) for a in range(3)],mask],tri))
                flat_result.add(face_key([ps[i] for i in t.vertices]))
            reports.append(dict(material=mi,cluster_mask=mask,source_ids=list(obj['source_surface_ids']),source_triangles=len(records),candidate_triangles=len(fs),
                                pinned_vertices=len(pinned),surface_error_limit=limit,attempts=attempts))
            evaluated.to_mesh_clear();break
        else:raise RuntimeError('No path/seam preserving candidate for '+obj.name)
    assert flat_source<=flat_result,'Walking surfaces on flatter rock changed'
    aggregated=[]
    for mi,name in [(7,'Cluster-aware cliffs'),(8,'Cluster-aware snow ground')]:
        rs=[r for r in reports if r['material']==mi]
        aggregated.append(dict(material=mi,name=name,source_triangles=sum(r['source_triangles'] for r in rs),candidate_triangles=sum(r['candidate_triangles'] for r in rs),
                               pinned_vertices=len(pins_by_material[mi]),surface_error_limit=.75 if mi==7 else .06,
                               attempts=[{'sampled_max_surface_error':max(r['attempts'][-1]['sampled_max_surface_error'] for r in rs),'missing_pins':0}],partitions=len(rs)))
    candidate=dict(source_sha256=source['source_sha256'],cluster_source_sha256=hashlib.sha256((OUT/'data/cluster-source.json').read_bytes()).hexdigest(),groups=output,
                   report=aggregated,partitions=reports,scope='Source-cluster-local cliff/snow reduction; cluster seams and flatter rock pinned; original collision/nonterrain retained.')
    (OUT/'terrain-candidate.json').write_text(json.dumps(candidate,separators=(',',':'))+'\n')
    (OUT/'path-protection.json').write_text(json.dumps({'walkable_cliff_faces_preserved':len(flat_source),'all_partition_pins_preserved':True,'cluster_partitions':len(reports),'collision':'Original non-render bank sections retained byte-for-byte'},indent=2)+'\n')
    scene.view_settings.view_transform='Standard'
    for o in scene.objects:o.select_set(not o.hide_get())
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'sidewinder-appraisal.blend'))
    print(json.dumps({'report':aggregated,'partitions':len(reports),'walkable_cliff_faces_preserved':len(flat_source)}))
