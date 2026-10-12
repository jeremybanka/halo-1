"""Select only redundant source foliage cards; preserve sampled color coverage.

Run on owned extracted meshes. Selection does not move vertices or rewrite UVs;
apply the retained face set through Blender and save only private asset banks.
"""
import argparse,json,sys,math
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_map_scenery import render
from audit_models import Mesh,engine,matching_bounds
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.output;root.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[2];models=json.loads(args.source.read_text());report=json.loads((repo/'halo64-assets/generated/maps/maps-report.json').read_text())
output={};metrics={}
angles=[(math.cos(a),e,math.sin(a)) for e in (-.4,.05,.4) for a in np.linspace(0,2*np.pi,8,endpoint=False)]
for path,model in models.items():
 if not ('trees' in path or 'plants' in path):continue
 material_names=report['maps']['beavercreek']['materials'];textures=[np.array(Image.open(repo/('halo64-assets/generated/maps/beavercreek-textures/packed-'+str(material_names.index(shader))+'.png')).convert('RGBA')) for shader in model['shaders']]
 leaf_materials={i for i,t in enumerate(textures) if np.any(t[...,3]<128)}
 points=np.array(model['vertices']);faces=model['faces'];leaf=[i for i,m in enumerate(model['materials']) if m in leaf_materials];opaque=[i for i in range(len(faces)) if i not in leaf]
 # Cards are coplanar edge-connected source triangles; UVs/points never change.
 edges={};normals={};parents={i:i for i in leaf}
 def parent(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 for i in leaf:
  p=points[faces[i]];n=np.cross(p[1]-p[0],p[2]-p[0]);n/=max(1e-12,np.linalg.norm(n));normals[i]=n
  for a,b in [(0,1),(1,2),(2,0)]:
   key=tuple(sorted([tuple(np.round(p[a],7)),tuple(np.round(p[b],7))]))
   for j in edges.get(key,[]):
    if model['materials'][i]==model['materials'][j] and abs(n@normals[j])>.99999:parents[parent(i)]=parent(j)
   edges.setdefault(key,[]).append(i)
 groups={}
 for i in leaf:groups.setdefault(parent(i),[]).append(i)
 groups=list(groups.values());masks=[]
 def sub(indices):return {**model,'faces':[faces[i] for i in indices],'materials':[model['materials'][i] for i in indices]}
 mesh=Mesh(engine(points[np.array(faces)]))
 for angle in angles:
  bounds=matching_bounds([mesh],angle)
  for size in (96,32):
   _,_,depth=render(sub(opaque),textures,bounds,angle,size,True)
   column=[]
   for group in groups:
    _,mask,z=render(sub(group),textures,bounds,angle,size,True);column.append((mask&(z>depth+1e-8)).ravel())
   masks.append(np.array(column))
 masks=np.transpose(np.array(masks),(1,0,2));counts=masks.sum(0).astype(np.int16);original=counts>0;limits=np.maximum(1,(original.sum(1)*.04).astype(int));lost=np.zeros(len(limits),int)
 retained=set(range(len(groups)));removed=[]
 while retained:
  best=None
  for group in retained:
   cost=(masks[group]&(counts==1)).sum(1)
   if np.any(lost+cost>limits):continue
   score=(float((cost/np.maximum(1,limits)).sum())+.00001)/len(groups[group])
   if best is None or score<best[0]:best=(score,group,cost)
  if best is None:break
  _,group,cost=best;counts-=masks[group];lost+=cost;retained.remove(group);removed.extend(groups[group])
 keep=sorted(set(range(len(faces)))-set(removed));output[path]={'keep_faces':keep,'source_triangles':len(faces),'retained_triangles':len(keep),'model':model['model'],'method':'Original textured cards retained or removed as complete coplanar groups; 24 directions x 96/32px visible-leaf coverage, maximum 4% loss per view'}
 metrics[path]={'groups':len(groups),'removed_faces':len(removed),'original_leaf_faces':len(leaf),'worst_leaf_coverage':float(((counts>0)&original).sum(1).astype(float).min()) if not len(limits) else float(np.min(((counts>0)&original).sum(1)/np.maximum(1,original.sum(1))))}
 print(path,len(faces),'->',len(keep),metrics[path],flush=True)
(root/'scenery-card-selection.json').write_text(json.dumps(output,indent=2));(root/'scenery-card-selection-metrics.json').write_text(json.dumps(metrics,indent=2))
