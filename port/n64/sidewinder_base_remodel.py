"""Authored west-base interior panel inserts; no collapse or decimation.

Replace four specific lower-room cornice/skirting runs with flat wall, floor
and ceiling panels. Source boundary profiles receive explicit transition caps.
Original floor/ceiling heights, exterior, doorways and collision are retained.
"""
import collections
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import numpy as np
from sidewinder_structures import ROOT,PREVIOUS,sha

OUT=ROOT/'build/n64-sidewinder-base-remodel'
FLOOR=-984;CEILING=-635
PANELS=[
    dict(name='West room, left front trim',side=-1,wall=-8717,inner=-8576,z0=8256,z1=8704),
    dict(name='West room, right front trim',side=1,wall=-7693,inner=-7834,z0=8256,z1=8704),
    dict(name='West room, left rear trim',side=-1,wall=-8717,inner=-8576,z0=10496,z1=11008),
    dict(name='West room, right rear trim',side=1,wall=-7693,inner=-7834,z0=10496,z1=11008),
]


def prepare():
    import sidewinder_structures as base
    base.OUT=OUT;base.prepare()
    (OUT/'design.json').write_text(json.dumps({'scope':__doc__,'floor':FLOOR,'ceiling':CEILING,'panels':PANELS},indent=2)+'\n')


def clip(poly,axis,coordinate,sign):
    if not poly:return []
    result=[]
    for i,a in enumerate(poly):
        b=poly[(i+1)%len(poly)];da=sign*(a[axis]-coordinate);db=sign*(b[axis]-coordinate)
        if da>=-1e-8:result.append(a)
        if (da>1e-8 and db< -1e-8) or (da< -1e-8 and db>1e-8):result.append(a+(b-a)*(da/(da-db)))
    clean=[]
    for p in result:
        if not clean or np.linalg.norm(p[:3]-clean[-1][:3])>1e-7:clean.append(p)
    if len(clean)>1 and np.linalg.norm(clean[0][:3]-clean[-1][:3])<1e-7:clean.pop()
    return clean


def fan(poly):
    for i in range(1,len(poly)-1):
        tri=[poly[0],poly[i],poly[i+1]]
        if np.linalg.norm(np.cross(tri[1][:3]-tri[0][:3],tri[2][:3]-tri[0][:3]))>1e-5:yield tri


def subtract(tri,panel):
    x0,x1=sorted((panel['wall'],panel['inner']));planes=[(0,x0,1),(0,x1,-1),(1,FLOOR,1),(1,CEILING,-1),(2,panel['z0'],1),(2,panel['z1'],-1)]
    points=np.array(tri,dtype=float)
    if any(np.max(sign*(points[:,axis]-coordinate))< -1e-7 for axis,coordinate,sign in planes):return [points],False
    inside=list(points);outside=[]
    for axis,coordinate,sign in planes:
        if all(sign*(v[axis]-coordinate)>=-1e-8 for v in inside):continue
        outside.extend(fan(clip(inside,axis,coordinate,-sign)));inside=clip(inside,axis,coordinate,sign)
        if len(inside)<3:return [points],False
    if not list(fan(inside)):return [points],False
    return outside,True


def section(rows,panel,z):
    x0,x1=sorted((panel['wall'],panel['inner']));segments=set()
    for r in rows:
        p=np.array([v[:3] for v in r['triangle']],dtype=float);points=[]
        for a,b in ((0,1),(1,2),(2,0)):
            da=p[a,2]-z;db=p[b,2]-z
            if abs(da)<1e-8:points.append(p[a])
            if da*db< -1e-8:points.append(p[a]+(p[b]-p[a])*(-da/(db-da)))
        unique={tuple(np.round(p,7)) for p in points}
        if len(unique)!=2:continue
        a,b=map(np.array,unique);t0,t1=0.,1.;d=b-a
        for axis,lo,hi in [(0,x0,x1),(1,FLOOR,CEILING)]:
            if abs(d[axis])<1e-10:
                if a[axis]<lo-1e-7 or a[axis]>hi+1e-7:t0,t1=1,0;break
            else:
                lo_t,hi_t=sorted(((lo-a[axis])/d[axis],(hi-a[axis])/d[axis]));t0=max(t0,lo_t);t1=min(t1,hi_t)
        if t1-t0>1e-8:
            u=tuple(np.round((a+t0*d)[:2],6));v=tuple(np.round((a+t1*d)[:2],6))
            if u!=v:segments.add(tuple(sorted((u,v))))
    adjacent=collections.defaultdict(set)
    for a,b in segments:adjacent[a].add(b);adjacent[b].add(a)
    start=min(adjacent,key=lambda p:np.linalg.norm(np.array(p)-[panel['inner'],FLOOR]));end=min(adjacent,key=lambda p:np.linalg.norm(np.array(p)-[panel['inner'],CEILING]))
    assert np.linalg.norm(np.array(start)-[panel['inner'],FLOOR])<1e-4 and np.linalg.norm(np.array(end)-[panel['inner'],CEILING])<1e-4,(panel['name'],z,'Missing section endpoints')
    queue=[start];parent={start:None}
    for v in queue:
        if v==end:break
        for n in adjacent[v]:
            if n not in parent:parent[n]=v;queue.append(n)
    assert end in parent,(panel['name'],z,'Disconnected profile')
    path=[];v=end
    while v is not None:path.append(v);v=parent[v]
    path.reverse();touch=[i for i,p in enumerate(path) if abs(p[0]-panel['wall'])<1e-4]
    assert touch,(panel['name'],z,'No original wall plane in section')
    polygons=[path[:touch[0]+1]+[(panel['wall'],FLOOR)],path[touch[-1]:]+[(panel['wall'],CEILING)]]
    return [np.array([[x,y,z] for x,y in polygon],dtype=float) for polygon in polygons]


def projector(rows,axis,value,material,panel):
    candidates=[];middle=(panel['z0']+panel['z1'])/2
    for r in rows:
        p=np.array([v[:3] for v in r['triangle']],float)
        if r['material']==material and np.max(abs(p[:,axis]-value))<1e-7:
            area=np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]));distance=abs(p[:,2].mean()-middle)
            candidates.append((distance/max(area,1),r))
    assert candidates,(axis,value,material)
    row=min(candidates,key=lambda item:item[0])[1];axes=[a for a in range(3) if a!=axis];p=np.array(row['triangle'],float)
    matrix=np.column_stack((p[:,axes],np.ones(3)));uv=np.linalg.solve(matrix,p[:,6:8])
    rgb=np.linalg.lstsq(matrix,p[:,3:6],rcond=None)[0]
    def attributes(point):
        q=np.array([*point[axes],1.]);color=np.clip(q@rgb,0,255)
        return [*np.round(point).astype(int).tolist(),*np.round(color).astype(int).tolist(),*np.round(q@uv).astype(int).tolist()]
    return attributes


def remodel():
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    def west_base(row):
        center=np.mean([v[:3] for v in row['triangle']],axis=0)/256
        return center[0]<-24 and center[2]>15
    data=json.loads((OUT/'source.json').read_text());rows=data['triangles'];west=[r for r in rows if r['editable'] and west_base(r)]
    scene=bpy.data.scenes.new('West base - authored planar inserts');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    materials=[];directory=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures'
    for mi in range(17):
        material=bpy.data.materials.new('Authored base '+str(mi));material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear()
        output=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission');texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(directory/f'packed-{mi}.png'),check_existing=True);texture.interpolation='Closest';color=nodes.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        links=material.node_tree.links;links.new(texture.outputs['Color'],mix.inputs[1]);links.new(color.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],emission.inputs['Color']);links.new(emission.outputs[0],output.inputs['Surface']);materials.append(material)
    all_west=[r for r in rows if r['category']=='structures' and west_base(r)];ps=np.array([v[:3] for r in all_west for v in r['triangle']],float)/256;center=(ps.min(0)+ps.max(0))/2
    def object_from_rows(name,records,hidden=False):
        points=[];faces=[]
        for r in records:
            at=len(points)
            for v in r['triangle']:
                p=np.array(v[:3],float)/256-center;points.append((p[0],-p[2],p[1]))
            faces.append((at,at+1,at+2))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces)
        for m in materials:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,r in zip(mesh.polygons,records):
            poly.material_index=r['material']
            for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj);obj.hide_render=hidden;obj.hide_set(hidden);return obj
    object_from_rows('Original west base',all_west,True)
    replacements=[];removed=set();notes=[]
    for r in west:
        pieces=[np.array(r['triangle'],float)];changed=False
        for panel in PANELS:
            next_pieces=[]
            for piece in pieces:
                for triangle in fan(list(piece)):
                    result,touched=subtract(triangle,panel);next_pieces.extend(result);changed|=touched
            pieces=next_pieces
        if changed:
            removed.add((r['batch'],r['face']))
            for tri in pieces:replacements.append({'material':r['material'],'triangle':np.round(tri).astype(int).tolist(),'old_batch':r['batch'],'mask':r['mask'],'kind':'Source clipped at authored panel boundary'})
    for panel in PANELS:
        wall=panel['wall'];inner=panel['inner'];z0,z1=panel['z0'],panel['z1'];side=panel['side'];count=0
        wall_uv=projector(west,0,wall,1,panel);floor_uv=projector(west,1,FLOOR,4,panel);ceil_uv=projector(west,1,CEILING,1,panel)
        def add_polygon(name,points,material,normal,attributes):
            nonlocal count
            vectors=[Vector(p) for p in points]
            for tri in tessellate_polygon([vectors]):
                p=np.array([list(vectors[i]) for i in tri],float) if isinstance(tri[0],int) else np.array([list(v) for v in tri],float)
                if np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))<1e-5:continue
                if np.cross(p[1]-p[0],p[2]-p[0])@np.array(normal)<0:p=p[[0,2,1]]
                replacements.append({'material':material,'triangle':[attributes(q) for q in p],'mask':(1<<35)-1,'kind':name,'panel':panel['name']});count+=1
        add_polygon('Flat wall panel',[(wall,FLOOR,z0),(wall,FLOOR,z1),(wall,CEILING,z1),(wall,CEILING,z0)],1,(side,0,0),wall_uv)
        add_polygon('Floor continuation',[(wall,FLOOR,z0),(inner,FLOOR,z0),(inner,FLOOR,z1),(wall,FLOOR,z1)],4,(0,-1,0),floor_uv)
        add_polygon('Ceiling continuation',[(wall,CEILING,z0),(wall,CEILING,z1),(inner,CEILING,z1),(inner,CEILING,z0)],1,(0,1,0),ceil_uv)
        for z,normal in [(z0,(0,0,-1)),(z1,(0,0,1))]:
            polygons=section(west,panel,z)
            def cap_attributes(point):
                q=point.copy();q[0]=wall;color=wall_uv(q)[3:6]
                return [*np.round(point).astype(int).tolist(),*color,round((point[0]-wall)*2),round((point[1]-FLOOR)*2)]
            for polygon in polygons:add_polygon('Explicit trim transition cap',polygon,1,normal,cap_attributes)
        notes.append({'name':panel['name'],'new_faces':count,'wall_plane':wall/256,'floor_height':FLOOR/256,'ceiling_height':CEILING/256,'z_range':[z0/256,z1/256]})
    retained=[r for r in all_west if (r['batch'],r['face']) not in removed];new=retained+replacements
    object_from_rows('Authored west base',new)
    result={'source_sha256':sha((OUT/'source.json').read_bytes()),'source_bank_sha256':data['bank_sha256'],'method':__doc__,'removed_source_refs':sorted(removed),'replacement_triangles':replacements,'panels':notes,'before_base_triangles':len(all_west),'after_base_triangles':len(new),'coordinate_center':center.tolist()}
    (OUT/'candidate.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    for obj in scene.objects:obj.select_set(not obj.hide_get())
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'west-base-appraisal.blend'))
    print(json.dumps({'before':len(all_west),'after':len(new),'removed_faces':len(removed),'replacement_faces':len(replacements),'panels':notes}))


PLANES=[('Lower room floor',1,-984,4),('Lower room ceiling',1,-635,1),('Upper deck floor',1,143,1),('Upper room ceiling',1,491,1),('Left inner walls',0,-8717,1),('Right inner walls',0,-7693,1),('Left exterior panels',0,-8922,1),('Right exterior panels',0,-7489,1),('Rear wall panels',2,10073,1),('Front interior panels',2,9049,1)]


def planar_remodel():
    """Rebuild explicitly selected planes from their original boundary loops."""
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    def west_base(r):
        p=np.mean([v[:3] for v in r['triangle']],axis=0)/256
        return r['category']=='structures' and p[0]<-24 and p[2]>15
    source=json.loads((OUT/'source.json').read_text());west=[r for r in source['triangles'] if west_base(r)]
    replacements=[];removed=set();notes=[]
    for name,axis,value,material in PLANES:
        for orientation in (-1,1):
            rows=[]
            for r in west:
                p=np.array([v[:3] for v in r['triangle']],float)
                if r['editable'] and r['material']==material and np.max(abs(p[:,axis]-value))<1e-8 and np.cross(p[1]-p[0],p[2]-p[0])[axis]*orientation>0:rows.append(r)
            if not rows:continue
            lookup={};positions=[];faces=[]
            for r in rows:
                face=[]
                for v in r['triangle']:
                    p=tuple(v[:3])
                    if p not in lookup:lookup[p]=len(positions);positions.append(p)
                    face.append(lookup[p])
                faces.append(face)
            mesh=bpy.data.meshes.new(name+' boundary source');mesh.from_pydata(positions,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh)
            # This operation stays on one exact authored plane. It can remove
            # collinear rim vertices but cannot move a wall, bevel or opening.
            bmesh.ops.dissolve_limit(bm,angle_limit=1e-7,use_dissolve_boundaries=False,verts=list(bm.verts),edges=list(bm.edges),delimit=set())
            collinear=[]
            for v in bm.verts:
                edges=[e for e in v.link_edges if e.is_boundary]
                if len(v.link_edges)!=2 or len(edges)!=2:continue
                a=edges[0].other_vert(v).co-v.co;b=edges[1].other_vert(v).co-v.co
                if a.cross(b).length<1e-6 and a.dot(b)<0:collinear.append(v)
            if collinear:bmesh.ops.dissolve_verts(bm,verts=collinear,use_face_split=False,use_boundary_tear=False)
            bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
            result=bpy.data.meshes.new(name+' rebuilt');bm.to_mesh(result);bm.free();result.calc_loop_triangles()
            if len(result.loop_triangles)>=len(rows):
                bpy.data.meshes.remove(mesh);bpy.data.meshes.remove(result);continue
            axes=[a for a in range(3) if a!=axis]
            # Use a coherent planar projector, with original texture density.
            reference=max(rows,key=lambda r:np.linalg.norm(np.cross(np.array(r['triangle'][1][:3])-r['triangle'][0][:3],np.array(r['triangle'][2][:3])-r['triangle'][0][:3])))
            p=np.array(reference['triangle'],float);uvmap=np.linalg.solve(np.column_stack((p[:,axes],np.ones(3))),p[:,6:8])
            original_bvh=BVHTree.FromPolygons([Vector(p) for p in positions],faces,all_triangles=True)
            corner_colors=collections.defaultdict(list)
            for r in rows:
                for v in r['triangle']:corner_colors[tuple(v[:3])].append(v[3:6])
            mask=0
            for r in rows:mask|=r['mask']
            emitted=[]
            for t in result.loop_triangles:
                tri=[]
                for vi in t.vertices:
                    point=np.round(result.vertices[vi].co).astype(int);assert point[axis]==value
                    rgb=np.mean(corner_colors[tuple(point)],axis=0)
                    uv=np.array([*point[axes],1.])@uvmap
                    tri.append([*point.tolist(),*np.clip(np.round(rgb),0,255).astype(int).tolist(),*np.round(uv).astype(int).tolist()])
                emitted.append({'material':material,'triangle':tri,'mask':mask,'kind':name})
            # The source signed area is an exact coverage check for these
            # planar boundary reconstructions, including their openings.
            area=lambda tris:sum(np.cross(np.array(t[1][:3],float)-t[0][:3],np.array(t[2][:3],float)-t[0][:3])[axis] for t in tris)
            before_area=area([r['triangle'] for r in rows]);after_area=area([r['triangle'] for r in emitted]);assert abs(before_area-after_area)<.01,(name,before_area,after_area)
            for r in rows:removed.add((r['batch'],r['face']))
            replacements.extend(emitted);notes.append({'name':name,'axis':axis,'coordinate':value,'orientation':orientation,'source_triangles':len(rows),'after_triangles':len(emitted),'signed_double_area_before':before_area,'signed_double_area_after':after_area,'source_refs':[[r['batch'],r['face']] for r in rows]})
            bpy.data.meshes.remove(mesh);bpy.data.meshes.remove(result)
    result={'source_sha256':sha((OUT/'source.json').read_bytes()),'source_bank_sha256':source['bank_sha256'],'method':'Explicit west-base plane reconstruction: remove coplanar subdivisions and collinear rim points. Fixed source planes and boundary loops; coherent projected UVs and source corner lighting. No decimation or vertex movement.','removed_source_refs':sorted(removed),'replacement_triangles':replacements,'panels':notes,'before_base_triangles':len(west),'after_base_triangles':len(west)-len(removed)+len(replacements)}
    (OUT/'candidate.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    # A centered inspection scene avoids the previous whole-map framing.
    scene=bpy.data.scenes.new('West base - reconstructed source planes');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    texture_dir=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures';materials=[]
    for mi in range(17):
        m=bpy.data.materials.new('West base plane '+str(mi));m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission');tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(texture_dir/f'packed-{mi}.png'),check_existing=True);tex.interpolation='Closest';color=n.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;l=m.node_tree.links;l.new(tex.outputs['Color'],mix.inputs[1]);l.new(color.outputs['Color'],mix.inputs[2]);l.new(mix.outputs[0],em.inputs['Color']);l.new(em.outputs[0],out.inputs['Surface']);materials.append(m)
    points=np.array([v[:3] for r in west for v in r['triangle']],float)/256;center=(points.min(0)+points.max(0))/2
    for label,rows,hidden in [('Original west base',west,True),('Rebuilt west base',[r for r in west if (r['batch'],r['face']) not in removed]+replacements,False)]:
        ps=[];fs=[]
        for r in rows:
            at=len(ps)
            for v in r['triangle']:
                p=np.array(v[:3],float)/256-center;ps.append((p[0],-p[2],p[1]))
            fs.append((at,at+1,at+2))
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(ps,[],fs)
        for m in materials:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for p,r in zip(mesh.polygons,rows):
            p.material_index=r['material']
            for li,v in zip(p.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(label,mesh);scene.collection.objects.link(obj);obj.hide_render=hidden;obj.hide_set(hidden);obj.select_set(not hidden)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'west-base-appraisal.blend'))
    print(json.dumps({'before':result['before_base_triangles'],'after':result['after_base_triangles'],'rebuilt_planes':notes}))


if __name__=='__main__':prepare()
