"""Verify the CE material pass preserves retained geometry and shared animation."""
import bpy,json,struct,hashlib,math,sys
import numpy as np
from mathutils.kdtree import KDTree
import jorge_ce_materials as ce
import jorge_animation_proof as animation
from validate_jorge_tactical import points

OUT=ce.OUT

def actions_for(rig):
    return {strip.action['source_clip']:strip.action for track in rig.animation_data.nla_tracks for strip in track.strips if strip.action and strip.action.get('source_clip')}

def inventory():
    path=OUT/'jorge-ce-materials.glb';raw=path.read_bytes();size=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+size])
    primitives=[p for m in d['meshes'] for p in m['primitives']]
    result={'body_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in primitives),'body_triangles':sum(d['accessors'][p['indices']]['count']//3 for p in primitives),'body_components':len(d['meshes']),'bones':len(d['skins'][0]['joints']),'materials':len(d['materials']),'embedded_images':len(d['images']),'animations':[a['name'] for a in d['animations']],'glb_bytes':len(raw),'normal_maps':sum('normalTexture' in m for m in d['materials'])}
    binary_start=20+size+8;images=[]
    for im in d['images']:
        view=d['bufferViews'][im['bufferView']];start=binary_start+view.get('byteOffset',0);png=raw[start:start+view['byteLength']];assert png[:8]==b'\x89PNG\r\n\x1a\n'
        images.append({'name':im['name'],'resolution':list(struct.unpack_from('>II',png,16)),'bytes':len(png)})
    result['images']=images
    assert result['materials']==2 and result['embedded_images']==1 and result['normal_maps']==0
    assert result['body_vertices']<=5000 and result['bones']==85 and images[0]['resolution']==[256,256]
    assert len(result['animations'])==4 and result['body_components']==99
    (OUT/'export-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print('CE INVENTORY',result,flush=True)

def preservation():
    scene,rig=ce.proof_scene();body={o['source_component']:o for o in scene.objects if o.get('texture_variant')=='ce_spartan'};actions=actions_for(rig)
    with bpy.data.libraries.load(str(ce.SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith('Jorge - tactical 5000')]
    reference=dst.scenes[0];ref_rig=next(o for o in reference.objects if o.type=='ARMATURE');ref_actions=actions_for(ref_rig);refs={o['source_component']:o for o in reference.objects if o.get('reduction_variant')=='tactical_5000'}
    source_report=json.loads((OUT/'material-report.json').read_text());assert hashlib.sha256(ce.SOURCE.read_bytes()).hexdigest()==source_report['source_blend_sha256']
    for path,digest in source_report['donor_images'].items():assert hashlib.sha256((ce.ROOT/path).read_bytes()).hexdigest()==digest
    assert set(refs)-set(body)=={r['component'] for r in source_report['retired_decal_overlays']}
    assert [b.name for b in rig.data.bones]==[b.name for b in ref_rig.data.bones]
    for a,b in zip(rig.data.bones,ref_rig.data.bones):
        assert (a.parent.name if a.parent else None)==(b.parent.name if b.parent else None)
        assert a.matrix_local==b.matrix_local
    counts={'vertices':0,'triangles':0};normal_error=0.;weight_error=0.
    def weights(ob,v):return {ob.vertex_groups[g.group].name:g.weight for g in v.groups}
    for key,ob in body.items():
        src=refs[key];a=ob.data;b=src.data
        assert len(a.vertices)==len(b.vertices) and [tuple(f.vertices) for f in a.polygons]==[tuple(f.vertices) for f in b.polygons]
        for v,w in zip(a.vertices,b.vertices):
            assert v.co==w.co;wa=weights(ob,v);wb=weights(src,w);assert wa.keys()==wb.keys();weight_error=max(weight_error,max((abs(wa[k]-wb[k]) for k in wa),default=0.))
        for n,m in zip(a.corner_normals,b.corner_normals):normal_error=max(normal_error,(n.vector-m.vector).length)
        assert all(math.isfinite(c) and 0<=c<=1 for uv in a.uv_layers.active.data for c in uv.uv)
        assert len(a.materials)==1 and all(p.material_index==0 for p in a.polygons)
        counts['vertices']+=len(a.vertices);counts['triangles']+=len(a.polygons)
    assert weight_error==0 and normal_error<1e-6,(weight_error,normal_error)
    for arm in (rig,ref_rig):arm.data.pose_position='POSE';arm.animation_data.use_nla=False
    clip_report={}
    for name in animation.CLIPS:
        maximum=0.;samples=round(actions[name]['duration_seconds']*30)+1
        assert actions[name]['duration_seconds']==ref_actions[name]['duration_seconds']
        for frame in range(samples):
            bpy.context.window.scene=scene;rig.animation_data.action=actions[name];scene.frame_set(frame);a=points(scene,list(body.values()))
            bpy.context.window.scene=reference;ref_rig.animation_data.action=ref_actions[name];reference.frame_set(frame);b=points(reference,[refs[k] for k in body])
            for k in body:
                assert np.isfinite(a[k]).all();maximum=max(maximum,float(np.linalg.norm(a[k]-b[k],axis=1).max()))
        assert maximum<1e-7,(name,maximum);clip_report[name]={'samples':samples,'max_position_change_m':maximum};print('CE PRESERVATION',name,clip_report[name],flush=True)
    report={'source_blend_and_donor_hashes_unchanged':True,'retained_components':len(body),'retired_decal_components':len(refs)-len(body),'retired_decal_triangles':sum(r['triangles'] for r in source_report['retired_decal_overlays']),'retained_positions_and_topology_exact':True,'bones_and_bind_matrices_exact':True,'max_weight_change':weight_error,'max_corner_normal_change':normal_error,'counts':counts,'clips':clip_report}
    (OUT/'preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')

def roundtrip():
    scene,rig=ce.proof_scene();body=[o for o in scene.objects if o.get('texture_variant')=='ce_spartan'];weapon=next(o for o in scene.objects if o.name.startswith('CE rifle'));actions=actions_for(rig);rig.animation_data.use_nla=False;old_actions=set(bpy.data.actions)
    imported_scene=bpy.data.scenes.new('CE material GLB verification');imported_scene.render.fps=30;bpy.context.window.scene=imported_scene;bpy.ops.import_scene.gltf(filepath=str(OUT/'jorge-ce-materials-with-rifle.glb'))
    imported_rig=next(o for o in imported_scene.objects if o.type=='ARMATURE');imported_rig.animation_data.use_nla=False;imported=[o for o in imported_scene.objects if o.get('texture_variant')=='ce_spartan'];imported_weapon=next(o for o in imported_scene.objects if o.type=='MESH' and o.name.startswith('CE rifle'))
    imported_actions={name:next(a for a in set(bpy.data.actions)-old_actions if a.name.startswith('Jorge / '+name)) for name in animation.CLIPS}
    assert len(imported)==99 and len(imported_rig.data.bones)==85
    def distance(a,b):
        tree=KDTree(len(a))
        for i,p in enumerate(a):tree.insert(p,i)
        tree.balance();return max(tree.find(p)[2] for p in b)
    report={}
    for name,action in actions.items():
        count=round(action['duration_seconds']*30)+1;error=reverse=weapon_error=0.
        for frame in range(count):
            bpy.context.window.scene=scene;rig.animation_data.action=action;scene.frame_set(frame);a=points(scene,body);wa=weapon.matrix_world.copy()
            bpy.context.window.scene=imported_scene;imported_rig.animation_data.action=imported_actions[name];imported_scene.frame_set(frame);b=points(imported_scene,imported);wb=imported_weapon.matrix_world.copy()
            for k in a:error=max(error,distance(a[k],b[k]));reverse=max(reverse,distance(b[k],a[k]))
            weapon_error=max(weapon_error,max(abs(wa[i][j]-wb[i][j]) for i in range(4) for j in range(4)))
        assert error<.0003 and reverse<.0003 and weapon_error<.0003,(name,error,reverse,weapon_error)
        report[name]={'samples':count,'max_export_to_blender_vertex_error_m':error,'max_blender_to_export_vertex_error_m':reverse,'max_weapon_matrix_error':weapon_error};print('CE ROUNDTRIP',name,report[name],flush=True)
    (OUT/'roundtrip-validation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    if '--inventory' in sys.argv:inventory()
    if '--preservation' in sys.argv:preservation()
    if '--roundtrip' in sys.argv:roundtrip()
