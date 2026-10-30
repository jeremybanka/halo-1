"""Quantized multi-angle image/silhouette comparison, separate from native photos."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from audit_pve_models import raster
from model_colors import load_images,bake_triangle
from pack_assets import position
OUT=ROOT/'build/vehicle-lods';DEST=OUT/'silhouettes';DEST.mkdir(exist_ok=True)
raw=json.loads((ROOT/'build/pve-vehicles/source/extended-raw.json').read_text())
reduced=json.loads((OUT/'reduced.json').read_text());rows=[]
views=[(1,.12,0),(-1,.12,0),(0,.12,1),(0,.12,-1),(1,.5,1),(-1,.5,-1),(0,1,.01),(1,-.25,1)]
labels=['front','back','left','right','front oblique','back oblique','top','below oblique']
for name,m in raw['models'].items():
    source=[{'p':[m['vertices'][i] for i in f],'uv':[m['uv'][i] for i in f],'material':mat} for f,mat in zip(m['faces'],m['materials'])]
    geometries=[source]+[[t for p in tier for t in p['triangles']] for tier in reduced['models'][name]['tiers']]
    images=load_images(m['textures'])
    positions=[np.rint(np.array([[position(p,(0,0,0)) for p in t['p']] for t in g])*1024)/1024 for g in geometries]
    colors=[np.array([bake_triangle(t,images,m) for t in g]) for g in geometries]
    base=positions[0];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2
    extent=max(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.15
    for tier in (1,2):
        sheet=Image.new('RGB',(192*3,212*len(views)),(24,24,24));draw=ImageDraw.Draw(sheet)
        for vi,view in enumerate(views):
            for size in (192,64,28):
                rendered=[raster(positions[j],colors[j],view,center,extent,size) for j in (0,tier)]
                a,b=[r[1] for r in rendered];extra=raster(positions[tier],colors[tier],view,center,extent,size,cull=False)[1]
                baseline_extra=raster(positions[0],colors[0],view,center,extent,size,cull=False)[1]
                rows.append({'model':name,'tier':tier,'view':labels[vi],'size':size,'iou':float((a&b).sum()/max(1,(a|b).sum())),
                             'source_pixels':int(a.sum()),'removed':int((a&~b).sum()),'added':int((b&~a).sum()),
                             'backface_only':int((extra&~b).sum()),'source_backface_only':int((baseline_extra&~a).sum())})
                if size==192:
                    delta=np.zeros_like(rendered[0][0]);delta[a&b]=[65,80,85];delta[a&~b]=[255,75,80];delta[b&~a]=[65,210,255]
                    for col,(image,label) in enumerate(zip([rendered[0][0],rendered[1][0],delta],['Source','Middle' if tier==1 else 'Coarse','Silhouette difference'])):
                        sheet.paste(Image.fromarray(image),(col*192,vi*212+20));draw.text((col*192+4,vi*212+3),labels[vi]+' | '+label,fill='white')
                    for label,r in zip(('source','middle' if tier==1 else 'coarse'),rendered):Image.fromarray(r[0]).save(DEST/f'{name}-{vi}-{label}.png')
                    Image.fromarray(delta).save(DEST/f'{name}-{vi}-diff-{tier}.png')
        sheet.save(DEST/f'{name}-{tier}-sheet.png')
(OUT/'silhouettes.json').write_text(json.dumps(rows,indent=2)+'\n')
for name in raw['models']:
 for tier in (1,2):
  selected=[r for r in rows if r['model']==name and r['tier']==tier and r['size']==192]
  print(name,tier,'IoU mean/min',round(np.mean([r['iou'] for r in selected]),4),round(min(r['iou'] for r in selected),4),
        'backface excess',max(r['backface_only']-r['source_backface_only'] for r in selected))
