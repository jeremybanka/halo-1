"""Blender-side final validation, GLB export and round-trip verification."""
import bpy,bmesh,json,math,hashlib,struct,re
from pathlib import Path
from mathutils import Vector
from jorge_workshop import OUT,camera,render_views
scene=bpy.context.scene
parts=[o for o in scene.objects if o.type=='MESH']
for o in parts:
 o.name=re.sub(r'\.\d{3}$','',o.name)
 o.data.name=o.name
root=bpy.data.objects.new('Jorge',None);scene.collection.objects.link(root)
root['triangles']=600;root['source']='Halo Reach - Jorge-052';root['units']='meters'
for o in parts:o.parent=root
rows=[];points=[]
for o in parts:
 me=o.data;me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me)
 deg=[t for t in me.loop_triangles if (me.vertices[t.vertices[1]].co-me.vertices[t.vertices[0]].co).cross(me.vertices[t.vertices[2]].co-me.vertices[t.vertices[0]].co).length<1e-10]
 boundary=sum(e.is_boundary for e in bm.edges);nonman=sum(not e.is_manifold and not e.is_boundary for e in bm.edges)
 badmat=sum(p.material_index>=len(me.materials) for p in me.polygons)
 assert not deg and not nonman and not badmat, (o.name,len(deg),nonman,badmat)
 assert not any(not all(math.isfinite(c) for c in v.co) for v in me.vertices)
 vol=bm.calc_volume(signed=True)
 if not boundary:assert vol>0,(o.name,vol)
 rows.append({'name':o.name,'triangles':len(me.loop_triangles),'vertices':len(me.vertices),'boundary_edges':boundary,'nonmanifold_nonboundary_edges':nonman,'degenerate_triangles':len(deg),'signed_volume':vol})
 points.extend(o.matrix_world@v.co for v in me.vertices);bm.free()
tri=sum(r['triangles'] for r in rows);assert tri==600,tri
bounds=[[min(v[a] for v in points),max(v[a] for v in points)] for a in range(3)]
for o in scene.objects:o.select_set(o in parts or o==root)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-lowpoly.glb'),export_format='GLB',use_selection=True,export_yup=True,export_normals=True,export_materials='EXPORT',export_extras=True)
blob=(OUT/'jorge-lowpoly.glb').read_bytes();n,typ=struct.unpack_from('<II',blob,12);g=json.loads(blob[20:20+n])
gltf_tris=sum(g['accessors'][p['indices']]['count']//3 for m in g['meshes'] for p in m['primitives'])
assert gltf_tris==tri
check=bpy.data.scenes.new('GLB validation');bpy.context.window.scene=check
bpy.ops.import_scene.gltf(filepath=str(OUT/'jorge-lowpoly.glb'))
roundtrip=[];rp=[]
for o in check.objects:
 if o.type=='MESH':
  o.data.calc_loop_triangles();roundtrip.append(len(o.data.loop_triangles));rp.extend(o.matrix_world@v.co for v in o.data.vertices)
assert sum(roundtrip)==tri
rb=[[min(v[a] for v in rp),max(v[a] for v in rp)] for a in range(3)]
assert all(abs(a-b)<1e-5 for row,rr in zip(bounds,rb) for a,b in zip(row,rr)),(bounds,rb)
bpy.context.window.scene=scene
camera(scene,'three_quarter')
# Store only this project, without unrelated scenes from the user's Blender session.
bpy.data.libraries.write(str(OUT/'jorge-lowpoly.blend'),{scene},fake_user=True)
orig=json.loads((OUT/'source-inspection.json').read_text())
assert orig['source_sha256']==hashlib.sha256((OUT/'jorge-original.json').read_bytes()).hexdigest()
report={'original_triangles':orig['triangles'],'final_triangles':tri,'reduction_percent':100*(1-tri/orig['triangles']),
 'dimensions_m':[b-a for a,b in bounds],'bounds_m':bounds,'materials':len(g.get('materials',[])),
 'parts':rows,'glb_triangles':gltf_tris,'roundtrip_triangles':sum(roundtrip),'roundtrip_bounds_match':True,
 'source_json_unchanged':True,'normals':'Outward volumes verified for closed solids; no degenerate triangles.',
 'intentional_open_surfaces':'Copper visor is an overlay; collar underside is open where hidden inside torso.',
 'rigging':'Static reference-pose asset. Game rig and gameplay integration are not included.'}
(OUT/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='parts'}))
render_views(scene,'after')
