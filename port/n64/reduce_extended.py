"""Blender reduction and offline skinning of original Xbox multiplayer animation.

Run with Blender --background --python THIS -- raw.json reduced.json.
All outputs are rebuildable local game-derived data.
"""
import json, math
from pathlib import Path


def reduce_extended(source,output):
    import bpy
    from mathutils import Matrix, Quaternion, Vector, kdtree
    data=json.loads(Path(source).read_text());out={'models':{},'vehicle_lods':{},'animations':{},'animations_lod':{},'weapon_attachment':{},'audio':data['audio'],'hud':data['hud'],'sources':data['sources']}
    scene=bpy.data.scenes.new('Halo N64 - Multiplayer assets')
    if bpy.context.window:bpy.context.window.scene=scene
    for index,(name,model) in enumerate(data['models'].items()):
        mesh=bpy.data.meshes.new('Xbox '+name);mesh.from_pydata(model['vertices'],[],model['faces'])
        for material in range(max(model['materials'])+1):
            mat=bpy.data.materials.new('Xbox '+name+' '+str(material));mat.use_nodes=True
            shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            if material<len(model['textures']) and model['textures'][material]:
                node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(model['textures'][material],check_existing=True)
                mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
            mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='Xbox diffuse')
        for face,mat in zip(mesh.polygons,model['materials']):
            face.material_index=mat
            for loop in face.loop_indices:
                a,b=model['uv'][mesh.loops[loop].vertex_index];uv.data[loop].uv=(a,1-b)
        obj=bpy.data.objects.new('N64 '+name,mesh);scene.collection.objects.link(obj)
        target=(170 if name=='spartan' else 240 if name in ('warthog','ghost','scorpion','banshee')
                else 60 if name in ('healthpack','overshield','camouflage')
                else 20 if name in ('frag','plasma_grenade') else 100)
        if len(model['faces'])>target:
            mod=obj.modifiers.new('N64 triangle budget','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=target/len(model['faces']);mod.use_collapse_triangulate=True
        with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):dep=bpy.context.evaluated_depsgraph_get()
        dep.update();ev=obj.evaluated_get(dep);m=ev.to_mesh();m.calc_loop_triangles();tris=[]
        for tri in m.loop_triangles:
            p=[list(m.vertices[i].co) for i in tri.vertices]
            coords=[list(m.uv_layers.active.data[i].uv) for i in tri.loops]
            tris.append({'p':p,'uv':[[u,1-v] for u,v in coords],'material':tri.material_index})
        ev.to_mesh_clear();out['models'][name]={'triangles':tris,'textures':model['textures']}
        if name in ('warthog','ghost','scorpion','banshee','spartan'):
            high_ratio=mod.ratio;mod.ratio=(60 if name=='spartan' else 80)/len(model['faces']);dep.update()
            ev=obj.evaluated_get(dep);m=ev.to_mesh();m.calc_loop_triangles();low=[]
            for tri in m.loop_triangles:
                coords=[list(m.uv_layers.active.data[i].uv) for i in tri.loops]
                low.append({'p':[list(m.vertices[i].co) for i in tri.vertices],
                            'uv':[[u,1-v] for u,v in coords],'material':tri.material_index})
            ev.to_mesh_clear();mod.ratio=high_ratio
            if name=='spartan':out['spartan_lod']={'triangles':low,'textures':model['textures']}
            else:out['vehicle_lods'][name]={'triangles':low,'textures':model['textures']}
        obj.location=((index%4)*3,(index//4)*3,0)
    model=data['models']['spartan'];nodes=model['nodes']
    def globals_for(states):
        result=[]
        for i,n in enumerate(states):
            x,y,z,w=n['q'];mat=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4()
            mat.translation=Vector(n['p']);parent=nodes[i]['parent']
            result.append(result[parent]@mat if parent>=0 else mat)
        return result
    inverse_bind=[m.inverted() for m in globals_for(nodes)]
    kd=kdtree.KDTree(len(model['vertices']))
    for i,p in enumerate(model['vertices']):kd.insert(p,i)
    kd.balance()
    # Blender's collapse vertices inherit skinning via nearest original mesh
    # vertex. Skinning is baked offline: the N64 only interpolates positions.
    weighted_lods=[]
    for mesh in (out['models']['spartan'],out['spartan_lod']):
        weighted=[]
        for p in (p for tri in mesh['triangles'] for p in tri['p']):
            _,i,_=kd.find(Vector(p));n0,n1,w=model['weights'][i]
            weighted.append((Vector(p),[(n0,1-w)]+([(n1,w)] if n1>=0 and w>0 else [])))
        weighted_lods.append(weighted)
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
    Path(output).write_text(json.dumps(out))
    bpy.data.libraries.write(str(Path(output).with_suffix('.blend')),{scene})
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            region=area.spaces.active.region_3d;region.view_location=(4.5,4.5,0);region.view_distance=16
    print(json.dumps({'models':{k:len(v['triangles']) for k,v in out['models'].items()},'animation_frames':sum(len(a['frames']) for a in out['animations'].values())}))

if __name__=='__main__':
    import sys
    args=sys.argv[sys.argv.index('--')+1:];reduce_extended(*args)
