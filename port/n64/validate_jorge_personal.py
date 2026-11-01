"""Validate the material/first-person checkpoint without changing its scene."""
import bpy,json,csv,hashlib
import numpy as np
import personalize_jorge as task
task.configure();scene,rig=task.task.proof_scene();obs=sorted(task.task.body(scene),key=lambda o:o['source_component'])
rows=[]
for ob in obs:
    me=ob.data
    assert all(p.area>1e-12 and len(p.vertices)==3 for p in me.polygons),ob.name
    assert all(abs(sum(g.weight for g in v.groups)-1)<1e-5 for v in me.vertices),ob.name
    assert np.isfinite([v.co[:] for v in me.vertices]).all()
    assert np.isfinite([n.vector[:] for n in me.corner_normals]).all()
    assert len(me.materials)==1 and all(p.material_index==0 for p in me.polygons)
    rows.append([ob['source_component'],len(me.vertices),len(me.polygons)])
with (task.OUT/'component-budgets.csv').open('w') as f:
    writer=csv.writer(f,lineterminator="\n");writer.writerow(['component','vertices','triangles']);writer.writerows(rows)
pack=next(o for o in obs if o['source_component']=='backpack-14:000')
bs=next(n for n in pack.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
assert bs.inputs['Metallic'].default_value==0 and bs.inputs['Roughness'].default_value>.9
old=np.load(task.SOURCE/'gameplay-poses.npz');new=np.load(task.OUT/'gameplay-poses.npz')
assert np.array_equal(old['rest'],new['rest'][:len(old['rest'])])
assert np.array_equal(old['triangles'],new['triangles'][:len(old['triangles'])])
for i in range(39):assert np.array_equal(old[f'frames_{i}'],new[f'frames_{i}'][:,:len(old['rest'])])
report={'components':len(rows),'bones':len(rig.data.bones),'native_vertices':sum(r[1] for r in rows),
        'triangles':sum(r[2] for r in rows),'accepted_geometry_topology_and_all_poses_exact':True,
        'backpack_metallic':0,'backpack_roughness':float(bs.inputs['Roughness'].default_value),
        'weights_normals_and_material_assignments_valid':True,
        'source_blend_sha256':hashlib.sha256((task.OUT/(task.NAME+'.blend')).read_bytes()).hexdigest()}
(task.OUT/'personalization-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
