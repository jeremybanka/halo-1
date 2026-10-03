#!/usr/bin/env python3
"""Pack original first-person poses with finer positional precision than terrain."""
import argparse,json
from pathlib import Path
from pack_assets import position
from pack_animation import emit_clip, clip_initializer
from model_colors import load_images, bake_triangle, bake_team_mask

def pack(source,out,pc_extras=False):
 data=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True)
 lines=['/* Generated owned Xbox first-person assets; do not commit. */','#include "asset_firstperson.h"'];sizes={};total=0;animation_packing={};animation_bytes=0;previews={}
 aliases={} if pc_extras else {'flamethrower':'ar'}
 packed={name:w for name,w in data['weapons'].items() if name not in aliases}
 def xyz(v):return '{'+','.join(map(str,v))+'}'
 for name,w in packed.items():
  images=load_images(w['textures']);verts=[];team_mask=[]
  masks=load_images(w.get('material_multipurpose',[]))
  channels=[2 if source==3 else None for source in w.get('material_change_source',[])]
  for tri in w['triangles']:
   points=[position(p,(0,0,0)) for p in tri['p']]
   team_mask.extend(bake_team_mask(tri,masks,channels))
   for p,rgb in zip(points,bake_triangle(tri,images,w,firstperson=True)):
    rgba=(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
    verts.append(([round(v*256) for v in p],rgba))
  previews[name]={'positions':[[c/256 for c in p] for p,rgba in verts],
                  'colors':[[(rgba>>24)&255,(rgba>>16)&255,(rgba>>8)&255] for p,rgba in verts],
                  'triangle_count':len(w['triangles']),'team_mask':[m/255 for m in team_mask]}
  lines.append(f'static const uint8_t fp_{name}_team_mask[]={{'+','.join(map(str,team_mask))+'};')
  total+=len(team_mask)
  sizes[name]=len(verts)
  if len(verts)%2:verts.append(verts[-1])
  lines.append(f'static T3DVertPacked fp_{name}[] __attribute__((aligned(16)))={{')
  for i in range(0,len(verts),2):
   a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{a[1]:08x},0x{b[1]:08x},{{0,0}},{{0,0}}'+'},')
  lines.append('};');total+=len(verts)*16
  for clipname,clip in w['clips'].items():
   packed_clip=emit_clip(lines,f'fp_{name}_{clipname}',clip,256)
   animation_packing[name,clipname]=packed_clip;total+=packed_clip['bytes'];animation_bytes+=packed_clip['bytes']
 lines.append(f'const unsigned bg_fp_max_vertices={(max(sizes.values())+5)//6*6};')
 lines.append('const uint8_t *const bg_fp_team_masks[BG_FP_WEAPONS]={'+','.join('fp_'+aliases.get(name,name)+'_team_mask' for name in data['weapons'])+'};')
 lines.append('const bg_model_asset bg_fp_models[BG_FP_WEAPONS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);lines.append(f'{{fp_{actual},{sizes[actual]},1.0f}},')
 lines.append('};\nconst bg_anim_asset bg_fp_animations[BG_FP_WEAPONS][BG_FP_CLIPS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);w=packed[actual]
  lines.append('{')
  for cname,a in w['clips'].items():lines.append(clip_initializer(f'fp_{actual}_{cname}',a,animation_packing[actual,cname]))
  lines.append('},')
 lines.append('};');(out/'firstperson_data.c').write_text('\n'.join(lines)+'\n')
 (out/'firstperson-preview.json').write_text(json.dumps(previews))
 report={'vertices':sizes,'total_bytes':total,'position_scale':256,'animation_bytes':animation_bytes,'animation_uncompressed_bytes':sum(p['uncompressed_bytes'] for p in animation_packing.values()),'pc_extras':pc_extras,'aliases':aliases,
         'clips':{n:{c:a['tag_name'] for c,a in w['clips'].items()} for n,w in packed.items()}}
 (out/'firstperson-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('source',type=Path,nargs='?',default=Path('build/n64/assets/firstperson-reduced.json'))
 p.add_argument('--output',type=Path,default=Path('build/n64/generated'))
 p.add_argument('--pc-extras',action='store_true',help='Include the optional PC flamethrower assets')
 a=p.parse_args();pack(a.source,a.output,a.pc_extras)
