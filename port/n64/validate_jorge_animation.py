"""Reimport the animated GLB and compare evaluated motion with native Blender."""
import bpy,json,struct
from pathlib import Path
from mathutils.kdtree import KDTree
import jorge_animation_proof as proof

def key(ob):return (ob.get('group'),ob.get('source_component'))

def points(scene,objects):
    bpy.context.window.scene=scene;bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();result={}
    for ob in objects:
        ev=ob.evaluated_get(graph);me=ev.to_mesh();result[key(ob)]=[ob.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
    return result

def distance(a,b):
    kd=KDTree(len(a))
    for i,p in enumerate(a):kd.insert(p,i)
    kd.balance();return max(kd.find(p)[2] for p in b)

def main():
    original,rig=proof.proof_scene();native=[o for o in original.objects if o.get('variant')=='B'];native_weapon=next(o for o in original.objects if o.name.startswith('CE rifle'))
    rig.animation_data.use_nla=False
    original_actions={name:next(a for a in bpy.data.actions if a.get('source_clip')==name) for name in proof.CLIPS}
    before=set(bpy.data.actions);scene=bpy.data.scenes.new('Animated GLB validation');bpy.context.window.scene=scene;scene.render.fps=30
    bpy.ops.import_scene.gltf(filepath=str(proof.OUT/'jorge-animation-proof.glb'))
    imported=next(o for o in scene.objects if o.type=='ARMATURE');imported.animation_data.use_nla=False
    actions={name:next(a for a in set(bpy.data.actions)-before if a.name.startswith('Jorge / '+name)) for name in proof.CLIPS}
    meshes=[o for o in scene.objects if o.get('variant')=='B'];weapon=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('CE rifle'))
    assert len(imported.data.bones)==85 and len(meshes)==110
    assert set(key(o) for o in native)==set(key(o) for o in meshes)
    triangles=sum(len(o.data.polygons) for o in meshes);assert triangles==26076
    report={'body_triangles':triangles,'weapon_triangles':len(weapon.data.polygons),'body_components':len(meshes),'bones':len(imported.data.bones),'clips':{}}
    for name in proof.CLIPS:
        action=original_actions[name];duration=action['duration_seconds'];maximum=reverse=socket=0.;floor=100.;sample_count=0
        for frame in range(round(duration*30)+1):
            bpy.context.window.scene=original;rig.animation_data.action=action;original.frame_set(frame);a=points(original,native);wa=native_weapon.matrix_world.copy()
            floor=min(floor,min(p.z for values in a.values() for p in values))
            bpy.context.window.scene=scene;imported.animation_data.action=actions[name];scene.frame_set(frame);b=points(scene,meshes);wb=weapon.matrix_world.copy()
            socket=max(socket,max(abs(wa[i][j]-wb[i][j]) for i in range(4) for j in range(4)))
            maximum=max(maximum,max(distance(a[k],b[k]) for k in a));reverse=max(reverse,max(distance(b[k],a[k]) for k in a));sample_count+=1
        # glTF key optimization and the importer's quaternion reconstruction
        # introduce small roundoff; keep the geometric bound below 0.3 mm.
        assert maximum<3e-4 and reverse<3e-4 and socket<3e-4,(name,maximum,reverse,socket)
        report['clips'][name]={'duration_seconds':duration,'samples_at_30fps_including_end':sample_count,'max_export_to_native_vertex_error_m':maximum,'max_native_to_export_vertex_error_m':reverse,'max_weapon_matrix_error':socket,'lowest_boot_z_between_source_keys_m':floor}
        print('ROUNDTRIP',name,report['clips'][name],flush=True)
    data=(proof.OUT/'jorge-animation-proof.glb').read_bytes();size=struct.unpack_from('<I',data,12)[0];gltf=json.loads(data[20:20+size])
    assert len(gltf['animations'])==4 and len(gltf['skins'])==1 and len(gltf['skins'][0]['joints'])==85
    report['export_animation_names']=[a['name'] for a in gltf['animations']];report['embedded_images']=len(gltf['images']);report['mesh_materials']=len(gltf['materials'])
    (proof.OUT/'animation-roundtrip-report.json').write_text(json.dumps(report,indent=2)+'\n')
    proof.cleanup.studio(scene);scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.camera.data.ortho_scale=2.95
    imported.animation_data.action=actions['reload'];scene.frame_set(35)
    for ob in scene.objects:
        if ob.type=='MESH' and ob not in meshes and ob!=weapon:ob.hide_render=True
    scene.render.filepath=str(proof.OUT/'renders/glb-reload-roundtrip.png');bpy.ops.render.render(write_still=True)
    print('ANIMATED GLB VERIFIED',flush=True)

if __name__=='__main__':main()
