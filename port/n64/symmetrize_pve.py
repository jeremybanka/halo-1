"""Author mirrored Covenant bind meshes, including matching skin weights/colors.

Run author() in Blender. A clipped half is reflected with reversed winding;
center weights are invariant under the bone-name permutation. The Hunter retains its connected source body shell and intentional equipment;
its coarse shell is reduced with Blender bilateral symmetry enabled.
"""
import collections,copy,json,math
from pathlib import Path

def bone_pairs(nodes):
 names={n['name']:i for i,n in enumerate(nodes)};result=[]
 for i,n in enumerate(nodes):
  name=n['name'];other=name
  if ' left' in name:other=name.replace(' left',' right')
  elif ' right' in name:other=name.replace(' right',' left')
  elif 'left' in name:other=name.replace('left','right')
  elif 'right' in name:other=name.replace('right','left')
  elif ' l ' in name:other=name.replace(' l ',' r ')
  elif ' r ' in name:other=name.replace(' r ',' l ')
  if other!=name:assert other in names,(name,other)
  result.append(names[other])
 assert all(result[result[i]]==i for i in range(len(nodes)))
 return result

def normalize(weights):
 out={int(b):float(w) for b,w in weights.items() if w>1e-9};total=sum(out.values());assert total>0
 return {b:out[b]/total for b in sorted(out)}

def mix(a,b,t):
 return {'p':[x+(y-x)*t for x,y in zip(a['p'],b['p'])],
         'uv':[x+(y-x)*t for x,y in zip(a['uv'],b['uv'])],
         'color':[x+(y-x)*t for x,y in zip(a['color'],b['color'])],
         'tint':a['tint']+(b['tint']-a['tint'])*t,
         'skin':normalize({k:a['skin'].get(k,0)*(1-t)+b['skin'].get(k,0)*t for k in a['skin'].keys()|b['skin'].keys()})}

def center(v,pairs):
 v=copy.deepcopy(v);v['p'][1]=0
 w=collections.defaultdict(float)
 for b,x in v['skin'].items():w[b]+=x*.5;w[pairs[b]]+=x*.5
 v['skin']=normalize(w);return v

def half(poly,pairs,epsilon=1e-7,side=1):
 poly=copy.deepcopy(poly)
 for v in poly:
  if abs(v['p'][1])<=epsilon:v.update(center(v,pairs))
 out=[]
 for a,b in zip(poly,poly[1:]+poly[:1]):
  if a['p'][1]*side>=0:out.append(a)
  if (a['p'][1]<0<b['p'][1]) or (b['p'][1]<0<a['p'][1]):out.append(center(mix(a,b,a['p'][1]/(a['p'][1]-b['p'][1])),pairs))
 clean=[]
 for v in out:
  if not clean or math.dist(v['p'],clean[-1]['p'])>epsilon:clean.append(v)
 if len(clean)>1 and math.dist(clean[0]['p'],clean[-1]['p'])<=epsilon:clean.pop()
 return clean

def reflected(v,pairs):
 v=copy.deepcopy(v);v['p'][1]*=-1;v['skin']=normalize({pairs[b]:w for b,w in v['skin'].items()});return v

def mirror_geometry(g,colors,pairs,keep_materials=(),keep_bones=(),side=1):
 assert len(colors)==len(g['faces']);faces=[];retained=[];protected=0
 keep_faces=set();at=collections.defaultdict(list)
 if keep_bones:
  # The Hunter's arms, torso and legs share a closed shell. Preserve the
  # complete connected shell, reduced with Blender's bilateral constraint,
  # rather than opening cracks by splicing two incompatible triangulations.
  for fi,f in enumerate(g['faces']):
   for vi in f:
    at[tuple(round(x,6) for x in g['vertices'][vi])].append(fi)
    skin=g['skin_weights'][vi] if 'skin_weights' in g else [(g['weights'][vi][0],1-g['weights'][vi][2]),(g['weights'][vi][1],g['weights'][vi][2])]
    if any(b in keep_bones and w>.01 for b,w in skin):keep_faces.add(fi)
   if g['materials'][fi] in keep_materials:keep_faces.add(fi)
  todo=list(keep_faces)
  while todo:
   for vi in g['faces'][todo.pop()]:
    for fi in at[tuple(round(x,6) for x in g['vertices'][vi])]:
     if fi not in keep_faces:keep_faces.add(fi);todo.append(fi)
 for fi,(f,material) in enumerate(zip(g['faces'],g['materials'])):
  corners=[]
  for c,i in enumerate(f):
   if 'skin_weights' in g:weights=dict(g['skin_weights'][i])
   else:
    a,b,w=g['weights'][i];weights={a:1-w if b>=0 else 1}
    if b>=0 and w>0:weights[b]=weights.get(b,0)+w
   rgba=colors[fi][c];corners.append(dict(p=list(g['vertices'][i]),uv=list(g['uv'][i]),skin=normalize(weights),color=rgba[:3],tint=rgba[3]))
  if material in keep_materials or fi in keep_faces:retained.append((corners,material));protected+=1;continue
  poly=half(corners,pairs,side=side)
  if len(poly)<3:continue
  # A face lying wholly on the symmetry plane has no external area. Avoid
  # duplicate internal caps; original equipment is exempt above.
  if all(abs(v['p'][1])<1e-7 for v in poly):continue
  for j in range(1,len(poly)-1):
   tri=[poly[0],poly[j],poly[j+1]]
   faces.append((tri,material));faces.append(([reflected(v,pairs) for v in reversed(tri)],material))
 faces+=retained
 result={k:copy.deepcopy(v) for k,v in g.items() if k not in ('vertices','uv','weights','skin_weights','faces','materials','corner_colors','corner_tints')}
 result.update(vertices=[],uv=[],skin_weights=[],faces=[],materials=[],corner_colors=[],corner_tints=[]);lookup={}
 for tri,material in faces:
  indices=[]
  for v in tri:
   key=(*[round(x,9) for x in v['p']],*[round(x,9) for x in v['uv']],tuple((b,round(w,9)) for b,w in v['skin'].items()))
   if key not in lookup:
    lookup[key]=len(result['vertices']);result['vertices'].append(v['p']);result['uv'].append(v['uv']);result['skin_weights'].append(list(map(list,v['skin'].items())))
   indices.append(lookup[key])
  result['faces'].append(indices);result['materials'].append(material)
  result['corner_colors'].append([[max(0,min(255,round(c))) for c in v['color']] for v in tri]);result['corner_tints'].append([max(0,min(255,round(v['tint']))) for v in tri])
 return result,{'before_triangles':len(g['faces']),'triangles':len(faces),'protected_equipment_triangles':protected,'vertices':len(result['vertices'])}

def author(source,colors_path,output,blend):
 import bpy
 data=json.loads(Path(source).read_text());colors=json.loads(Path(colors_path).read_text());report={}
 scene=bpy.data.scenes.new('Bilateral Covenant authoring');bpy.context.window.scene=scene
 for row,name in enumerate(('grunt','elite','jackal','hunter')):
  model=data['models'][name];pairs=bone_pairs(model['nodes']);report[name]=[]
  for lod,key in enumerate(model['n64_lods']):
   g=model['source_geometry_lods'][key];keep=(3,4) if name=='hunter' else ()
   # Hunter arm lengths and bind skeletons are deliberately different. Keep
   # both complete articulated arms and their shoulders with the equipment;
   # reflecting one would disconnect the other from its original animation.
   arms={i for i,n in enumerate(model['nodes']) if any(s in n['name'] for s in ('clavicle','upperarm','forearm','hand'))} if name=='hunter' else set()
   # The Jackal's negative half retains the better elbow/beak outline in
   # six-angle source comparisons; the opposite reduced half forms a web.
   g,info=mirror_geometry(g,colors[name][lod],pairs,keep,arms,side=-1 if name=='jackal' else 1);report[name].append(info);model['source_geometry_lods'][key]=g
   # Weld preview position + skin only. Export keeps independent source UVs.
   verts=[];ids={};remap=[]
   for i,p in enumerate(g['vertices']):
    k=(*p,tuple(map(tuple,g['skin_weights'][i])))
    if k not in ids:ids[k]=len(verts);verts.append(p)
    remap.append(ids[k])
   mesh=bpy.data.meshes.new(name+' symmetric '+str(lod));mesh.from_pydata(verts,[],[[remap[i] for i in f] for f in g['faces']]);mesh.update()
   obj=bpy.data.objects.new(name+' symmetric '+str(lod),mesh);scene.collection.objects.link(obj);obj.location=(lod*1.6,row*2,0)
   c=mesh.color_attributes.new(name='Source Color',type='FLOAT_COLOR',domain='CORNER')
   for fi,face in enumerate(mesh.polygons):
    for li,rgb in zip(face.loop_indices,g['corner_colors'][fi]):c.data[li].color=[x/255 for x in rgb]+[1]
   mat=bpy.data.materials.new(name+' symmetric material '+str(lod));mat.use_nodes=True
   bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');attr=mat.node_tree.nodes.new('ShaderNodeVertexColor');attr.layer_name='Source Color';mat.node_tree.links.new(attr.outputs['Color'],bsdf.inputs['Base Color']);mesh.materials.append(mat)
   groups=[obj.vertex_groups.new(name=n['name']) for n in model['nodes']]
   for i,skin in enumerate(g['skin_weights']):
    for b,w in skin:groups[b].add([remap[i]],w,'REPLACE')
 Path(output).write_text(json.dumps(data,separators=(',',':'))+'\n');Path(output).with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
 bpy.ops.wm.save_as_mainfile(filepath=str(Path(blend).resolve()));print(json.dumps(report,indent=2))
