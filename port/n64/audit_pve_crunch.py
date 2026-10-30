"""Small-screen silhouette audit; native photos remain the rendering oracle."""
import argparse,collections,json,gzip,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_pve_models import read,colors,raster
from pack_assets import position
from pack_pve import CLIPS
NAMES=('grunt','elite','jackal','hunter')
def main():
 p=argparse.ArgumentParser();p.add_argument('capture',type=Path);a=p.parse_args();out=a.capture;bank=read(out/'source/squad-baked.json.gz');raw=json.loads((out/'source/squad-source.json').read_text());original=read(Path('halo64-assets/assets/covenant-model-appraisal/source/squad-baked.json.gz'))
 checks={};audit=[];(out/'audit').mkdir(exist_ok=True)
 views=[(1,.15,0),(-1,.15,0),(0,.15,1),(0,.15,-1),(1,.7,1),(-1,-.4,-1)]
 poses=[('idle',0),('run',.25),('run',.75),('fire',.5),('melee',.5),('death',.75),('flee',.5),('evade_left',.5)]
 for name in NAMES:
  assert bank[name][:2]==original[name],name
  before,after=bank[name][1:];assert after['grips']==before['grips']
  for clip in CLIPS:
   assert after['clips'][clip]['duration']==before['clips'][clip]['duration']
   assert len(after['clips'][clip]['frames'])==len(before['clips'][clip]['frames'])
   assert np.isfinite(np.asarray(after['clips'][clip]['frames'])).all()
  geom=raw['models'][name]['source_geometry_lods']['n64 crunch']
  assert all(abs(sum(w for _,w in row)-1)<1e-5 for row in geom['skin_weights'])
  checks[name]={'near_far_identical':True,'grips_identical':True,'clip_timings_identical':True,'frames':sum(len(after['clips'][c]['frames']) for c in CLIPS),'triangles':len(after['triangles']),'normalized_skin_weights':True}
  rgb=[colors(m,raw,name) for m in (before,after)]
  keep=[np.array([m['material_metadata'][t['material']]['class']=='shader_model' for t in m['triangles']]) for m in (before,after)]
  for clip,phase in poses:
   pts=[np.rint(np.array([position(p,(0,0,0)) for p in m['clips'][clip]['frames'][round(phase*(len(m['clips'][clip]['frames'])-1))]])*128).reshape(-1,3,3)/128 for m in (before,after)]
   base=pts[0][keep[0]];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2;extent=np.linalg.norm(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.12
   sheet=Image.new('RGB',(576,212*6),(24,24,24));draw=ImageDraw.Draw(sheet)
   for view,eye in enumerate(views):
    for size in (192,28,16):
     results=[raster(p[k],c[k],eye,center,extent,size=size) for p,c,k in zip(pts,rgb,keep)]
     masks=[r[1] for r in results];union=masks[0]|masks[1];inter=masks[0]&masks[1]
     row={'model':name,'clip':clip,'phase':phase,'view':view,'canvas_pixels':size,'before_pixels':int(masks[0].sum()),'after_pixels':int(masks[1].sum()),'silhouette_iou':round(float(inter.sum()/max(1,union.sum())),5),'lost_pixels':int((masks[0]&~masks[1]).sum()),'added_pixels':int((masks[1]&~masks[0]).sum())}
     if size==192:
      diff=np.zeros_like(results[0][0]);diff[inter]=[50,65,70];diff[masks[0]&~masks[1]]=[255,75,80];diff[masks[1]&~masks[0]]=[65,210,255]
      for col,img in enumerate([results[0][0],results[1][0],diff]):sheet.paste(Image.fromarray(img),(col*192,view*212+20))
      draw.text((6,view*212+3),f'{name} {clip} {phase:g} v{view}',fill='white')
      for label,p,c,k,r in zip(('before','after'),pts,rgb,keep,results):
       _,two=raster(p[k],c[k],eye,center,extent,size=size,cull=False);row[label+'_backface_only_pixels']=int((two&~r[1]).sum())
     audit.append(row)
   sheet.save(out/'audit'/f'{name}-{clip}-{phase:g}.png')
 (out/'asset-checks.json').write_text(json.dumps(checks,indent=2)+'\n');(out/'silhouette-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 print(json.dumps({n:{size:{'mean_iou':round(float(np.mean([r['silhouette_iou'] for r in audit if r['model']==n and r['canvas_pixels']==size])),4),'minimum_iou':min(r['silhouette_iou'] for r in audit if r['model']==n and r['canvas_pixels']==size)} for size in (192,28,16)} for n in NAMES},indent=2))
if __name__=='__main__':main()
