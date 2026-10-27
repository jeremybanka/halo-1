"""Private, outline-preserving architecture appraisal through Blender MCP."""
import collections
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
PREVIOUS=ROOT/'build/n64-sidewinder-cluster-terrain'
OUT=ROOT/'build/n64-sidewinder-structures'

def sha(data):return hashlib.sha256(data).hexdigest()

def prepare():
    from investigate_sidewinder_costs import attribution
    from remap_sidewinder_visibility import sections
    bank=(PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes();ss=sections(bank)
    visibility=json.loads((PREVIOUS/'data/visibility.json').read_text())
    assert sha(bank)==visibility['map_sha256']
    rows=[];protected=[];info=attribution()
    proof=json.loads((PREVIOUS/'data/batch-memberships.json').read_text())
    baseline=json.loads((ROOT/'build/n64-visibility-rollout/sidewinder/data/visibility.json').read_text())
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c;at,n=rest[-2:]
        indices=struct.unpack_from('>'+str(n)+'H',ss[2],at*2)
        points=[]
        for i in range(count):
            o=(first+i)//2*32;h=(first+i)%2
            pos=struct.unpack_from('>3h',ss[0],o+h*8)
            rgb=tuple(ss[0][o+16+h*4:o+19+h*4]);uv=struct.unpack_from('>2h',ss[0],o+24+h*4)
            points.append([*pos,*rgb,*uv])
        editable=material<7 and set(info[b]['loads'])=={'structures'}
        if not editable:protected.append(b)
        for t in range(0,n,3):
            category=next(iter(info[b]['loads'])) if len(info[b]['loads'])==1 else ('scenery' if baseline['chunk_source_ids'][proof['batches'][b]['old_chunk']][t//3]<0 else 'structures')
            rows.append(dict(batch=b,face=t//3,material=material,mask=visibility['chunk_masks'][b],category=category,editable=editable,triangle=[points[i] for i in indices[t:t+3]]))
    OUT.mkdir(parents=True,exist_ok=True)
    data=dict(bank_sha256=sha(bank),source='Packed previous candidate; exact vertex color and wrapped UV attributes.',triangles=rows,protected_batches=protected)
    (OUT/'source.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({'editable_triangles':sum(r['editable'] for r in rows),'protected_batches':len(protected),'partitions':len({(r['material'],r['mask']) for r in rows if r['editable']})}))


def prototype(mode='planar'):
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import math
    data=json.loads((OUT/'source.json').read_text());scene=bpy.data.scenes.new('Sidewinder - architecture appraisal')
    bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    source_collection=bpy.data.collections.new('Original architecture');scene.collection.children.link(source_collection)
    candidate_collection=bpy.data.collections.new('Reduced architecture');scene.collection.children.link(candidate_collection)
    materials=[]
    texture_dir=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures'
    for i in range(17):
        m=bpy.data.materials.new('Structure source '+str(i));m.use_nodes=True
        nodes=m.node_tree.nodes;nodes.clear();output=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission')
        texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(texture_dir/f'packed-{i}.png'),check_existing=True);texture.interpolation='Closest'
        color=nodes.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        links=m.node_tree.links;links.new(texture.outputs['Color'],mix.inputs[1]);links.new(color.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],emission.inputs['Color']);links.new(emission.outputs[0],output.inputs['Surface']);materials.append(m)
    groups=collections.defaultdict(list)
    for r in data['triangles']:
        if r['editable']:groups[r['material'],r['mask']].append(r)
    # Validate each connected surface independently, so one lighting seam does
    # not force unrelated parts sharing a material/membership to stay dense.
    components={}
    for (mi,mask),rows in sorted(groups.items()):
        parent=list(range(len(rows)));edges={}
        def root(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for i,r in enumerate(rows):
            xyz=[tuple(v[:3]) for v in r['triangle']]
            for a,b in ((0,1),(1,2),(2,0)):
                edge=tuple(sorted((xyz[a],xyz[b])))
                if edge in edges:parent[root(i)]=root(edges[edge])
                else:edges[edge]=i
        connected=collections.defaultdict(list)
        for i,r in enumerate(rows):connected[root(i)].append(r)
        for component,items in enumerate(connected.values()):components[mi,mask,component]=items
    output=[];reports=[]
    for (mi,mask,component),rows in sorted(components.items()):
        lookup={};points=[];faces=[]
        for r in rows:
            face=[]
            for v in r['triangle']:
                xyz=(v[0]/256,-v[2]/256,v[1]/256)
                if xyz not in lookup:lookup[xyz]=len(points);points.append(xyz)
                face.append(lookup[xyz])
            faces.append(face)
        mesh=bpy.data.meshes.new(f'Architecture {mi}/{mask:x}');mesh.from_pydata(points,[],faces);mesh.materials.append(materials[mi])
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,r in zip(mesh.polygons,rows):
            for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();original=bpy.data.objects.new(f'Original {mi}/{mask:x}',mesh);source_collection.objects.link(original)
        bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        boundary_edges=[(e.verts[0].co.copy(),e.verts[1].co.copy()) for e in bm.edges if len(e.link_faces)!=2]
        pins={tuple(round(v*256) for v in p) for edge in boundary_edges for p in edge}
        original_points=[Vector(p) for p in points];reference=BVHTree.FromPolygons(original_points,faces,all_triangles=True)
        # A small-angle dissolve removes subdivisions, retaining profile edges,
        # UV discontinuities, holes, material boundaries and membership seams.
        if mode=='detail':
            # Diagnostic trial: keep membership/material boundary vertices
            # fixed. Surface and appearance checks reject unsuitable results.
            fixed={v.index for e in bm.edges if len(e.link_faces)!=2 for v in e.verts}
            free=[v.index for v in bm.verts if v.index not in fixed]
            bm.free()
            group=original.vertex_groups.new(name='Detail interiors only')
            if free:group.add(free,1,'REPLACE')
            mod=original.modifiers.new('Shallow architecture detail','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=.85
            mod.vertex_group=group.name;mod.vertex_group_factor=1000;mod.use_collapse_triangulate=True
            if not free:mod.ratio=1.
            bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();graph.update();evaluated=original.evaluated_get(graph)
            evaluated_mesh=evaluated.to_mesh();bm=bmesh.new();bm.from_mesh(evaluated_mesh);evaluated.to_mesh_clear();original.modifiers.remove(mod)
        else:bmesh.ops.dissolve_limit(bm,angle_limit=.08,use_dissolve_boundaries=False,verts=list(bm.verts),edges=list(bm.edges),delimit={'NORMAL','MATERIAL','UV'})
        bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
        new_boundary=[(e.verts[0].co.copy(),e.verts[1].co.copy()) for e in bm.edges if len(e.link_faces)!=2]
        reduced=bpy.data.meshes.new(f'Reduced {mi}/{mask:x}');bm.to_mesh(reduced);bm.free();reduced.update();reduced.calc_loop_triangles()
        candidate=bpy.data.objects.new(f'Reduced {mi}/{mask:x}',reduced);candidate_collection.objects.link(candidate)
        ps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in reduced.vertices];fs=[list(t.vertices) for t in reduced.loop_triangles]
        retained={tuple(round(x*256) for x in v) for v in ps};missing=len(pins-retained)
        target=BVHTree.FromPolygons(ps,fs,all_triangles=True)
        def samples(points,faces):
            for face in faces:
                a,b,c=[points[i] for i in face]
                yield a;yield b;yield c;yield (a+b)/2;yield (b+c)/2;yield (c+a)/2;yield (a+b+c)/3
        error=max([reference.find_nearest(p)[3] for p in samples(ps,fs)]+[target.find_nearest(p)[3] for p in samples(original_points,faces)])
        def line_distance(p,a,b):
            edge=b-a;t=max(0,min(1,(p-a).dot(edge)/max(edge.length_squared,1e-20)))
            return (p-a-t*edge).length
        def boundary_error(a,b):
            if not a:return 0.
            if not b:return float('inf')
            return max(min(line_distance(p,*other) for other in b) for edge in a for p in (*edge,(edge[0]+edge[1])*.5))
        outline_error=max(boundary_error(boundary_edges,new_boundary),boundary_error(new_boundary,boundary_edges))
        # Check interpolation at the original mesh's corners, edge mids and
        # centers. UV error is periodic, measured in 32px texture texels.
        newuv=reduced.uv_layers.active;newcolor=reduced.color_attributes['Source lightmap'];uv_error=0.;color_error=0.
        for t in reduced.loop_triangles:
            xyz=[ps[i] for i in t.vertices];u=[Vector((newuv.data[i].uv[0],newuv.data[i].uv[1],0)) for i in t.loops];rgb=[Vector(newcolor.data[i].color[:3]) for i in t.loops]
            # Stay just inside faces: nearest-face attributes are ambiguous
            # exactly on a seam shared by differently shaded/UV-mapped faces.
            for w in ((.998,.001,.001),(.001,.998,.001),(.001,.001,.998),(.4995,.4995,.001),(.001,.4995,.4995),(.4995,.001,.4995),(1/3,1/3,1/3)):
                q=sum((v*k for v,k in zip(xyz,w)),Vector());near,normal,index,distance=reference.find_nearest(q)
                abc=[original_points[i] for i in faces[index]]
                ab=abc[1]-abc[0];ac=abc[2]-abc[0];aq=near-abc[0];aa=ab.dot(ab);bb=ab.dot(ac);cc=ac.dot(ac);den=aa*cc-bb*bb
                if abs(den)<1e-16:continue
                b=(cc*aq.dot(ab)-bb*aq.dot(ac))/den;c=(aa*aq.dot(ac)-bb*aq.dot(ab))/den;weights=(1-b-c,b,c)
                old=rows[index]['triangle'];old_rgb=sum((Vector(v[3:6])*k for v,k in zip(old,weights)),Vector());new_rgb=sum((v*k*255 for v,k in zip(rgb,w)),Vector())
                color_error=max(color_error,max(abs(a-b) for a,b in zip(old_rgb,new_rgb)))
                old_uv=sum((Vector((v[6]/1024,1-v[7]/1024,0))*k for v,k in zip(old,weights)),Vector());candidate_uv=sum((v*k for v,k in zip(u,w)),Vector())
                uv_error=max(uv_error,max(abs((a-b+.5)%1-.5)*32 for a,b in zip(old_uv[:2],candidate_uv[:2])))
        surface_limit=.025 if mode=='detail' else .05
        accepted=outline_error<=.004 and error<=surface_limit and uv_error<=.5 and color_error<=48 and len(fs)<len(faces)
        report=dict(material=mi,mask=mask,component=component,source_refs=[[r['batch'],r['face']] for r in rows],source_triangles=len(faces),candidate_triangles=len(fs) if accepted else len(faces),attempted_triangles=len(fs),removed_boundary_vertices=missing,sampled_boundary_error=outline_error,sampled_surface_error=error,sampled_color_error=color_error,sampled_uv_error_texels=uv_error,accepted=accepted)
        reports.append(report)
        if accepted:
            for t in reduced.loop_triangles:
                tri=[]
                for vi,li in zip(t.vertices,t.loops):
                    x,y,z=ps[vi];u,v=newuv.data[li].uv;rgb=newcolor.data[li].color[:3]
                    tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in rgb],round(u*1024),round((1-v)*1024)])
                output.append(dict(material=mi,mask=mask,component=component,triangle=tri))
        else:
            candidate.data=mesh.copy();bpy.data.meshes.remove(reduced)
            output.extend({**{k:r[k] for k in ('material','mask','triangle')},'component':component} for r in rows)
    source_collection.hide_render=True;source_collection.hide_viewport=True
    scene['scope']='Planar-only architecture prototype; exact source membership partitions; unchanged collision.'
    result=dict(source_sha256=sha((OUT/'source.json').read_bytes()),bank_sha256=data['bank_sha256'],triangles=output,report=reports,method=mode,surface_limit=.025 if mode=='detail' else .05,boundary_limit=.004,uv_error_limit_texels=.5,color_error_limit=48,scope='Blender geometry prototype; preserve membership/material boundaries; planar dissolve 0.08 rad or boundary-weighted collapse. Symmetric sampled geometry/outline checks plus sampled new-face UV and color checks. Reject failed components. Original walking collision unchanged.')
    (OUT/'candidate.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    for o in scene.objects:o.select_set(True)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_all(center=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'structure-appraisal.blend'))
    print(json.dumps({'source_triangles':sum(r['source_triangles'] for r in reports),'candidate_triangles':sum(r['candidate_triangles'] for r in reports),'accepted_components':sum(r['accepted'] for r in reports),'components':len(reports)}))

if __name__=='__main__':prepare()
