"""Independent, explicitly budgeted component reductions to half Jorge's triangles."""
import bpy,bmesh,json,math,hashlib,sys,csv,shutil
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import jorge_detail_pass as parent
import jorge_tactical_reduce as tactical
import jorge_shoulder_study as shoulder
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
import jorge_ce_materials as ce

ROOT=parent.ROOT;BASE=parent.BASE;OUT=BASE/'half-budget';SOURCE=parent.OUT/(parent.NAME+'.blend')
NAME='jorge-half-budget';SCENE='Jorge - half triangle budget'
# Each entry is an independent cap, indexed by stable physical component ID.
# Totals: 2,136 triangles; rounded down from 4,273 / 2.
GROUP_BUDGETS={
 'arms-01':[18,18,16,16,16,16], 'arms-04':[112,8], 'arms-05':[110],
 'arms-07':[26,26,10,10], 'arms-08':[66,66], 'arms-09':[24,24], 'arms-10':[8,8],
 'body-00':[104,8,8], 'body-02':[54,54,42,16,16], 'body-03':[268,32,18],
 'body-06':[76],
 'body-09':[44,42,18,18,18,18,28,28,32,32,22,22,8,8,12,8,8,8,9,9],
 'body-10':[36,20,20,20,24,18,18,28,28,12,12], 'backpack-14':[200,14],
}
BUDGETS={f'{group}:{i:03d}':n for group,values in GROUP_BUDGETS.items() for i,n in enumerate(values)}
assert len(BUDGETS)==64 and sum(BUDGETS.values())==2136
AR_SOURCE=ROOT/'halo64-assets/generated/model-preview.json'

def port_ar(ob):
    """Use exact expanded triangles/quantized RGB of the N64 world AR bank."""
    raw=json.loads(AR_SOURCE.read_text())['ar'];assert raw['triangle_count']==140
    # pack_assets.position is (Halo X, Halo Z, -Halo Y); the grip socket expects
    # raw Halo axes in meters. Invert packing, then apply the established scale.
    points=[(p[0]*animation.SCALE,-p[2]*animation.SCALE,p[1]*animation.SCALE) for p in raw['positions']]
    mesh=bpy.data.meshes.new('N64 port AR - exact packed triangles');mesh.from_pydata(points,[],[(i,i+1,i+2) for i in range(0,len(points),3)])
    colors=mesh.color_attributes.new(name='N64 packed RGB',type='FLOAT_COLOR',domain='CORNER')
    for color,rgb in zip(colors.data,raw['colors']):color.color_srgb=(*[x/255 for x in rgb],1)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8);bm.to_mesh(mesh);bm.free();mesh.update()
    mat=bpy.data.materials.new('N64 AR - original unlit vertex colors');mat.use_nodes=True;ns=mat.node_tree.nodes;ls=mat.node_tree.links;ns.clear()
    # Direct color-to-surface is Blender's implicit emission and is recognized
    # by its glTF exporter as KHR_materials_unlit (a plain Emission node is not).
    vertex=ns.new('ShaderNodeVertexColor');vertex.layer_name=colors.name;out=ns.new('ShaderNodeOutputMaterial');ls.new(vertex.outputs['Color'],out.inputs['Surface']);mesh.materials.append(mat)
    ob.data=mesh;ob.name='CE rifle - N64 port AR';ob['n64_weapon']='ar';ob['runtime_source_sha256']=hashlib.sha256(AR_SOURCE.read_bytes()).hexdigest();ob['weapon_triangles']=140
    return {'source':str(AR_SOURCE.relative_to(ROOT)),'sha256':ob['runtime_source_sha256'],'triangles':140,'appearance':'Original packed vertex RGB, unlit','attachment':'Existing b_r_grip socket and transform preserved'}

def body(scene):return [o for o in scene.objects if o.get('texture_variant')=='ce_spartan']

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith(SCENE));bpy.context.window.scene=scene
    return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def clean_geometry(ob):
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-12],context='FACES_ONLY')
    bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()

def transfer(ob,source):
    src=source.data;src.calc_loop_triangles();tris=list(src.loop_triangles)
    tree=BVHTree.FromPolygons([v.co for v in src.vertices],[t.vertices for t in tris],all_triangles=True)
    bone_names={g.index:g.name for g in source.vertex_groups if g.name.startswith('b_')}
    groups={g.name:g for g in ob.vertex_groups if g.name in bone_names.values()}
    for g in groups.values():g.remove(list(range(len(ob.data.vertices))))
    mapping=[];distances=[];clamped=0;largest_correction=0.
    for v in ob.data.vertices:
        hit,normal,ti,distance=tree.find_nearest(v.co);t=tris[ti]
        # Prevent low-budget concave torso/joint surfaces from drifting into
        # their cavities. Keep the QEM position unless over 20 mm off-surface.
        if distance>.020:
            correction=distance-.020;v.co=hit+(v.co-hit).normalized()*.020
            clamped+=1;largest_correction=max(largest_correction,correction)
            hit,normal,ti,distance=tree.find_nearest(v.co);t=tris[ti]
        bary=barycentric_transform(hit,*[src.vertices[i].co for i in t.vertices],Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
        bary=Vector([max(0.,min(1.,x)) for x in bary]);bary/=sum(bary);weights=defaultdict(float)
        for vi,factor in zip(t.vertices,bary):
            for g in src.vertices[vi].groups:
                if g.group in bone_names:weights[bone_names[g.group]]+=g.weight*factor
        weights=sorted(((n,w) for n,w in weights.items() if w>1e-6),key=lambda x:-x[1])[:4];total=sum(w for n,w in weights);assert total>0
        for name,w in weights:groups[name].add([v.index],w/total,'REPLACE')
        mapping.append((ti,tuple(bary)));distances.append(distance)
    # Sample component-local normals, retaining the decimator's interpolated UVs.
    uv=[u.uv.copy() for u in ob.data.uv_layers.active.data];shoulder.transfer_normals(ob,source)
    for u,co in zip(ob.data.uv_layers.active.data,uv):u.uv=co
    # Prior face/barycentric IDs no longer describe the new topology. Replace
    # them with correspondence to this exact, checkpointed parent component.
    for attr in list(ob.data.attributes):
        if attr.name.startswith(('nearest_source','source_barycentric','lod_parent','candidate_','reference_corner')):ob.data.attributes.remove(attr)
    a=ob.data.attributes.new('lod_parent_triangle','INT','POINT');a.data.foreach_set('value',[t for t,b in mapping])
    a=ob.data.attributes.new('lod_parent_barycentric','FLOAT_VECTOR','POINT');a.data.foreach_set('vector',[x for t,b in mapping for x in b])
    return {'max_vertex_to_parent_surface_m':max(distances),'mean_vertex_to_parent_surface_m':sum(distances)/len(distances),'surface_clamped_vertices':clamped,'largest_surface_correction_m':largest_correction}

def reduce_component(ob,source,budget):
    prepass=tactical.cleanup_mesh(ob)
    reasons=tactical.weights_for_reduction(ob);template=ob.data.copy();count=len(template.polygons);factor=1.2 if ob['group'] in ('body-03','body-06') else .5
    def attempt(ratio):
        previous=ob.data;ob.data=template.copy()
        if previous.users==0:bpy.data.meshes.remove(previous)
        shoulder.select(ob);mod=ob.modifiers.new('Independent component budget','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True;mod.vertex_group='Tactical reduction freedom';mod.vertex_group_factor=factor
        bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name);clean_geometry(ob)
        return len(ob.data.polygons)
    ratio=min(1.,(budget+.1)/count);actual=attempt(ratio);trials=[{'ratio':ratio,'triangles':actual}]
    # Some boundary/closed meshes skip odd counts. Keep the largest attainable
    # result under its own cap, never borrowing another component's allocation.
    best=(actual,ratio) if 0<actual<=budget else None;lo=ratio if actual<=budget else 0.;hi=1. if actual<=budget else ratio
    for _ in range(12):
        if actual==budget:break
        ratio=(lo+hi)/2;actual=attempt(ratio);trials.append({'ratio':ratio,'triangles':actual})
        if actual<=budget:
            lo=ratio
            if actual>0 and (best is None or actual>best[0]):best=(actual,ratio)
        else:hi=ratio
    assert best is not None,(ob['source_component'],budget,trials)
    if actual!=best[0]:actual=attempt(best[1])
    ob['half_budget']=True;ob['reduction_variant']='half_detail';ob['triangle_budget']=budget;ob['parent_triangle_count']=len(source.data.polygons);ob['prepass_triangle_count']=count;ob['actual_triangles']=actual
    for g in list(ob.vertex_groups):
        if not g.name.startswith('b_'):ob.vertex_groups.remove(g)
    result={'component':ob['source_component'],'group':ob['group'],'source_triangles':len(source.data.polygons),'prepass':prepass,'budget':budget,'actual_triangles':actual,'budget_met':actual<=budget,'native_vertices':len(ob.data.vertices),'collapse_ratio':best[1],'constraint_candidates':reasons,'search_trials':trials,**transfer(ob,source)}
    bpy.data.meshes.remove(template);return result

def build():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    shutil.copy2(SOURCE.parent/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    source,old_rig=parent.proof_scene();scene=bpy.data.scenes.new(SCENE);bpy.context.window.scene=scene;scene.render.fps=30
    rig=old_rig.copy();rig.data=old_rig.data.copy();rig.name='Jorge half budget - preserved shared rig';scene.collection.objects.link(rig);rig.data.pose_position='REST';rig.hide_set(True)
    records=[]
    for ob in source.objects:
        if ob.type!='MESH':continue
        new=ob.copy();new.data=ob.data.copy();scene.collection.objects.link(new);new.parent=rig;new.hide_set(False);new.hide_render=False
        for mod in new.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if ob.get('texture_variant')=='ce_spartan':
            key=ob['source_component'];new.name='Half budget / '+key;row=reduce_component(new,ob,BUDGETS[key]);records.append(row);print('COMPONENT',key,row['source_triangles'],'->',row['actual_triangles'],'cap',row['budget'],flush=True)
        else:weapon=port_ar(new)
    assert {r['component'] for r in records}==set(BUDGETS)
    rig.data.pose_position='POSE';cleanup.studio(scene);scene.camera.data.ortho_scale=2.95;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0)
    groups={g:{'label':cleanup.GROUP_NAMES[g],'source':sum(r['source_triangles'] for r in records if r['group']==g),'budget':sum(r['budget'] for r in records if r['group']==g),'actual':sum(r['actual_triangles'] for r in records if r['group']==g)} for g in GROUP_BUDGETS}
    report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_triangles':4273,'target_triangles':2136,'actual_triangles':sum(r['actual_triangles'] for r in records),'native_vertices':sum(r['native_vertices'] for r in records),'component_count':len(records),'budget_scope':'Body including backpack; rifle separate','method':'Compatible-position weld and conservative coplanar dissolve, then independent weighted component collapse; graded contour/UV/joint candidates; 20 mm vertex-to-parent surface clamp; interpolated UVs; component-local source normals and barycentric skin weights','weapon':weapon,'components':records,'groups':groups}
    (OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'component-budgets.json').write_text(json.dumps(BUDGETS,indent=2)+'\n')
    with (OUT/'component-budgets.csv').open('w') as f:
        fields=['component','group','source_triangles','budget','actual_triangles','native_vertices'];writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(records)
    actions={s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action}
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{scene,*actions},fake_user=True);print('HALF BUDGET BUILT',report['actual_triangles'],flush=True)

def export():
    # Reuse the background-only exporter with an explicit output/name override.
    scene,rig=proof_scene();records={r['component']:r for r in json.loads((OUT/'reduction-report.json').read_text())['components']}
    for ob in body(scene):
        row=records[ob['source_component']];ob['parent_triangle_count']=row['source_triangles'];ob['prepass_triangle_count']=row['prepass']['surgical_prepass']['triangles']
    for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
    parent.OUT=OUT;parent.NAME=NAME;parent.proof_scene=proof_scene;parent.export()

def render():ce.OUT=OUT;ce.proof_scene=proof_scene;ce.render()

def reference():
    # Re-render the checkpoint with the same port AR for a fair body comparison.
    if bpy.data.filepath==str(SOURCE):scene=next(s for s in bpy.data.scenes if s.name.startswith(parent.SCENE))
    else:
        with bpy.data.libraries.load(str(SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith(parent.SCENE)]
        scene=dst.scenes[0]
    bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
    port_ar(next(o for o in scene.objects if o.type=='MESH' and not o.get('texture_variant')))
    ref=OUT/'reference';ref.mkdir(exist_ok=True);ce.OUT=ref;ce.proof_scene=lambda:(scene,rig);ce.render()
    animation.OUT=ref;animation.proof_scene=lambda:(scene,rig);animation.render_motion()

if __name__=='__main__':
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:render()
    if '--motion' in sys.argv:animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
    if '--reference' in sys.argv:reference()
