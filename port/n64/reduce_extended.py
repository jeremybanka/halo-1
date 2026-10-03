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
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from geometry_reduce import reduce_geometry
    targets={'spartan':460,'warthog':800,'ghost':560,'scorpion':720,'banshee':600,
             'ar':220,'pistol':180,'plasma_pistol':180,'plasma_rifle':230,
             'needler':240,'shotgun':220,'sniper':240,'rocket':240,
             'frag':64,'plasma_grenade':64,'flamethrower':220,
             'healthpack':44,'overshield':90,'camouflage':90}
    weighted_by_name={};out['reduction']={}
    metadata=('textures_fullres','multipurpose_fullres','team_masks','team_mask_channels',
              'material_metadata','material_colors','material_overrides','uv_origin','source_lod')
    def derived(model,tris):
        return {'triangles':tris,'textures':model.get('textures_fullres',model['textures']),
                **{key:model[key] for key in metadata if key in model}}
    for index,(name,model) in enumerate(data['models'].items()):
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
            return {'weight':weight,'min':min(minimum,info['face_count'])}
        # The Spartan's armor is one closed source surface. Independent bone
        # or tint partitions tear its shoulder/chest seams when decimated;
        # retain connectivity and carry the original skin weights instead.
        bone_labels={i:'body' for i in range(len(model['nodes']))} if name=='spartan' else None
        projection='outside' if name in ('frag','plasma_grenade') else True
        obj,tris,weighted,report=reduce_geometry(scene,model,'N64 '+name,targets[name],importance,
            bone_labels=bone_labels,partition_colors=False,protect_boundaries=True,project_surface=projection)
        out['models'][name]=derived(model,tris);out['reduction'][name]=report
        weighted_by_name[name]=weighted
        obj.location=((index%4)*3,(index//4)*3,0)
        if name in ('warthog','ghost','scorpion','banshee','spartan'):
            def low_importance(material,bone,info):
                value=importance(material,bone,info);value['min']=min(value['min'],2 if info['face_count']<6 else 4)
                return value
            low_target=160 if name=='spartan' else 240
            low_obj,low,low_weighted,low_report=reduce_geometry(scene,model.get('lod_source',model),'N64 '+name+' LOD',low_target,low_importance,
                bone_labels=bone_labels,partition_colors=False,protect_boundaries=True)
            low_obj.hide_render=True;low_obj.hide_set(True)
            out['reduction'][name+'_lod']=low_report
            if name=='spartan':
                out['spartan_lod']=derived(model.get('lod_source',model),low);weighted_by_name['spartan_lod']=low_weighted
            else:out['vehicle_lods'][name]=derived(model.get('lod_source',model),low)
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
    Path(output).write_text(json.dumps(out))
    bpy.data.libraries.write(str(Path(output).with_suffix('.blend')),{scene})
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            region=area.spaces.active.region_3d;region.view_location=(4.5,4.5,0);region.view_distance=16
    print(json.dumps({'models':{k:len(v['triangles']) for k,v in out['models'].items()},'animation_frames':sum(len(a['frames']) for a in out['animations'].values())}))

if __name__=='__main__':
    import sys
    args=sys.argv[sys.argv.index('--')+1:];reduce_extended(*args)
