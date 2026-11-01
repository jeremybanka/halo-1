"""Exact retained-surface/skin checks, sampled silhouettes and GLB round trip."""
import bpy,bmesh,json,math,struct,hashlib,sys
import numpy as np
from mathutils.kdtree import KDTree
import jorge_detail_pass as task
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
from validate_jorge_ce_materials import actions_for
from validate_jorge_tactical import points

OUT=task.OUT

def load_reference():
    with bpy.data.libraries.load(str(task.SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith('Jorge - CE texture simplification')]
    scene=dst.scenes[0];return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def inventory():
    raw=(OUT/(task.NAME+'.glb')).read_bytes();size=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+size]);ps=[p for m in d['meshes'] for p in m['primitives']]
    result={'body_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'body_triangles':sum(d['accessors'][p['indices']]['count']//3 for p in ps),'body_components':len(d['meshes']),'bones':len(d['skins'][0]['joints']),'materials':len(d['materials']),'images':len(d['images']),'animations':[a['name'] for a in d['animations']],'glb_bytes':len(raw),'normal_maps':sum('normalTexture' in m for m in d['materials'])}
    assert result['body_components']==64 and result['body_triangles']==4273 and result['body_vertices']<4403
    assert result['bones']==85 and result['materials']==2 and result['images']==1 and result['normal_maps']==0
    assert len(result['animations'])==4
    (OUT/'export-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print('INVENTORY',result,flush=True)

def health(ob):
    bm=bmesh.new();bm.from_mesh(ob.data)
    r={'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'loose_vertices':sum(not v.link_faces for v in bm.verts),'wire_edges':sum(not e.link_faces for e in bm.edges),'nonmanifold_internal_edges':sum(not e.is_manifold and not e.is_boundary and bool(e.link_faces) for e in bm.edges),'boundary_edges':sum(e.is_boundary for e in bm.edges)};bm.free();return r

def preservation():
    scene,rig=task.proof_scene();reference,ref_rig=load_reference();body={o['source_component']:o for o in task.body(scene)};refs={o['source_component']:o for o in task.body(reference)};actions=actions_for(rig);ref_actions=actions_for(ref_rig)
    r=json.loads((OUT/'detail-report.json').read_text());assert hashlib.sha256(task.SOURCE.read_bytes()).hexdigest()==r['source_blend_sha256'];assert hashlib.sha256(task.HELMET_SOURCE.read_bytes()).hexdigest()==r['helmet_uv_source_sha256']
    for p,digest in r['source_images'].items():assert hashlib.sha256((task.ROOT/p).read_bytes()).hexdigest()==digest
    assert set(refs)-set(body)==set(task.CULL)
    assert [b.name for b in rig.data.bones]==[b.name for b in ref_rig.data.bones]
    for a,b in zip(rig.data.bones,ref_rig.data.bones):
        assert (a.parent.name if a.parent else None)==(b.parent.name if b.parent else None);assert a.matrix_local==b.matrix_local
    def weights(ob,v):return {ob.vertex_groups[g.group].name:g.weight for g in v.groups}
    component_checks=[]
    for key,ob in body.items():
        src=refs[key];a=ob.data;b=src.data;assert len(a.vertices)==len(b.vertices)
        assert [tuple(f.vertices) for f in a.polygons]==[tuple(f.vertices) for f in b.polygons]
        for v,w in zip(a.vertices,b.vertices):assert v.co==w.co and weights(ob,v)==weights(src,w)
        assert all(n.vector==m.vector for n,m in zip(a.corner_normals,b.corner_normals))
        h=health(ob);assert h==health(src) and not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges'])
        assert all(math.isfinite(x) and 0<=x<=1 for uv in a.uv_layers.active.data for x in uv.uv)
        assert len(a.materials)==1 and all(f.material_index==0 for f in a.polygons)
        component_checks.append({'component':key,**h})
    for arm in (rig,ref_rig):arm.data.pose_position='POSE';arm.animation_data.use_nla=False
    clips={}
    for name in animation.CLIPS:
        maximum=0.;samples=round(actions[name]['duration_seconds']*30)+1
        for frame in range(samples):
            bpy.context.window.scene=scene;rig.animation_data.action=actions[name];scene.frame_set(frame);a=points(scene,list(body.values()))
            bpy.context.window.scene=reference;ref_rig.animation_data.action=ref_actions[name];reference.frame_set(frame);b=points(reference,[refs[k] for k in body])
            for k in body:maximum=max(maximum,float(np.linalg.norm(a[k]-b[k],axis=1).max()));assert np.isfinite(a[k]).all()
        assert maximum==0.;clips[name]={'samples':samples,'max_position_change_m':maximum};print('PRESERVATION',name,clips[name],flush=True)
    report={'sources_unchanged':True,'retained_positions_topology_weights_normals_exact':True,'bone_hierarchy_and_bind_matrices_exact':True,'retained_components':len(body),'removed_components':len(task.CULL),'component_health':component_checks,'clips':clips}
    (OUT/'preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')

def roundtrip():
    scene,rig=task.proof_scene();body=task.body(scene);weapon=next(o for o in scene.objects if o.name.startswith('CE rifle'));actions=actions_for(rig);rig.animation_data.use_nla=False;old_actions=set(bpy.data.actions)
    other=bpy.data.scenes.new('Detail GLB verification');other.render.fps=30;bpy.context.window.scene=other;bpy.ops.import_scene.gltf(filepath=str(OUT/(task.NAME+'-with-rifle.glb')))
    irig=next(o for o in other.objects if o.type=='ARMATURE');irig.animation_data.use_nla=False;imported=task.body(other);iw=next(o for o in other.objects if o.type=='MESH' and o.name.startswith('CE rifle'))
    ia={name:next(a for a in set(bpy.data.actions)-old_actions if a.name.startswith('Jorge / '+name)) for name in animation.CLIPS};assert len(imported)==len(body) and len(irig.data.bones)==85
    def distance(a,b):
        tree=KDTree(len(a))
        for i,p in enumerate(a):tree.insert(p,i)
        tree.balance();return max(tree.find(p)[2] for p in b)
    report={}
    for name,action in actions.items():
        count=round(action['duration_seconds']*30)+1;error=reverse=weapon_error=0.
        for frame in range(count):
            bpy.context.window.scene=scene;rig.animation_data.action=action;scene.frame_set(frame);a=points(scene,body);wa=weapon.matrix_world.copy()
            bpy.context.window.scene=other;irig.animation_data.action=ia[name];other.frame_set(frame);b=points(other,imported);wb=iw.matrix_world.copy()
            for k in a:error=max(error,distance(a[k],b[k]));reverse=max(reverse,distance(b[k],a[k]))
            weapon_error=max(weapon_error,max(abs(wa[i][j]-wb[i][j]) for i in range(4) for j in range(4)))
        assert max(error,reverse,weapon_error)<.0003,(name,error,reverse,weapon_error)
        report[name]={'samples':count,'max_export_to_native_vertex_error_m':error,'max_native_to_export_vertex_error_m':reverse,'max_weapon_matrix_error':weapon_error};print('ROUNDTRIP',name,report[name],flush=True)
    (OUT/'roundtrip-validation.json').write_text(json.dumps(report,indent=2)+'\n')

def silhouettes():
    target,rig=task.proof_scene();source,ref=load_reference()
    mat=bpy.data.materials.new('Body silhouette');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear();out=ns.new('ShaderNodeOutputMaterial');em=ns.new('ShaderNodeEmission');em.inputs[0].default_value=(1,1,1,1);mat.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
    for label,scene,arm in [('after',target,rig),('before',source,ref)]:
        bpy.context.window.scene=scene;scene.view_layers[0].material_override=mat;scene.render.resolution_x=480;scene.render.resolution_y=600;scene.cycles.samples=1;scene.render.film_transparent=True;scene.camera.data.ortho_scale=2.95
        for ob in scene.objects:
            if ob.type=='MESH' and ob.get('texture_variant')!='ce_spartan':ob.hide_render=True
        actions=actions_for(arm);arm.animation_data.use_nla=False
        for name,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
            arm.animation_data.action=actions[name];f=actions[name]['duration_seconds']*30*fraction;scene.frame_set(int(f),subframe=f-int(f))
            for view in (('front','back','left','right','three_quarter') if name=='idle' else ('three_quarter',)):
                cleanup.camera(scene,view);scene.render.filepath=str(OUT/'renders'/f'mask-{label}-{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    print('SILHOUETTE RENDERS COMPLETE',flush=True)

if __name__=='__main__':
    if '--inventory' in sys.argv:inventory()
    if '--preservation' in sys.argv:preservation()
    if '--roundtrip' in sys.argv:roundtrip()
    if '--silhouettes' in sys.argv:silhouettes()
