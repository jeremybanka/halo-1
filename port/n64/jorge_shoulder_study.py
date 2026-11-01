"""Surgical shoulder experiment. Source geometry/UV/rig retained; no primitives."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'halo64-assets/assets/jorge/shoulder-study'
def pos(p):return Vector((p[1]*3.048,-p[0]*3.048,p[2]*3.048))
def direction(p):return Vector((p[1],-p[0],p[2])).normalized()
def load_source(scene):
 raw=json.loads((OUT/'shoulder-original.json').read_text())
 me=bpy.data.meshes.new('Untouched shoulder geometry');me.from_pydata([pos(v) for v in raw['vertices']],[],raw['faces'])
 uv=me.uv_layers.new(name='Retail UV')
 for face in me.polygons:
  face.use_smooth=True
  for li,vi in zip(face.loop_indices,face.vertices):uv.data[li].uv=(raw['uv'][vi][0],1-raw['uv'][vi][1])
 me.normals_split_custom_set_from_vertices([direction(v) for v in raw['normals']])
 ob=bpy.data.objects.new('A - original',me);scene.collection.objects.link(ob)
 for n in raw['nodes']:ob.vertex_groups.new(name=n['name'])
 for i,ws in enumerate(raw['weights']):
  for bi,w in ws:ob.vertex_groups[bi].add([i],w,'REPLACE')
 return raw,ob

def connected(bm):
 remaining=set(bm.faces);cs=[]
 while remaining:
  todo=[min(remaining,key=lambda f:f.index)];remaining.remove(todo[0]);group=[]
  while todo:
   f=todo.pop();group.append(f)
   for e in f.edges:
    for n in e.link_faces:
     if n in remaining:remaining.remove(n);todo.append(n)
  cs.append(group)
 return sorted(cs,key=lambda c:-sum(f.calc_area() for f in c))
def inspect():
 scene=bpy.data.scenes.new('Jorge shoulder - inspection');bpy.context.window.scene=scene
 raw,a=load_source(scene);bm=bmesh.new();bm.from_mesh(a.data)
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bm.normal_update();bm.faces.ensure_lookup_table();bm.verts.ensure_lookup_table()
 cs=connected(bm);report=[]
 for i,fs in enumerate(cs):
  vs=set(v for f in fs for v in f.verts)
  info={'component':i,'triangles':sum(len(f.verts)-2 for f in fs),'area':sum(f.calc_area() for f in fs),'bounds':[[min(v.co[k] for v in vs),max(v.co[k] for v in vs)] for k in range(3)]}
  report.append(info)
  me=bpy.data.meshes.new('Component '+str(i));ids={v:j for j,v in enumerate(vs)}
  me.from_pydata([v.co for v in vs],[],[[ids[v] for v in f.verts] for f in fs]);o=bpy.data.objects.new(me.name,me);scene.collection.objects.link(o);o.hide_set(True)
 print(json.dumps({'source_vertices':len(a.data.vertices),'welded_vertices':len(bm.verts),'components':report},indent=2))
 (OUT/'component-inspection.json').write_text(json.dumps(report,indent=2))
 bm.free();bpy.data.libraries.write(str(OUT/'shoulder-inspection.blend'),{scene},fake_user=True)
 return scene

def culled_source(raw,a,scene):
 # Find physical islands on a disposable welded copy; keep source vertices/loops intact.
 bm=bmesh.new();bm.from_mesh(a.data)
 source_id=bm.faces.layers.int.new('source_face_id')
 for f in bm.faces:f[source_id]=f.index
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bm.normal_update();bm.faces.ensure_lookup_table()
 cs=connected(bm);keep=sorted(f[source_id] for c in cs[:2] for f in c);bm.free()
 ids=sorted({v for fi in keep for v in raw['faces'][fi]});remap={v:i for i,v in enumerate(ids)}
 me=bpy.data.meshes.new('Original plate and mounting structure')
 me.from_pydata([pos(raw['vertices'][i]) for i in ids],[],[[remap[v] for v in raw['faces'][fi]] for fi in keep])
 uv=me.uv_layers.new(name='Retail UV')
 for f,fi in zip(me.polygons,keep):
  f.use_smooth=True
  for li,vi in zip(f.loop_indices,raw['faces'][fi]):uv.data[li].uv=(raw['uv'][vi][0],1-raw['uv'][vi][1])
 me.normals_split_custom_set_from_vertices([direction(raw['normals'][i]) for i in ids])
 ob=bpy.data.objects.new('B - surgical culling',me);scene.collection.objects.link(ob)
 group=ob.vertex_groups.new(name='b_l_shoulderpad');group.add(list(range(len(ids))),1,'REPLACE')
 ob['operation']='Ten disconnected fastener meshes removed. Main plate and mounting geometry untouched.'
 return ob,keep

def welded(ob,scene,name):
 def key(co,uv):return tuple(round(x,6) for x in (*co,*uv))
 source=ob.data;uv0=source.uv_layers.active.data
 normals={key(source.vertices[l.vertex_index].co,uv0[l.index].uv):source.corner_normals[l.index].vector.copy() for l in source.loops}
 me=ob.data.copy();bm=bmesh.new();bm.from_mesh(me)
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
 bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-12],context='FACES_ONLY')
 bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
 bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
 bm.to_mesh(me);bm.free();me.update()
 uv1=me.uv_layers.active.data
 me.normals_split_custom_set([normals[key(me.vertices[l.vertex_index].co,uv1[l.index].uv)] for l in me.loops])
 out=bpy.data.objects.new(name,me);scene.collection.objects.link(out)
 for g in ob.vertex_groups:out.vertex_groups.new(name=g.name)
 return out

def constraints(ob):
 # Keep endpoints of actual boundaries and selected discontinuities stationary.
 me=ob.data;me.calc_loop_triangles();uv=me.uv_layers.active.data
 edges=defaultdict(list)
 for f in me.polygons:
  ls=list(f.loop_indices)
  for j,li in enumerate(ls):
   lj=ls[(j+1)%len(ls)];vi=me.loops[li].vertex_index;vj=me.loops[lj].vertex_index
   edges[tuple(sorted((vi,vj)))].append((f.index,{vi:li,vj:lj}))
 locked=set();reasons=Counter();protected=[]
 for (i,j),sides in edges.items():
  why=[]
  if len(sides)!=2:why.append('open_boundary')
  else:
   (fi,li),(fj,lj)=sides
   if any((uv[li[v]].uv-uv[lj[v]].uv).length>1e-4 for v in (i,j)):why.append('uv_seam')
   if me.polygons[fi].normal.dot(me.polygons[fj].normal)<math.cos(math.radians(30)):why.append('hard_contour')
   if any(me.corner_normals[li[v]].vector.dot(me.corner_normals[lj[v]].vector)<math.cos(math.radians(28)) for v in (i,j)):why.append('split_normal')
  if why:
   locked.update((i,j));reasons.update(why);protected.append((i,j))
 return locked,dict(reasons),protected

def probe():
 scene=bpy.data.scenes.new('Jorge shoulder - surgical study');bpy.context.window.scene=scene
 raw,a=load_source(scene);b,keep=culled_source(raw,a,scene)
 c=welded(b,scene,'C - constrained');locked,reasons,edges=constraints(c)
 print(json.dumps({'B_triangles':len(b.data.polygons),'C_welded_vertices':len(c.data.vertices),'locked_vertices':len(locked),'constraint_edges':len(edges),'reasons':reasons}))
 return scene

def select(ob):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob

def count(ob):
 ob.data.calc_loop_triangles();return len(ob.data.loop_triangles)

def apply_reduction(ob,ratio,locked=None):
 select(ob);mod=ob.modifiers.new('Contour-constrained collapse' if locked is not None else 'Direct collapse','DECIMATE')
 mod.ratio=ratio;mod.use_collapse_triangulate=True
 if locked is not None:
  g=ob.vertex_groups.new(name='Reduction freedom')
  for v in ob.data.vertices:g.add([v.index],0 if v.index in locked else 1,'REPLACE')
  mod.vertex_group=g.name;mod.vertex_group_factor=1000
 bpy.ops.object.modifier_apply(modifier=mod.name)
 return count(ob)

def transfer_normals(ob,source):
 from mathutils.bvhtree import BVHTree
 from mathutils.geometry import barycentric_transform
 src=source.data;src.calc_loop_triangles();tris=list(src.loop_triangles)
 tree=BVHTree.FromPolygons([v.co for v in src.vertices],[t.vertices for t in tris],all_triangles=True)
 exact=defaultdict(list);uv=src.uv_layers.active.data
 key=lambda co:tuple(round(x,6) for x in co)
 # Identify UV charts so nearest-surface sampling cannot jump across a folded seam.
 adjacency=defaultdict(set);edge_faces=defaultdict(list)
 for ti,t in enumerate(tris):
  corners=[key((*src.vertices[v].co,*uv[li].uv)) for v,li in zip(t.vertices,t.loops)]
  for j in range(3):edge_faces[tuple(sorted((corners[j],corners[(j+1)%3])))].append(ti)
 for faces in edge_faces.values():
  for ti in faces:adjacency[ti].update(faces)
 charts={};chart_faces=[]
 for ti in range(len(tris)):
  if ti in charts:continue
  cid=len(chart_faces);todo=[ti];group=[];charts[ti]=cid
  while todo:
   fi=todo.pop();group.append(fi)
   for ni in adjacency[fi]:
    if ni not in charts:charts[ni]=cid;todo.append(ni)
  chart_faces.append(group)
 chart_trees=[BVHTree.FromPolygons([v.co for v in src.vertices],[tris[i].vertices for i in fs],all_triangles=True) for fs in chart_faces]
 for ti,t in enumerate(tris):
  center=sum((src.vertices[i].co for i in t.vertices),Vector())/3
  for vi,li in zip(t.vertices,t.loops):exact[(key(src.vertices[vi].co),charts[ti])].append((uv[li].uv.copy(),src.corner_normals[li].vector.copy(),center))
 normals=[];target_uv=ob.data.uv_layers.active.data
 for face in ob.data.polygons:
  center=sum((ob.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
  cid=charts[tree.find_nearest(center)[2]]
  for li in face.loop_indices:
   l=ob.data.loops[li];co=ob.data.vertices[l.vertex_index].co;matches=exact.get((key(co),cid))
   if matches:
    source_uv,n,_=min(matches,key=lambda item:(item[2]-center).length_squared)
    target_uv[li].uv=source_uv
   else:
    hit,face_normal,idx,distance=chart_trees[cid].find_nearest(co);t=tris[chart_faces[cid][idx]]
    n=barycentric_transform(hit,*[src.vertices[i].co for i in t.vertices],*[src.corner_normals[i].vector for i in t.loops]).normalized()
    sampled_uv=barycentric_transform(hit,*[src.vertices[i].co for i in t.vertices],*[Vector((*uv[i].uv,0)) for i in t.loops])
    target_uv[li].uv=sampled_uv.xy
   normals.append(n)
 for f in ob.data.polygons:f.use_smooth=True
 ob.data.normals_split_custom_set(normals)

def make_rig(scene,raw):
 from mathutils import Quaternion
 arm=bpy.data.armatures.new('Original Reach skeleton - 85 nodes');rig=bpy.data.objects.new('Original Reach rig',arm);scene.collection.objects.link(rig)
 select(rig);bpy.ops.object.mode_set(mode='EDIT');world=[];bones=[]
 rot=Matrix(((0,1,0),(-1,0,0),(0,0,1)))
 for n in raw['nodes']:
  x,y,z,w=n['q'];q=Quaternion((w,x,y,z));q.normalize()
  local=q.to_matrix().to_4x4();local.translation=Vector(n['p'])
  g=world[n['parent']]@local if n['parent']>=0 else local;world.append(g)
  mat=(rot@g.to_3x3()).to_4x4();mat.translation=pos(g.translation)
  bone=arm.edit_bones.new(n['name']);bone.head=mat.translation;bone.tail=bone.head+mat.to_3x3()@Vector((0,.045,0));bone.matrix=mat
  if n['parent']>=0:bone.parent=bones[n['parent']]
  bones.append(bone)
 bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
 return rig

def material(raw):
 mat=bpy.data.materials.new('Retail diffuse and normal with Jorge color mask');mat.use_nodes=True
 ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED')
 bs.inputs['Roughness'].default_value=.73
 tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(raw['material']['diffuse'],check_existing=True);tex.image.alpha_mode='NONE';color=tex.outputs['Color']
 mask=ns.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(raw['material']['cc'],check_existing=True);mask.image.colorspace_settings.name='Non-Color';mask.image.alpha_mode='NONE'
 sep=ns.new('ShaderNodeSeparateColor');ls.new(mask.outputs['Color'],sep.inputs['Color'])
 for ch,tint in [('Red',(.42,.48,.22,1)),('Green',(.5,.52,.35,1)),('Blue',(.42,.08,.055,1))]:
  mix=ns.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';ls.new(sep.outputs[ch],mix.inputs[0]);ls.new(color,mix.inputs[1]);mix.inputs[2].default_value=tint;color=mix.outputs[0]
 ls.new(color,bs.inputs['Base Color'])
 normal=ns.new('ShaderNodeTexImage');normal.image=bpy.data.images.load(raw['normal_map'],check_existing=True);normal.image.colorspace_settings.name='Non-Color'
 # D3D tangent normal Y is inverted for Blender/glTF. Bake this conversion for portability.
 ns_sep=ns.new('ShaderNodeSeparateColor');ls.new(normal.outputs['Color'],ns_sep.inputs['Color'])
 inv=ns.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1;ls.new(ns_sep.outputs['Green'],inv.inputs[1])
 combine=ns.new('ShaderNodeCombineColor');ls.new(ns_sep.outputs['Red'],combine.inputs['Red']);ls.new(inv.outputs[0],combine.inputs['Green']);ls.new(ns_sep.outputs['Blue'],combine.inputs['Blue'])
 nm=ns.new('ShaderNodeNormalMap');ls.new(combine.outputs[0],nm.inputs['Color']);ls.new(nm.outputs[0],bs.inputs['Normal'])
 mat['normal_note']='Original CTX1 normal map, D3D green channel inverted; game lighting not recreated.'
 return mat

def simple_material(name,wire=False):
 m=bpy.data.materials.new(name);m.use_nodes=True;ns=m.node_tree.nodes;ls=m.node_tree.links
 bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(.42,.47,.51,1);bs.inputs['Roughness'].default_value=.8
 if wire:
  w=ns.new('ShaderNodeWireframe');w.use_pixel_size=True;w.inputs['Size'].default_value=.65
  mix=ns.new('ShaderNodeMixRGB');ls.new(w.outputs[0],mix.inputs[0]);mix.inputs[1].default_value=(.5,.56,.6,1);mix.inputs[2].default_value=(.018,.022,.03,1);ls.new(mix.outputs[0],bs.inputs['Base Color'])
 return m

VIEWS={'front':(0,-1,0),'side':(1,0,0),'three_quarter':(1,-1,.6)}
CENTER=Vector((.3708,.11135,1.77667))
def studio(scene):
 scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=540;scene.render.resolution_y=540;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True;scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-2
 scene.world=bpy.data.worlds.new('Shoulder neutral studio');scene.world.use_nodes=True
 next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.28,.28,.28,1)
 for name,delta,power,size in [('Key',(.45,-.65,1),45,1.1),('Fill',(-.7,-.4,.3),20,1),('Rim',(.3,.7,.7),55,.8)]:
  d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size
  o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=CENTER+Vector(delta);o.rotation_euler=(CENTER-o.location).to_track_quat('-Z','Y').to_euler()
 d=bpy.data.cameras.new('Matched orthographic camera');d.type='ORTHO';d.ortho_scale=.52
 o=bpy.data.objects.new(d.name,d);scene.collection.objects.link(o);scene.camera=o;camera(scene,'three_quarter')

def camera(scene,view):
 scene.camera.location=CENTER+Vector(VIEWS[view])*2;scene.camera.rotation_euler=(CENTER-scene.camera.location).to_track_quat('-Z','Y').to_euler()

def build():
 from mathutils.kdtree import KDTree
 scene=bpy.data.scenes.new('Jorge shoulder - A B C D');bpy.context.window.scene=scene
 raw,a=load_source(scene);a.name='A - original';b,keep=culled_source(raw,a,scene);b.name='B - surgical culling'
 c=welded(b,scene,'C - constrained');locked,reasons,edges=constraints(c)
 anchors=[c.data.vertices[i].co.copy() for i in sorted(locked)]
 key=lambda p:tuple(round(x,6) for x in p)
 protected=[frozenset((key(c.data.vertices[i].co),key(c.data.vertices[j].co))) for i,j in edges]
 ct=apply_reduction(c,.90,locked)
 out_edges={frozenset((key(c.data.vertices[e.vertices[0]].co),key(c.data.vertices[e.vertices[1]].co))) for e in c.data.edges}
 kd=KDTree(len(c.data.vertices))
 for v in c.data.vertices:kd.insert(v.co,v.index)
 kd.balance();anchor_errors=[kd.find(p)[2] for p in anchors]
 assert max(anchor_errors)<1e-7 and all(e in out_edges for e in protected),'Constraints violated'
 # Search exact actual count, not a merely matching modifier ratio.
 lo,hi=0.0,1.0;d=None
 for attempt in range(28):
  if d:bpy.data.objects.remove(d,do_unlink=True)
  d=welded(a,scene,'D - direct decimation');ratio=(lo+hi)/2;dt=apply_reduction(d,ratio)
  if dt==ct:break
  if dt<ct:lo=ratio
  else:hi=ratio
 aligned=0
 if dt!=ct:
  # A boundary collapse makes the direct sequence skip this integer count.
  # Neutral subdivision adds no shape/detail; record it rather than hide the mismatch.
  bpy.data.objects.remove(d,do_unlink=True);d=welded(a,scene,'D - direct decimation');dt=apply_reduction(d,lo);ratio=lo
  assert ct-dt==1,(ct,dt)
  bm=bmesh.new();bm.from_mesh(d.data)
  edge=max((e for e in bm.edges if e.is_boundary),key=lambda e:e.calc_length())
  bmesh.ops.subdivide_edges(bm,edges=[edge],cuts=1,use_grid_fill=False)
  bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(d.data);bm.free();aligned=1;dt=count(d)
 assert dt==ct,(ct,dt)
 transfer_normals(c,b);transfer_normals(d,a)
 textured=material(raw);clay=simple_material('Untextured - no normal map');wire=simple_material('Topology - no normal map',True)
 clay.use_fake_user=True;wire.use_fake_user=True
 rig=make_rig(scene,raw);variants=[a,b,c,d]
 report={'source_sha256':hashlib.sha256((OUT/'shoulder-original.json').read_bytes()).hexdigest(),'counts':{},'source_bones':len(raw['nodes']),
  'removed_fasteners':10,'removed_fastener_triangles':1080,'plate_triangles_unchanged_in_B':828,'mount_triangles_unchanged_in_B':16,
  'constraint_reasons':reasons,'protected_edges':len(edges),'protected_edges_retained':sum(e in out_edges for e in protected),
  'protected_vertices':len(locked),'max_protected_vertex_displacement_m':max(anchor_errors),'direct_ratio':ratio,'direct_neutral_triangle_alignment':aligned,'poses':{},'geometry':{}}
 for label,ob in zip('ABCD',variants):
  ob['variant']=label;ob['triangles']=count(ob);ob.data.materials.clear();ob.data.materials.append(textured)
  # This shoulder is rigid in the retail asset: all source weights are 100% node 39.
  assert all(len(ws)==1 and ws[0][0]==39 and abs(ws[0][1]-1)<1e-6 for ws in raw['weights'])
  ob.vertex_groups.clear();group=ob.vertex_groups.new(name=raw['nodes'][39]['name']);group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
  arm=ob.modifiers.new('Original shoulder attachment','ARMATURE');arm.object=rig;ob.parent=rig
  report['counts'][label]={'triangles':count(ob),'vertices':len(ob.data.vertices)}
  bm=bmesh.new();bm.from_mesh(ob.data);bm.normal_update()
  report['geometry'][label]={'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'loose_vertices':sum(not v.link_faces for v in bm.verts),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_not_boundary':sum(not e.is_manifold and not e.is_boundary for e in bm.edges),'uv_layers':len(ob.data.uv_layers)};bm.free()
 validate_poses(scene,rig,variants,report)
 measure_surfaces(b,c,d,report)
 assert report['retained_plate_surface_error_m']['C']['maximum']<.001,'Retained-surface sample error exceeds 1 mm'
 studio(scene)
 for ob in variants:ob.hide_render=ob!=c;ob.hide_set(ob!=c)
 rig.hide_set(True);select(c)
 for im in bpy.data.images:
  if im.filepath and 'jorge' in bpy.path.abspath(im.filepath):im.pack()
 (OUT/'study-report.json').write_text(json.dumps(report,indent=2))
 bpy.data.libraries.write(str(OUT/'jorge-shoulder-study.blend'),{scene,clay,wire},fake_user=True)
 print(json.dumps(report,indent=2));return scene

def measure_surfaces(b,c,d,report):
 from mathutils.bvhtree import BVHTree
 from mathutils.kdtree import KDTree
 # Sample only retained armor, so deliberately removed bolts do not mask plate distortion.
 points=[v.co.copy() for v in b.data.vertices]
 for f in b.data.polygons:
  vs=[b.data.vertices[i].co for i in f.vertices]
  points.append(sum(vs,Vector())/3)
  points.extend((vs[i]+vs[(i+1)%3])/2 for i in range(3))
 report['retained_plate_surface_error_m']={}
 for label,ob in [('C',c),('D',d)]:
  me=ob.data;me.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in me.vertices],[t.vertices for t in me.loop_triangles],all_triangles=True)
  distances=[tree.find_nearest(p)[3] for p in points]
  report['retained_plate_surface_error_m'][label]={'samples':len(points),'rms':(sum(x*x for x in distances)/len(distances))**.5,'maximum':max(distances)}

POSES={'rest':{},'arm_raised':{'b_l_upperarm':(0,0,math.radians(55))},'aiming':{'b_l_upperarm':(math.radians(-35),math.radians(25),math.radians(15))},'pad_articulation':{'b_l_shoulderpad':(math.radians(20),math.radians(-15),0)}}
def set_pose(rig,pose):
 for p in rig.pose.bones:p.rotation_mode='XYZ';p.rotation_euler=(0,0,0)
 for name,angles in POSES[pose].items():
  assert name in rig.pose.bones,name
  rig.pose.bones[name].rotation_euler=angles
 bpy.context.view_layer.update()

def validate_poses(scene,rig,variants,report):
 for pose in POSES:
  set_pose(rig,pose);dg=bpy.context.evaluated_depsgraph_get();p=rig.pose.bones['b_l_shoulderpad'];xf=p.matrix@p.bone.matrix_local.inverted();errors={}
  for ob in variants:
   ev=ob.evaluated_get(dg);me=ev.to_mesh()
   errors[ob['variant']]=max((v.co-xf@original.co).length for v,original in zip(me.vertices,ob.data.vertices));ev.to_mesh_clear()
  report['poses'][pose]=errors
  assert max(errors.values())<1e-5,(pose,errors)
 set_pose(rig,'rest')

def render_all():
 scene=bpy.context.scene;variants={ob['variant']:ob for ob in scene.objects if 'variant' in ob}
 originals={label:ob.data.materials[0] for label,ob in variants.items()}
 mats={'textured':variants['A'].data.materials[0],'clay':next(m for m in bpy.data.materials if m.name.startswith('Untextured - no normal map')),'wire':next(m for m in bpy.data.materials if m.name.startswith('Topology - no normal map'))}
 folder=OUT/'renders';folder.mkdir(exist_ok=True)
 for style,mat in mats.items():
  for label,ob in variants.items():
   for other in variants.values():other.hide_render=other!=ob
   ob.data.materials[0]=originals[label] if style=='textured' else mat
   for view in VIEWS:
    camera(scene,view);scene.render.filepath=str(folder/f'{label}-{style}-{view}.png');bpy.ops.render.render(write_still=True)
   ob.data.materials[0]=originals[label]
 rig=next(o for o in scene.objects if o.type=='ARMATURE')
 c=variants['C']
 for ob in variants.values():ob.hide_render=ob!=c
 for pose in POSES:
  set_pose(rig,pose);camera(scene,'three_quarter')
  # Follow the rigid pad for readable articulation checks.
  p=rig.pose.bones['b_l_shoulderpad'];xf=p.matrix@p.bone.matrix_local.inverted();focus=xf@CENTER
  scene.camera.location=focus+Vector(VIEWS['three_quarter'])*2;scene.camera.rotation_euler=(focus-scene.camera.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(folder/f'C-pose-{pose}.png');bpy.ops.render.render(write_still=True)
 set_pose(rig,'rest')

def rebake_surface(source,target,scene,label):
 # Retain the imported UV layer for inspection, and bake onto a new distortion-controlled atlas.
 select(target)
 uv=target.data.uv_layers.new(name='Rebaked UV');target.data.uv_layers.active=uv
 for layer in target.data.uv_layers:layer.active_render=layer==uv
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
 bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.025)
 bpy.ops.object.mode_set(mode='OBJECT')
 srcmat=source.data.materials[0];srcns=srcmat.node_tree.nodes;srcls=srcmat.node_tree.links
 srcbs=next(n for n in srcns if n.type=='BSDF_PRINCIPLED');srcout=next(n for n in srcns if n.type=='OUTPUT_MATERIAL')
 targetmat=srcmat.copy();targetmat.name=f'{label} - rebaked original surface';target.data.materials[0]=targetmat
 ns=targetmat.node_tree.nodes;ls=targetmat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED');nm=next(n for n in ns if n.type=='NORMAL_MAP')
 uvnode=ns.new('ShaderNodeUVMap');uvnode.uv_map=uv.name;nm.uv_map=uv.name
 for ob in scene.objects:
  if ob.type=='MESH':ob.hide_render=ob not in (source,target)
 source.hide_set(False);target.hide_set(False)
 for kind,socket in [('color',bs.inputs['Base Color']),('normal',nm.inputs['Color'])]:
  im=bpy.data.images.new(f'{label} rebaked {kind}',512,512,alpha=False);im.colorspace_settings.name='sRGB' if kind=='color' else 'Non-Color'
  tex=ns.new('ShaderNodeTexImage');tex.image=im;ls.new(uvnode.outputs[0],tex.inputs['Vector'])
  for n in ns:n.select=False
  tex.select=True;ns.active=tex
  emit=None
  if kind=='color':
   emit=srcns.new('ShaderNodeEmission');srcls.new(srcbs.inputs['Base Color'].links[0].from_socket,emit.inputs['Color']);srcls.new(emit.outputs[0],srcout.inputs['Surface'])
  select(target);source.select_set(True);scene.cycles.samples=8
  bpy.ops.object.bake(type='EMIT' if kind=='color' else 'NORMAL',use_selected_to_active=True,cage_extrusion=.006,max_ray_distance=.02,margin=8,use_clear=True)
  if emit:srcns.remove(emit);srcls.new(srcbs.outputs[0],srcout.inputs['Surface'])
  im.filepath_raw=str(OUT/'textures'/f'shoulder-{label}-{kind}-rebaked.png');im.file_format='PNG';im.save();im.pack();ls.new(tex.outputs['Color'],socket)
 target['texture_note']='Original surface color and tangent normals rebaked to a separate atlas; retail UV layer retained for inspection.'
 scene.cycles.samples=24

def export_all():
 scene=next(s for s in bpy.data.scenes if any('variant' in o for o in s.objects));bpy.context.window.scene=scene
 variants={ob['variant']:ob for ob in scene.objects if 'variant' in ob};a=variants['A'];mat=a.data.materials[0]
 rig=next(o for o in scene.objects if o.type=='ARMATURE');set_pose(rig,'rest')
 for ob in variants.values():ob.hide_render=ob!=a;ob.hide_set(False)
 select(a);ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED');out=next(n for n in ns if n.type=='OUTPUT_MATERIAL')
 nm=next(n for n in ns if n.type=='NORMAL_MAP')
 sources=[('Jorge shoulder color',bs.inputs['Base Color'],False),('Jorge shoulder tangent normal',nm.inputs['Color'],True)]
 for name,socket,noncolor in sources:
  source=socket.links[0].from_socket;emit=ns.new('ShaderNodeEmission');ls.new(source,emit.inputs['Color']);ls.new(emit.outputs[0],out.inputs['Surface'])
  im=bpy.data.images.new(name,256,256,alpha=False);im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB'
  target=ns.new('ShaderNodeTexImage');target.image=im
  for n in ns:n.select=False
  target.select=True;ns.active=target
  scene.cycles.samples=1;bpy.ops.object.bake(type='EMIT',margin=4,use_clear=True)
  im.filepath_raw=str(OUT/'textures'/('shoulder-normal-opengl.png' if noncolor else 'shoulder-color.png'));im.file_format='PNG';im.save();im.pack()
  ls.new(target.outputs['Color'],socket);ns.remove(emit)
 ls.new(bs.outputs[0],out.inputs['Surface']);scene.cycles.samples=24
 rebake_surface(variants['B'],variants['C'],scene,'C')
 rebake_surface(variants['A'],variants['D'],scene,'D')
 for label,ob in variants.items():
  select(ob);rig.hide_set(False);rig.select_set(True)
  bpy.ops.export_scene.gltf(filepath=str(OUT/f'shoulder-{label}.glb'),export_format='GLB',use_selection=True,export_animations=False,export_skins=True)
 c=variants['C']
 for ob in variants.values():ob.hide_render=ob!=c;ob.hide_set(ob!=c)
 rig.hide_set(True);select(c);camera(scene,'three_quarter')
 # Save a normal standalone project after loading the isolated library in this background process.
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-shoulder-study.blend'))

if __name__=='__main__':
 import sys
 if '--export' in sys.argv:export_all()
 if '--render' in sys.argv:render_all()
