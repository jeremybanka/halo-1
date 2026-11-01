"""Fitted rear faces close armor shells without changing their outer contour."""
import bpy,bmesh,json,shutil
from mathutils import Vector
import jorge_playable_reduce as task
OUT=task.OUT

def run():
    scene,rig=task.proof_scene();records=[]
    for ob in task.body(scene):
        key=ob['source_component'];before=task.count(ob);me=ob.data;original=me.copy();health=task.solid.topology(ob)
        # Backing only on open armor shells; garment closures already exist.
        if ob['group'] in ('body-10','arms-10','arms-08'):continue
        bm=bmesh.new();bm.from_mesh(me);edges=[e for e in bm.edges if e.is_boundary]
        if not edges:bm.free();continue
        olduv={l.vert: l[bm.loops.layers.uv.active].uv.copy() for f in bm.faces for l in f.loops};uv=bm.loops.layers.uv.active
        oldn=[v.normal.copy() for v in me.vertices]
        faces=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces']
        for f in faces:
            for l in f.loops:l[uv].uv=olduv[l.vert]
        n=len(faces);bmesh.ops.triangulate(bm,faces=faces);bm.to_mesh(me);bm.free();task.half.clean_geometry(ob)
        for p in me.polygons:p.use_smooth=True
        me.normals_split_custom_set_from_vertices(oldn)
        after=task.solid.topology(ob)
        if after['nonmanifold_internal_edges']>health['nonmanifold_internal_edges'] or after['zero_area_faces']:
            ob.data=original;continue
        bpy.data.meshes.remove(original)
        records.append({'component':key,'filled_loops':n,'vertices_before':before,'vertices_after':task.count(ob),'health':task.solid.topology(ob)})
    report=json.loads((OUT/'reduction-report.json').read_text());report['shell_backings']=records
    for row in report['components']:
        ob=next(o for o in task.body(scene) if o['source_component']==row['component']);row['vertices']=task.count(ob);row['triangles']=len(ob.data.polygons)
    report['vertices']=sum(r['vertices'] for r in report['components']);report['triangles']=sum(r['triangles'] for r in report['components']);(OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    actions={a for a in bpy.data.actions if a.get('source_clip')}
    bpy.data.libraries.write(str(OUT/(task.NAME+'.blend')),{scene,*actions},fake_user=True,compress=True)
    print('SEALED',report['vertices'],report['triangles'],len(records),flush=True)
if __name__=='__main__':run()
