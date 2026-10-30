#!/usr/bin/env python3
"""Count native omission differences per viewport; frozen diagnostics, never FPS."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True)
def fields(s):
 out={}
 for k,v in re.findall(r'(\w+)=([^ ]+)',s):
  try:v=float(v) if '.' in v else int(v)
  except ValueError:pass
  out[k]=v
 return out
results={}
for log in sorted(a.capture.glob('*-native.log')):
 text=log.read_text();blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S)
 assert len(blocks)==17,(log,len(blocks))
 frames=[np.frombuffer(b''.join(bytes.fromhex(d) for _,d in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M)),dtype='>u2').reshape(240,320) for block in blocks]
 name=log.name.removesuffix('-native.log');manifest=json.loads(next((a.capture/name).glob('*.build.json')).read_text());empty=bool(manifest['options']['gpu_empty_scissor'])
 stable=bool(np.array_equal(frames[0],frames[1]) and np.array_equal(frames[0],frames[16]))
 assert stable or empty,('Baseline drift',log,np.count_nonzero(frames[0]!=frames[1]),np.count_nonzero(frames[0]!=frames[16]))
 out=a.output/name;out.mkdir(exist_ok=True)
 def rgb(raw):return np.stack([((raw>>n)&31)*255//31 for n in (11,6,1)],axis=2).astype('uint8')
 Image.fromarray(rgb(frames[0])).save(out/'baseline.png')
 cameras=[fields(s) for s in re.findall(r'^DRAW_CAMERA .*$',text,re.M)];assert len(cameras)==4
 cats=[fields(s) for s in re.findall(r'^DRAW_CATEGORY .*$',text,re.M)]
 actors=[fields(s) for s in re.findall(r'^DRAW_ACTOR .*$',text,re.M)]
 ships=[fields(s) for s in re.findall(r'^DRAW_SHIP .*$',text,re.M)]
 differences=[];unions=[]
 actor_union=np.logical_or.reduce([frames[0]!=frames[page] for page in range(2,14)])
 for camera in cameras:
  x,y,w,h=[camera[k] for k in ('x','y','width','height')];unions.append(dict(view=camera['view'],actor_pixels=int(actor_union[y:y+h,x:x+w].sum()),viewport_pixels=w*h))
 for page in range(2,16):
  delta=frames[0]!=frames[page];colored=np.zeros((240,320,3),dtype='uint8');colored[delta]=[255,180,40]
  Image.fromarray(colored).save(out/f'omit-{page-2:02}-diff.png')
  for camera in cameras:
   x,y,w,h=[camera[k] for k in ('x','y','width','height')];mask=delta[y:y+h,x:x+w];ys,xs=np.where(mask)
   differences.append(dict(view=camera['view'],omitted=page-2,pixels=int(mask.sum()),bbox=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else None))
 results[name]=dict(state=fields(re.search(r'^DRAW_STATE .*$',text,re.M)[0]),cameras=cameras,categories=cats,actors=actors,ships=ships,differences=differences,actor_pixel_union=unions,timings=[fields(s) for s in re.findall(r'^DRAW_TIMING .*$',text,re.M)],log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),stable_baselines=stable,pixel_measurement_valid=not empty)
 print(name,'loads',sum(c['vertices'] for c in cats),'actors',len(actors),'submitted_zero_pixel',sum(next(d['pixels'] for d in differences if d['view']==actor['view'] and d['omitted']==actor['actor'])==0 for actor in actors))
(a.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
