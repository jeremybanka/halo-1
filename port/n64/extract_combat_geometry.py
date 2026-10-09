"""Compact original vehicle collision surfaces, at their authored bind pose.

The hull follows the live rigid-body basis. Articulated collision nodes retain
bind pose until the moving-node collision adapter is available.
"""
import json,struct
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
  model=raw['models'][name];nodes=model.get('bind_nodes',model['nodes']);transforms=globals_for(nodes,nodes)
  vertices=[];triangles=[]
  for node in collision.nodes.STEPTREE:
   index=next(i for i,n in enumerate(nodes) if n['name']==node.name);r,p=transforms[index]
   for bsp in node.bsps.STEPTREE:
    base=len(vertices)
    for x,y,z,_ in struct.iter_unpack('<fffi',bsp.vertices.STEPTREE):
     q=rotate(r,[x,y,z]);q=[q[a]+p[a] for a in range(3)];vertices.append([round(q[0]*1024),round(q[2]*1024),round(-q[1]*1024)])
    edges=list(struct.iter_unpack('<6i',bsp.edges.STEPTREE))
    for si,(_,first,flags,_,material) in enumerate(struct.iter_unpack('<iiBbh',bsp.surfaces.STEPTREE)):
     if flags&2:continue
     polygon=[];edge=first
     while True:
      a,b,forward,reverse,left,right=edges[edge]
      polygon.append(base+(a if left==si else b));edge=forward if left==si else reverse
      if edge==first:break
      if len(polygon)>len(edges):raise ValueError('Broken collision surface loop')
     triangles.extend([polygon[0],polygon[j],polygon[j+1]] for j in range(1,len(polygon)-1))
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
  rows.append('{hit_'+name+'_vertices,hit_'+name+'_triangles,hit_'+name+'_nodes,'+str(len(vertices))+','+str(len(triangles))+',{'+','.join(map(str,bounds))+'}},')
  report[name]={'vertices':len(vertices),'triangles':len(triangles),'bytes':(len(vertices)+len(triangles))*6+len(tree)*18,'bvh_nodes':len(tree),'source':obj.obje_attrs.collision_model.filepath,'pose':'authored bind; live hull orientation'}
 lines+=['const bg_hit_mesh bg_vehicle_hit_meshes[4]={',*rows,'};']
 return lines,report
