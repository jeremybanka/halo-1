"""Component-local reduction from the repaired Jorge, with fixed open rims."""
import bpy,bmesh,json,sys,hashlib,shutil,csv
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import jorge_coverage_repair as parent
import jorge_solid_reduce as solid
import jorge_half_budget as half
import jorge_shoulder_study as shoulder
import jorge_surgical_cleanup as cleanup
import jorge_ce_materials as ce
import jorge_detail_pass as exporter

ROOT=parent.ROOT;BASE=parent.BASE;OUT=BASE/'playable-half';SOURCE=parent.OUT/(parent.NAME+'.blend')
NAME='jorge-playable-half';SCENE='Jorge - playable half budget';TARGET=1092
body=parent.body;count=parent.count
CULL={'arms-04:001':'Concealed inner shoulder mechanical insert',
      **{f'body-00:{i:03d}':'Small chest hinge under retained breastplate' for i in (1,2)},
      **{f'body-09:{i:03d}':'Covered spine/chest fitting; main shell and fabric backing retained' for i in (12,14,15,16,17,18,19)}}

def proof_scene():
    s=next(s for s in bpy.data.scenes if s.name.startswith(SCENE));bpy.context.window.scene=s
    return s,next(o for o in s.objects if o.type=='ARMATURE')

def continuous_normals(ob):
    me=ob.data;ns=[Vector() for v in me.vertices]
    for l,n in zip(me.loops,me.corner_normals):ns[l.vertex_index]+=n.vector
    for e in me.edges:e.use_edge_sharp=False
    for p in me.polygons:p.use_smooth=True
    me.normals_split_custom_set_from_vertices([n.normalized() for n in ns])

def simplify_rim(ob):
    """Remove only near-collinear rim samples with identical skin weights.

    Existing contour points survive; no rim vertex is moved. Protect the
    repaired collar/rump and major extrema. This is a contour resampling pass,
    not an unconstrained boundary collapse.
    """
    if ob['source_component'] in ('body-09:000','body-09:004','body-10:000'):return 0
    bm=bmesh.new();bm.from_mesh(ob.data);deform=bm.verts.layers.deform.active;removed=0
    while True:
        bm.verts.ensure_lookup_table();bm.normal_update();candidate=None
        extremes={f(bm.verts,key=lambda v:v.co[axis]) for axis in range(3) for f in (min,max)}
        for v in bm.verts:
            es=[e for e in v.link_edges if e.is_boundary]
            if len(es)!=2 or v in extremes:continue
            a,b=[e.other_vert(v) for e in es];ab=b.co-a.co;t=(v.co-a.co).dot(ab)/max(ab.length_squared,1e-20)
            tolerance=.006 if ob['source_component'].startswith(('body-03','body-06')) else .010
            if not 0<t<1 or (v.co-(a.co+ab*t)).length>tolerance:continue
            if deform and any(abs(v[deform].get(k,0)-q[deform].get(k,0))>1e-4 for q in (a,b) for k in set(v[deform].keys())|set(q[deform].keys())):continue
            candidate=v;break
        if candidate is None:break
        bmesh.ops.dissolve_verts(bm,verts=[candidate],use_face_split=False,use_boundary_tear=False);removed+=1
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();return removed

def build():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    shutil.copy2(SOURCE.parent/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    source,oldrig=parent.proof_scene();s=bpy.data.scenes.new(SCENE);bpy.context.window.scene=s;s.render.fps=30
    rig=oldrig.copy();rig.data=oldrig.data.copy();s.collection.objects.link(rig);rig.data.pose_position='REST';rig.hide_set(True)
    rows=[];removed=[]
    for src in source.objects:
        if src.type!='MESH':continue
        key=src.get('source_component')
        if key in CULL:removed.append({'component':key,'reason':CULL[key],'vertices':count(src),'triangles':len(src.data.polygons)});continue
        ob=src.copy();ob.data=src.data.copy();s.collection.objects.link(ob);ob.parent=rig;ob.hide_set(False);ob.hide_render=False
        for m in ob.modifiers:
            if m.type=='ARMATURE':m.object=rig
        if not ob.get('texture_variant'):continue
        ob.name='Playable / '+key
        rim_removed=simplify_rim(ob)
        _,locked,anchors=solid.prepare(ob)
        freedom=ob.vertex_groups['Solid surface freedom']
        # The exact repaired collar clearance is an explicit protected feature.
        if key=='body-09:000':
            for v in ob.data.vertices:
                if v.co.z>1.85 and v.co.y<-.06:freedom.add([v.index],0,'REPLACE')
        # The rump return and joint cover hems stay exact for this pass.
        protected=key=='body-09:004'
        template=ob.data.copy();original=solid.topology(ob);attempts=[]
        tree=KDTree(len(src.data.vertices))
        for v in src.data.vertices:tree.insert(v.co,v.index)
        tree.balance();names={g.index:g.name for g in src.vertex_groups}
        for ratio in ([1.] if protected else [.15,.25,.35,.45,.55,.65,.8,1.]):
            old=ob.data;ob.data=template.copy()
            if old.users==0:bpy.data.meshes.remove(old)
            shoulder.select(ob)
            if ratio<1:
                mod=ob.modifiers.new('Interior reduction; protected original rims','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
                mod.vertex_group='Solid surface freedom';mod.vertex_group_factor=1000
                bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name)
            half.clean_geometry(ob);half.transfer(ob,src)
            for v in ob.data.vertices:
                _,i,d=tree.find(v.co)
                if d<1e-7:
                    for g in ob.vertex_groups:
                        if g.name.startswith('b_'):g.remove([v.index])
                    for g in src.data.vertices[i].groups:ob.vertex_groups[names[g.group]].add([v.index],g.weight,'REPLACE')
            continuous_normals(ob);h=solid.topology(ob);error=solid.surface_error(ob,src)
            closed=original['boundary_edges']==0 and not original['nonmanifold_internal_edges']
            vr=h['signed_volume']/original['signed_volume'] if closed and abs(original['signed_volume'])>1e-9 else None
            limit,p95=(.085,.051) if key.startswith('backpack') else (.060,.035) if key.startswith(('body-03','body-06')) else (.050,.030) if key.startswith('body-10') else (.090,.040)
            valid=(solid.boundary_error(original,h)<1e-7 and h['euler']==original['euler'] and h['nonmanifold_internal_edges']<=original['nonmanifold_internal_edges']
                   and not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges']) and (vr is None or .80<=vr<=1.15)
                   and error['max_m']<limit and error['p95_m']<p95)
            attempts.append({'ratio':ratio,'vertices':count(ob),'triangles':len(ob.data.polygons),'valid':valid,'volume_ratio':vr,'surface_error':error})
            if valid:break
        assert valid,(key,attempts)
        for g in list(ob.vertex_groups):
            if not g.name.startswith('b_'):ob.vertex_groups.remove(g)
        ob['reduction_variant']='playable_half';ob['protected_coverage_rims']=True
        rows.append({'component':key,'source_vertices':count(src),'vertices':count(ob),'native_vertices':len(ob.data.vertices),'source_triangles':len(src.data.polygons),'triangles':len(ob.data.polygons),'rim_samples_removed':rim_removed,'attempts':attempts,'health':h})
        bpy.data.meshes.remove(template);print('REDUCED',key,rows[-1]['source_vertices'],'->',count(ob),'ratio',ratio,flush=True)
    rig.data.pose_position='POSE';rig.animation_data.action=None;rig.animation_data.use_nla=True
    cleanup.studio(s);s.camera.data.ortho_scale=2.95;s.frame_start=0;s.frame_end=230;s.frame_set(0)
    report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'target_vertices':TARGET,'vertices':sum(r['vertices'] for r in rows),'triangles':sum(r['triangles'] for r in rows),'components':rows,'removed':removed}
    (OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (OUT/'component-budgets.csv').open('w') as f:
        keys=['component','source_vertices','vertices','source_triangles','triangles','native_vertices'];w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in keys} for r in rows)
    actions={st.action for t in rig.animation_data.nla_tracks for st in t.strips if st.action}
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{s,*actions},fake_user=True,compress=True)
    print('TOTAL',report['vertices'],report['triangles'],flush=True)

def export():
    s,r=proof_scene()
    for m in list(s.timeline_markers):s.timeline_markers.remove(m)
    exporter.OUT=OUT;exporter.NAME=NAME;exporter.proof_scene=proof_scene;exporter.export()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(NAME+".blend")),compress=True)

if __name__=='__main__':
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:ce.OUT=OUT;ce.proof_scene=proof_scene;ce.render()
