"""Original vehicle surfaces, materials, rigid parts and hatch animation.

The runtime refits the authored collision tree to the live turret/barrel/hatch
pose before applying the rigid-body transform.
"""
import json,struct
import numpy as np
from vehicle_parts import _layout,node_positions
from pack_fp_ammo import globals_for,rotate
from extract_extended import MODEL_PATHS

def vehicle_meshes(h,campaign,root):
 raw=json.loads((root/'build/n64/assets/extended-raw.json').read_text())
 lines=['#include "combat_geometry.h"'];rows=[];report={}
 for name in ['warthog','ghost','scorpion','banshee']:
  cache=campaign if name=='banshee' else h;es=cache.tag_index.tag_index
  path=MODEL_PATHS[name]
  candidates=[i for i,e in enumerate(es) if e.class_1.enum_name=='vehicle' and e.path.startswith('vehicles\\'+name+'\\')]
  if not any(es[i].path==path for i in candidates):path=es[candidates[0]].path
  obj=cache.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name=='vehicle'))
  collision=cache.get_meta(obj.obje_attrs.collision_model.id)
  model=raw['models'][name];nodes=model.get('bind_nodes',model['nodes']);transforms=globals_for(model['nodes'],model['nodes'])
  if name!='ghost':
   roots,kinds,turret,group=_layout(name,model);positions=node_positions(model['nodes'])
  else:roots,kinds,turret,group=[-1],[0],0,lambda i:0
  groups=[];pivots=[]
  for ri in roots:
   q=positions[ri] if ri>=0 else [0,0,0];pivots.append([q[0],q[2],-q[1]])
  vertices=[];triangles=[];materials={}
  for node in collision.nodes.STEPTREE:
   index=next(i for i,n in enumerate(nodes) if n['name']==node.name);r,p=transforms[index]
   for bsp in node.bsps.STEPTREE:
    base=len(vertices)
    for x,y,z,_ in struct.iter_unpack('<fffi',bsp.vertices.STEPTREE):
     q=rotate(r,[x,y,z]);q=[q[a]+p[a] for a in range(3)];vertices.append([round(q[0]*1024),round(q[2]*1024),round(-q[1]*1024)]);groups.append(group(index))
    edges=list(struct.iter_unpack('<6i',bsp.edges.STEPTREE))
    for si,(_,first,flags,_,material) in enumerate(struct.iter_unpack('<iiBbh',bsp.surfaces.STEPTREE)):
     if flags&2:continue
     polygon=[];edge=first
     while True:
      a,b,forward,reverse,left,right=edges[edge]
      polygon.append(base+(a if left==si else b));edge=forward if left==si else reverse
      if edge==first:break
      if len(polygon)>len(edges):raise ValueError('Broken collision surface loop')
     for j in range(1,len(polygon)-1):
      tri=(polygon[0],polygon[j],polygon[j+1]);triangles.append(tri)
      kind=collision.materials.STEPTREE[material].material_type.enum_name
      materials[tri]=['metal_thick','metal_thin','rubber','glass'].index(kind) if kind in ['metal_thick','metal_thin','rubber','glass'] else 0
  assert all(-32768<=v<=32767 for p in vertices for v in p)
  bounds=[f(p[a] for p in vertices) for f in [min,max] for a in range(3)]
  tree=[];ordered=[]
  def partition(items):
   index=len(tree);tree.append(None)
   pts=[vertices[v] for tri in items for v in tri]
   box=[f(p[a] for p in pts) for f in [min,max] for a in range(3)]
   if len(items)<=8:
    first=len(ordered);ordered.extend(items);tree[index]=(box,first,len(items),0)
   else:
    axis=max(range(3),key=lambda a:box[a+3]-box[a]);items.sort(key=lambda tri:sum(vertices[v][axis] for v in tri))
    mid=len(items)//2;left=partition(items[:mid]);right=partition(items[mid:]);tree[index]=(box,left,0,right)
   return index
  partition(triangles);triangles=ordered
  lines.append('static const bg_hit_node hit_'+name+'_nodes[]={'+','.join('{ {'+','.join(map(str,box))+'},'+str(first)+','+str(count)+','+str(right)+'}' for box,first,count,right in tree)+'};')
  for label,ctype,data in [('vertices','int16_t',vertices),('triangles','uint16_t',triangles)]:
   lines.append('static const '+ctype+' hit_'+name+'_'+label+'[][3]={'+','.join('{'+','.join(map(str,p))+'}' for p in data)+'};')
  lines.append('static const uint8_t hit_'+name+'_groups[]={'+','.join(map(str,groups))+'};')
  lines.append('static const bg_hit_part hit_'+name+'_parts[]={'+','.join('{'+str(k)+',{'+','.join(str(float(v))+'f' for v in p)+'}}' for k,p in zip(kinds,pivots))+'};')
  lines.append('static const uint8_t hit_'+name+'_materials[]={'+','.join(str(materials[t]) for t in triangles)+'};')
  rows.append('{hit_'+name+'_vertices,hit_'+name+'_triangles,hit_'+name+'_nodes,hit_'+name+'_materials,'+str(len(vertices))+','+str(len(triangles))+',{'+','.join(map(str,bounds))+'},hit_'+name+'_groups,hit_'+name+'_parts,'+str(len(roots))+','+str(len(tree))+','+str(roots.index(turret) if turret in roots else 0)+'},')
  report[name]={'vertices':len(vertices),'triangles':len(triangles),'bytes':(len(vertices)+len(triangles))*6+len(tree)*18,'bvh_nodes':len(tree),'source':obj.obje_attrs.collision_model.filepath,'pose':'authored collision nodes; live turret, barrel, hatch and hull transforms'}
 lines+=['const bg_hit_mesh bg_vehicle_hit_meshes[4]={',*rows,'};']
 # Match the renderer's authored opening/closing node transforms exactly.
 from reclaimer.animation.animation_decompilation import extract_animation
 rows=[]
 for name,cache in [('scorpion',h),('banshee',campaign)]:
  es=cache.tag_index.tag_index;path='vehicles\\'+name+'\\'+name
  ix=next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name=='model_animations')
  graph=cache.get_meta(ix);cache.meta_to_tag_data(graph,'antr',es[ix]);model=raw['models'][name]
  def matrix(states):
   r,p=globals_for(states,model['nodes'])[1];m=np.eye(4);m[:3,:3]=r;m[:3,3]=p;return m
  inverse=np.linalg.inv(matrix(model['nodes']));basis=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
  for label in ['stand opening','stand closing']:
   ix=next(i for i,a in enumerate(graph.animations.STEPTREE) if a.name==label);anim=extract_animation(ix,graph,write_jma=False)
   count=graph.animations.STEPTREE[ix].frame_count;frames=[]
   for frame in anim.frames[:count]:
    states=[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in frame]
    m=basis@matrix(states)@inverse@basis.T
    points=np.array([m[:3,3],m[:3,0],m[:3,1],m[:3,2]])
    frames.append(np.rint(points*4096).astype(int).tolist())
   symbol='hit_'+name+'_'+label.split()[1]
   lines.append('static const int16_t '+symbol+'[][4][3]='+str(frames).replace('[','{').replace(']','}')+';')
   rows.append('{'+symbol+','+str(count)+'}')
 lines+=['const bg_hit_hatch bg_hit_hatches[2][2]={{'+','.join(rows[:2])+'},{'+','.join(rows[2:])+'}};']
 return lines,report
