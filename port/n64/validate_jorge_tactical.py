"""Rest/animated geometric and GLB validation for the tactical Jorge mesh."""
import bpy,bmesh,json,sys,math,struct,hashlib
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
import jorge_tactical_reduce as tactical
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
import jorge_shoulder_study as shoulder
OUT=tactical.OUT

def load_reference():
    path=tactical.BASE/'animation-proof/jorge-animation-proof.blend'
    if bpy.data.filepath==str(path):scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - CE animation proof'))
    else:
        with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith('Jorge - CE animation proof')]
        scene=dst.scenes[0]
    bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');return scene,rig

def key(ob):return ob.get('source_component')

def points(scene,objects):
    bpy.context.window.scene=scene;bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();result={}
    for ob in objects:
        ev=ob.evaluated_get(graph);me=ev.to_mesh();result[key(ob)]=np.array([tuple(ob.matrix_world@v.co) for v in me.vertices]);ev.to_mesh_clear()
    return result

def validate():
    scene,rig=tactical.proof_scene();objects=[o for o in scene.objects if o.get('reduction_variant')=='tactical_5000'];ref_scene,ref_rig=load_reference();refs={key(o):o for o in ref_scene.objects if o.get('variant')=='B'}
    reduction=json.loads((OUT/'reduction-report.json').read_text())
    report={'components':[],'clips':{},'source_geometry_unchanged':hashlib.sha256((tactical.BASE/'animation-proof/jorge-animation-proof.blend').read_bytes()).hexdigest()==reduction['source_sha256'],'motion_metric_note':'Source-correspondence deviation includes intended rest-geometry approximation and interpolated skinning; it is not a pure export or skin-weight error.'};mapping={};topology={};binding={}
    rig.data.pose_position='REST';ref_rig.data.pose_position='REST'
    for ob in objects:
        src=refs[key(ob)];me=ob.data;me.calc_loop_triangles();src.data.calc_loop_triangles();polys=[t.vertices for t in me.loop_triangles];src_polys=[t.vertices for t in src.data.loop_triangles]
        tree=BVHTree.FromPolygons([v.co for v in me.vertices],polys,all_triangles=True);src_tree=BVHTree.FromPolygons([v.co for v in src.data.vertices],src_polys,all_triangles=True)
        distances=[tree.find_nearest(v.co)[3] for v in src.data.vertices];distances += [tree.find_nearest(sum((src.data.vertices[v].co for v in f),Vector())/3)[3] for f in src_polys]
        reverse=[src_tree.find_nearest(sum((me.vertices[v].co for v in f),Vector())/3)[3] for f in polys]
        bm=bmesh.new();bm.from_mesh(me);bm.normal_update();health={'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'loose_vertices':sum(not v.link_faces for v in bm.verts),'wire_edges':sum(not e.link_faces for e in bm.edges),'nonmanifold_internal_edges':sum(not e.is_manifold and not e.is_boundary and bool(e.link_faces) for e in bm.edges),'boundary_edges':sum(e.is_boundary for e in bm.edges)};bm.free()
        assert health['zero_area_faces']==0 and health['loose_vertices']==0 and health['wire_edges']==0,(ob.name,health)
        assert len(me.uv_layers)==1 and all(math.isfinite(x) for uv in me.uv_layers.active.data for x in uv.uv)
        normal_lengths=[n.vector.length for n in me.corner_normals];assert min(normal_lengths)>.99 and max(normal_lengths)<1.01
        bones={g.index:g.name for g in ob.vertex_groups if g.name in rig.data.bones};weight_error=0;max_influences=0
        for v in me.vertices:
            ws=[g.weight for g in v.groups if g.group in bones and g.weight>0];weight_error=max(weight_error,abs(sum(ws)-1));max_influences=max(max_influences,len(ws))
        assert weight_error<1e-6 and max_influences<=4
        source_face={a.value:f for a,f in zip(src.data.attributes['source_face'].data,src.data.polygons)}
        indices=np.array([source_face[a.value].vertices[:] for a in me.attributes['nearest_source_face'].data]);bary=np.array([a.vector for a in me.attributes['source_barycentric'].data]);mapping[key(ob)]=(indices,bary)
        r={'component':key(ob),'group':ob['group'],**tactical.stats(ob),'source_to_reduced_max_m':max(distances),'source_to_reduced_p95_m':float(np.percentile(distances,95)),'source_to_reduced_mean_m':float(np.mean(distances)),'reduced_face_centers_to_source_max_m':max(reverse),'max_weight_sum_error':weight_error,'max_bone_influences':max_influences,**health};report['components'].append(r)
    rig.data.pose_position='POSE';ref_rig.data.pose_position='POSE';native_actions={name:next(a for a in bpy.data.actions if a.get('source_clip')==name) for name in animation.CLIPS}
    for name in animation.CLIPS:
        duration=native_actions[name]['duration_seconds'];errors=[];minimum_z=100.;maximum=0
        for frame in range(round(duration*30)+1):
            bpy.context.window.scene=scene;animation.select_clip(scene,rig,name,frame/30);a=points(scene,objects)
            bpy.context.window.scene=ref_scene;animation.select_clip(ref_scene,ref_rig,name,frame/30);b=points(ref_scene,list(refs.values()))
            per_frame=[]
            for k,values in a.items():
                indices,bary=mapping[k];expected=(b[k][indices]*bary[:,:,None]).sum(axis=1);d=np.linalg.norm(values-expected,axis=1);assert np.isfinite(values).all();maximum=max(maximum,float(d.max()));per_frame.extend(d.tolist());minimum_z=min(minimum_z,float(values[:,2].min()))
            errors.extend(per_frame)
        report['clips'][name]={'samples':round(duration*30)+1,'barycentric_deformation_max_error_m':maximum,'barycentric_deformation_p95_error_m':float(np.percentile(errors,95)),'barycentric_deformation_mean_error_m':float(np.mean(errors)),'minimum_z_m':minimum_z};print('POSE VALIDATION',name,report['clips'][name],flush=True)
    report['bones']=len(rig.data.bones);assert report['bones']==85
    (OUT/'geometry-motion-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('TACTICAL GEOMETRY VALIDATED',flush=True)

def reference_renders():
    scene,rig=load_reference();objects=[o for o in scene.objects if o.get('variant')=='B'];original={o.name:list(o.data.materials) for o in objects};clay=shoulder.simple_material('Reference clay')
    scene.render.resolution_x=600;scene.render.resolution_y=750;scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.camera.data.ortho_scale=2.95
    for style in ('textured','clay'):
        if style=='clay':
            for ob in objects:ob.data.materials.clear();ob.data.materials.append(clay)
        for name,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
            action=next(a for a in bpy.data.actions if a.get('source_clip')==name);animation.select_clip(scene,rig,name,action['duration_seconds']*fraction)
            for view in (('front','back','left','right','three_quarter') if name=='idle' else ('three_quarter',)):
                cleanup.camera(scene,view);scene.render.filepath=str(OUT/'renders'/f'source-{style}-{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    print('REFERENCE RENDERS COMPLETE',flush=True)

def glb_inventory():
    b=(OUT/'jorge-tactical-5000.glb').read_bytes();size=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+size]);counts={}
    for label,nodes in [('jorge',[n for n in d['nodes'] if 'mesh' in n and 'skin' in n]),('rifle',[n for n in d['nodes'] if 'mesh' in n and 'skin' not in n])]:
        primitives=[p for n in nodes for p in d['meshes'][n['mesh']]['primitives']];counts[label]={'vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in primitives),'triangles':sum(d['accessors'][p['indices']]['count']//3 for p in primitives),'mesh_objects':len(nodes)}
    counts['animations']=[a['name'] for a in d['animations']];counts['joints']=len(d['skins'][0]['joints']);counts['materials']=len(d['materials']);counts['embedded_images']=len(d['images']);assert counts['jorge']['vertices']<=5000,counts
    (OUT/'export-inventory.json').write_text(json.dumps(counts,indent=2)+'\n');print('EXPORTED COUNTS',json.dumps(counts),flush=True)

def roundtrip():
    scene,rig=tactical.proof_scene();objects=[o for o in scene.objects if o.get('reduction_variant')=='tactical_5000'];weapon=next(o for o in scene.objects if o.name.startswith('CE rifle'));rig.animation_data.use_nla=False
    actions={name:next(a for a in bpy.data.actions if a.get('source_clip')==name) for name in animation.CLIPS};old_actions=set(bpy.data.actions)
    imported_scene=bpy.data.scenes.new('Tactical GLB validation');imported_scene.render.fps=30;bpy.context.window.scene=imported_scene;bpy.ops.import_scene.gltf(filepath=str(OUT/'jorge-tactical-5000-with-rifle.glb'))
    imported_rig=next(o for o in imported_scene.objects if o.type=='ARMATURE');imported_rig.animation_data.use_nla=False;imported=[o for o in imported_scene.objects if o.get('reduction_variant')=='tactical_5000'];imported_weapon=next(o for o in imported_scene.objects if o.type=='MESH' and o.name.startswith('CE rifle'))
    imported_actions={name:next(a for a in set(bpy.data.actions)-old_actions if a.name.startswith('Jorge / '+name)) for name in animation.CLIPS}
    assert len(imported)==110 and len(imported_rig.data.bones)==85
    def distance(a,b):
        tree=KDTree(len(a))
        for i,p in enumerate(a):tree.insert(p,i)
        tree.balance();return max(tree.find(p)[2] for p in b)
    report={}
    for name,action in actions.items():
        count=round(action['duration_seconds']*30)+1;error=reverse=weapon_error=0.
        for frame in range(count):
            bpy.context.window.scene=scene;rig.animation_data.action=action;scene.frame_set(frame);a=points(scene,objects);wa=weapon.matrix_world.copy()
            bpy.context.window.scene=imported_scene;imported_rig.animation_data.action=imported_actions[name];imported_scene.frame_set(frame);b=points(imported_scene,imported);wb=imported_weapon.matrix_world.copy()
            for k in a:error=max(error,distance(a[k],b[k]));reverse=max(reverse,distance(b[k],a[k]))
            weapon_error=max(weapon_error,max(abs(wa[i][j]-wb[i][j]) for i in range(4) for j in range(4)))
        assert error<.0003 and reverse<.0003 and weapon_error<.0003,(name,error,reverse,weapon_error)
        report[name]={'samples':count,'max_export_to_blender_vertex_error_m':error,'max_blender_to_export_vertex_error_m':reverse,'max_weapon_matrix_error':weapon_error};print('GLB ROUNDTRIP',name,report[name],flush=True)
    (OUT/'roundtrip-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('TACTICAL GLB VERIFIED',flush=True)

def silhouettes():
    target,rig=tactical.proof_scene();source,ref_rig=load_reference()
    mat=bpy.data.materials.new('Body silhouette');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear();out=ns.new('ShaderNodeOutputMaterial');em=ns.new('ShaderNodeEmission');em.inputs[0].default_value=(1,1,1,1);mat.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
    for label,scene,arm in [('reduced',target,rig),('source',source,ref_rig)]:
        bpy.context.window.scene=scene;scene.view_layers[0].material_override=mat;scene.render.resolution_x=480;scene.render.resolution_y=600;scene.cycles.samples=1;scene.render.film_transparent=True;scene.camera.data.ortho_scale=2.95
        for ob in scene.objects:
            if ob.type=='MESH' and ob.get('variant')!='B':ob.hide_render=True
        for name,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
            action=next(a for a in bpy.data.actions if a.get('source_clip')==name);animation.select_clip(scene,arm,name,action['duration_seconds']*fraction)
            for view in (('front','back','left','right','three_quarter') if name=='idle' else ('three_quarter',)):
                cleanup.camera(scene,view);scene.render.filepath=str(OUT/'renders'/f'mask-{label}-{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    print('BODY SILHOUETTES COMPLETE',flush=True)

if __name__=='__main__':
    if '--validate' in sys.argv:validate()
    if '--reference-renders' in sys.argv:reference_renders()
    if '--inventory' in sys.argv:glb_inventory()
    if '--roundtrip' in sys.argv:roundtrip()
    if '--silhouettes' in sys.argv:silhouettes()
