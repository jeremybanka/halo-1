"""Coverage-first reduction directly from the accepted 3,867-vertex Jorge.

Open rims and their skinning are invariant. Reductions may only retriangulate
interiors; independent budgets never override surface/volume/coverage checks.
"""
import bpy, bmesh, json, math, sys, shutil, hashlib, csv
import numpy as np
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
import jorge_detail_pass as source_stage
import jorge_half_budget as half
import jorge_tactical_reduce as tactical
import jorge_shoulder_study as shoulder
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup
import jorge_ce_materials as ce

ROOT=half.ROOT; BASE=half.BASE; OUT=BASE/'solid-2000'
SOURCE=source_stage.OUT/(source_stage.NAME+'.blend')
NAME='jorge-solid-2000'; SCENE='Jorge - solid coverage reduction'
AR_SOURCE=half.AR_SOURCE; TARGET=2000
CULL={**{f'arms-01:{i:03d}':'Forearm strap consolidated into the retained gauntlet/forearm silhouette' for i in range(2,6)},
      'backpack-14:001':'Requested removal of dangling lower backpack connector'}
# Assembly-level review: preserve knee fabric through running, retain broad
# upper-arm coverage, and restore chest/backpack silhouette support.
MIN_RATIOS={'body-10:005':1.,'body-10:006':1.,'arms-09:000':1.,'arms-09:001':1.,
            'body-09:008':1.,'body-09:009':1.,'body-00:000':.6,'backpack-14:000':.5}
body=half.body

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith(SCENE));bpy.context.window.scene=scene
    return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def count(ob):
    me=ob.data;ns=np.round(np.array([n.vector for n in me.corner_normals],dtype=np.float32),4);uv=me.uv_layers.active.data
    return len({(l.vertex_index,tuple(ns[i]),tuple(uv[i].uv)) for i,l in enumerate(me.loops)})

def topology(ob):
    bm=bmesh.new();bm.from_mesh(ob.data);bm.normal_update()
    boundary=[tuple(sorted((tuple(v.co) for v in e.verts))) for e in bm.edges if e.is_boundary]
    r={'boundary_edges':len(boundary),'boundary_segments':boundary,
       'nonmanifold_internal_edges':sum(not e.is_manifold and not e.is_boundary and bool(e.link_faces) for e in bm.edges),
       'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),
       'loose_vertices':sum(not v.link_faces for v in bm.verts),'wire_edges':sum(not e.link_faces for e in bm.edges),
       'euler':len(bm.verts)-len(bm.edges)+len(bm.faces),'signed_volume':bm.calc_volume(signed=True)}
    bm.free();return r

def prepare(ob):
    pre=tactical.cleanup_mesh(ob);me=ob.data;bm=bmesh.new();bm.from_mesh(me);bm.verts.ensure_lookup_table();bm.normal_update()
    # Fix actual open rims and nonmanifold authored joins, not every UV seam.
    locked={v.index for e in bm.edges if not e.is_manifold for v in e.verts}
    anchors=set()
    # Extremal contour points protect the broad mass even on a closed mesh.
    for axis in range(3):
        for f in (min,max):anchors.add(f(bm.verts,key=lambda v:v.co[axis]).index)
    bm.free()
    group=ob.vertex_groups.get('Solid surface freedom') or ob.vertex_groups.new(name='Solid surface freedom')
    for v in me.vertices:group.add([v.index],0 if v.index in locked|anchors else 1,'REPLACE')
    return pre,locked,anchors

def boundary_error(a,b):
    sa={tuple(tuple(p) for p in e) for e in a['boundary_segments']};sb={tuple(tuple(p) for p in e) for e in b['boundary_segments']}
    if sa==sb:return 0.
    if len(sa)!=len(sb):return 1e9
    # Blender float round trips can vary by a few nanometers.
    return max((max(min((Vector(p)-Vector(q)).length for seg in sb for q in seg) for p in seg) for seg in sa),default=0.)

def simplify_normals(ob):
    """Merge redundant shading splits within 25 degrees, retaining major creases.

    This changes no positions, faces, UVs or skin weights. Continuous fans avoid
    tiny custom-normal quantization differences becoming extra GLB vertices.
    """
    me=ob.data;normals=[n.vector.copy() for n in me.corner_normals];loops=defaultdict(list)
    for l in me.loops:loops[l.vertex_index].append(l.index)
    result=[None]*len(normals);threshold=math.cos(math.radians(25))
    for ids in loops.values():
        clusters=[]
        for i in ids:
            cluster=next((c for c in clusters if all(normals[i].dot(normals[j])>=threshold for j in c)),None)
            if cluster is None:clusters.append([i])
            else:cluster.append(i)
        for cluster in clusters:
            normal=sum((normals[i] for i in cluster),Vector()).normalized()
            for i in cluster:result[i]=normal
    for edge in me.edges:edge.use_edge_sharp=False
    for face in me.polygons:face.use_smooth=True
    me.normals_split_custom_set(result)

def trial(ob,source,template,ratio):
    previous=ob.data;ob.data=template.copy()
    if previous.users==0:bpy.data.meshes.remove(previous)
    shoulder.select(ob)
    if ratio<1:
        mod=ob.modifiers.new('Interior retriangulation - fixed coverage rims','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
        mod.vertex_group='Solid surface freedom';mod.vertex_group_factor=1000
        bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name)
    half.clean_geometry(ob)
    # Interpolated UVs remain; source normals/weights are sampled by component.
    transfer=half.transfer(ob,source)
    simplify_normals(ob)
    # A locked rim keeps its exact source skinning as well as its position.
    # This prevents a gap from reappearing only when a joint is bent.
    tree=KDTree(len(source.data.vertices))
    for v in source.data.vertices:tree.insert(v.co,v.index)
    tree.balance();bone_names={g.index:g.name for g in source.vertex_groups if g.name.startswith('b_')}
    for v in ob.data.vertices:
        co,index,distance=tree.find(v.co)
        if distance<1e-7:
            for group in ob.vertex_groups:
                if group.name.startswith('b_'):group.remove([v.index])
            for g in source.data.vertices[index].groups:
                if g.group in bone_names:ob.vertex_groups[bone_names[g.group]].add([v.index],g.weight,'REPLACE')
    clearance=[]
    if ob['source_component']=='body-09:001':
        # Give the lower rigid front plate clearance over the animated fabric.
        # Keep the waist rim and topology; do not cut a hole in the undersuit.
        for v in ob.data.vertices:
            if v.co.y<-.14 and v.co.z<1.34:
                offset=.012*min(1.,max(0.,(1.34-v.co.z)/.08));v.co.y-=offset
                clearance.append({'vertex':v.index,'forward_m':offset})
        ob.data.update()
    return {'vertices':count(ob),'triangles':len(ob.data.polygons),'ratio':ratio,'health':topology(ob),'codpiece_clearance':clearance,**transfer}

def surface_error(ob,source):
    me=ob.data;me.calc_loop_triangles();src=source.data;src.calc_loop_triangles()
    tree=BVHTree.FromPolygons([v.co for v in me.vertices],[t.vertices for t in me.loop_triangles],all_triangles=True)
    samples=[v.co for v in src.vertices]
    samples.extend(sum((src.vertices[i].co for i in t.vertices),Vector())/3 for t in src.loop_triangles)
    distances=[tree.find_nearest(p)[3] for p in samples]
    return {'max_m':max(distances),'p95_m':float(np.percentile(distances,95))}

def build():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    shutil.copy2(SOURCE.parent/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    source,old_rig=source_stage.proof_scene();scene=bpy.data.scenes.new(SCENE);bpy.context.window.scene=scene;scene.render.fps=30
    rig=old_rig.copy();rig.data=old_rig.data.copy();rig.name='Jorge - fixed coverage rims and shared CE motion';scene.collection.objects.link(rig);rig.data.pose_position='REST';rig.hide_set(True)
    records=[];removed=[]
    for original in source.objects:
        if original.type!='MESH':continue
        key=original.get('source_component')
        if key in CULL:
            removed.append({'component':key,'reason':CULL[key],'source_vertices':count(original),'triangles':len(original.data.polygons)});continue
        ob=original.copy();ob.data=original.data.copy();scene.collection.objects.link(ob);ob.parent=rig;ob.hide_render=False;ob.hide_set(False)
        for mod in ob.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if not original.get('texture_variant'):
            weapon=half.port_ar(ob);continue
        ob.name='Solid / '+key
        pre,locked,anchors=prepare(ob);template=ob.data.copy();before=topology(ob);attempts=[]
        limit={'arms-04':.030,'arms-05':.030,'arms-08':.035,'body-00':.030,
               'body-02':.018,'body-03':.025,'backpack-14':.035}.get(ob['group'],.020)
        if key in ('body-09:000','body-10:004'):limit=.030
        # A component may keep more geometry whenever coverage or solid volume
        # requires it. There is deliberately no per-component destructive cap.
        for ratio in (.40,.50,.60,.70,.80,.90,1.):
            if ratio<MIN_RATIOS.get(key,0):continue
            row=trial(ob,original,template,ratio);h=row['health'];error=surface_error(ob,original)
            closed=before['boundary_edges']==0 and before['nonmanifold_internal_edges']==0
            volume_ratio=h['signed_volume']/before['signed_volume'] if closed and abs(before['signed_volume'])>1e-10 else None
            rim_error=boundary_error(before,h)
            valid=(rim_error<1e-7 and h['euler']==before['euler'] and h['nonmanifold_internal_edges']<=before['nonmanifold_internal_edges']
                   and not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges'])
                   and (volume_ratio is None or .90<=volume_ratio<=1.10) and error['max_m']<=limit and error['p95_m']<=.020)
            attempts.append({'ratio':ratio,'vertices':row['vertices'],'triangles':row['triangles'],'valid':valid,'surface_error':error,'volume_ratio':volume_ratio,'rim_error_m':rim_error})
            if valid:break
        assert valid,(key,attempts)
        for g in list(ob.vertex_groups):
            if not g.name.startswith('b_'):ob.vertex_groups.remove(g)
        ob['solid_coverage']=True;ob['reduction_variant']='solid_2000';ob['actual_export_vertices']=row['vertices'];ob['actual_triangles']=row['triangles'];ob['parent_triangle_count']=len(original.data.polygons)
        row.update({'component':key,'group':ob['group'],'source_vertices':count(original),'source_triangles':len(original.data.polygons),
                    'native_vertices':len(ob.data.vertices),'locked_rim_vertices':len(locked),'extremal_anchors':len(anchors),
                    'original_health':before,'rim_error_m':rim_error,'volume_ratio':volume_ratio,'surface_error':error,'surface_max_limit_m':limit,'attempts':attempts})
        records.append(row);bpy.data.meshes.remove(template)
        print('SOLID',key,row['source_vertices'],'->',row['vertices'],'tri',row['triangles'],'ratio',ratio,flush=True)
    rig.data.pose_position='POSE';cleanup.studio(scene);scene.camera.data.ortho_scale=2.95;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0)
    report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_vertices':3867,'source_triangles':4273,'target_vertices_approximate':TARGET,
            'predicted_export_vertices':sum(r['vertices'] for r in records),'actual_triangles':sum(r['triangles'] for r in records),'native_vertices':sum(r['native_vertices'] for r in records),
            'components':records,'removed':removed,'weapon':weapon,
            'method':'Fixed original open rims and skin weights; preserved topological type; closed volumes within 10%; sampled source surface error bounded per region with p95 <=20 mm; redundant shading splits within 25 degrees merged; assembly coverage checked separately',
            'budget_scope':'Body exported POSITION vertices; weapon excluded. Coverage constraints outrank the approximate count.'}
    (OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    actions={s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action}
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{scene,*actions},fake_user=True)
    print('SOLID BUILT',report['predicted_export_vertices'],report['actual_triangles'],flush=True)

def export():
    scene,rig=proof_scene()
    for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
    source_stage.OUT=OUT;source_stage.NAME=NAME;source_stage.proof_scene=proof_scene;source_stage.export()

def render():ce.OUT=OUT;ce.proof_scene=proof_scene;ce.render()

def probe():
    OUT.mkdir(exist_ok=True);scene,rig=source_stage.proof_scene();rig.data.pose_position='REST';rows=[]
    for source in list(body(scene)):
        key=source['source_component']
        if key in CULL:continue
        ob=source.copy();ob.data=source.data.copy();scene.collection.objects.link(ob)
        pre,locked,anchors=prepare(ob);template=ob.data.copy();before=topology(ob)
        row=trial(ob,source,template,.45);row.update({'component':key,'source_vertices':count(source),'source_triangles':len(source.data.polygons),'locked':len(locked),'anchors':len(anchors),'boundary_error_m':boundary_error(before,row['health']),'original_health':before})
        rows.append(row);print('PROBE',key,row['source_vertices'],'->',row['vertices'],'T',row['triangles'],'B',row['boundary_error_m'],'V',round(row['health']['signed_volume']/before['signed_volume'],3) if abs(before['signed_volume'])>1e-8 else None,flush=True)
        bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(template)
    (OUT/'probe.json').write_text(json.dumps(rows,indent=2)+'\n');print('PROBE TOTAL',sum(r['vertices'] for r in rows),sum(r['triangles'] for r in rows),flush=True)

if __name__=='__main__':
    if '--probe' in sys.argv:probe()
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:render()
    if '--motion' in sys.argv:animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
