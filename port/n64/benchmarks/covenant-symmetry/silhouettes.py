"""Reference/previous/corrected silhouettes, including isolated skull and arms."""
import sys,json,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
import numpy as np
from PIL import Image,ImageDraw
from audit_pve_models import raster,colors,read
from pack_assets import position
out=ROOT/'build/covenant-symmetry';dest=out/'silhouettes';dest.mkdir(exist_ok=True)
old=json.loads((ROOT/'halo64-assets/assets/covenant-crunch/reduced-source.json').read_text());new=json.loads((out/'reduced-source.json').read_text());col=json.loads((out/'source-colors.json').read_text());rows=[]
views=[(1,0,0),(-1,0,0),(0,0,1),(0,0,-1),(1,.4,1),(-1,.3,-1)]
labels=['front','back','left','right','front oblique','back oblique']
for name in ['grunt','elite','jackal','hunter']:
 om,nm=old['models'][name],new['models'][name];geoms=[om['source_geometry_lods'][om['n64_lods'][1]],om['source_geometry_lods'][om['n64_lods'][2]],nm['source_geometry_lods'][nm['n64_lods'][2]]]
 pts=[np.array([[position(g['vertices'][i],(0,0,0)) for i in f] for f in g['faces']]) for g in geoms]
 rgb=[np.array(col[name][1])[:,:,:3],np.array(col[name][2])[:,:,:3],np.array(geoms[2]['corner_colors'])]
 base=pts[0];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2;extent=max(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.25
 sheet=Image.new('RGB',(256*4,282*6),(24,24,24));draw=ImageDraw.Draw(sheet)
 for vi,view in enumerate(views):
  rr=[raster(p,c,view,center,extent,256) for p,c in zip(pts,rgb)];a,b,c=[r[1] for r in rr];diff=np.zeros_like(rr[0][0]);diff[a&c]=[65,80,85];diff[a&~c]=[255,75,80];diff[c&~a]=[65,210,255]
  for j,(im,title) in enumerate(zip([rr[0][0],rr[1][0],rr[2][0],diff],['Source far','Previous crunch','Corrected','Source/corrected diff'])):
   sheet.paste(Image.fromarray(im),(j*256,vi*282+26));draw.text((j*256+4,vi*282+4),labels[vi]+' | '+title,fill='white')
  rows.append({'model':name,'pose':'bind','view':labels[vi],'previous_iou':float((a&b).sum()/max(1,(a|b).sum())),'corrected_iou':float((a&c).sum()/max(1,(a|c).sum()))})
 sheet.save(dest/(name+'-bind.png'))
(out/'bind-silhouettes.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
# Original animation samples, not forced symmetric poses: walking/firing
# naturally differ across the body. Compare all meshes at the same phase.
previous=read(ROOT/'halo64-assets/assets/covenant-crunch/source/squad-baked.json.gz');current=read(out/'source/squad-baked.json.gz');animated=[]
poses=[('idle',0),('run',.25),('run',.75),('fire',.5),('melee',.5),('death',.75),('flee',.5),('evade_left',.5)]
for name in ['grunt','elite','jackal','hunter']:
 models=[previous[name][1],previous[name][2],current[name][2]];rgb=[colors(m,new,name) for m in models]
 for clip,phase in poses:
  pts=[np.rint(np.array([position(p,(0,0,0)) for p in m['clips'][clip]['frames'][round(phase*(len(m['clips'][clip]['frames'])-1))]])*128).reshape(-1,3,3)/128 for m in models]
  base=pts[0];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2;extent=max(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.35
  sheet=Image.new('RGB',(192*4,212*6),(24,24,24));draw=ImageDraw.Draw(sheet)
  for vi,view in enumerate(views):
   for size in (192,28,16):
    rr=[raster(p,c,view,center,extent,size) for p,c in zip(pts,rgb)];a,b,c=[r[1] for r in rr]
    row={'model':name,'clip':clip,'phase':phase,'view':labels[vi],'size':size,'previous_iou':float((a&b).sum()/max(1,(a|b).sum())),'corrected_iou':float((a&c).sum()/max(1,(a|c).sum()))}
    if size==192:
     diff=np.zeros_like(rr[0][0]);diff[a&c]=[65,80,85];diff[a&~c]=[255,75,80];diff[c&~a]=[65,210,255]
     for j,(im,title) in enumerate(zip([rr[0][0],rr[1][0],rr[2][0],diff],['Source far','Previous crunch','Corrected','Diff'])):
      sheet.paste(Image.fromarray(im),(j*192,vi*212+20));draw.text((j*192+4,vi*212+3),labels[vi]+' | '+title,fill='white')
     for label,p,c,r in zip(['source','previous','corrected'],pts,rgb,rr):
      two=raster(p,c,view,center,extent,size,cull=False)[1];row[label+'_backface_only_pixels']=int((two&~r[1]).sum())
    animated.append(row)
  sheet.save(dest/f'{name}-{clip}-{phase:g}.png')
(out/'animated-silhouettes.json').write_text(json.dumps(animated,indent=2)+'\n')
summary={n:{size:{key:round(float(np.mean([r[key] for r in animated if r['model']==n and r['size']==size])),4) for key in ['previous_iou','corrected_iou']} for size in (192,28,16)} for n in ['grunt','elite','jackal','hunter']}
(out/'silhouette-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
# Whole-body overlap must not hide the disconnected-shell failure encountered
# during authoring. Compare both shape and backface exposure against baseline.
for name in ['grunt','elite','jackal','hunter']:
 rr=[r for r in animated if r['model']==name and r['size']==192]
 assert np.mean([r['corrected_iou'] for r in rr])>=np.mean([r['previous_iou'] for r in rr])-.01,name
 if name=='hunter':
  assert np.mean([r['corrected_backface_only_pixels'] for r in rr])<=np.mean([r['previous_backface_only_pixels'] for r in rr])+4,'Hunter shell opened'
