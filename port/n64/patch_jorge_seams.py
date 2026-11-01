"""Retain small source-surface bridges where quantized joint coverage needs them."""
import bpy,json,csv
from mathutils import Vector
import jorge_playable_reduce as task
from validate_jorge_coverage_repair import load
OUT=task.OUT
PATCHES={'body-02:000':[46],'body-02:001':[74,93],'body-00:000':[29,34,41],
 'backpack-14:000':[60,158],'body-09:005':[7],'body-03:000':[96,158],
 'arms-08:000':[16,37,61,68],'arms-04:000':[13],'arms-07:000':[15],'arms-01:000':[16]}
def run():
    scene,rig=task.proof_scene();ref,rr=load(task.SOURCE,task.parent.SCENE);refs={o['source_component']:o for o in task.body(ref)};records=[]
    for ob in task.body(scene):
        key=ob['source_component']
        if key not in PATCHES:continue
        source=refs[key];old=ob.data;src=source.data;vertices=[v.co.copy() for v in old.vertices];faces=[list(p.vertices) for p in old.polygons];uv=[u.uv.copy() for u in old.uv_layers.active.data];weights=[[(ob.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in old.vertices]
        ns=[n.vector.copy() for n in old.corner_normals];mapped={};before=len(vertices)
        for fi in PATCHES[key]:
            poly=src.polygons[fi];face=[]
            for li,vi in zip(poly.loop_indices,poly.vertices):
                if vi not in mapped:
                    mapped[vi]=len(vertices);vertices.append(src.vertices[vi].co.copy());weights.append([(source.vertex_groups[g.group].name,g.weight) for g in src.vertices[vi].groups])
                face.append(mapped[vi]);uv.append(src.uv_layers.active.data[li].uv.copy());ns.append(src.corner_normals[li].vector.copy())
            faces.append(face)
        me=bpy.data.meshes.new(old.name+' / original seam backing');me.from_pydata(vertices,[],faces);me.materials.append(old.materials[0]);layer=me.uv_layers.new(name=old.uv_layers.active.name)
        for a,b in zip(layer.data,uv):a.uv=b
        for p in me.polygons:p.use_smooth=True
        me.normals_split_custom_set(ns);ob.data=me
        for g in ob.vertex_groups:g.remove(list(range(len(vertices))))
        for vi,ws in enumerate(weights):
            for name,w in ws:
                group=ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name);group.add([vi],w,'REPLACE')
        task.continuous_normals(ob)
        records.append({'component':key,'original_faces':PATCHES[key],'vertices_added':len(vertices)-before,'triangles_added':len(PATCHES[key])})
    report=json.loads((OUT/'reduction-report.json').read_text());report['source_seam_backings']=records
    for row in report['components']:
        o=next(o for o in task.body(scene) if o['source_component']==row['component']);row.update(vertices=task.count(o),triangles=len(o.data.polygons),native_vertices=len(o.data.vertices))
    report['vertices']=sum(r['vertices'] for r in report['components']);report['triangles']=sum(r['triangles'] for r in report['components']);(OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (OUT/'component-budgets.csv').open('w') as f:
        keys=['component','source_vertices','vertices','source_triangles','triangles','native_vertices'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in report['components'])
    actions={st.action for t in rig.animation_data.nla_tracks for st in t.strips if st.action}
    actions|={a for a in bpy.data.actions if a.get('source_clip') not in ('idle','run','fire','reload')}
    bpy.data.libraries.write(str(OUT/(task.NAME+'.blend')),{scene,*actions},fake_user=True,compress=True);print('PATCHED',report['vertices'],report['triangles'],flush=True)
if __name__=='__main__':run()
