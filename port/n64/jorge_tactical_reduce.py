"""Component-aware Jorge reduction; retain the shared-motion proof and source."""
import bpy,bmesh,json,math,sys,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
import jorge_shoulder_study as shoulder

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'tactical-5000'
SURFACE_FIRST='--projected-test' not in sys.argv
if '--surface-first' in sys.argv:OUT=ROOT/'build/jorge-inspection/tactical-surface-test'
RATIOS={'body-03':.38,'body-06':.75,'arms-04':.46,'arms-05':.42,'body-00':.30,'body-02':.30,'backpack-14':.32,'body-09':.26,'body-10':.22,'arms-01':.21,'arms-07':.30,'arms-08':.24,'arms-09':.28,'arms-10':.24,'jorge_decals-11':1.,'jorge_decals-12':1.,'jorge_decals-13':.65}

def stats(ob):
    me=ob.data;me.calc_loop_triangles();uv=me.uv_layers.active.data;normals=me.corner_normals
    unique=set((l.vertex_index,tuple(uv[l.index].uv),tuple(normals[l.index].vector),me.polygons[l.polygon_index].material_index if hasattr(l,'polygon_index') else 0) for l in me.loops)
    return {'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'corner_vertex_estimate':len(unique)}

def setup():
    source,original_rig=animation.proof_scene();scene=bpy.data.scenes.new('Jorge - tactical 5000 vertices');bpy.context.window.scene=scene;scene.render.fps=30
    rig=original_rig.copy();rig.data=original_rig.data.copy();rig.name='Jorge 5000 - retained animation rig';scene.collection.objects.link(rig);rig.hide_set(False)
    objects=[];references={}
    for ob in source.objects:
        if ob.type!='MESH':continue
        new=ob.copy();new.data=ob.data.copy();scene.collection.objects.link(new);new.parent=rig
        for mod in new.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if ob.get('variant')=='B':
            new.name='5000 / '+ob.name;new['reduction_variant']='tactical_5000';objects.append(new);references[new.name]=ob
        else:new.name='CE rifle - separate unchanged weapon'
        new.hide_render=False;new.hide_set(False)
    cleanup.studio(scene);scene.camera.data.ortho_scale=2.95;rig.data.pose_position='REST';return scene,rig,objects,references

def cleanup_mesh(ob):
    me=ob.data;before=stats(ob);normals=[n.vector.copy() for n in me.corner_normals]
    attr=me.attributes.new('reference_corner_normal','FLOAT_VECTOR','CORNER');attr.data.foreach_set('vector',[x for n in normals for x in n])
    bm=bmesh.new();bm.from_mesh(me);bm.verts.ensure_lookup_table();deform=bm.verts.layers.deform.active;lookup={};target={};bone_indices={g.index for g in ob.vertex_groups if g.name.startswith('b_')}
    for v in bm.verts:
        w=tuple((i,round(weight,6)) for i,weight in sorted(v[deform].items()) if i in bone_indices)
        key=(*[round(x,6) for x in v.co],w)
        if key in lookup:target[v]=lookup[key]
        else:lookup[key]=v
    if target:bmesh.ops.weld_verts(bm,targetmap=target)
    bm.normal_update()
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle()>math.radians(40):e.smooth=False
    welded=len(bm.verts)
    # Conservative coplanar/bevel redundancy pass before any collapse.
    bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(1.5),use_dissolve_boundaries=False,verts=list(bm.verts),edges=list(bm.edges),delimit={'NORMAL','MATERIAL','SEAM','SHARP','UV'})
    bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
    me.normals_split_custom_set([a.vector for a in me.attributes['reference_corner_normal'].data])
    return {'original':before,'welded_vertices':welded,'surgical_prepass':stats(ob)}

def weights_for_reduction(ob):
    """Candidate constraints are graded; physical components never merge."""
    me=ob.data;bm=bmesh.new();bm.from_mesh(me);bm.normal_update();bm.verts.ensure_lookup_table();deform=bm.verts.layers.deform.active
    bone_indices={g.index for g in ob.vertex_groups if g.name.startswith('b_')};importance=[0.]*len(bm.verts)
    def raise_weight(vs,value):
        for v in vs:importance[v.index]=max(importance[v.index],value)
    uv=bm.loops.layers.uv.active
    reasons=Counter()
    for e in bm.edges:
        if e.is_boundary:raise_weight(e.verts,.65);reasons['boundary']+=1
        elif e.is_manifold:
            angle=e.calc_face_angle()
            if angle>math.radians(55):raise_weight(e.verts,.75);reasons['major_contour']+=1
            elif angle>math.radians(30):raise_weight(e.verts,.35)
            a,b=e.link_loops
            au={a.vert.index:a[uv].uv,a.link_loop_next.vert.index:a.link_loop_next[uv].uv};bu={b.vert.index:b[uv].uv,b.link_loop_next.vert.index:b.link_loop_next[uv].uv}
            if any((au[i]-bu[i]).length>1e-4 for i in au):raise_weight(e.verts,.45);reasons['uv_seam']+=1
        va,vb=e.verts;wa={i:w for i,w in va[deform].items() if i in bone_indices};wb={i:w for i,w in vb[deform].items() if i in bone_indices}
        difference=sum(abs(wa.get(i,0)-wb.get(i,0)) for i in wa.keys()|wb.keys())
        if difference>.65:raise_weight(e.verts,.65);reasons['weight_transition']+=1
    bm.free();group=ob.vertex_groups.get('Tactical reduction freedom') or ob.vertex_groups.new(name='Tactical reduction freedom')
    for i,value in enumerate(importance):group.add([i],1-value,'REPLACE')
    return dict(reasons)

def probe():
    OUT.mkdir(exist_ok=True);scene,rig,objects,references=setup();records=[]
    for ob in objects:
        record={'name':ob.name,'group':ob['group'],'component':ob['source_component'],**cleanup_mesh(ob)};record['constraints']=weights_for_reduction(ob);records.append(record)
    report={'components':records,'totals':{stage:{k:sum(r[stage][k] for r in records) for k in ('vertices','triangles','corner_vertex_estimate')} for stage in ('original','surgical_prepass')},'groups':{}}
    for group in sorted({r['group'] for r in records}):
        rows=[r for r in records if r['group']==group];report['groups'][group]={'components':len(rows),'original_vertices':sum(r['original']['vertices'] for r in rows),'prepass_vertices':sum(r['surgical_prepass']['vertices'] for r in rows),'prepass_triangles':sum(r['surgical_prepass']['triangles'] for r in rows),'corner_vertex_estimate':sum(r['surgical_prepass']['corner_vertex_estimate'] for r in rows),'starting_ratio':RATIOS[group]}
    (OUT/'prepass-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='components'},indent=2),flush=True)
    bpy.data.libraries.write(str(OUT/'jorge-tactical-prepass.blend'),{scene,*bpy.data.actions},fake_user=True)

def source_surface(ob,source,project=True):
    """Component-local projection and barycentric skin transfer; no rig changes."""
    from mathutils.geometry import barycentric_transform
    src=source.data;src.calc_loop_triangles();tris=list(src.loop_triangles);tree=BVHTree.FromPolygons([v.co for v in src.vertices],[t.vertices for t in tris],all_triangles=True)
    bones={g.index:g.name for g in source.vertex_groups if g.name.startswith('b_')};target_bones={g.name:g for g in ob.vertex_groups if g.name.startswith('b_')}
    for group in target_bones.values():group.remove(list(range(len(ob.data.vertices))))
    projection=[];mapping=[]
    for v in ob.data.vertices:
        hit,normal,ti,distance=tree.find_nearest(v.co);t=tris[ti];projection.append(distance)
        if project:v.co=hit
        bary=barycentric_transform(hit,*[src.vertices[i].co for i in t.vertices],Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)));weights=defaultdict(float)
        bary=Vector([max(0,min(1,x)) for x in bary]);bary/=sum(bary)
        for vi,factor in zip(t.vertices,bary):
            for g in src.vertices[vi].groups:
                if g.group in bones:weights[bones[g.group]]+=g.weight*factor
        weights=sorted(((n,w) for n,w in weights.items() if w>1e-6),key=lambda nw:-nw[1])[:4];total=sum(w for n,w in weights);assert total>0
        for name,w in weights:target_bones[name].add([v.index],w/total,'REPLACE')
        mapping.append({'source_triangle':ti,'source_face':src.attributes['source_face'].data[t.polygon_index].value,'barycentric':list(bary)})
    ob.data.update();old_uv=[u.uv.copy() for u in ob.data.uv_layers.active.data];shoulder.transfer_normals(ob,source)
    if SURFACE_FIRST:
        for u,value in zip(ob.data.uv_layers.active.data,old_uv):u.uv=value
    # The old per-vertex and per-face integer IDs no longer describe new topology.
    for attr in list(ob.data.attributes):
        if attr.name.startswith(('source_','candidate_','reference_corner')):ob.data.attributes.remove(attr)
    a=ob.data.attributes.new('nearest_source_face','INT','POINT');a.data.foreach_set('value',[m['source_face'] for m in mapping]);a=ob.data.attributes.new('source_barycentric','FLOAT_VECTOR','POINT');a.data.foreach_set('vector',[x for m in mapping for x in m['barycentric']])
    return {'max_vertex_distance_from_source_m':max(projection,default=0),'mean_vertex_distance_from_source_m':sum(projection)/max(1,len(projection)),'vertex_projection_applied':project}

def reduce_object(ob,source,template,factor):
    previous=ob.data;ob.data=template.copy()
    if previous.users==0:bpy.data.meshes.remove(previous)
    group=ob['group'];n=stats(ob)['triangles'];ratio=min(1.,RATIOS[group]*factor)
    if n<32:ratio=1.
    else:ratio=max(ratio,12/n)
    # Reviewed silhouette floors: boot bodies must remain volumes, and the
    # backpack's rounded top fittings must not turn into triangular spikes.
    component=int(ob['source_component'].split(':')[-1])
    if group=='body-09' and 6<=component<=11:ratio=max(ratio,.34)
    if group=='body-10':
        if component in (7,8):ratio=max(ratio,.36)
        elif component in (9,10):ratio=max(ratio,.32)
        elif component in (5,6):ratio=max(ratio,.24)
        elif component==0:ratio=max(ratio,.18)
    if group=='backpack-14' and component>0:ratio=max(ratio,.50)
    if group=='backpack-14' and component==0:ratio=max(ratio,.35)
    if ratio<.999:
        shoulder.select(ob);mod=ob.modifiers.new('Tactical component collapse','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True;mod.vertex_group='Tactical reduction freedom';mod.vertex_group_factor=.5 if SURFACE_FIRST else 8.
        # Apply in the bind pose; the armature modifier remains intact.
        bpy.ops.object.modifier_move_up(modifier=mod.name)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-12],context='FACES_ONLY')
    bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(ob.data);bm.free();ob.data.update()
    transfer=source_surface(ob,source,project=not SURFACE_FIRST)
    transfer['reduction_topology_artifacts_removed']=repair_topology(ob)
    ob['reduction_ratio']=ratio;ob['reduction_factor']=factor;return {'name':ob.name,'group':group,'component':ob['source_component'],'ratio':ratio,**stats(ob),**transfer}

def repair_topology(ob):
    # The source helmet and two torso fittings have seven authored junctions.
    # Remove only new undersuit wire edges or ambiguous fans, preserving faces.
    if ob.get('source_component')!='body-10:001':return 0
    me=ob.data;normal=me.attributes.new('normal_before_topology_repair','FLOAT_VECTOR','CORNER');normal.data.foreach_set('vector',[x for n in me.corner_normals for x in n.vector])
    bm=bmesh.new();bm.from_mesh(me);wires=[e for e in bm.edges if not e.link_faces];count=len(wires)
    if wires:bmesh.ops.delete(bm,geom=wires,context='EDGES')
    edges=[e for e in bm.edges if not e.is_manifold and not e.is_boundary and e.link_faces];count+=len(edges)
    if edges:bmesh.ops.split_edges(bm,edges=edges)
    bm.to_mesh(me);bm.free();me.update();me.normals_split_custom_set([a.vector for a in me.attributes['normal_before_topology_repair'].data]);me.attributes.remove(me.attributes['normal_before_topology_repair']);return count

def repair_existing():
    scene,rig=proof_scene();report=json.loads((OUT/'reduction-report.json').read_text());changed=[]
    for ob in scene.objects:
        if ob.get('reduction_variant')!='tactical_5000':continue
        before=[tuple(ob.data.vertices[v].co) for f in ob.data.polygons for v in f.vertices];count=repair_topology(ob);after=[tuple(ob.data.vertices[v].co) for f in ob.data.polygons for v in f.vertices];assert before==after
        if count:
            changed.append({'component':ob['source_component'],'removed_wire_edges_or_split_fans':count,'face_corner_positions_unchanged':True})
            r=next(r for r in report['components'] if r['component']==ob['source_component']);r.update(stats(ob));r['reduction_topology_artifacts_removed']=count
    report['topology_repairs']=changed;report['totals']={k:sum(r[k] for r in report['components']) for k in ('vertices','triangles','corner_vertex_estimate')};(OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n');print('TOPOLOGY REPAIR',changed,report['totals'],flush=True)

def build():
    OUT.mkdir(exist_ok=True);scene,rig,objects,references=setup();templates={};prepass=[]
    for ob in objects:
        r=cleanup_mesh(ob);r.update({'name':ob.name,'group':ob['group'],'component':ob['source_component'],'constraints':weights_for_reduction(ob)});prepass.append(r);templates[ob.name]=ob.data.copy()
    # glTF merges tiny custom-normal differences that the conservative corner
    # estimate retains. The final accessor count is checked separately.
    target=5150;factor=1.;trials=[];best=None
    for attempt in range(7):
        records=[reduce_object(ob,references[ob.name],templates[ob.name],factor) for ob in objects];total=sum(r['corner_vertex_estimate'] for r in records);native=sum(r['vertices'] for r in records);triangles=sum(r['triangles'] for r in records)
        trials.append({'factor':factor,'corner_vertex_estimate':total,'vertices':native,'triangles':triangles});print('TRIAL',attempt,trials[-1],flush=True)
        if 5100<=total<=5180:break
        if total<=5180 and (best is None or total>best[0]):best=(total,factor)
        factor*=max(.45,min(1.7,(target/total)**1.12))
    if not 5100<=total<=5180 and best:
        factor=best[1];records=[reduce_object(ob,references[ob.name],templates[ob.name],factor) for ob in objects]
    report={'target_exported_body_vertices':5000,'budget_scope':'Jorge, backpack and retained decals; rifle counted separately','prepass':prepass,'trials':trials,'components':records,'totals':{k:sum(r[k] for r in records) for k in ('vertices','triangles','corner_vertex_estimate')},'source_sha256':hashlib.sha256((BASE/'animation-proof/jorge-animation-proof.blend').read_bytes()).hexdigest(),'method':'Semantic per-component budgets, compatible-position weld, limited coplanar dissolve, surface-error-first weighted collapse, retained interpolated UVs, chart-aware source normals, nearest-surface barycentric skin transfer'}
    rig.data.pose_position='POSE';rig.hide_set(True);scene.frame_start=0;scene.frame_end=230;scene.frame_set(0)
    for ob in scene.objects:ob.select_set(False)
    (OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.data.libraries.write(str(OUT/'jorge-tactical-5000.blend'),{scene,*bpy.data.actions},fake_user=True)
    print('BUILT',report['totals'],flush=True)

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - tactical 5000'));bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');return scene,rig

def render():
    scene,rig=proof_scene();folder=OUT/'renders';folder.mkdir(exist_ok=True);scene.render.resolution_x=600;scene.render.resolution_y=750;scene.cycles.samples=16;scene.cycles.use_denoising=True
    objects=[o for o in scene.objects if o.get('reduction_variant')=='tactical_5000'];original={o.name:list(o.data.materials) for o in objects};clay=shoulder.simple_material('Tactical clay')
    for style in ('textured','clay'):
        if style=='clay':
            for o in objects:o.data.materials.clear();o.data.materials.append(clay)
        for name,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
            action=next(a for a in bpy.data.actions if a.get('source_clip')==name);animation.select_clip(scene,rig,name,action['duration_seconds']*fraction)
            for view in (('front','back','left','right','three_quarter') if name=='idle' else ('three_quarter',)):
                cleanup.camera(scene,view);scene.render.filepath=str(folder/f'{style}-{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
        if style=='clay':
            for o in objects:
                o.data.materials.clear()
                for m in original[o.name]:o.data.materials.append(m)
    print('TACTICAL RENDER COMPLETE',flush=True)

def export():
    scene,rig=proof_scene();animation.select_clip(scene,rig,'idle');rig.hide_set(False)
    for ob in scene.objects:ob.select_set(ob.type in ('MESH','ARMATURE'))
    bpy.context.view_layer.objects.active=rig
    options=dict(export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False,export_frame_step=1,export_skins=True,export_extras=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-tactical-5000-with-rifle.glb'),**options)
    for ob in scene.objects:
        if ob.type=='MESH' and ob.get('reduction_variant')!='tactical_5000':ob.select_set(False)
    bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-tactical-5000.glb'),**options)
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0);rig.hide_set(True)
    for ob in scene.objects:ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-tactical-5000.blend'))
    print('TACTICAL EXPORT COMPLETE',flush=True)

if __name__=='__main__':
    if '--probe' in sys.argv:probe()
    if '--build' in sys.argv:build()
    if '--repair' in sys.argv:repair_existing()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:render()
    if '--motion' in sys.argv:
        animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
