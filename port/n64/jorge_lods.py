"""Build separate, source-derived Jorge body LODs in background Blender.

Every recipe names its source components. Hull consolidation is limited to
overlapping layers; the principal plates retain their original surface mesh.
The accepted personal asset and its first-person arm sources are read-only.
"""
from pathlib import Path
from collections import defaultdict
import argparse, csv, hashlib, json, shutil, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import personalize_jorge as personal
import jorge_playable_reduce as task
import jorge_surgical_cleanup as studio
import refine_jorge as paint

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'halo64-assets/assets/jorge'
SOURCE = BASE / 'playable-personal'
OUT = BASE / 'playable-lods'
COLOR = paint.COLOR


def recipe(lod):
    # Component-local triangle budgets. Coverage validation may require a
    # revised recipe; never silently accept a failed candidate to meet a cap.
    rows = []
    def add(name, ids, triangles, method='surface', symmetric=False):
        rows.append(dict(name=name, sources=ids.split(), budget=triangles,
                         method=method, symmetric=symmetric))
    if lod == 'near':
        add('forearm-r', 'arms-01:000 arms-07:000', 18, 'hull')
        add('forearm-l', 'arms-01:001 arms-07:001', 18, 'hull')
        add('shoulder-l', 'arms-04:000', 24)
        add('shoulder-r', 'arms-05:000', 20)
        for side, i in [('l', 0), ('r', 1)]:
            add('upperarm-'+side, f'arms-09:{i:03d}', 16)
            add('elbow-'+side, f'arms-10:{i:03d}', 10, 'hull')
        add('glove-r', 'arms-08:000 arms-07:003', 20, 'hull')
        add('glove-l', 'arms-08:001 arms-07:002', 20, 'hull')
        add('pack', 'backpack-14:000', 72, 'open', True)
        add('pack-backing', 'backpack-14:000', 20, 'backing', True)
        add('chest', 'body-00:000', 38, 'surface', True)
        add('chest-backing', 'body-00:000', 12, 'backing', True)
        add('collar', 'body-09:000', 36, 'open', True)
        add('codpiece', 'body-09:001', 24, symmetric=True)
        add('abdomen', 'body-09:013', 10)
        add('neckguard', 'body-02:002', 16)
        add('helmet', 'body-03:000', 89, 'open')
        add('forehead-fitting', 'body-03:002', 0, 'omit')
        add('visor-frame', 'body-03:001', 0, 'omit')
        add('visor', 'body-06:000', 23, 'open')
        for side, calf, thigh, boot, sole, ankle, knee, cap in [
                ('r', 0, 5, 6, 8, 9, 6, 12), ('l', 1, 4, 7, 7, 10, 5, 11)]:
            add('calf-'+side, f'body-02:{calf:03d} body-09:{calf+2:03d}', 24, 'hull')
            add('kneecap-'+side, f'body-02:{calf+3:03d}', 10)
            add('thigh-'+side, f'body-09:{thigh:03d}', 24, 'open')
            add('firstperson-cap-'+side, f'body-10:{cap:03d}', 0, 'omit')
            add('boot-'+side, f'body-09:{boot:03d} body-09:{calf+8:03d} body-09:{calf+10:03d} body-10:{sole:03d}', 22, 'hull')
            add('ankle-'+side, f'body-10:{ankle:03d}', 10, 'hull')
            add('knee-'+side, f'body-10:{knee:03d}', 14, 'hull')
        add('pelvis','body-10:000',32,'surface',True)
        add('waist','body-10:001',40,'surface',True)
        add('armpit-r','body-10:002',16,'surface')
        add('armpit-l','body-10:003',18,'surface')
        add('neck','body-10:004',18,'hull')
    else:
        add('forearm-r', 'arms-01:000 arms-07:000 arms-07:003 arms-08:000', 16, 'hull')
        add('forearm-l', 'arms-01:001 arms-07:001 arms-07:002 arms-08:001', 16, 'hull')
        add('shoulder-l', 'arms-04:000', 12)
        add('shoulder-r', 'arms-05:000', 10)
        add('upperarm-l', 'arms-09:000 arms-10:000', 12, 'hull')
        add('upperarm-r', 'arms-09:001 arms-10:001', 12, 'hull')
        add('pack', 'backpack-14:000', 36, 'pack-envelope', True)
        add('chest', 'body-00:000 body-09:013', 18, 'surface', True)
        add('collar', 'body-09:000', 18, 'open', True)
        add('torso-backing', 'body-10:002 body-10:003 body-10:004', 12, 'hull', True)
        add('waist', 'body-10:001', 8, 'hull', True)
        add('codpiece', 'body-09:001', 12, 'front', True)
        add('pelvis', 'body-10:000', 16, 'hull', True)
        rows[-1]['coverage_sources']=['body-09:001']
        add('neckguard', 'body-02:002', 8)
        add('helmet', 'body-03:000', 89, 'open')
        add('visor-frame', 'body-03:001', 0, 'omit')
        add('forehead-fitting', 'body-03:002', 0, 'omit')
        add('visor', 'body-06:000', 23, 'open')
        for side, calf, thigh, boot, sole, ankle, knee, cap in [
                ('r', 0, 5, 6, 8, 9, 6, 12), ('l', 1, 4, 7, 7, 10, 5, 11)]:
            add('calf-'+side, f'body-02:{calf:03d} body-02:{calf+3:03d} body-09:{calf+2:03d} body-10:{knee:03d} body-10:{ankle:03d}', 18, 'hull')
            add('thigh-'+side, f'body-09:{thigh:03d} body-10:{cap:03d}', 14, 'hull')
            add('boot-'+side, f'body-09:{boot:03d} body-09:{calf+8:03d} body-09:{calf+10:03d} body-10:{sole:03d}', 14, 'hull')
    return rows


class Reference:
    def __init__(self, objects):
        self.points, self.faces, self.weights, self.colors, self.uv = [], [], [], [], []
        for ob in objects:
            me = ob.data; me.calc_loop_triangles(); offset = len(self.points)
            self.points.extend(v.co.copy() for v in me.vertices)
            self.weights.extend({ob.vertex_groups[g.group].name: g.weight for g in v.groups
                                 if ob.vertex_groups[g.group].name.startswith('b_')} for v in me.vertices)
            ca = me.color_attributes[COLOR]
            for tri in me.loop_triangles:
                self.faces.append([offset+i for i in tri.vertices])
                self.colors.append([list(ca.data[i].color_srgb[:3]) for i in tri.loops])
                self.uv.append([me.uv_layers.active.data[i].uv.copy() for i in tri.loops])
        self.tree = BVHTree.FromPolygons(self.points, self.faces, all_triangles=True)

    def sample(self, point):
        hit, normal, fi, distance = self.tree.find_nearest(point)
        ids = self.faces[fi]
        bary = barycentric_transform(hit, *[self.points[i] for i in ids],
                                      Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1)))
        bary = np.maximum(0, np.array(bary)); bary /= bary.sum()
        weights = defaultdict(float)
        for i, factor in zip(ids, bary):
            for name, value in self.weights[i].items(): weights[name] += value*factor
        weights = sorted(weights.items(), key=lambda item: -item[1])[:4]
        total = sum(v for _, v in weights)
        return ({n: v/total for n,v in weights if v > 1e-8},
                bary @ np.array(self.colors[fi]), bary @ np.array(self.uv[fi]), distance)


def close_mesh(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
    edges = [e for e in bm.edges if e.is_boundary]
    if edges: bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data); bm.free(); ob.data.update()


def attributes(ob, reference):
    me=ob.data; ob.vertex_groups.clear()
    samples=[reference.sample(v.co) for v in me.vertices]
    for i, (weights, rgb, uv, distance) in enumerate(samples):
        for name, weight in weights.items():
            g=ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
            g.add([i],weight,'REPLACE')
    for layer in list(me.color_attributes): me.color_attributes.remove(layer)
    ca=me.color_attributes.new(name=COLOR,type='FLOAT_COLOR',domain='CORNER')
    me.color_attributes.active_color=ca
    uv=me.uv_layers.active or me.uv_layers.new(name='CE Atlas UV')
    for loop in me.loops:
        sample=samples[loop.vertex_index]
        ca.data[loop.index].color_srgb=(*np.clip(sample[1],0,1),1)
        uv.data[loop.index].uv=sample[2]
    if ob['source_component']=='helmet':
        # One deliberate black/olive value per point, rather than dozens of
        # corner copies along the high-resolution source paint-mask boundary.
        pools=defaultdict(list)
        for face,rgbs in zip(reference.faces,reference.colors):
            for vi,rgb in zip(face,rgbs):pools[vi].append(rgb)
        point_colors=[]
        for v in me.vertices:
            vi=min(range(len(reference.points)),key=lambda i:(v.co-reference.points[i]).length_squared)
            pool=np.array(pools[vi]);dark=pool.max(1)<.26
            chosen=pool[dark] if dark.sum()>=len(pool)/2 else pool[~dark]
            point_colors.append(chosen.mean(0))
        for loop in me.loops:ca.data[loop.index].color_srgb=(*point_colors[loop.vertex_index],1)
    # One normal/color per point prevents artificial export splits. Panel
    # outlines remain separate components and the visor remains a gold surface.
    if me.has_custom_normals: bpy.context.view_layer.objects.active=ob; bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in me.polygons: p.use_smooth=True
    return max(s[3] for s in samples)


def build(lod):
    personal.configure(); source, oldrig=task.proof_scene()
    src={o['source_component']:o for o in task.body(source)}
    rows=recipe(lod); allids=[i for r in rows if r['method']!='backing' for i in r['sources']]
    assert len(allids)==len(set(allids)) and set(allids)==set(src), (set(src)-set(allids),set(allids)-set(src))
    folder=OUT/lod; folder.mkdir(parents=True,exist_ok=True)
    shutil.copytree(SOURCE/'textures',folder/'textures',dirs_exist_ok=True)
    shutil.copy2(SOURCE/'ce-motion-source.json',folder/'ce-motion-source.json')
    scene=bpy.data.scenes.new('Jorge - '+lod+' body LOD'); bpy.context.window.scene=scene; scene.render.fps=30
    rig=oldrig.copy();rig.data=oldrig.data.copy();scene.collection.objects.link(rig);rig.data.pose_position='REST'
    for row in rows:
        originals=[src[k] for k in row['sources']+row.get('coverage_sources',[])]; ref=Reference(originals)
        if row['method']=='omit':
            row.update(vertices=0,triangles=0,source_vertices=sum(len(o.data.vertices) for o in originals),
                       source_triangles=sum(len(o.data.polygons) for o in originals))
            continue
        me=bpy.data.meshes.new(lod+' / '+row['name']); me.from_pydata(ref.points,[],ref.faces)
        if row['method']=='pack-envelope':
            # Two inspected source contour rings retain the paired crown,
            # middle saddle, wide shoulders, side depth and tapered base.
            # A convex hull bridges the saddle and loses this silhouette.
            front=[64,111,16,35,32,40,105,108,89,119]
            back=[38,0,15,37,31,46,104,110,88,73]
            points=[ref.points[i] for i in front+back];n=len(front)
            faces=[list(range(n-1,-1,-1)),list(range(n,n*2))]
            faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
            me.clear_geometry();me.from_pydata(points,[],faces)
        ob=originals[0].copy();ob.data=me;ob.name=lod+' / '+row['name'];scene.collection.objects.link(ob)
        for key in ('actual_export_vertices','actual_triangles','parent_triangle_count','reduction_ratio',
                    'reduction_factor','protected_coverage_rims','coverage_repair','solid_coverage'):
            if key in ob:del ob[key]
        ob.parent=rig;ob.hide_render=False;ob.hide_set(False)
        ob['source_components']=json.dumps(row['sources']);ob['source_component']=row['name']
        ob['lod']=lod;ob['detail_variant']='coverage_lod';ob['reduction_variant']='playable_lods'
        for mod in ob.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if row['method']=='front':
            bm=bmesh.new();bm.from_mesh(me)
            bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_center_median().y>-.10],context='FACES')
            bm.to_mesh(me);bm.free()
        if row['method'] in ('hull','backing'):
            bm=bmesh.new()
            for point in ref.points:bm.verts.new(point)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
            result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
            delete=[g for g in result['geom_interior']+result['geom_unused'] if g.is_valid]
            if delete:bmesh.ops.delete(bm,geom=list(set(delete)),context='VERTS')
            bm.to_mesh(me);bm.free()
        if row['method'] not in ('open','front'):close_mesh(ob)
        if row['method']=='backing':
            center=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices)
            for v in ob.data.vertices:v.co=center+(v.co-center)*.93
        if row['name']=='torso-backing':
            center=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices)
            for v in ob.data.vertices:v.co=center+(v.co-center)*.90
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
        ratio=min(1.,row['budget']/max(1,len(me.polygons)))
        if ratio<1:
            free=ob.vertex_groups.new(name='LOD surface freedom')
            anchors={f(me.vertices,key=lambda v:v.co[a]).index for a in range(3) for f in (min,max)}
            protected=set()
            if row['name']=='pack' and lod=='near':
                protected.update(v.index for v in me.vertices if v.co.z>2.04)
                bm=bmesh.new();bm.from_mesh(me);bm.verts.ensure_lookup_table()
                protected.update(v.index for e in bm.edges if not e.is_manifold for v in e.verts);bm.free()
            for v in me.vertices:free.add([v.index],0 if v.index in protected else .05 if v.index in anchors else 1,'REPLACE')
            mod=ob.modifiers.new('Component budget / authored surface','DECIMATE')
            mod.ratio=ratio;mod.use_collapse_triangulate=True
            mod.use_symmetry=row['symmetric'];mod.symmetry_axis='X'
            mod.vertex_group=free.name;mod.vertex_group_factor=1000 if protected else 10
            bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name)
        if row['method'] not in ('open','front'):close_mesh(ob)
        if row['method']=='backing' or (lod=='far' and row['method']=='hull'):
            # A very thin collapsed hull can leave a doubled, zero-volume
            # fin. Re-envelope the retained points to keep the volume solid.
            bm=bmesh.new()
            for v in ob.data.vertices:bm.verts.new(v.co)
            result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
            discard=[g for g in result['geom_interior']+result['geom_unused'] if g.is_valid]
            if discard:bmesh.ops.delete(bm,geom=list(set(discard)),context='VERTS')
            bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            bm.to_mesh(ob.data);bm.free();ob.data.update()
        # Restore overlap at deforming garment interfaces. These are concealed
        # source-fitted backing surfaces, never replacement visible plates.
        if row['name'] in ('waist','pelvis') and (lod=='far' or row['name']=='pelvis'):
            coords=np.array([v.co[:] for v in ob.data.vertices]);center=coords.mean(0)
            for v in ob.data.vertices:
                delta=v.co-Vector(center);length=delta.length
                if length:v.co+=delta/length*min(.025,length*.10)
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(ob.data);bm.free();ob.data.update()
        error=attributes(ob,ref)
        if lod=='far' and row['name']=='torso-backing':
            # This consolidated armor volume must move with the torso, not
            # stretch with the armpit/fixup weights of its source layers.
            ob.vertex_groups.clear();group=ob.vertex_groups.new(name='b_torso')
            group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
            row['rigid_bone']='b_torso'
        if row.get('coverage_sources'):
            # Concealed pelvis remains fabric even where its fitted coverage
            # uses the rigid belt's bounds; the green front plate is separate.
            for c in ob.data.color_attributes[COLOR].data:c.color_srgb=(.15,.17,.15,1)
        me=ob.data
        me.materials.clear();me.materials.append(paint.material(lod+' / '+row['name'],row['name']=='visor'))
        if row['name'].startswith('pack'):
            bs=next(n for n in me.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=1
        bm=bmesh.new();bm.from_mesh(me);bm.normal_update()
        row.update(vertices=len(me.vertices),triangles=len(me.polygons),boundary_edges=sum(e.is_boundary for e in bm.edges),
                   nonmanifold=sum(not e.is_manifold and not e.is_boundary for e in bm.edges),
                   max_source_distance_m=error,source_vertices=sum(len(o.data.vertices) for o in originals),
                   source_triangles=sum(len(o.data.polygons) for o in originals))
        assert not any(f.calc_area()<1e-12 for f in bm.faces), row
        bm.free();print('COMPONENT',lod,row,flush=True)
    rig.data.pose_position='POSE';rig.animation_data.action=None;rig.animation_data.use_nla=True
    studio.studio(scene);scene.camera.data.ortho_scale=2.95;scene.frame_set(0)
    actions={a for a in bpy.data.actions if a.get('source_clip')}
    report=dict(source_blend_sha256=hashlib.sha256((SOURCE/(personal.NAME+'.blend')).read_bytes()).hexdigest(),
                lod=lod,vertices=sum(r['vertices'] for r in rows),triangles=sum(r['triangles'] for r in rows),components=rows)
    (folder/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (folder/'component-budgets.csv').open('w') as f:
        keys=['name','sources','method','budget','source_vertices','vertices','source_triangles','triangles']
        writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in rows)
    bpy.data.libraries.write(str(folder/('jorge-'+lod+'.blend')),{scene,*actions},fake_user=True,compress=True)
    print('LOD TOTAL',lod,report['vertices'],report['triangles'],flush=True)


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser();parser.add_argument('--lod',choices=['near','far'],required=True)
    build(parser.parse_args(args).lod)
