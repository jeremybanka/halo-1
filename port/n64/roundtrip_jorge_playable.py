"""Independent GLB importer check across all 39 body and weapon animations."""
import bpy,json
from mathutils.kdtree import KDTree
import jorge_playable_reduce as task
from validate_jorge_tactical import points
from validate_jorge_ce_materials import actions_for
s,r=task.proof_scene();body=task.body(s);weapon=next(o for o in s.objects if o.name.startswith('CE rifle'));actions=actions_for(r)
for a in bpy.data.actions:
    if a.get('source_clip') and a['source_clip'] not in actions:actions[a['source_clip']]=a
old=set(bpy.data.actions);other=bpy.data.scenes.new('Playable GLB roundtrip');other.render.fps=30;bpy.context.window.scene=other
bpy.ops.import_scene.gltf(filepath=str(task.OUT/(task.NAME+'-with-rifle.glb')))
ir=next(o for o in other.objects if o.type=='ARMATURE');iw=next(o for o in other.objects if o.type=='MESH' and o.name.startswith('CE rifle'));imported=task.body(other)
new=set(bpy.data.actions)-old;ia={n:next(a for a in new if a.name.startswith('Jorge / '+n)) for n in actions}
r.animation_data.use_nla=ir.animation_data.use_nla=False
assert len(actions)==39 and len(imported)==len(body)==49 and len(ir.data.bones)==85
report={}
def distance(a,b):
    tree=KDTree(len(a))
    for i,p in enumerate(a):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in b)
for name,a in actions.items():
    error=we=0;frames=sorted(set(round(a['duration_seconds']*30*f) for f in (0,.25,.5,.75,1)))
    for frame in frames:
        bpy.context.window.scene=s;r.animation_data.action=a;s.frame_set(frame);x=points(s,body);wa=weapon.matrix_world.copy()
        bpy.context.window.scene=other;ir.animation_data.action=ia[name];other.frame_set(frame);y=points(other,imported);wb=iw.matrix_world.copy()
        for k in x:error=max(error,distance(x[k],y[k]),distance(y[k],x[k]))
        we=max(we,max(abs(wa[i][j]-wb[i][j]) for i in range(4) for j in range(4)))
    assert max(error,we)<.0003,(name,error,we)
    report[name]={'samples':len(frames),'max_bidirectional_vertex_error_m':error,'max_weapon_matrix_error':we}
    print('ROUNDTRIP',name,error,we,flush=True)
(task.OUT/'roundtrip-validation.json').write_text(json.dumps(report,indent=2)+'\n')
