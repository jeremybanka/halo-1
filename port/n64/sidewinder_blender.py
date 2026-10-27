"""Blender MCP review scene and targeted terrain-only reduction experiment.

All output is private build data. Collision and nonterrain render triangles are
not rewritten. Run import_scene first, inspect the native photos, then reduce.
"""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-photography'
SOURCE=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/bsp-source.json'

def import_scene():
    import bpy
    data=json.loads(SOURCE.read_text())
    scene=bpy.data.scenes.new('Sidewinder - terrain appraisal')
    bpy.context.window.scene=scene
    materials=[]
    for i,name in enumerate(data['materials']):
        mat=bpy.data.materials.new('Sidewinder '+name.split('\\')[-1]);mat.use_nodes=True
        shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        texture=mat.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image=bpy.data.images.load(str(SOURCE.parent/f'packed-{i}.png'),check_existing=True)
        colors=mat.node_tree.nodes.new('ShaderNodeVertexColor');colors.layer_name='Source lightmap'
        mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        mat.node_tree.links.new(texture.outputs['Color'],mix.inputs[1]);mat.node_tree.links.new(colors.outputs['Color'],mix.inputs[2])
        mat.node_tree.links.new(mix.outputs[0],shader.inputs['Base Color']);materials.append(mat)
    objects=[]
    for selected,label in [([7],'Cliffs'),([8],'Snow ground'),([9],'Ice'),([i for i in range(len(materials)) if i not in (7,8,9)],'Preserved architecture')]:
        triangles=[(key[0],t) for key,tris in data['groups'] if key[0] in selected for t in tris]
        points=[];lookup={};faces=[]
        for mi,t in triangles:
            f=[]
            for v in t:
                p=(v[0]/256,-v[2]/256,v[1]/256)
                if p not in lookup:lookup[p]=len(points);points.append(p)
                f.append(lookup[p])
            faces.append(f)
        mesh=bpy.data.meshes.new('Source '+label);mesh.from_pydata(points,[],faces)
        for mat in materials:mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,(mi,t) in zip(mesh.polygons,triangles):
            poly.material_index=mi;period=2048 if mi==8 else 1024
            for loop,v in zip(poly.loop_indices,t):
                uv.data[loop].uv=(v[6]/period,1-v[7]/period)
                color.data[loop].color=tuple(x/255 for x in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new('Sidewinder '+label,mesh);scene.collection.objects.link(obj)
        obj['source_triangles']=len(triangles);obj['material_ids']=selected;objects.append(obj)
    scene.view_settings.view_transform='Standard'
    scene.view_layers[0].objects.active=objects[0]
    for obj in objects:obj.select_set(True)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_all(center=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'sidewinder-appraisal.blend'))
    print(json.dumps({obj.name:{'vertices':len(obj.data.vertices),'triangles':len(obj.data.polygons)} for obj in objects}))

def reduce_terrain(aggressive=False):
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    data=json.loads(SOURCE.read_text());groups=[];report=[]
    bins=json.loads((ROOT/'halo64-assets/generated/maps/maps-report.json').read_text())['maps']['sidewinder']['bins']
    for name,mi,limit in [('Sidewinder Cliffs',7,.75 if aggressive else .15),('Sidewinder Snow ground',8,.06 if aggressive else .03)]:
        obj=bpy.data.objects[name];mesh=obj.data
        bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        boundary={v.index for e in bm.edges if e.is_boundary for v in e.verts};bm.free()
        if aggressive and mi==7:
            # Source winding varies; protect both orientations of flatter rock.
            boundary.update(i for p in mesh.polygons if abs(p.normal.z)>.65 for i in p.vertices)
        pinned={tuple(round(v*256) for v in mesh.vertices[i].co) for i in boundary}
        group=obj.vertex_groups.new(name='Pinned joins - interior only')
        group.add([v.index for v in mesh.vertices if v.index not in boundary],1,'REPLACE')
        modifier=obj.modifiers.new('Targeted terrain appraisal','DECIMATE')
        modifier.decimate_type='COLLAPSE';modifier.vertex_group=group.name
        modifier.vertex_group_factor=1000;modifier.use_collapse_triangulate=True
        original_points=[v.co.copy() for v in mesh.vertices];original_faces=[list(p.vertices) for p in mesh.polygons]
        original_bvh=BVHTree.FromPolygons(original_points,original_faces,all_triangles=True)
        def samples(points,faces):
            for face in faces:
                a,b,c=[points[i] for i in face]
                yield a;yield b;yield c;yield (a+b)*.5;yield (b+c)*.5;yield (c+a)*.5;yield (a+b+c)/3
        attempts=[]
        types=[i.identifier for i in modifier.bl_rna.properties['decimate_type'].enum_items]
        trials=([('COLLAPSE',r) for r in (.5,.6,.65,.675,.7,.725,.75,.775,.8,.825,.85,.875,.9,.92,.97,1.)] if aggressive else
                [('DISSOLVE',a) for a in (.04,.02,.01,.005)]+[('COLLAPSE',r) for r in (.65,.75,.85,.92,.97,1.)])
        for kind,setting in trials:
            modifier.decimate_type=next(t for t in types if t==kind)
            if kind=='DISSOLVE':modifier.angle_limit=setting;modifier.use_dissolve_boundaries=False
            else:modifier.ratio=setting
            bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();graph.update()
            evaluated=obj.evaluated_get(graph);result=evaluated.to_mesh();result.calc_loop_triangles()
            points=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in result.vertices]
            faces=[list(t.vertices) for t in result.loop_triangles]
            retained={tuple(round(x*256) for x in p) for p in points}
            missing=len(pinned-retained)
            target_bvh=BVHTree.FromPolygons(points,faces,all_triangles=True)
            error=max([original_bvh.find_nearest(p)[3] for p in samples(points,faces)]+
                      [target_bvh.find_nearest(p)[3] for p in samples(original_points,original_faces)])
            attempts.append({'method':kind,'setting':setting,'triangles':len(faces),'missing_pins':missing,'sampled_max_surface_error':error})
            if not missing and error<=limit+1e-5:
                uv=result.uv_layers.active;color=result.color_attributes['Source lightmap'];period=2048 if mi==8 else 1024
                for t in result.loop_triangles:
                    tri=[]
                    for vi,li in zip(t.vertices,t.loops):
                        x,y,z=points[vi];u,v=uv.data[li].uv;rgb=color.data[li].color[:3]
                        tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in rgb],round(u*period),round((1-v)*period)])
                    center=[sum(points[i][a] for i in t.vertices)/3 for a in range(3)]
                    key=[mi,*[math.floor(center[a]/bins[a]) for a in range(3)]]
                    groups.append((key,tri))
                report.append({'material':mi,'name':name,'source_triangles':len(mesh.polygons),'candidate_triangles':len(faces),
                               'pinned_vertices':len(pinned),'surface_error_limit':limit,'attempts':attempts})
                evaluated.to_mesh_clear();break
            evaluated.to_mesh_clear()
        else:raise RuntimeError('No conservative candidate for '+name)
    result={'source_sha256':data['source_sha256'],'groups':groups,'report':report,
            'scope':'Only cliff/snow interiors. Original collision, ice, architecture, scenery and textures retained.'}
    (OUT/'terrain-candidate.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'sidewinder-appraisal.blend'))
    print(json.dumps(report))
