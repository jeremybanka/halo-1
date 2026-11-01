"""Export both editable LODs and verify their GLB animation round trips."""
from pathlib import Path
import hashlib,json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils.kdtree import KDTree
import jorge_lods as task

def points(scene,objects):
    bpy.context.window.scene=scene;bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();result={}
    for ob in objects:
        ev=ob.evaluated_get(graph);me=ev.to_mesh()
        result[ob['source_component']]=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
    return result

def distance(a,b):
    tree=KDTree(len(a))
    for i,p in enumerate(a):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in b)

def run(lod):
    folder=task.OUT/lod;path=folder/('jorge-'+lod+'.blend');original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - '+lod+' body LOD'));bpy.context.window.scene=scene
    rig=next(o for o in scene.objects if o.type=='ARMATURE');obs=task.task.body(scene)
    actions={a['source_clip']:a for a in bpy.data.actions if a.get('source_clip')};assert len(actions)==39 and len(rig.data.bones)==85
    counts=json.loads((folder/'reduction-report.json').read_text())
    assert hashlib.sha256((task.SOURCE/'jorge-playable-personal.blend').read_bytes()).hexdigest()==counts['source_blend_sha256']
    for ob in obs:
        me=ob.data;assert len(me.materials)==1 and all(p.material_index==0 and p.area>1e-12 and len(p.vertices)==3 for p in me.polygons),ob.name
        assert all(.99<n.vector.length<1.01 for n in me.corner_normals),ob.name
        assert all(abs(sum(g.weight for g in v.groups if ob.vertex_groups[g.group].name in rig.data.bones)-1)<1e-5 for v in me.vertices)
        if ob['source_component'].startswith('pack'):
            bs=next(n for n in me.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            assert bs.inputs['Metallic'].default_value==0 and bs.inputs['Roughness'].default_value==1
    for ob in scene.objects:ob.hide_set(False);ob.select_set(ob==rig or ob in obs)
    rig.animation_data.use_nla=False;rig.animation_data.action=actions['idle'];scene.frame_set(0);bpy.context.view_layer.objects.active=rig
    glb=folder/('jorge-'+lod+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
        export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,
        export_frame_range=False,export_frame_step=1,export_optimize_animation_size=False,export_skins=True,export_extras=True)
    raw=glb.read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    inventory=dict(vertices=sum(gltf['accessors'][p['attributes']['POSITION']]['count'] for m in gltf['meshes'] for p in m['primitives']),
        triangles=sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf['meshes'] for p in m['primitives']),
        components=len(gltf['meshes']),bones=len(gltf['skins'][0]['joints']),clips=len(gltf['animations']))
    assert inventory['triangles']==counts['triangles'] and inventory['bones']==85 and inventory['clips']==39,inventory
    assert all('COLOR_0' in p['attributes'] for m in gltf['meshes'] for p in m['primitives'])
    before=set(bpy.data.actions);other=bpy.data.scenes.new(lod+' GLB roundtrip');other.render.fps=30;bpy.context.window.scene=other
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported=next(o for o in other.objects if o.type=='ARMATURE');imported.animation_data.use_nla=False
    meshes=[o for o in other.objects if o.type=='MESH' and o.get('source_component')];assert {o['source_component'] for o in meshes}=={o['source_component'] for o in obs}
    newactions=set(bpy.data.actions)-before
    pairs={name:next(a for a in newactions if a.name.startswith(old.name)) for name,old in actions.items()}
    worst=0;rows=[]
    for name,action in actions.items():
        error=0
        # Validate sampled 30 Hz keys. Native Blender component interpolation
        # and glTF quaternion interpolation need not match between those keys;
        # the game uses its separately verified vertex-frame interpolation.
        for fraction in (0,.25,.5,.75,1):
            frame=round(action['duration_seconds']*30*fraction)
            bpy.context.window.scene=scene;rig.animation_data.action=action;scene.frame_set(int(frame),subframe=frame-int(frame));a=points(scene,obs)
            bpy.context.window.scene=other;imported.animation_data.action=pairs[name];other.frame_set(int(frame),subframe=frame-int(frame));b=points(other,meshes)
            errors={k:max(distance(a[k],b[k]),distance(b[k],a[k])) for k in a}
            error=max(error,max(errors.values()))
            if max(errors.values())>.0003:print('ROUNDTRIP DIAGNOSTIC',lod,name,fraction,frame,action.frame_range[:],pairs[name].frame_range[:],sorted(errors.items(),key=lambda x:-x[1])[:3],flush=True)
        assert error<.0003,(lod,name,error);worst=max(worst,error);rows.append(dict(clip=name,max_vertex_error_m=error))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==original_hash
    result=dict(**inventory,native_blend_preserved=True,source_preserved=True,weights_normals_materials_valid=True,
        maximum_roundtrip_error_m=worst,pose_samples=len(rows)*5,sample_grid_hz=30,animations=rows,
        blend_sha256=original_hash,glb_sha256=hashlib.sha256(glb.read_bytes()).hexdigest())
    (folder/'export-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('EXPORT VALIDATED',lod,inventory,worst,flush=True)

if __name__=='__main__':
    for lod in ('near','far'):
        if '--lod' not in sys.argv or sys.argv[sys.argv.index('--lod')+1]==lod:run(lod)
