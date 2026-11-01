"""Small overlapping hems and original garment coverage at moving joints."""
import bpy,json
from mathutils import Vector
import jorge_playable_reduce as task
from validate_jorge_coverage_repair import load
OUT=task.OUT

def run():
    scene,rig=task.proof_scene();ref,rr=load(task.SOURCE,task.parent.SCENE);refs={o['source_component']:o for o in task.body(ref)};changes=[]
    bpy.context.window.scene=scene
    for ob in list(task.body(scene)):
        key=ob['source_component'];before=task.count(ob)
        if key in ('body-10:000','body-10:003'):
            src=refs[key];new=src.copy();new.data=src.data.copy();scene.collection.objects.link(new);new.parent=rig
            for m in new.modifiers:
                if m.type=='ARMATURE':m.object=rig
            bpy.data.objects.remove(ob,do_unlink=True);ob=new;task.solid.prepare(ob);task.continuous_normals(ob)
            for g in list(ob.vertex_groups):
                if not g.name.startswith('b_'):ob.vertex_groups.remove(g)
            changes.append({'component':key,'operation':'Restore original covered garment surface; merge redundant shading splits','before_vertices':before,'vertices':task.count(ob)})
        elif key not in ('body-09:000','body-09:004'):
            center=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices);distance=0
            for v in ob.data.vertices:
                delta=(v.co-center)*.05
                if delta.length>.016:delta=delta.normalized()*.016
                v.co+=delta;distance=max(distance,delta.length)
            changes.append({'component':key,'operation':'Fitted overlap allowance, capped at 16 mm','max_offset_m':distance})
    report=json.loads((OUT/'reduction-report.json').read_text());report['coverage_fit']=changes
    for row in report['components']:
        o=next(o for o in task.body(scene) if o['source_component']==row['component']);row.update(vertices=task.count(o),triangles=len(o.data.polygons),native_vertices=len(o.data.vertices))
    report['vertices']=sum(r['vertices'] for r in report['components']);report['triangles']=sum(r['triangles'] for r in report['components']);(OUT/'reduction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    actions={a for a in bpy.data.actions if a.get('source_clip')};bpy.data.libraries.write(str(OUT/(task.NAME+'.blend')),{scene,*actions},fake_user=True,compress=True);print('FIT',report['vertices'],report['triangles'],flush=True)
if __name__=='__main__':run()
