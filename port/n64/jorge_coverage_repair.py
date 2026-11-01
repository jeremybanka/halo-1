"""Local clearance and overlapping garment seams on the accepted solid Jorge.

No reduction is performed here. Original armor surfaces, UVs and skinning are
copied; fitted backing closes garment openings beneath adjoining plates.
"""
import bpy, bmesh, json, sys, hashlib, shutil, csv
from mathutils import Vector
import jorge_solid_reduce as solid
import jorge_detail_pass as exporter
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
import jorge_ce_materials as ce

ROOT=solid.ROOT; BASE=solid.BASE; OUT=BASE/'coverage-repair'
SOURCE=solid.OUT/(solid.NAME+'.blend')
NAME='jorge-coverage-repair'; SCENE='Jorge - repaired coverage and collar'
body=solid.body; count=solid.count; topology=solid.topology

def proof_scene():
    s=next(s for s in bpy.data.scenes if s.name.startswith(SCENE));bpy.context.window.scene=s
    return s,next(o for o in s.objects if o.type=='ARMATURE')

def close_backing(ob):
    """Close garment openings inside the armor, retaining their authored rims.

    Added center points lie inside the existing armor and use the rim's skinning
    (rigid upper-leg weights for thigh backing). Existing UVs are exact and
    custom normals are reapplied with Blender's normal-encoding precision.
    """
    old=ob.data;bm=bmesh.new();bm.from_mesh(old);bm.verts.ensure_lookup_table()
    key=ob['source_component'];edges=[]
    for e in bm.edges:
        if e.is_boundary and (key!='body-10:000' or all(v.co.z<1.35 for v in e.verts)):
            l=e.link_loops[0];edges.append((l.vert.index,l.link_loop_next.vert.index))
    bm.free();remaining={i for edge in edges for i in edge};loops=[]
    while remaining:
        stack=[remaining.pop()];ids=[]
        while stack:
            i=stack.pop();ids.append(i)
            for a,b in edges:
                if i not in (a,b):continue
                j=b if a==i else a
                if j in remaining:remaining.remove(j);stack.append(j)
        loops.append(ids)
    names=[g.name for g in ob.vertex_groups];weights=[[(g.group,g.weight) for g in v.groups] for v in old.vertices]
    vertices=[v.co.copy() for v in old.vertices];faces=[tuple(p.vertices) for p in old.polygons]
    uv=[u.uv.copy() for u in old.uv_layers.active.data];ns=[n.vector.copy() for n in old.corner_normals]
    vu={l.vertex_index:uv[l.index] for l in old.loops};vn={l.vertex_index:ns[l.index] for l in old.loops};patches=[]
    for ids in loops:
        selected=[(a,b) for a,b in edges if a in ids];ci=len(vertices)
        center=sum((vertices[i] for i in ids),Vector())/len(ids)
        totals={}
        for i in ids:
            for g,w in weights[i]:totals[g]=totals.get(g,0)+w
        cw=sorted(totals.items(),key=lambda x:-x[1])[:4];total=sum(w for g,w in cw);cw=[(g,w/total) for g,w in cw]
        if key=='body-10:000':
            sign=1 if center.x>0 else -1;side='l' if sign>0 else 'r'
            center=Vector((sign*.245,-.025,1.12));cw=[(names.index('b_'+side+'_upperleg_jiggle'),1.)]
        elif key=='body-10:001' and center.y<-.15:
            center.y+=.025  # Behind the yellow breastplate.
        vertices.append(center);weights.append(cw)
        center_uv=sum((vu[i] for i in ids),Vector((0.,0.)))/len(ids)
        center_n=sum((vn[i] for i in ids),Vector()).normalized()
        if center_n.length<.9:center_n=vn[ids[0]]
        for a,b in selected:
            faces.append((b,a,ci));uv.extend((vu[b],vu[a],center_uv));ns.extend((vn[b],vn[a],center_n))
        patches.append({'rim':ids,'center':tuple(center),'center_weights':{names[g]:w for g,w in cw},'triangles':len(selected)})
    me=bpy.data.meshes.new(old.name+' / fitted backing');me.from_pydata(vertices,[],faces)
    for mat in old.materials:me.materials.append(mat)
    layer=me.uv_layers.new(name=old.uv_layers.active.name)
    for d,a in zip(layer.data,uv):d.uv=a
    for p in me.polygons:p.use_smooth=True
    me.normals_split_custom_set(ns);ob.data=me
    if not len(ob.vertex_groups):
        for name in names:ob.vertex_groups.new(name=name)
    for i,ws in enumerate(weights):
        for g,w in ws:ob.vertex_groups[g].add([i],w,'REPLACE')
    return {'operation':'fitted garment backing inside armor openings','added_native_vertices':len(loops),'added_triangles':len(edges),'original_perimeter_and_weights_unchanged':True,'patches':patches}

def rump_return(ob,garment):
    """One contour-fitted triangle bridges the tagged left rump seam.

    The armor's long straight rim skipped a bend in the adjacent fabric rim.
    Fit that bend instead of inflating the whole thigh or deleting fabric.
    """
    old=ob.data;bm=bmesh.new();bm.from_mesh(old);bm.verts.ensure_lookup_table()
    edge=next(e for e in bm.edges if {v.index for v in e.verts}=={8,9});assert edge.is_boundary
    l=edge.link_loops[0];a,b=l.vert.index,l.link_loop_next.vert.index;bm.free()
    point=garment.data.vertices[44].co+Vector((.008,.012,.002));ci=len(old.vertices)
    names=[g.name for g in ob.vertex_groups];weights=[[(g.group,g.weight) for g in v.groups] for v in old.vertices]
    weights.append([(names.index('b_l_upperleg_jiggle'),1.)])
    uv=[u.uv.copy() for u in old.uv_layers.active.data];ns=[n.vector.copy() for n in old.corner_normals]
    vu={l.vertex_index:uv[l.index] for l in old.loops};vn={l.vertex_index:ns[l.index] for l in old.loops}
    t=max(0,min(1,(point-old.vertices[a].co).dot(old.vertices[b].co-old.vertices[a].co)/(old.vertices[b].co-old.vertices[a].co).length_squared))
    uv.extend((vu[b],vu[a],vu[a].lerp(vu[b],t)));ns.extend((vn[b],vn[a],vn[a].lerp(vn[b],t).normalized()))
    positions=[v.co.copy() for v in old.vertices]+[point]
    me=bpy.data.meshes.new(old.name+' / rump seam return');me.from_pydata(positions,[],[tuple(p.vertices) for p in old.polygons]+[(b,a,ci)])
    for mat in old.materials:me.materials.append(mat)
    layer=me.uv_layers.new(name=old.uv_layers.active.name)
    for d,v in zip(layer.data,uv):d.uv=v
    for p in me.polygons:p.use_smooth=True
    me.normals_split_custom_set(ns);ob.data=me
    if not len(ob.vertex_groups):
        for name in names:ob.vertex_groups.new(name=name)
    for i,ws in enumerate(weights):
        for g,w in ws:ob.vertex_groups[g].add([i],w,'REPLACE')
    return {'operation':'left rump armor return fitted to adjoining fabric bend','original_rim_edge':[a,b],'new_position':tuple(point),'added_native_vertices':1,'added_triangles':1,'same_rigid_bone_as_adjoining_fabric':True}

def build():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    shutil.copy2(SOURCE.parent/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    source,oldrig=solid.proof_scene();s=bpy.data.scenes.new(SCENE);bpy.context.window.scene=s;s.render.fps=30
    rig=oldrig.copy();rig.data=oldrig.data.copy();rig.name='Jorge - repaired seams / shared CE motion';s.collection.objects.link(rig)
    records=[]
    for src in source.objects:
        if src.type!='MESH':continue
        ob=src.copy();ob.data=src.data.copy();s.collection.objects.link(ob);ob.parent=rig;ob.hide_set(False);ob.hide_render=False
        for m in ob.modifiers:
            if m.type=='ARMATURE':m.object=rig
        if not ob.get('texture_variant'):continue
        key=ob['source_component'];ob.name='Repaired / '+key;changes=[]
        if key=='body-09:000':
            moved=[];normals=[n.vector.copy() for n in ob.data.corner_normals]
            for v in ob.data.vertices:
                if v.co.y<-.1 and v.co.z>1.85:
                    # Recess the green support beneath the yellow collar. Both
                    # are rigid on b_torso; their clearance is pose invariant.
                    before=tuple(v.co);v.co.y+=.028
                    moved.append({'vertex':v.index,'before':before,'after':tuple(v.co)})
            ob.data.update();ob.data.normals_split_custom_set(normals);changes.append({'operation':'collar support clearance','vertices':moved})
        if key in ('body-10:000','body-10:001','body-10:002','body-10:003'):
            changes.append(close_backing(ob))
            if key=='body-10:000':
                # Clear a fabric sliver at the upper armor tip while preserving
                # the armor silhouette and its existing coverage.
                ns=[n.vector.copy() for n in ob.data.corner_normals];v=ob.data.vertices[43];before=tuple(v.co)
                v.co+=Vector((-.006,-.006,-.006));ob.data.update();ob.data.normals_split_custom_set(ns)
                changes.append({'operation':'tuck fabric under original left thigh tip','vertices':[{'vertex':43,'before':before,'after':tuple(v.co)}]})
        if key=='body-09:004':
            changes.append(rump_return(ob,next(o for o in source.objects if o.get('source_component')=='body-10:000')))
        ob['coverage_repair']=bool(changes);ob['reduction_variant']='coverage_repair'
        ob['actual_export_vertices']=count(ob);ob['actual_triangles']=len(ob.data.polygons)
        if changes:
            # Old correspondence describes the previous reduction, not these edits.
            for a in list(ob.data.attributes):
                if a.name.startswith('lod_parent_'):ob.data.attributes.remove(a)
        records.append({'component':key,'source_vertices':count(src),'source_native_vertices':len(src.data.vertices),'source_triangles':len(src.data.polygons),
                        'vertices':count(ob),'native_vertices':len(ob.data.vertices),'triangles':len(ob.data.polygons),'changes':changes})
    rig.hide_set(True);rig.data.pose_position='POSE';rig.animation_data.action=None;rig.animation_data.use_nla=True
    cleanup.studio(s);s.camera.data.ortho_scale=2.95;s.frame_start=0;s.frame_end=230;s.frame_set(0)
    report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_vertices':2169,'source_triangles':2743,
            'predicted_export_vertices':sum(r['vertices'] for r in records),'native_vertices':sum(r['native_vertices'] for r in records),
            'actual_triangles':sum(r['triangles'] for r in records),'components':records,'global_reduction':False,
            'method':'Recess green collar support beneath yellow armor; close concealed garment openings with fitted backing while preserving original rim weights; add one contour-fitted triangle at the left rump seam.'}
    (OUT/'repair-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (OUT/'component-inventory.csv').open('w') as f:
        keys=['component','source_vertices','vertices','source_triangles','triangles','native_vertices'];w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in keys} for r in records)
    actions={strip.action for track in rig.animation_data.nla_tracks for strip in track.strips if strip.action}
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{s,*actions},fake_user=True)
    print('REPAIR BUILT',report['predicted_export_vertices'],report['actual_triangles'],flush=True)

def export():
    s,r=proof_scene()
    for m in list(s.timeline_markers):s.timeline_markers.remove(m)
    exporter.OUT=OUT;exporter.NAME=NAME;exporter.proof_scene=proof_scene;exporter.export()

def render():ce.OUT=OUT;ce.proof_scene=proof_scene;ce.render()

def closeups():
    target,rig=proof_scene()
    with bpy.data.libraries.load(str(SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith(solid.SCENE)]
    reference=dst.scenes[0];rr=next(o for o in reference.objects if o.type=='ARMATURE')
    folder=OUT/'renders';folder.mkdir(exist_ok=True)
    from validate_jorge_ce_materials import actions_for
    samples=[('collar-front',None,0,(0,-1,.2)),('collar-oblique',None,0,(1,-1,.3)),
             ('rump-rest',None,0,(1,1,.2)),('rump-running','run',.75,(1,1,.2)),('rump-running-back','run',.25,(0,1,.2))]
    for label,scene,arm in [('before',reference,rr),('after',target,rig)]:
        bpy.context.window.scene=scene;scene.render.resolution_x=640;scene.render.resolution_y=640;scene.cycles.samples=24;scene.cycles.use_denoising=True
        for ob in scene.objects:
            if ob.type=='MESH' and not ob.get('texture_variant'):ob.hide_render=True
        for name,clip,fraction,direction in samples:
            arm.data.pose_position='REST' if clip is None else 'POSE'
            if clip:
                arm.animation_data.use_nla=False;arm.animation_data.action=actions_for(arm)[clip]
                f=arm.animation_data.action['duration_seconds']*30*fraction;scene.frame_set(int(f),subframe=f-int(f))
            bpy.context.view_layer.update()
            if name.startswith('collar'):center=Vector((0,-.08,1.94));scale=.85
            else:
                ob=next(o for o in scene.objects if o.get('source_component')=='body-10:000')
                ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());center=sum((ev.matrix_world@Vector(p) for p in ev.bound_box),Vector())/8;scale=.95
            scene.camera.location=center+Vector(direction).normalized()*4;scene.camera.rotation_euler=(center-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=scale
            scene.render.filepath=str(folder/f'close-{label}-{name}.png');bpy.ops.render.render(write_still=True)
        arm.data.pose_position='POSE'
        for ob in scene.objects:
            if ob.type=='MESH' and not ob.get('texture_variant'):ob.hide_render=False
    print('CLOSEUP RENDERS COMPLETE',flush=True)

if __name__=='__main__':
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:render()
    if '--closeups' in sys.argv:closeups()
    if '--motion' in sys.argv:animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
