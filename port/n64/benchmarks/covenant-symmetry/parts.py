"""Regional source comparison: a good whole-body score can hide a lost limb."""
import sys,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from audit_pve_models import raster
from pack_assets import position
p=ROOT/'build/covenant-symmetry';old=json.loads((ROOT/'halo64-assets/assets/covenant-crunch/reduced-source.json').read_text());new=json.loads((p/'reduced-source.json').read_text());col=json.loads((p/'source-colors.json').read_text());report=[]
for name,part in [('grunt','head'),('hunter','l arm'),('hunter','r arm')]:
 m=old['models'][name];geoms=[m['source_geometry_lods'][m['n64_lods'][1]],m['source_geometry_lods'][m['n64_lods'][2]],new['models'][name]['source_geometry_lods']['n64 crunch']]
 bones={i for i,n in enumerate(m['nodes']) if ('head' in n['name'] if part=='head' else (' '+part[0]+' ' in n['name'] and any(s in n['name'] for s in ['upperarm','forearm','hand'])))}
 points=[];rgb=[]
 for k,g in enumerate(geoms):
  def weights(i):
   if 'skin_weights' in g:return g['skin_weights'][i]
   a,b,w=g['weights'][i];return [(a,1-w if b>=0 else 1)]+([(b,w)] if b>=0 else [])
  ids=[fi for fi,f in enumerate(g['faces']) if any(any(b in bones and w>.1 for b,w in weights(i)) for i in f)]
  points.append(np.array([[position(g['vertices'][i],(0,0,0)) for i in g['faces'][fi]] for fi in ids]))
  rgb.append(np.array([g['corner_colors'][fi] if k==2 else [c[:3] for c in col[name][1 if k==0 else 2][fi]] for fi in ids]))
 base=points[0];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2;extent=max(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.35
 sheet=Image.new('RGB',(256*4,282*4),(24,24,24));draw=ImageDraw.Draw(sheet)
 for vi,eye in enumerate([(1,0,0),(0,0,1),(0,0,-1),(1,.4,1)]):
  rr=[raster(x,c,eye,center,extent,256) for x,c in zip(points,rgb)];a,b,c=[r[1] for r in rr];diff=np.zeros_like(rr[0][0]);diff[a&c]=[65,80,85];diff[a&~c]=[255,75,80];diff[c&~a]=[65,210,255]
  for j,(im,title) in enumerate(zip([rr[0][0],rr[1][0],rr[2][0],diff],['Source far','Previous crunch','Corrected','Diff'])):
   sheet.paste(Image.fromarray(im),(j*256,vi*282+26));draw.text((j*256+4,vi*282+4),name+' '+part+' | '+title,fill='white')
  report.append({'model':name,'part':part,'view':vi,'previous_iou':float((a&b).sum()/max(1,(a|b).sum())),'corrected_iou':float((a&c).sum()/max(1,(a|c).sum()))})
 sheet.save(p/'silhouettes'/(name+'-'+part.replace(' ','-')+'.png'))
(p/'part-silhouettes.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
