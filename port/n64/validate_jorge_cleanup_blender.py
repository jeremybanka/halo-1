"""Independently reimport the cleaned GLB, check rest geometry, and render it."""
import bpy,json
from mathutils.kdtree import KDTree
import jorge_surgical_cleanup as jsc

raw=json.loads((jsc.OUT/'jorge-cleaned.json').read_text())
scene=bpy.data.scenes.new('GLB round-trip validation');bpy.context.window.scene=scene
bpy.ops.import_scene.gltf(filepath=str(jsc.OUT/'jorge-cleaned.glb'))
scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE']
# Blender's glTF importer also creates an unskinned custom bone-display mesh.
# It is an editor helper, not part of the exported character.
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
helpers=[o for o in scene.objects if o.type=='MESH' and o not in meshes]
for helper in helpers:helper.hide_render=True
assert len(rigs)==1 and len(rigs[0].data.bones)==85
assert {b.name for b in rigs[0].data.bones}=={n['name'] for n in raw['nodes']}
kd=KDTree(len(raw['vertices']))
for i,v in enumerate(raw['vertices']):kd.insert(jsc.pos(v),i)
kd.balance();points=[];triangles=0;max_error=0.;bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
for ob in meshes:
    ev=ob.evaluated_get(dg);me=ev.to_mesh();me.calc_loop_triangles();triangles+=len(me.loop_triangles)
    for v in me.vertices:
        co=ob.matrix_world@v.co;points.append(co);max_error=max(max_error,kd.find(co)[2])
    ev.to_mesh_clear()
assert triangles==len(raw['faces'])==26076,(scene.name,len(meshes),triangles,len(raw['faces']),[(o.name,len(o.data.polygons)) for o in meshes[:3]])
assert max_error<1e-5,max_error
reverse=KDTree(len(points))
for i,p in enumerate(points):reverse.insert(p,i)
reverse.balance();max_reverse=max(reverse.find(jsc.pos(v))[2] for v in raw['vertices']);assert max_reverse<1e-5,max_reverse
report={'triangles':triangles,'mesh_objects':len(meshes),'bones':len(rigs[0].data.bones),'importer_display_helpers_excluded':[o.name for o in helpers],'max_export_to_source_vertex_error_m':max_error,'max_source_to_export_vertex_error_m':max_reverse}
(jsc.OUT/'roundtrip-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
jsc.studio(scene);scene.render.filepath=str(jsc.OUT/'renders'/'B-glb-roundtrip-three_quarter.png');bpy.ops.render.render(write_still=True)
