"""Editable independent Reach-rig LOD library, native-skin proof and body GLBs."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from jorge_workshop import point


def run(candidate,motion,output):
    candidate,motion,output=map(Path,(candidate,motion,output));output.mkdir(parents=True,exist_ok=True)
    data=json.loads((candidate/'solid.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(motion/'gungnir-motion.blend'))
    scene=bpy.context.scene;scene.render.fps=30;scene.unit_settings.scale_length=1
    rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.name='GUNGNIR / native Reach gameplay rig';rig.hide_set(False);rig.hide_render=True;rig.animation_data.use_nla=False
    reference=bpy.data.collections.new('REFERENCE / intact source components');scene.collection.children.link(reference)
    for ob in list(scene.objects):
        if ob.type!='MESH':continue
        for collection in list(ob.users_collection):collection.objects.unlink(ob)
        reference.objects.link(ob);ob.hide_set(True);ob.hide_render=True
    reference.hide_render=True;reference.hide_viewport=True
    import subprocess
    subprocess.run([str(Path('build/n64-python/bin/python').absolute()),str(Path(__file__).with_name('gungnir_library_colors.py')),str(candidate/'solid.json'),str(output/'colors.json')],check=True)
    prepared=json.loads((output/'colors.json').read_text())
    actions={a['source_clip']:a for a in bpy.data.actions if a.get('source_clip')};assert len(actions)==39
    objects=[];mappings=[];reports=[]
    for lod,model in enumerate(data['lods']):
        vertices=[];weights=[];faces=[];mapping=[];lookup={};seen=set();colors=[];uvs=[];masks=[]
        for ti,t in enumerate(model['triangles']):
            face=[];rgb,mask=prepared[lod][ti];colors.extend(rgb);masks.extend(mask);uvs.extend(t['uv'])
            for p,ws in zip(t['p'],t['weights']):
                key=(tuple(round(v,7) for v in p),tuple((b,round(w,7)) for b,w in ws))
                if key not in lookup:lookup[key]=len(vertices);vertices.append(point(p));weights.append(ws)
                face.append(lookup[key])
            if tuple(sorted(face)) in seen:
                face=[]
                for p,ws in zip(t['p'],t['weights']):face.append(len(vertices));vertices.append(point(p));weights.append(ws)
            seen.add(tuple(sorted(face)));faces.append(face);mapping.extend(face)
        mesh=bpy.data.meshes.new('Source armor / source-fitted local continuity / '+str(lod));mesh.from_pydata(vertices,[],faces)
        assert not mesh.validate(clean_customdata=False),'Invalid candidate topology cannot be silently dropped'
        ob=bpy.data.objects.new('GUNGNIR near' if lod==0 else 'GUNGNIR far',mesh);scene.collection.objects.link(ob);ob.parent=rig
        ob['source_sha256']=data['source_sha256'];ob['component_ledger']=json.dumps([x for x in data['ledger'] if x['lod']==lod]);ob['policy']='CHARACTER_DEMAKE.md / JORGE_LODS.md'
        for node in data['nodes']:ob.vertex_groups.new(name=node['name'])
        for vi,ws in enumerate(weights):
            for bone,w in ws:ob.vertex_groups[bone].add([vi],w,'REPLACE')
        modifier=ob.modifiers.new('Own native 82-bone Reach skinning','ARMATURE');modifier.object=rig
        uv=mesh.uv_layers.new(name='Original source correspondence UV');color=mesh.color_attributes.new(name='N64 broad source RGB',type='BYTE_COLOR',domain='CORNER');team=mesh.attributes.new(name='Muted plate team amount',type='FLOAT',domain='CORNER')
        for i in range(len(mesh.loops)):
            uv.data[i].uv=(uvs[i][0],1-uvs[i][1]);color.data[i].color_srgb=(*np.array(colors[i])/255,1);team.data[i].value=masks[i]/255
        material=bpy.data.materials.new('N64 vertex colors / neutral armor / gold eye');material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear();vertex=nodes.new('ShaderNodeVertexColor');vertex.layer_name=color.name;out=nodes.new('ShaderNodeOutputMaterial');material.node_tree.links.new(vertex.outputs['Color'],out.inputs['Surface']);mesh.materials.append(material)
        source=mesh.attributes.new(name='source_face',type='INT',domain='FACE')
        for face,t in zip(mesh.polygons,model['triangles']):source.data[face.index].value=t['source_faces'][0]['face']
        objects.append(ob);mappings.append(np.array(mapping));ob.hide_set(bool(lod));ob.hide_render=bool(lod)
        # Numerical bake and the actual Blender modifier are independent paths.
        proof=np.load(candidate/f'poses-{lod}.npz');maximum=0;comparisons=0
        for ci,clip in enumerate(model['animations']):
            rig.animation_data.action=actions[clip['name']]
            for fi in range(clip['frames']):
                frame=fi*clip['duration']*30/max(1,clip['frames']-1);scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();actual=np.array([v.co for v in me.vertices])[mappings[lod]];ev.to_mesh_clear()
                expected=proof['frames_'+str(ci)][fi]@np.array(((0,-1,0),(0,0,1),(-1,0,0)))*3.048
                error=float(np.abs(actual-expected).max());maximum=max(maximum,error);comparisons+=len(actual)
        assert maximum<.0001,(lod,maximum)
        reports.append(dict(lod=lod,candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),motion_report_sha256=hashlib.sha256((motion/'motion-report.json').read_bytes()).hexdigest(),native_vertices=len(vertices),triangles=len(faces),skin_vertex_comparisons=comparisons,max_blender_bake_error_m=maximum))
    rig.animation_data.action=actions['idle'];scene.frame_set(0);scene.view_settings.view_transform='Raw'
    bpy.data.libraries.write(str(output/'gungnir.blend'),{scene,*actions.values()},fake_user=True,compress=True)
    # Dense interchange sampling keeps normalized quaternion authoring and
    # glTF interpolation in agreement without replacing the editable rig.
    for action in actions.values():
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.co.x*=10;key.handle_left.x*=10;key.handle_right.x*=10
    scene.render.fps=300
    for lod,ob in enumerate(objects):
        bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=ob
        # The target is unlit baked RGB. NORMAL is unused and would split
        # every flat polygon in the interchange file; preserve full editable
        # geometry/normals in BLEND and source UVs/colors/skin in the GLB.
        bpy.ops.export_scene.gltf(filepath=str(output/f'gungnir-{lod}.glb'),use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_apply=False,export_normals=False)
        raw=(output/f'gungnir-{lod}.glb').read_bytes();length=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+length]);reports[lod]['exported_vertices']=sum(gltf['accessors'][p['attributes']['POSITION']]['count'] for m in gltf['meshes'] for p in m['primitives']);reports[lod]['unlit_normals_omitted']=True
        reports[lod]['glb_sha256']=hashlib.sha256(raw).hexdigest();ob.hide_set(bool(lod))
    (output/'library-report.json').write_text(json.dumps(reports,indent=2)+'\n');print('PASS native candidate rig / independent bake',reports,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('motion');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.candidate,a.motion,a.output)
