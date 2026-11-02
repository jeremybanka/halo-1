"""Save independent editable CE-bound ODST LODs, source reference and body GLBs."""
import json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import globals_for
from pack_assets import normal,position

def corner_colors(tri,materials,textures):
    if tri.get('color_override'):return [tri['color_override']]*3,[0]*3
    role=materials[tri["material"]]["path"].split("\\")[-1]
    if role=="odst_crown_stripe":return [[235,235,235]]*3,[255]*3
    if role=="odst_visor":return [[24,230,255]]*3,[0]*3
    if tri.get('corner_color_override'):return tri['corner_color_override'],[0]*3
    image=textures.get(tri["material"]);light=.68+.32*max(0,np.dot(normal([position(p,(0,0,0)) for p in tri["p"]]),(.25,.83,.49)))
    rgb=[]
    for uv in tri["uv"]:
        uv=np.array(uv)*.94+np.mean(tri["uv"],axis=0)*.06
        if image is None:value=np.array((100,105,108))
        else:
            w,h,p=image;value=p[h-1-int(uv[1]%1*h),int(uv[0]%1*w),:3]*255
        rgb.append(np.rint(value*light).astype(int).tolist())
    return rgb,[0]*3

def run(folder,candidate="covered",library="library"):
    folder=Path(folder);data=json.loads((folder/candidate/'solid.json').read_text())
    source=json.loads((folder/'source/odst-ce-raw.json').read_text())
    original=json.loads((folder/'source/odst-original.json').read_text())
    extras=json.loads((folder.parents[0]/'jorge/playable-half/ce-motion-source.json').read_text())
    clips=dict(source['animations']);clips.update(extras)
    data.setdefault('materials',source['models']['spartan']['material_metadata'])
    data.setdefault('textures',source['models']['spartan']['textures'])
    # This script runs in a dedicated --factory-startup background process.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=True)
    scene=bpy.context.scene;scene.name='ODST - fresh source demake';scene.render.fps=30
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=3.048
    bind=globals_for(data['nodes'])
    rig=bpy.data.objects.new('ODST / CE gameplay rig',bpy.data.armatures.new('CE 19 bone rig'));scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for i,node in enumerate(data['nodes']):
        bone=rig.data.edit_bones.new(node['name']);bone.length=.025;bone.matrix=bind[i]
        if node['parent']>=0:bone.parent=rig.data.edit_bones[data['nodes'][node['parent']]['name']]
    bpy.ops.object.mode_set(mode='OBJECT')
    print('MAXIMUM_REST_AXIS_ERROR',float(np.max(np.abs(np.array(bind)-np.array([rig.data.bones[n['name']].matrix_local for n in data['nodes']])))),flush=True)
    textures={}
    for i,p in enumerate(data['textures']):
        if p:
            im=bpy.data.images.load(p,check_existing=True);w,h=im.size; textures[i]=(w,h,np.array(im.pixels[:]).reshape(h,w,4))
    objects=[];corner_maps=[]
    for lod,model in enumerate(data['lods']):
        points=[];faces=[];weights=[];colors=[];uv=[];components=[]
        for t in model['triangles']:
            faces.append(list(range(len(points),len(points)+3)));points.extend(t['p']);weights.extend(t['weights']);components.extend([(t['component'],t['material'])]*3)
            rgb,_=corner_colors(t,data['materials'],textures);colors.extend(rgb);uv.extend(t['uv'])
        native=[];native_weights=[];lookup={};mapping=[]
        for point,values,component in zip(points,weights,components):
            key=(component,tuple(round(x,8) for x in point),tuple((b,round(w,8)) for b,w in values))
            if key not in lookup:
                lookup[key]=len(native);native.append(point);native_weights.append(values)
            mapping.append(lookup[key])
        # Collapse can retain an authored thin surface in both winding
        # directions. Blender rejects a shared-vertex duplicate polygon;
        # split its vertices without deleting either visible side.
        seen=set()
        for face in faces:
            key=tuple(sorted(mapping[i] for i in face))
            if key in seen:
                for i in face:
                    mapping[i]=len(native);native.append(points[i]);native_weights.append(weights[i])
            seen.add(key)
        points=native;weights=native_weights;faces=[[mapping[i] for i in f] for f in faces];corner_maps.append(np.array(mapping))
        mesh=bpy.data.meshes.new('Fresh original surfaces / '+str(lod));mesh.from_pydata(points,[],faces)
        assert not mesh.validate(verbose=True,clean_customdata=False), 'Export must preserve all source-derived faces'
        ob=bpy.data.objects.new('ODST near' if lod==0 else 'ODST far',mesh);scene.collection.objects.link(ob);ob.parent=rig;objects.append(ob)
        ob['source_sha256']=data['source_sha256'];ob['demake_policy']='CHARACTER_DEMAKE.md';ob['source_components']=json.dumps([r for r in data['ledger'] if r['lod']==lod])
        for node in data['nodes']:ob.vertex_groups.new(name=node['name'])
        for i,values in enumerate(weights):
            for bone,w in values:ob.vertex_groups[bone].add([i],w,'REPLACE')
        mod=ob.modifiers.new('Original source skin weights on CE rig','ARMATURE');mod.object=rig
        layer=mesh.uv_layers.new(name='Original source UV')
        ca=mesh.color_attributes.new(name='Native RGB',type='BYTE_COLOR',domain='CORNER')
        for i in range(len(mesh.loops)):
            u,v=uv[i];layer.data[i].uv=(u,1-v);ca.data[i].color_srgb=(*np.array(colors[i])/255,1)
        mat=bpy.data.materials.new('N64 source color / cyan visor / neutral crown');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
        node=ns.new('ShaderNodeVertexColor');node.layer_name=ca.name;out=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(node.outputs['Color'],out.inputs['Surface']);mesh.materials.append(mat)
        ob.hide_render=bool(lod);ob.hide_set(bool(lod))
    refmesh=bpy.data.meshes.new('Intact retail ODST / untouched source coordinates');refmesh.from_pydata(original['vertices'],[],original['faces'])
    ref=bpy.data.objects.new('REFERENCE ONLY / original 55-bone source geometry',refmesh);scene.collection.objects.link(ref);ref.hide_render=True;ref.hide_set(True)
    ref['source_nodes']=json.dumps(original['nodes']);ref['source_skin_weights']=json.dumps(original['skin_weights']);ref['source_geometry']='source/odst-original.json'
    # Keep an actual editable native source skeleton, not only its JSON.
    from extract_odst import globals_for as native_globals
    native_bind=native_globals(original['nodes'],conjugate=False)
    native_rig=bpy.data.objects.new('REFERENCE / intact native 55-bone rig',bpy.data.armatures.new('Original Halo 3 ODST skeleton'))
    scene.collection.objects.link(native_rig);bpy.context.view_layer.objects.active=native_rig
    rig.select_set(False);native_rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for i,node in enumerate(original['nodes']):
        bone=native_rig.data.edit_bones.new(node['name']);bone.length=.025;bone.matrix=Matrix(native_bind[i])
        if node['parent']>=0:bone.parent=native_rig.data.edit_bones[original['nodes'][node['parent']]['name']]
    bpy.ops.object.mode_set(mode='OBJECT');native_rig.select_set(False);native_rig.hide_set(True);native_rig.hide_render=True
    for node in original['nodes']:ref.vertex_groups.new(name=node['name'])
    for i,values in enumerate(original['skin_weights']):
        for bone,w in values:ref.vertex_groups[bone].add([i],w,'REPLACE')
    modifier=ref.modifiers.new('Untouched original skinning','ARMATURE');modifier.object=native_rig;ref.parent=native_rig
    layer=refmesh.uv_layers.new(name='Untouched source diffuse UV')
    for face,ids in zip(refmesh.polygons,original['faces']):
        for li,vi in zip(face.loop_indices,ids):
            u,v=original['uv'][vi];layer.data[li].uv=(u,1-v)
    bpy.context.view_layer.objects.active=rig

    rig.animation_data_create()
    bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
    for name,clip in clips.items():
        action=bpy.data.actions.new('CE / '+name);action['source_clip']=name;action['duration_seconds']=clip['duration'];action.use_fake_user=True;rig.animation_data.action=action
        count=min(12,len(clip['frames']));previous={}
        idle=clips['idle']['frames'][0]
        from mathutils import Quaternion
        for fi in range(count):
            states=clip['frames'][round(fi*(len(clip['frames'])-1)/max(1,count-1))]
            if clip['type']=='overlay':
                combined=[]
                for ni,(a,b) in enumerate(zip(idle,states)):
                    ax,ay,az,aw=a['q'];bx,by,bz,bw=b['q']
                    q=Quaternion((bw,bx,by,bz))@Quaternion((aw,ax,ay,az)) if clip['rot_flags']&(1<<ni) else Quaternion((aw,ax,ay,az))
                    combined.append(dict(p=[a['p'][i]+(b['p'][i] if clip['trans_flags']&(1<<ni) else 0) for i in range(3)],q=[q.x,q.y,q.z,q.w]))
                states=combined
            poses=globals_for(data['nodes'],states)
            frame=fi*clip['duration']*30/max(1,count-1)
            for ni,(node,pose) in enumerate(zip(data['nodes'],poses)):
                pb=rig.pose.bones[node['name']];pb.rotation_mode='QUATERNION'
                parent=node['parent']
                pb.matrix_basis=bind[ni].inverted()@bind[parent]@poses[parent].inverted()@pose if parent>=0 else bind[ni].inverted()@pose
                q=pb.rotation_quaternion.copy()
                if node['name'] in previous and q.dot(previous[node['name']])<0:q.negate();pb.rotation_quaternion=q
                previous[node['name']]=q.copy()
                pb.keyframe_insert('location',frame=frame);pb.keyframe_insert('rotation_quaternion',frame=frame);pb.keyframe_insert('scale',frame=frame)
        for fc in action.fcurves if hasattr(action,'fcurves') else []:
            for key in fc.keyframe_points:key.interpolation='LINEAR'
    checks=[]
    for lod,ob in enumerate(objects):
        proof=np.load(folder/candidate/f'poses-{lod}.npz');worst=0.;samples=0
        for ci,c in enumerate(data['lods'][lod]['animations']):
            rig.animation_data.action=next(a for a in bpy.data.actions if a.get('source_clip')==c['name'])
            for fi in range(c['frames']):
                frame=fi*c['duration']*30/max(1,c['frames']-1)
                scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
                ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
                actual=np.array([position(v.co,(0,0,0)) for v in mesh.vertices])[corner_maps[lod]];ev.to_mesh_clear()
                error=float(np.abs(actual-proof['frames_'+str(ci)][fi]).max())
                if error>1e-5 and error>worst+1e-4:print('RIG_ERROR',lod,c['name'],fi,error,actual[0],proof['frames_'+str(ci)][fi][0],flush=True)
                worst=max(worst,error);samples+=1
        assert worst<1e-5,(lod,worst)
        checks.append(dict(lod=lod,native_vertices=len(ob.data.vertices),triangles=len(ob.data.polygons),samples=samples,maximum_coordinate_error=worst))
    (folder/library).mkdir(parents=True,exist_ok=True)
    (folder/library/'rig-validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    rig.animation_data.action=next(a for a in bpy.data.actions if a.get('source_clip')=='idle');scene.frame_set(0)
    scene.view_settings.view_transform='Raw'
    bpy.data.libraries.write(str((folder/library/'odst.blend').resolve()),{scene,*[a for a in bpy.data.actions if a.get('source_clip')]},fake_user=True,compress=True)
    # Bake unit conversion into mesh, rest skeleton and translation keys.
    # Object scale on a skinned glTF can cancel against inverse bind matrices.
    conversion=Matrix.Scale(3.048,4)
    rig.data.transform(conversion)
    for ob in objects:ob.data.transform(conversion)
    for action in bpy.data.actions:
        if not action.get('source_clip'):continue
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        if curve.data_path.endswith('.location'):
                            for key in curve.keyframe_points:
                                key.co.y*=3.048;key.handle_left.y*=3.048;key.handle_right.y*=3.048
    # Dense 300 Hz interchange sampling also preserves Blender's normalized
    # quaternion curves between the sparse authoring keys in glTF playback.
    for action in bpy.data.actions:
        if not action.get('source_clip'):continue
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.co.x*=10;key.handle_left.x*=10;key.handle_right.x*=10
    scene.render.fps=300
    scene.unit_settings.scale_length=1
    for lod,ob in enumerate(objects):
        bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=ob
        bpy.ops.export_scene.gltf(filepath=str((folder/library/f'odst-{lod}.glb').resolve()),use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_apply=False)
        if lod:ob.hide_set(True)
    print('Saved independent editable library and two skinned GLBs',flush=True)

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
