"""Blender reduction with source material, anatomy and disconnected-feature budgets.

Input/output UVs use image-row (top-left) coordinates. No live scene is assumed.
Each component receives a minimum triangle allocation before the remaining
budget is distributed by area/detail/importance. Skin weights are interpolated
by Blender, or barycentrically resampled when projecting onto the source
surface, rather than reassigned to a nearest original vertex/bone.
"""
import math
from collections import defaultdict


def reduce_geometry(scene, model, name, target, part_importance=None, bone_labels=None,
                    partition_colors=True, protect_boundaries=False, project_surface=True,
                    partition_materials=True):
    """Return scene object, triangles, skinned vertices and allocation report.

    ``part_importance`` returns a weight or ``{'weight': n, 'min': triangles}``.
    ``protect_boundaries`` is a soft influence in [0,1] (True means .75).
    ``project_surface`` True resamples the source surface/UV/skin; 'outside'
    repairs only AABB outliers and retains interpolated UV/skin; False uses the
    collapse result. Set ``partition_materials=False`` to collapse connected
    geometry across shader borders while retaining per-face materials and loop
    UVs. Pair it with common bone labels and ``partition_colors=False`` to
    avoid cracks in continuous skinned surfaces. Mixed-material partitions pass
    material -1 to ``part_importance`` and retain that sentinel in the report.
    """
    import bpy
    from mathutils import Vector,interpolate
    from mathutils.bvhtree import BVHTree
    points=[Vector(p) for p in model['vertices']]
    faces=model['faces'];materials=model['materials'];uvs=model['uv']
    nodes=model.get('nodes',[]);weights=model.get('weights',[[0,-1,0]]*len(points))
    labels=bone_labels or {i:n['name'] for i,n in enumerate(nodes)}
    texture_paths=model.get('textures_fullres',model.get('textures',[]))
    image_cache={}
    def image(path):
        if not path:return None
        if path not in image_cache:
            im=bpy.data.images.load(path,check_existing=True)
            image_cache[path]=(im.size[0],im.size[1],list(im.pixels))
        return image_cache[path]
    def sample(path,u,v):
        im=image(path)
        if im is None:return (.5,.5,.5,1)
        w,h,pixels=im;x=min(w-1,int((u%1)*w));y=min(h-1,int(((1-v)%1)*h))
        at=(y*w+x)*4;return pixels[at:at+4]
    def face_region(fi):
        if not partition_colors:return 'material'
        material=materials[fi];face=faces[fi]
        u=sum(uvs[i][0] for i in face)/3;v=sum(uvs[i][1] for i in face)/3
        rgb=sample(texture_paths[material] if material<len(texture_paths) else None,u,v)[:3]
        masks=model.get('team_masks',[]);channels=model.get('team_mask_channels',[])
        if material<len(masks) and masks[material] and channels[material] is not None:
            mask=sample(masks[material],u,v)[channels[material]]
            return 'team' if mask>.35 else 'fixed'
        maximum=max(rgb);minimum=min(rgb)
        if maximum<.16:return 'dark'
        if maximum-minimum<.12:return 'light' if maximum>.55 else 'neutral'
        r,g,b=rgb
        if r>g*1.3 and r>b*1.3:return 'red'
        if g>r*1.3 and g>b*1.3:return 'green'
        if b>r*1.3 and b>g*1.3:return 'blue'
        if r>g*1.2 and b>g*1.2:return 'violet'
        if r>b*1.3 and g>b*1.2:return 'gold'
        return 'cyan'
    def face_bone(fi):
        influence=defaultdict(float)
        for i in faces[fi]:
            a,b,w=weights[i]
            if a>=0:influence[labels.get(a,str(a))]+=1-w
            if b>=0 and w>0:influence[labels.get(b,str(b))]+=w
        return max(influence,key=influence.get) if influence else 'static'
    # Position welding is only for connectivity and geometry; per-loop UVs
    # retain texture seams. Only explicitly selected partitions stay separate.
    geometric=[tuple(round(v,6) for v in p) for p in points]
    groups=defaultdict(list)
    for fi in range(len(faces)):groups[(materials[fi] if partition_materials else -1,face_bone(fi),face_region(fi))].append(fi)
    vertex_partitions=defaultdict(set)
    for key,indices in groups.items():
        for fi in indices:
            for vi in faces[fi]:vertex_partitions[geometric[vi]].add(key)
    boundary_keys={key for key,parts in vertex_partitions.items() if len(parts)>1}
    components=[]
    for (material,bone,region),indices in groups.items():
        by_vertex=defaultdict(list)
        for fi in indices:
            for i in faces[fi]:by_vertex[geometric[i]].append(fi)
        remaining=set(indices)
        while remaining:
            pending=[min(remaining)];remaining.remove(pending[0]);connected=[]
            while pending:
                fi=pending.pop();connected.append(fi)
                for vi in faces[fi]:
                    for other in by_vertex[geometric[vi]]:
                        if other in remaining:remaining.remove(other);pending.append(other)
            vertices={i for fi in connected for i in faces[fi]}
            area=sum((points[faces[fi][1]]-points[faces[fi][0]]).cross(points[faces[fi][2]]-points[faces[fi][0]]).length*.5 for fi in connected)
            info={'face_count':len(connected),'area':area,'color_region':region,
                  'bounds':[[min(points[i][a] for i in vertices),max(points[i][a] for i in vertices)] for a in range(3)]}
            importance=part_importance(material,bone,info) if part_importance else 1
            minimum=min(len(connected),max(2,min(8,round(math.sqrt(len(connected))))))
            if isinstance(importance,dict):minimum=min(len(connected),importance.get('min',minimum));importance=importance.get('weight',1)
            components.append({'faces':connected,'material':material,'bone':bone,'region':region,'info':info,
                               'minimum':minimum,'target':minimum,'score':max(1e-10,area)**.45*len(connected)**.55*importance})
    target=min(target,len(faces));minimum=sum(c['minimum'] for c in components)
    # If preserving all separately identifiable pieces needs more than the
    # requested budget, retain them and report the explicit budget overrun.
    remaining=max(0,target-minimum)
    while remaining:
        eligible=[c for c in components if c['target']<len(c['faces'])]
        if not eligible:break
        total=sum(c['score'] for c in eligible);allocated=0
        for c in eligible:
            n=min(len(c['faces'])-c['target'],max(0,int(remaining*c['score']/total)))
            c['target']+=n;allocated+=n
        if not allocated:
            max(eligible,key=lambda c:c['score']/(c['target']+1))['target']+=1;allocated=1
        remaining-=allocated
    tris=[];weighted=[];reports=[]
    with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):dep=bpy.context.evaluated_depsgraph_get()
    for ci,c in enumerate(components):
        vert_lookup={};source_indices=[];local_faces=[]
        for fi in c['faces']:
            local=[]
            for source in faces[fi]:
                key=geometric[source]
                if key not in vert_lookup:vert_lookup[key]=len(source_indices);source_indices.append(source)
                local.append(vert_lookup[key])
            local_faces.append(local)
        mesh=bpy.data.meshes.new(name+' part');mesh.from_pydata([points[i] for i in source_indices],[],local_faces)
        if not partition_materials:
            # Shared geometry across material borders keeps armor/rubber seams
            # connected while loop UVs and per-face shader IDs stay distinct.
            for mi in range(max(materials,default=0)+1):
                mesh.materials.append(bpy.data.materials.get('Reduction material '+str(mi)) or bpy.data.materials.new('Reduction material '+str(mi)))
            for poly,fi in zip(mesh.polygons,c['faces']):poly.material_index=materials[fi]
        source_surface=BVHTree.FromPolygons([points[i] for i in source_indices],local_faces,all_triangles=True)
        uv=mesh.uv_layers.new(name='Source diffuse')
        for poly,fi in zip(mesh.polygons,c['faces']):
            for loop,source in zip(poly.loop_indices,faces[fi]):
                u,v=uvs[source];uv.data[loop].uv=(u,1-v)
        obj=bpy.data.objects.new(name+' part',mesh);scene.collection.objects.link(obj)
        for bi in range(max(1,len(nodes))):obj.vertex_groups.new(name='bone'+str(bi))
        for i,source in enumerate(source_indices):
            a,b,w=weights[source]
            if a>=0 and 1-w>0:obj.vertex_groups[a].add([i],1-w,'REPLACE')
            if b>=0 and w>0:obj.vertex_groups[b].add([i],w,'REPLACE')
        boundary=[i for i,source in enumerate(source_indices) if geometric[source] in boundary_keys]
        if len(c['faces'])>max(3,c['target']):
            mod=obj.modifiers.new('Feature budget','DECIMATE');mod.decimate_type='COLLAPSE'
            mod.ratio=c['target']/len(c['faces']);mod.use_collapse_triangulate=True
            if protect_boundaries and boundary:
                group=obj.vertex_groups.new(name='Reduce interiors')
                strength=.75 if protect_boundaries is True else min(1,float(protect_boundaries))
                group.add(list(range(len(source_indices))),1,'REPLACE');group.add(boundary,max(.001,1-strength),'REPLACE')
                mod.vertex_group=group.name;mod.vertex_group_factor=1
        dep.update();ev=obj.evaluated_get(dep);reduced=ev.to_mesh();reduced.calc_loop_triangles();first=len(tris)
        projected=[];projected_skin=[];projected_uv=[]
        for vertex in reduced.vertices:
            needs_projection=(project_surface is True or (project_surface=='outside' and
                any(vertex.co[a]<c['info']['bounds'][a][0]-1e-6 or vertex.co[a]>c['info']['bounds'][a][1]+1e-6
                    for a in range(3))))
            if not needs_projection:
                influence=[(g.group,g.weight) for g in vertex.groups if g.group<len(nodes) and g.weight>1e-6]
                total=sum(w for _,w in influence)
                projected.append(vertex.co.copy());projected_skin.append([(b,w/total) for b,w in influence] if total else [(0,1)])
                projected_uv.append(None);continue
            point,normal,face_index,distance=source_surface.find_nearest(vertex.co)
            if point is None:raise ValueError('Could not project reduced vertex onto source surface')
            if project_surface=='outside':
                # The outlier repair changes position only. A nearby source
                # triangle can lie on another UV island (scope lens vs metal),
                # so replacing UV/skin here would damage a valid material seam.
                influence=[(g.group,g.weight) for g in vertex.groups if g.group<len(nodes) and g.weight>1e-6]
                total=sum(w for _,w in influence)
                projected.append(point);projected_skin.append([(b,w/total) for b,w in influence] if total else [(0,1)])
                projected_uv.append(None);continue
            original=faces[c['faces'][face_index]]
            bary=interpolate.poly_3d_calc([points[i] for i in original],point)
            influence=defaultdict(float)
            for source,factor in zip(original,bary):
                a,b,w=weights[source]
                if a>=0:influence[a]+=factor*(1-w)
                if b>=0 and w>0:influence[b]+=factor*w
            values=[(b,w) for b,w in influence.items() if w>1e-6];total=sum(w for _,w in values)
            if not total:values=[(0,1)];total=1
            projected.append(point);projected_skin.append([(b,w/total) for b,w in values])
            projected_uv.append([sum(uvs[i][axis]*factor for i,factor in zip(original,bary)) for axis in range(2)])
        for tri in reduced.loop_triangles:
            xyz=[list(projected[i]) for i in tri.vertices]
            coords=[projected_uv[vi] if projected_uv[vi] is not None else
                    [reduced.uv_layers.active.data[loop].uv[0],1-reduced.uv_layers.active.data[loop].uv[1]]
                    for vi,loop in zip(tri.vertices,tri.loops)]
            skin=[]
            for vi,p in zip(tri.vertices,xyz):
                values=projected_skin[vi];skin.append(values);weighted.append((Vector(p),values))
            tris.append({'p':xyz,'uv':coords,'material':c['material'] if partition_materials else reduced.polygons[tri.polygon_index].material_index,
                         'weights':skin,'part':ci})
        boundary_displacement=max((min((v-points[source_indices[i]]).length for v in projected)
                                   for i in boundary),default=0)
        reports.append({'material':c['material'],'bone':c['bone'],'color_region':c['region'],
                        'source_triangles':len(c['faces']),'requested_triangles':c['target'],
                        'triangles':len(tris)-first,'boundary_vertices':len(boundary),
                        'max_boundary_displacement':boundary_displacement,**c['info']})
        ev.to_mesh_clear();bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
    # A single reviewable scene object, with all original material assignments.
    mesh=bpy.data.meshes.new(name);mesh.from_pydata([p for t in tris for p in t['p']],[],
                                                  [[i*3,i*3+1,i*3+2] for i in range(len(tris))])
    uv=mesh.uv_layers.new(name='Source diffuse')
    for mi in range(max(materials,default=0)+1):
        mat=bpy.data.materials.new(name+' '+str(mi));mat.use_nodes=True
        if mi<len(texture_paths) and texture_paths[mi]:
            shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(texture_paths[mi],check_existing=True)
            mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
        mesh.materials.append(mat)
    for poly,tri in zip(mesh.polygons,tris):
        poly.material_index=tri['material']
        for loop,(u,v) in zip(poly.loop_indices,tri['uv']):uv.data[loop].uv=(u,1-v)
    obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj)
    report={'source_triangles':len(faces),'requested_triangles':target,'minimum_feature_triangles':minimum,
            'triangles':len(tris),'parts':reports}
    return obj,tris,weighted,report
