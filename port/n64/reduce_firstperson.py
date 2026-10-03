"""Reduce original first-person gun/hands and bake shared retail animation skeletons."""
import json,math
from pathlib import Path

def reduce_firstperson(source,output):
 import bpy
 from mathutils import Quaternion,Vector,kdtree
 data=json.loads(Path(source).read_text());scene=bpy.data.scenes.new('Halo N64 - First person')
 if bpy.context.window:bpy.context.window.scene=scene
 def reduce_model(model,name,target):
  mesh=bpy.data.meshes.new(name);mesh.from_pydata(model['vertices'],[],model['faces']);uv=mesh.uv_layers.new(name='Xbox UV')
  for mi,tex in enumerate(model['textures']):
   mat=bpy.data.materials.new(name+str(mi));mat.use_nodes=True
   if tex:
    shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(tex,check_existing=True)
    mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
   mesh.materials.append(mat)
  for poly,mi in zip(mesh.polygons,model['materials']):
   poly.material_index=mi
   for loop in poly.loop_indices:
    u,v=model['uv'][mesh.loops[loop].vertex_index];uv.data[loop].uv=(u,1-v)
  obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj)
  if len(model['faces'])>target:
   mod=obj.modifiers.new('N64 first person triangle budget','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=target/len(model['faces']);mod.use_collapse_triangulate=True
  with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):dep=bpy.context.evaluated_depsgraph_get()
  dep.update();ev=obj.evaluated_get(dep);m=ev.to_mesh();m.calc_loop_triangles();tris=[]
  for tri in m.loop_triangles:
   p=[list(m.vertices[i].co) for i in tri.vertices];coords=[list(m.uv_layers.active.data[i].uv) for i in tri.loops]
   tris.append({'p':p,'uv':[[u,1-v] for u,v in coords],'material':tri.material_index})
  ev.to_mesh_clear()
  kd=kdtree.KDTree(len(model['vertices']))
  for i,p in enumerate(model['vertices']):kd.insert(p,i)
  kd.balance();weighted=[]
  for tri in tris:
   for p in tri['p']:
    _,i,_=kd.find(Vector(p));n0,n1,w=model['weights'][i]
    if n0<0:raise ValueError('Unresolved Xbox skin palette '+name)
    weighted.append((Vector(p),[(n0,1-w)]+([(n1,w)] if n1>=0 and w>0 else [])))
  return obj,tris,weighted
 def globals_for(states,parents):
  result=[None]*len(states)
  def visit(i):
   if result[i] is not None:return result[i]
   n=states[i];x,y,z,w=n['q'];m=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();m.translation=Vector(n['p']);p=parents[i]
   result[i]=visit(p)@m if p>=0 and p!=i else m
   return result[i]
  for i in range(len(states)):visit(i)
  return result
 hands=data['hands'];obj,htris,hweights=reduce_model(hands,'Xbox hands',100);obj.hide_set(True)
 hinv=[m.inverted() for m in globals_for(hands['nodes'],[n['parent'] for n in hands['nodes']])]
 result={'weapons':{}};limit={'idle':4,'fire':4,'reload':8,'melee':6}
 for idx,(name,weapon) in enumerate(data['weapons'].items()):
  gun=weapon['gun'];obj,gtris,gweights=reduce_model(gun,'FP '+name,120);obj.location=(idx*.5,0,0)
  ginv=[m.inverted() for m in globals_for(gun['nodes'],[n['parent'] for n in gun['nodes']])]
  skeleton=weapon['nodes'];lookup={n['name']:i for i,n in enumerate(skeleton)};clips={}
  for cname,clip in weapon['clips'].items():
   frames=[];count=min(limit[cname],len(clip['frames']))
   for fi in range(count):
    states=clip['frames'][round(fi*(len(clip['frames'])-1)/max(1,count-1))];pose=globals_for(states,[n['parent'] for n in skeleton]);points=[]
    for model,weighted,inverse in [(hands,hweights,hinv),(gun,gweights,ginv)]:
     skin=[pose[lookup[n['name']]]@inverse[i] for i,n in enumerate(model['nodes'])]
     for p,weights in weighted:
      v=Vector((0,0,0))
      for bone,w in weights:v+=(skin[bone]@p)*w
      if not all(math.isfinite(x) for x in v):raise ValueError('Nonfinite FP skin')
      points.append(list(v))
    frames.append(points)
   clips[cname]={'frames':frames,'duration':clip['duration'],'tag_name':clip['name']}
  tris=json.loads(json.dumps(htris+gtris))
  for t in tris[len(htris):]:t['material']+=len(hands['textures'])
  # Store idle-pose geometry as the static model, same vertex order as clips.
  for ti,t in enumerate(tris):t['p']=clips['idle']['frames'][0][ti*3:ti*3+3]
  result['weapons'][name]={'triangles':tris,'textures':hands['textures']+gun['textures'],'clips':clips}
 Path(output).write_text(json.dumps(result));bpy.data.libraries.write(str(Path(output).with_suffix('.blend')),{scene})
 print(json.dumps({n:len(w['triangles']) for n,w in result['weapons'].items()}))
if __name__=='__main__':
 import sys
 a=sys.argv[sys.argv.index('--')+1:];reduce_firstperson(*a)
