#!/usr/bin/env python3
"""Pack original first-person poses with finer positional precision than terrain."""
import argparse,json
from pathlib import Path
from pack_assets import position,normal
from PIL import Image

def pack(source,out,pc_extras=False):
 data=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True)
 lines=['/* Generated owned Xbox first-person assets; do not commit. */','#include "asset_firstperson.h"'];sizes={};total=0
 aliases={} if pc_extras else {'flamethrower':'ar'}
 packed={name:w for name,w in data['weapons'].items() if name not in aliases}
 def xyz(v):return '{'+','.join(map(str,v))+'}'
 for name,w in packed.items():
  images=[Image.open(p).convert('RGB') if p else None for p in w['textures']];verts=[]
  for tri in w['triangles']:
   points=[position(p,(0,0,0)) for p in tri['p']];n=normal(points);light=.78+.22*max(0,sum(a*b for a,b in zip(n,[.25,.83,.49])))
   im=images[tri['material']] if tri['material']<len(images) else None
   for p,(u,v) in zip(points,tri['uv']):
    rgb=im.getpixel((int((u%1)*im.width)%im.width,int((v%1)*im.height)%im.height)) if im else (140,145,140)
    rgb=[round(c*light) for c in rgb];rgba=(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
    verts.append(([round(v*256) for v in p],rgba))
  sizes[name]=len(verts)
  if len(verts)%2:verts.append(verts[-1])
  lines.append(f'static T3DVertPacked fp_{name}[] __attribute__((aligned(16)))={{')
  for i in range(0,len(verts),2):
   a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{a[1]:08x},0x{b[1]:08x},{{0,0}},{{0,0}}'+'},')
  lines.append('};');total+=len(verts)*16
  for clipname,clip in w['clips'].items():
   values=[round(v*256) for frame in clip['frames'] for p in frame for v in position(p,(0,0,0))]
   if not all(-32768<=v<=32767 for v in values):raise ValueError('FP vertex overflow')
   lines.append(f'static const int16_t fp_{name}_{clipname}[] __attribute__((aligned(16)))={{'+','.join(map(str,values))+'};');total+=len(values)*2
 lines.append('const bg_model_asset bg_fp_models[BG_FP_WEAPONS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);lines.append(f'{{fp_{actual},{sizes[actual]},1.0f}},')
 lines.append('};\nconst bg_anim_asset bg_fp_animations[BG_FP_WEAPONS][BG_FP_CLIPS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);w=packed[actual]
  lines.append('{')
  for cname,a in w['clips'].items():lines.append(f'{{fp_{actual}_{cname},{len(a["frames"])},{sizes[actual]},{a["duration"]:.6f}f}},')
  lines.append('},')
 lines.append('};');(out/'firstperson_data.c').write_text('\n'.join(lines)+'\n')
 report={'vertices':sizes,'total_bytes':total,'position_scale':256,'pc_extras':pc_extras,'aliases':aliases,
         'clips':{n:{c:a['tag_name'] for c,a in w['clips'].items()} for n,w in packed.items()}}
 (out/'firstperson-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('source',type=Path,nargs='?',default=Path('build/n64/assets/firstperson-reduced.json'))
 p.add_argument('--output',type=Path,default=Path('build/n64/generated'))
 p.add_argument('--pc-extras',action='store_true',help='Include the optional PC flamethrower assets')
 a=p.parse_args();pack(a.source,a.output,a.pc_extras)
