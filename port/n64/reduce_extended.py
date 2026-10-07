"""Blender reduction and offline skinning of original Xbox multiplayer animation.

Run with Blender --background --python THIS -- raw.json reduced.json.
Add --performance-profile after extracting with --include-source-lods for the
measured tactical preset. It regenerates its own quality-reference input.
All outputs are rebuildable local game-derived data.
"""
import json, math
from pathlib import Path


def reduce_extended(source,output,budget_file=None,refine_approved=None):
    import bpy
    from mathutils import Matrix, Quaternion, Vector, kdtree
    data=json.loads(Path(source).read_text());out={'models':{},'vehicle_lods':{},'animations':{},'animations_lod':{},'weapon_attachment':{},'audio':data['audio'],'hud':data['hud'],'sources':data['sources']}
    scene=bpy.data.scenes.new('Halo N64 - Multiplayer assets')
    if bpy.context.window:bpy.context.window.scene=scene
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from geometry_reduce import reduce_geometry
    targets={'spartan':460,'warthog':800,'ghost':560,'scorpion':720,'banshee':600,
             'ar':220,'pistol':180,'plasma_pistol':180,'plasma_rifle':230,
             'needler':240,'shotgun':220,'sniper':240,'rocket':240,
             'frag':64,'plasma_grenade':64,'flamethrower':220,
             'healthpack':44,'overshield':90,'camouflage':90}
    # Optional isolated performance profiles leave the approved default intact.
    budget=json.loads(Path(budget_file).read_text()) if budget_file else {}
    if budget_file:out['reduction_profile']=budget
    approved=json.loads(Path(refine_approved).read_text()) if refine_approved else None
    targets.update(budget.get('targets',{}))
    low_targets={'spartan':160,'warthog':240,'ghost':240,'scorpion':240,'banshee':240}
    low_targets.update(budget.get('lod_targets',{}))
    weighted_by_name={};out['reduction']={}
    metadata=('textures_fullres','multipurpose_fullres','team_masks','team_mask_channels',
              'material_metadata','material_colors','material_overrides','uv_origin','source_lod')
    def derived(model,tris):
        return {'triangles':tris,'textures':model.get('textures_fullres',model['textures']),
                **{key:model[key] for key in metadata if key in model}}
    def update_review_mesh(obj,tris,model,name):
        mesh=obj.data;mesh.clear_geometry()
        mesh.from_pydata([p for t in tris for p in t['p']],[],
                         [[i*3,i*3+1,i*3+2] for i in range(len(tris))])
        texture_paths=model.get('textures_fullres',model['textures'])
        while len(mesh.materials)<=max(t['material'] for t in tris):
            mi=len(mesh.materials);material=bpy.data.materials.new('N64 '+name+' '+str(mi));material.use_nodes=True
            if mi<len(texture_paths) and texture_paths[mi]:
                shader=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
                node=material.node_tree.nodes.new('ShaderNodeTexImage')
                node.image=bpy.data.images.load(texture_paths[mi],check_existing=True)
                material.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
            mesh.materials.append(material)
        uv=mesh.uv_layers.active or mesh.uv_layers.new(name='Source diffuse')
        for poly,t in zip(mesh.polygons,tris):
            poly.material_index=t['material']
            for loop,(u,v) in zip(poly.loop_indices,t['uv']):uv.data[loop].uv=(u,1-v)
    def refinement_source(model,reduced):
        """Refine existing silhouette planes rather than reselecting source detail.

        This option is for rigid world meshes; retaining the strongest two
        influences keeps the original dominant node used for vehicle parts.
        Animated Spartan meshes continue from the original source skeleton.
        """
        vertices=[];uv=[];weights=[];faces=[];materials=[]
        for tri in reduced['triangles']:
            faces.append([len(vertices)+i for i in range(3)]);materials.append(tri['material'])
            for p,tuv,influence in zip(tri['p'],tri['uv'],tri['weights']):
                vertices.append(p);uv.append(tuv)
                selected=sorted(influence,key=lambda x:x[1],reverse=True)[:2]
                total=sum(w for _,w in selected)
                weights.append([selected[0][0],selected[1][0] if len(selected)>1 else -1,
                                selected[1][1]/total if len(selected)>1 else 0])
        return {**model,'vertices':vertices,'uv':uv,'weights':weights,'faces':faces,
                'materials':materials,'source_lod':'refined approved '+reduced.get('source_lod','mesh')}
    for index,(name,model) in enumerate(data['models'].items()):
        original=model
        source_lod=budget.get('source_lods',{}).get(name)
        if source_lod:model={**original,**original['source_geometry_lods'][source_lod]}
        if name in budget.get('refine_models',[]):
            if approved is None:raise ValueError('Profile requires --refine-approved')
            if name=='spartan':raise ValueError('Refine only rigid meshes; Spartan must preserve original skinning')
            model=refinement_source(model,approved['models'][name])
        def importance(material,bone,info):
            label=bone.lower();weight=1.;minimum=2 if info['face_count']<=2 else 4
            shader=model.get('material_metadata',[])
            shader=shader[material]['path'].lower() if material<len(shader) else ''
            if name=='spartan':
                if 'head' in label:weight=3;minimum=6
                elif 'hand' in label:weight=2;minimum=4
                elif 'foot' in label:weight=1.6
                if info['color_region']=='fixed-dark':weight*=1.25
            if name in ('warthog','scorpion') and any(k in label for k in ('tire','barrel','gun','turret')):
                weight=1.7;minimum=6
            if name=='needler' and any(k in shader for k in ('crystal','needle')):weight=3;minimum=6
            minimum=min(minimum,budget.get('feature_minimum',{}).get(name,minimum))
            return {'weight':weight,'min':min(minimum,info['face_count'])}
        # The Spartan's armor is one closed source surface. Independent bone
        # or tint partitions tear its shoulder/chest seams when decimated;
        # retain connectivity and carry the original skin weights instead.
        bone_labels={i:'body' for i in range(len(model['nodes']))} if name=='spartan' else None
        projection=budget.get('projection',{}).get(name,'outside' if name in ('frag','plasma_grenade') else True)
        obj,tris,weighted,report=reduce_geometry(scene,model,'N64 '+name,targets[name],importance,
            bone_labels=bone_labels,partition_colors=False,protect_boundaries=True,project_surface=projection)
        preserved=set(budget.get('preserve_quality_materials',{}).get(name,[]))
        if preserved:
            if approved is None:raise ValueError('Material preservation requires a quality reference')
            # Authored distant LODs bake small luminous/gauge elements into
            # their textures. Untextured vertex colors lose those cues; keep
            # their few original high-detail faces on the economical shell.
            tris=[t for t in tris if t['material'] not in preserved]
            retained=[t for t in approved['models'][name]['triangles'] if t['material'] in preserved]
            tris.extend(retained)
            weighted=[(Vector(p),w) for t in tris for p,w in zip(t['p'],t['weights'])]
            report['triangles']=len(tris)
            report['preserved_quality_materials']=sorted(preserved)
            report['preserved_quality_triangles']=len(retained)
            update_review_mesh(obj,tris,model,name)
        nearby=derived(model,tris)
        bounded=budget.get('bounded_near',{}).get(name)
        if bounded:
            from geometry_bounded import reduce_near_bounded
            nearby,collapse=reduce_near_bounded(name,nearby,original,bounded)
            report['bounded']=collapse;report['triangles']=len(nearby['triangles'])
            update_review_mesh(obj,nearby['triangles'],model,name+' bounded near')
        out['models'][name]=nearby;out['reduction'][name]=report
        weighted_by_name[name]=weighted
        obj.location=((index%4)*3,(index//4)*3,0)
        if name in ('warthog','ghost','scorpion','banshee','spartan'):
            def low_importance(material,bone,info):
                value=importance(material,bone,info);value['min']=min(value['min'],2 if info['face_count']<6 else 4)
                return value
            low_target=low_targets[name]
            low_model=original.get('lod_source',original)
            low_source=budget.get('lod_source_lods',{}).get(name)
            if low_source:low_model={**original,**original['source_geometry_lods'][low_source]}
            if name in budget.get('refine_lods',[]):
                if approved is None:raise ValueError('Profile requires --refine-approved')
                if name=='spartan':raise ValueError('Refine only rigid meshes; Spartan must preserve original skinning')
                low_model=refinement_source(low_model,approved['vehicle_lods'][name])
            low_bone_labels=({i:'body' for i in range(len(low_model['nodes']))}
                if name in budget.get('merge_lod_bones',[]) else bone_labels)
            low_obj,low,low_weighted,low_report=reduce_geometry(scene,low_model,'N64 '+name+' LOD',low_target,low_importance,
                bone_labels=low_bone_labels,partition_colors=False,protect_boundaries=True,
                project_surface=budget.get('lod_projection',{}).get(name,True))
            low_obj.hide_render=True;low_obj.hide_set(True)
            out['reduction'][name+'_lod']=low_report
            if name=='spartan':
                out['spartan_lod']=derived(low_model,low);weighted_by_name['spartan_lod']=low_weighted
            else:
                distant=derived(low_model,low)
                bounded=budget.get('bounded_lods',{}).get(name)
                if bounded:
                    from geometry_bounded import reduce_bounded
                    distant,collapse=reduce_bounded(name,distant,original,bounded)
                    low_report['bounded']=collapse;low_report['triangles']=len(distant['triangles'])
                    update_review_mesh(low_obj,distant['triangles'],low_model,name+' bounded LOD')
                out['vehicle_lods'][name]=distant
    if budget.get('scorpion_cannon'):
        from scorpion_barrel import apply_recipe
        apply_recipe(out,data,budget['scorpion_cannon'])
    if budget.get('pickup_targets'):
        out['pickup_lods']={}
        for index,(name,target) in enumerate(budget['pickup_targets'].items()):
            original=data['models'][name];model=original
            lod=budget.get('pickup_source_lods',{}).get(name)
            if lod:model={**original,**original['source_geometry_lods'][lod]}
            if name in budget.get('pickup_convex_hulls',[]) or name in budget.get('pickup_hull_bones',[]):
                # Tiny powerups need one opaque envelope. A distant rocket
                # retains separate gun, tube and grip envelopes so thinning
                # its many open decorative sheets cannot punch through caps.
                import bmesh
                by_bone=name in budget.get('pickup_hull_bones',[])
                groups={}
                for vi,p in enumerate(original['vertices']):
                    bone=original['weights'][vi][0] if by_bone else 0
                    groups.setdefault(bone,[]).append(vi)
                vertices=[];uv=[];weights=[];faces=[];materials=[]
                for bone,indices in groups.items():
                    bm=bmesh.new()
                    for vi in indices:bm.verts.new(original['vertices'][vi])
                    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
                    if len(bm.verts)<4:
                        bm.free();continue
                    hull=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
                    hull_faces=[f for f in hull['geom'] if isinstance(f,bmesh.types.BMFace)]
                    triangles=bmesh.ops.triangulate(bm,faces=hull_faces)['faces']
                    bm.verts.index_update();offset=len(vertices)
                    tree=kdtree.KDTree(len(indices))
                    for vi in indices:tree.insert(Vector(original['vertices'][vi]),vi)
                    tree.balance()
                    for v in bm.verts:
                        _,vi,_=tree.find(v.co);vertices.append(list(v.co))
                        uv.append(original['uv'][vi] if by_bone else [.5,.5]);weights.append([bone,-1,0])
                    source_materials=[m for f,m in zip(original['faces'],original['materials'])
                                      if original['weights'][f[0]][0]==bone]
                    material=max(set(source_materials),key=source_materials.count) if source_materials else 0
                    faces.extend([[v.index+offset for v in f.verts] for f in triangles])
                    materials.extend([material]*len(triangles));bm.free()
                model={**original,'vertices':vertices,'uv':uv,'weights':weights,
                       'faces':faces,'materials':materials,
                       'source_lod':'convex '+('bone envelopes' if by_bone else 'silhouette envelope')+' of original source vertices'}
            def pickup_importance(material,bone,info):
                return {'weight':1,'min':min(2,info['face_count'])}
            obj,tris,weighted,report=reduce_geometry(scene,model,'N64 pickup '+name,target,pickup_importance,
                bone_labels={i:'static' for i in range(len(model['nodes']))},
                partition_colors=False,protect_boundaries=False,project_surface='outside')
            preserved_materials=set(budget.get('pickup_preserve_materials',{}).get(name,[]))
            preserved_parts=set(budget.get('pickup_preserve_parts',{}).get(name,[]))
            if preserved_materials or preserved_parts:
                tris=[t for t in tris if t['material'] not in preserved_materials]
                retained=[t for t in out['models'][name]['triangles']
                          if t['material'] in preserved_materials or t['part'] in preserved_parts]
                if name in budget.get('pickup_project_preserved',[]):
                    # A convex distant shell can cover decals that sat on the
                    # original curved surface. Lift only retained source faces
                    # along their own normal to that shell, preserving their UV.
                    from mathutils.bvhtree import BVHTree
                    points=[Vector(p) for t in tris for p in t['p']]
                    surface=BVHTree.FromPolygons(points,[[i*3+j for j in range(3)] for i in range(len(tris))],all_triangles=True)
                    projected=[]
                    for face in retained:
                        a,b,c=map(Vector,face['p']);normal=(b-a).cross(c-a).normalized();positions=[]
                        for p in (a,b,c):
                            hit,_,_,distance=surface.ray_cast(p-normal*.000001,normal)
                            positions.append(list(hit+normal/1024) if hit is not None else list(p))
                        projected.append({**face,'p':positions})
                    retained=projected;report['preserved_projected_to_shell']=True
                tris.extend(retained)
                report['preserved_near_triangles']=len(retained);report['triangles']=len(tris)
            if len(tris)>=len(out['models'][name]['triangles']):
                # The packer may alias these equal-count entries to the near
                # bank. Never select a more expensive mesh for distant use.
                tris=out['models'][name]['triangles'];model={**original,**out['models'][name]}
                report['aliased_near']=True;report['triangles']=len(tris)
            if preserved_materials or preserved_parts or report.get('aliased_near'):
                update_review_mesh(obj,tris,model,name+' pickup')
            out['pickup_lods'][name]=derived(model,tris);out['reduction'][name+'_pickup']=report
            obj.location=((index%4)*3,(index//4)*3,-3)
    model=data['models']['spartan'];nodes=model['nodes']
    def globals_for(states):
        result=[]
        for i,n in enumerate(states):
            x,y,z,w=n['q'];mat=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4()
            mat.translation=Vector(n['p']);parent=nodes[i]['parent']
            result.append(result[parent]@mat if parent>=0 else mat)
        return result
    inverse_bind=[m.inverted() for m in globals_for(nodes)]
    # The reducer carries/interpolates original weights through each collapse.
    # This avoids nearest-vertex reassignment across fingers and bent joints.
    weighted_lods=[weighted_by_name['spartan'],weighted_by_name['spartan_lod']]
    limits={'idle':8,'run':10,'fire':5,'reload':12,'death':12,'jump':8,'melee':8,'throw':8,'drive':6,
            'passenger':4,'gunner':4}
    idle=data['animations']['idle']['frames'][0]
    marker=model['markers']['right hand'][0]
    x,y,z,w=marker['q'];marker_matrix=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4()
    marker_matrix.translation=Vector(marker['p'])
    basis=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    for name,clip in data['animations'].items():
        lod_frames=[[],[]];attachment=[];count=min(limits[name],len(clip['frames']))
        for fi in range(count):
            states=clip['frames'][round(fi*(len(clip['frames'])-1)/max(1,count-1))]
            # Halo overlay transforms are deltas relative to the base idle pose.
            if clip['type']=='overlay':
                combined=[]
                for ni,(a,b) in enumerate(zip(idle,states)):
                    ax,ay,az,aw=a['q'];bx,by,bz,bw=b['q']
                    q=(Quaternion((bw,bx,by,bz))@Quaternion((aw,ax,ay,az))
                       if clip['rot_flags']&(1<<ni) else Quaternion((aw,ax,ay,az)))
                    combined.append({'p':[a['p'][i]+(b['p'][i] if clip['trans_flags']&(1<<ni) else 0) for i in range(3)],'q':[q.x,q.y,q.z,q.w]})
                states=combined
            pose=globals_for(states);skin=[a@b for a,b in zip(pose,inverse_bind)]
            grip=basis@pose[marker['node']]@marker_matrix@basis.inverted()
            q=grip.to_quaternion().normalized()
            attachment.append({'pos':list(grip.translation),'quat':[q.x,q.y,q.z,q.w]})
            for weighted,frames in zip(weighted_lods,lod_frames):
                points=[]
                for p,weights in weighted:
                    posed=Vector((0,0,0))
                    for bone,w in weights:posed+=(skin[bone]@p)*w
                    if not all(math.isfinite(v) for v in posed):raise ValueError('Nonfinite skinned vertex')
                    points.append(list(posed))
                frames.append(points)
        for key,frames in zip(('animations','animations_lod'),lod_frames):
            out[key][name]={'frames':frames,'duration':clip['duration'],'tag_name':clip['tag_name']}
        out['weapon_attachment'][name]={'poses':attachment,'duration':clip['duration']}
    if budget.get('occlusion_closures'):
        from geometry_closures import apply_closures
        apply_closures(out,scene)
    Path(output).write_text(json.dumps(out))
    bpy.data.libraries.write(str(Path(output).with_suffix('.blend')),{scene})
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            region=area.spaces.active.region_3d;region.view_location=(4.5,4.5,0);region.view_distance=16
    print(json.dumps({'models':{k:len(v['triangles']) for k,v in out['models'].items()},'animation_frames':sum(len(a['frames']) for a in out['animations'].values())}))

if __name__=='__main__':
    import argparse,sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('output')
    profiles=parser.add_mutually_exclusive_group()
    profiles.add_argument('--performance-profile',action='store_true',help='Use the tracked tactical preset and regenerate its quality-reference geometry automatically')
    profiles.add_argument('--budget-file',help='Optional JSON targets/lod_targets/feature_minimum overrides for an isolated candidate')
    parser.add_argument('--refine-approved',help='Approved reduced JSON to refine only the rigid models selected by an experimental budget profile')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.performance_profile:
        if args.refine_approved:parser.error('--performance-profile regenerates its own reference; omit --refine-approved')
        reference=Path(args.output).with_name(Path(args.output).stem+'-quality-reference.json')
        reduce_extended(args.source,reference)
        reduce_extended(args.source,args.output,Path(__file__).with_name('world_performance.json'),reference)
    else:reduce_extended(args.source,args.output,args.budget_file,args.refine_approved)
